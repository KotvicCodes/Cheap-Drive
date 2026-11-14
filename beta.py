"""Beta: a markup that follows the market and dealer trust, and a driver fee that pays for time only when time is short."""
from __future__ import annotations

from dataclasses import dataclass
import re

from dispatch import Journal, JournalDesk
from spread import World
from spread.starter import DAY, HOUR, Retry, steep
from spread.types import DeskEvent, FeeStep, Order, PriceRequest

# Fixed by the rules or by design; the three tuned numbers are in BetaSettings.
TRUST_CAP = 25                       # a dealer counts at most 25 on-time orders and accepts 1% more for each
START_MARKUP = 15_000.0              # bps of the list price, before the first win or loss
LEARN = 0.02                         # markup step per decided quote
MARKUP_MIN, MARKUP_MAX = 12_000.0, 20_000.0
MIN_SLACK = 8 * HOUR                 # a driver gets at least this long from the dealer's decision to the last pickup
FEE_CAP, FEE_STEPS = 15_000, 8       # the fee reaches 1.5x the typical fee, in 8 steps, at the deadline warning
WARNING = 3 * HOUR                   # deadline_close comes this long before the last pickup
PLATES = re.compile(r"kilvet|kilpi|rekkar|plates|skylt")
MANUAL = re.compile(r"manuaal|käsivaiht|manual|manuell")


@dataclass(frozen=True)
class BetaSettings:
    win_target_bps: int = 3_000    # share of quotes to win; the markup moves until the market gives it
    opening_fee_bps: int = 8_000   # first driver fee, as a share of the request's typical fee
    max_km: int = 500              # longest route to compete for; 0 for no limit

    def __post_init__(self):
        for name, value in vars(self).items():
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if not 0 < self.win_target_bps < 10_000:
            raise ValueError("win_target_bps must be between 1 and 9999")
        if not 0 < self.opening_fee_bps <= FEE_CAP:
            raise ValueError(f"opening_fee_bps must be between 1 and {FEE_CAP}")


class BetaDesk(JournalDesk):
    """Posting, retries and deadline rescue stay the starter's; Beta owns the quote and the fee."""

    # A lost quote moves the learned markup and queues no action, so fast practice
    # can deliver it with the next decision event, still before that decision.
    passive_wake_events = JournalDesk.passive_wake_events

    def __init__(self, world: World, level: int, now: int, journal: Journal,
                 settings: BetaSettings = BetaSettings()):
        super().__init__(world, level, now, journal)
        self.settings = settings
        self.markup = START_MARKUP
        self.trust: dict[str, int] = {}   # dealer -> counted on-time orders, as the rules count them
        self.dealers: dict[str, str] = {}  # order -> dealer
        self.pending: set[str] = set()    # competitive quotes that the dealer has not decided
        roads = getattr(world, "initial_map", None)  # play_model has already read and journaled it
        if roads is None:
            roads = getattr(world, "world", world).client.map()
        self.roads = {(road["from"], road["to"]): road for road in roads["roads"]}

    # ---- quotes ----

    def quote(self, request: PriceRequest) -> None:
        if request["id"] in self.requests or self.now >= request["respondBy"]:
            return
        if self.level <= 3:  # every quote wins at the list price there
            super().quote(request)
            return
        self.requests[request["id"]] = request
        legs = request["legs"]
        route = sum(self.roads[leg["pickup"]["placeId"], leg["delivery"]["placeId"]]["km"] for leg in legs)
        limit = self.settings.max_km
        options = [option for option in request["options"] if self.slack(request, option) >= MIN_SLACK]
        if len(legs) > 1:
            reason, options = "trade-in", []
        elif limit and route > limit:
            reason, options = "route too long", []
        else:
            reason = "no option leaves a driver enough time"
        if options:
            trust = self.trust.get(request["dealerId"], 0)
            factor = int(self.markup) * (100 + trust)  # bps x percent
            prices = {option["kind"]: -(-option["listPriceCents"] * factor // 1_000_000) for option in options}
            self.pending.add(request["id"])
            self.journal.record("beta_quote", at=self.now, requestId=request["id"], dealerId=request["dealerId"],
                                trust=trust, markupBps=int(self.markup), routeKm=route, prices=prices)
        else:
            # A losing quote costs nothing; silence costs goodwill. Ten times the list price is not a
            # guaranteed loss, only a practical one.
            first = request["options"][0]
            prices = {first["kind"]: first["listPriceCents"] * 10}
            self.journal.record("beta_decline", at=self.now, requestId=request["id"], routeKm=route, reason=reason)
        self.outbox.append({"type": "quote", "requestId": request["id"], "prices": prices})

    def slack(self, request: PriceRequest, option) -> int:
        """Minutes from the dealer's decision to the last pickup that still meets the option's deadline."""
        last = option["deadline"]
        for leg in reversed(request["legs"]):
            pickup, delivery = leg["pickup"], leg["delivery"]
            last = min(last, delivery["window"]["to"], closing(delivery, last))
            last -= self.roads[pickup["placeId"], delivery["placeId"]]["minutes"]
            last = min(last, pickup["window"]["to"], closing(pickup, last))
            if last < pickup["window"]["from"]:
                return -1
        return last - request["respondBy"]

    def learn(self, request_id: str, won: bool) -> None:
        """A win says the market is above our price, a loss that it is below. The steps cancel
        when the share of wins equals the target, so the markup settles where the market gives it."""
        if request_id in self.pending:
            self.pending.discard(request_id)
            target = self.settings.win_target_bps / 10_000
            markup = self.markup * (1 + LEARN * (1 - target) if won else 1 - LEARN * target)
            self.markup = min(MARKUP_MAX, max(MARKUP_MIN, markup))

    # ---- driver fees ----

    def fees_for(self, order: Order, cars: int) -> list[FeeStep]:
        """Open below the typical fee, then rise evenly so the cap arrives with the deadline warning:
        an order with a day to spare waits for a cheap driver, an order with hours to spare pays up."""
        fee = self.requests[order["id"]]["referenceFeeCents"] * cars / len(order["legs"])
        if order["id"] in self.urgent or self.level == 1:
            return steep(self.now, fee, self.level)
        opening = self.settings.opening_fee_bps
        every = max(HOUR, (order["lastPickupAt"] - WARNING - self.now) // (FEE_STEPS - 1))
        return [{"at": self.now + k * every,
                 "feeCents": max(1, int(fee * (opening + (FEE_CAP - opening) * k / (FEE_STEPS - 1)) / 10_000 + 0.5))}
                for k in range(FEE_STEPS)]

    def post(self, order: Order, legs: list[int], retry: Retry = Retry()) -> None:
        """Two notes that the starter does not read: a car without plates, and a manual gearbox."""
        note = self.requests[order["id"]]["note"]
        text = note["text"].lower() if note else ""
        super().post(order, legs, Retry(retry.pickup_from, retry.manual_licence or bool(MANUAL.search(text)),
                                        retry.plates or bool(PLATES.search(text))))

    # ---- books ----

    def observe_feedback(self, event: DeskEvent) -> None:
        """Model bookkeeping only; also used by offline rejoin replay."""
        kind = event["kind"]
        if kind == "order_won":
            self.learn(event["order"]["id"], True)
            self.dealers[event["order"]["id"]] = event["order"]["dealerId"]
        elif kind == "order_lost":
            self.learn(event["requestId"], False)
        elif kind == "ledger":
            line = event["line"]
            dealer = self.dealers.get(line.get("orderId") or "")
            if dealer is not None and line["kind"] == "revenue":
                self.trust[dealer] = min(TRUST_CAP, self.trust.get(dealer, 0) + 1)
            elif dealer is not None and line["kind"] == "late_refund":
                # The revenue line counted this order as on time; take that back, then halve.
                self.trust[dealer] = max(0, self.trust.get(dealer, 0) - 1) // 2

    def handle(self, event: DeskEvent) -> None:
        self.observe_feedback(event)
        super().handle(event)

    def read_results(self, actions, results) -> None:
        super().read_results(actions, results)
        for action, result in zip(actions, results):
            if action["type"] == "quote" and not result["ok"]:
                self.pending.discard(action["requestId"])


def closing(stop, minute: int) -> int:
    """The site's stated closing time on the day of `minute`; no limit at a private address."""
    hours = stop["hours"]
    if hours is None:
        return minute
    day = minute // DAY
    if day % 7 not in hours["weekdays"]:
        if day % 7 != 5 or hours["saturday"] is None:
            return minute  # closed that day: the deadline's own day decides, not this guess
        hours = hours["saturday"]
    return day * DAY + hours["closes"]


def make_beta(world, level, now, journal, **settings):
    return BetaDesk(world, level, now, journal, BetaSettings(**settings))
