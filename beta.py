"""Beta: list-anchored quotes that follow dealer trust, an owned driver fee, and a backlog valve."""
from __future__ import annotations

from dataclasses import dataclass
import re

from dispatch import Journal, JournalDesk
from spread import World
from spread.starter import DAY, HOUR, Retry, steep
from spread.types import DeskEvent, FeeStep, Order, PriceRequest

TRUST_CAP = 25  # rules: a dealer counts at most 25 on-time orders, 1% each
LEARN, MARKUP_MIN, MARKUP_MAX = 0.02, 12_000.0, 20_000.0  # markup step per decided quote, and its bounds
PLATES = re.compile(r"kilvet|kilpi|rekkar|plates|skylt")
MANUAL = re.compile(r"manuaal|käsivaiht|manual|manuell")


@dataclass(frozen=True)
class BetaSettings:
    """The three parameters of Beta, then experiment switches that default to the rules' or starter's values."""
    markup_bps: int = 13_500        # quote = list price x markup x dealer trust, per option
    opening_fee_bps: int = 10_000   # first driver fee as a share of the request's typical fee
    max_waiting: int = 40           # stop competing while this many orders have no driver
    trust_bps: int = 100            # price rise per counted on-time order; the rules say dealers accept 1%
    fee_step_bps: int = 1_000       # hourly rise of the driver fee, as a share of the typical fee
    fee_cap_bps: int = 15_000       # where the hourly rise stops
    min_slack: int = 0              # minutes a driver must have, from the dealer's decision to the last pickup
    ramp: int = 0                   # 1: spread the rise from posting to the deadline warning, not over 5 hours
    trade_ins: int = 1              # 0: decline two-car requests
    win_target_bps: int = 0         # above 0: move the markup until this share of quotes wins
    short_km: int = 0               # above 0: routes shorter than this learn a markup of their own
    short_target_bps: int = 0       # their win share; 0 uses win_target_bps
    skip_premium: int = 0           # 1: decline premium cars
    max_km: int = 0                 # above 0: decline longer routes
    markup_max_bps: int = 20_000    # where the learned markup stops
    skip_private: int = 0           # 1: decline private addresses

    def __post_init__(self):
        for name, value in vars(self).items():
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if not self.markup_bps or not self.opening_fee_bps:
            raise ValueError("markup_bps and opening_fee_bps must be positive")


class BetaDesk(JournalDesk):
    """Posting, retries and deadline rescue stay the starter's; Beta owns the quote and the fee."""

    def __init__(self, world: World, level: int, now: int, journal: Journal,
                 settings: BetaSettings = BetaSettings()):
        super().__init__(world, level, now, journal)
        self.settings = settings
        self.trust: dict[str, int] = {}     # dealer -> counted on-time orders, as the rules count them
        self.dealers: dict[str, str] = {}   # order -> dealer
        self.pending: dict[str, bool] = {}  # competitive quotes that the dealer has not decided -> short route
        self.markup = {False: float(settings.markup_bps), True: float(settings.markup_bps)}  # by short route
        source = getattr(world, "world", world)  # play_model wraps the SDK world
        roads = source.client.map()["roads"]
        self.roads = {(road["from"], road["to"]): road["minutes"] for road in roads}
        self.km = {(road["from"], road["to"]): road["km"] for road in roads}

    # ---- quotes ----

    def waiting(self) -> int:
        """Orders with a car that no driver holds, plus quotes that may still become such orders."""
        count = len(self.pending)
        for order_id, order in self.orders.items():
            gigs = self.leg_gigs.get(order_id, {})
            if any(done is None and gigs.get(leg) not in self.booked for leg, done in enumerate(order["deliveredAt"])):
                count += 1
        return count

    def quote(self, request: PriceRequest) -> None:
        if request["id"] in self.requests or self.now >= request["respondBy"]:
            return
        if self.level <= 3:  # every quote wins at the list price there
            super().quote(request)
            return
        self.requests[request["id"]] = request
        settings = self.settings
        waiting = self.waiting()
        trust = self.trust.get(request["dealerId"], 0)
        options = [option for option in request["options"] if self.slack(request, option) >= settings.min_slack]
        legs = request["legs"]
        if len(legs) > 1 and not settings.trade_ins:
            options = []
        if settings.skip_premium and any(leg["car"]["premium"] for leg in legs):
            options = []
        if settings.skip_private and any(leg[stop]["privateAddress"] for leg in legs for stop in ("pickup", "delivery")):
            options = []
        route = sum(self.km[leg["pickup"]["placeId"], leg["delivery"]["placeId"]] for leg in legs)
        if settings.max_km and route > settings.max_km:
            options = []
        short = route < settings.short_km
        if waiting >= settings.max_waiting or not options:
            # A losing quote costs nothing; silence costs goodwill.
            first = request["options"][0]
            prices = {first["kind"]: first["listPriceCents"] * 10}
            self.journal.record("beta_decline", at=self.now, requestId=request["id"], waiting=waiting,
                                reason="backlog" if options else "no option leaves a driver enough time")
        else:
            factor = int(self.markup[short]) * (10_000 + settings.trust_bps * trust)
            prices = {option["kind"]: -(-option["listPriceCents"] * factor // 100_000_000) for option in options}
            self.pending[request["id"]] = short
            self.journal.record("beta_quote", at=self.now, requestId=request["id"], dealerId=request["dealerId"],
                                trust=trust, waiting=waiting, markupBps=int(self.markup[short]), prices=prices)
        self.outbox.append({"type": "quote", "requestId": request["id"], "prices": prices})

    def slack(self, request: PriceRequest, option) -> int:
        """Minutes from the dealer's decision to the last pickup that still meets the option's deadline."""
        last = option["deadline"]
        for leg in reversed(request["legs"]):
            pickup, delivery = leg["pickup"], leg["delivery"]
            last = min(last, delivery["window"]["to"], closing(delivery, last))
            last -= self.roads[pickup["placeId"], delivery["placeId"]]
            last = min(last, pickup["window"]["to"], closing(pickup, last))
            if last < pickup["window"]["from"]:
                return -1
        return last - request["respondBy"]

    # ---- driver fees ----

    def fees_for(self, order: Order, cars: int) -> list[FeeStep]:
        fee = self.requests[order["id"]]["referenceFeeCents"] * cars / len(order["legs"])
        if order["id"] in self.urgent or self.level == 1:
            return steep(self.now, fee, self.level)
        settings = self.settings
        shares = [settings.opening_fee_bps]
        while settings.fee_step_bps and shares[-1] < settings.fee_cap_bps and len(shares) < 48:
            shares.append(min(settings.fee_cap_bps, shares[-1] + settings.fee_step_bps))
        every = HOUR
        if settings.ramp and len(shares) > 1:
            # The warning comes 3 hours before the last pickup; the steep fees take over there.
            every = max(HOUR, (order["lastPickupAt"] - 3 * HOUR - self.now) // (len(shares) - 1))
        return [{"at": self.now + k * every, "feeCents": max(1, int(fee * share / 10_000 + 0.5))}
                for k, share in enumerate(shares)]

    # ---- books ----

    def handle(self, event: DeskEvent) -> None:
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
        super().handle(event)

    def learn(self, request_id: str, won: bool) -> None:
        """A win says the market is above our price, a loss that it is below: step towards the target share."""
        short = self.pending.pop(request_id, None)
        settings = self.settings
        target = (settings.short_target_bps if short and settings.short_target_bps else settings.win_target_bps) / 10_000
        if short is not None and target:
            markup = self.markup[short] * (1 + LEARN * (1 - target) if won else 1 - LEARN * target)
            self.markup[short] = min(float(settings.markup_max_bps), max(MARKUP_MIN, markup))

    def post(self, order: Order, legs: list[int], retry: Retry = Retry()) -> None:
        """Two notes that the starter does not read: a car without plates, and a manual gearbox."""
        note = self.requests[order["id"]]["note"]
        text = note["text"].lower() if note else ""
        super().post(order, legs, Retry(retry.pickup_from, retry.manual_licence or bool(MANUAL.search(text)),
                                        retry.plates or bool(PLATES.search(text))))

    def read_results(self, actions, results) -> None:
        super().read_results(actions, results)
        for action, result in zip(actions, results):
            if action["type"] == "quote" and not result["ok"]:
                self.pending.pop(action["requestId"], None)


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
