"""Gamma's pricing and admission controls; defaults reproduce Beta."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from beta import BetaDesk, TRUST_CAP, WARNING
from dispatch import JournalDesk
from spread.starter import DAY, HOUR, steep, undelivered


DEALER_FACTORS = {"D01": 1.04, "D03": 0.97, "D08": 0.91, "D10": 0.95, "D19": 0.94}
DELIVERY_FACTORS = {"lappeenranta": 1.10, "mikkeli": 1.08, "lahti": 1.05,
                    "ylivieska": 1.05, "rauma": 1.05, "kouvola": 1.04,
                    "salo": 1.04, "pori": 1.04, "vantaa": 0.95}
LANE_FACTORS = {("espoo", "vantaa"): 0.90, ("helsinki", "vantaa"): 0.90,
                ("helsinki", "espoo"): 0.91, ("hyvinkaa", "tampere"): 1.10,
                ("hyvinkaa", "raisio"): 1.10, ("vantaa", "pori"): 1.08}
PLACE_IDS = frozenset("espoo hameenlinna helsinki hyvinkaa joensuu jyvaskyla kajaani kemi kokkola kotka "
                      "kouvola kuopio lahti lappeenranta lempaala mikkeli oulu pori porvoo raisio rauma "
                      "rovaniemi salo savonlinna seinajoki tampere turku vaasa vantaa ylivieska".split())
BIG_DEALERS = ("D01", "D02", "D03", "D04")
OPTION_KINDS = frozenset({"same_day", "next_day", "within_3_days"})


@dataclass(frozen=True)
class GammaSettings:
    win_target_bps: int = 3000
    opening_fee_bps: int = 8000
    max_km: int = 500
    start_markup_bps: int = 15000
    markup_min_bps: int = 12000
    markup_max_bps: int = 20000
    learn_bps: int = 200
    min_slack_minutes: int = 480
    fee_cap_bps: int = 15000
    fee_steps: int = 8
    trust_bps_per_order: int = 100
    trade_ins: int = 0
    dealer_table: int = 0
    place_table: int = 0
    table_strength: int = 100
    trust_build_bps: int = 0
    trust_guard: int = 0
    trust_build_until_day: int = 7
    capacity_valve: int = 0
    win_target_low_bps: int = 2600
    win_target_mid_bps: int = 3000
    win_target_high_bps: int = 3400
    open_low: int = 5
    open_high: int = 10
    long_max_km: int | None = None  # omission follows max_km, including sweep overrides
    long_options: str = "next_day,within_3_days"
    long_min_slack_minutes: int = 1440
    long_open_cap: int = 3
    long_markup_bps: int = 10000
    long_opening_fee_bps: int = 10000
    same_day_bps: int = 10000
    next_day_bps: int = 10000
    within_3_days_bps: int = 10000
    short_km: int = 50
    short_bps: int = 10000
    quote_options: str = "all"
    markup_scope: str = "global"
    freeze_day_drop_bps: int = 0

    def __post_init__(self):
        if self.long_max_km is None:
            object.__setattr__(self, "long_max_km", self.max_km)
        strings = {"long_options", "quote_options", "markup_scope"}
        for name, value in vars(self).items():
            if name in strings:
                if type(value) is not str:
                    raise ValueError(f"{name} must be a string")
            elif type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        for name in ("trade_ins", "dealer_table", "place_table", "trust_guard", "capacity_valve"):
            if getattr(self, name) not in (0, 1):
                raise ValueError(f"{name} must be 0 or 1")
        for name in ("win_target_bps", "win_target_low_bps", "win_target_mid_bps", "win_target_high_bps"):
            if not 0 < getattr(self, name) < 10000:
                raise ValueError(f"{name} must be between 1 and 9999")
        for name, maximum in (("table_strength", 100), ("learn_bps", 10000),
                              ("trust_build_bps", 9999), ("freeze_day_drop_bps", 10000),
                              ("trust_build_until_day", 7)):
            if getattr(self, name) > maximum or (name == "trust_build_until_day" and getattr(self, name) < 1):
                raise ValueError(f"{name} outside its allowed range")
        if not 0 < self.markup_min_bps <= self.start_markup_bps <= self.markup_max_bps:
            raise ValueError("markup bounds must contain a positive start_markup_bps")
        if not 0 < self.opening_fee_bps <= self.fee_cap_bps or self.fee_steps < 1:
            raise ValueError("opening_fee_bps must be positive and <= fee_cap_bps; fee_steps must be >= 1")
        if not 0 < self.long_opening_fee_bps <= self.fee_cap_bps:
            raise ValueError("long_opening_fee_bps must be positive and <= fee_cap_bps")
        for name in ("long_markup_bps", "same_day_bps", "next_day_bps", "within_3_days_bps", "short_bps"):
            if getattr(self, name) == 0:
                raise ValueError(f"{name} must be positive")
        if self.open_low > self.open_high:
            raise ValueError("open_low must be <= open_high")
        if not self.win_target_low_bps <= self.win_target_mid_bps <= self.win_target_high_bps:
            raise ValueError("capacity win targets must be in low, mid, high order")
        kinds = self.long_options.split(",")
        if not set(kinds) <= OPTION_KINDS or len(kinds) != len(set(kinds)):
            raise ValueError("long_options must be comma-separated, distinct option kinds")
        if self.quote_options not in ("all", "cheapest_only", "slowest_only", "no_same_day"):
            raise ValueError("unknown quote_options mode")
        if self.markup_scope not in ("global", "dealer", "km"):
            raise ValueError("markup_scope must be global, dealer or km")


class GammaDesk(BetaDesk):
    """Quote-side core. An offers mixin can override fees/post/handle cooperatively."""

    passive_wake_events = JournalDesk.passive_wake_events
    big_dealers = BIG_DEALERS

    def __init__(self, world, level, now, journal, settings=GammaSettings()):
        super().__init__(world, level, now, journal, settings)
        self.markup = float(settings.start_markup_bps)
        self.markups: dict[str, float] = {}
        self.quote_trackers: dict[str, str] = {}
        self.day_starts: dict[str, tuple[int, float]] = {}
        table_places = set(DELIVERY_FACTORS) | {place for lane in LANE_FACTORS for place in lane}
        unknown = table_places - PLACE_IDS
        if settings.place_table:
            # Disabled tables also work with the starter's small synthetic demo map.
            map_places = {place for lane in self.roads for place in lane}
            unknown |= table_places - map_places
        if unknown:
            raise ValueError(f"unknown table place ids: {', '.join(sorted(unknown))}")

    # ---- admission ----

    def route_km(self, request):
        return sum(self.roads[leg["pickup"]["placeId"], leg["delivery"]["placeId"]]["km"]
                   for leg in request["legs"])

    def is_long_route(self, km):
        return bool(self.settings.max_km and self.settings.max_km < km <= self.settings.long_max_km)

    def orders_without_driver(self):
        # Missing posts and partially booked split trade-ins still need a driver.
        return {identity for identity, order in self.orders.items()
                if order["status"] not in ("cancelled", "delivered") and undelivered(order)
                and any(self.leg_gigs.get(identity, {}).get(leg) not in self.booked for leg in undelivered(order))}

    def long_orders_without_driver(self):
        if not self.settings.max_km or self.settings.long_max_km <= self.settings.max_km:
            return set()
        return {identity for identity in self.orders_without_driver()
                if self.is_long_route(self.route_km(self.requests[identity]))}

    def eligible_options(self, request, km, trust):
        s = self.settings
        if len(request["legs"]) > 1 and not s.trade_ins:
            return [], "trade-in"
        if s.max_km and km > s.max_km and not self.is_long_route(km):
            return [], "route too long"
        options = [o for o in request["options"] if self.slack(request, o) >= s.min_slack_minutes]
        if not options:
            return [], "no option leaves a driver enough time"
        if s.trust_guard and request["dealerId"] in self.big_dealers and trust >= 10:
            options = [o for o in options if self.slack(request, o) >= 720]
            if not options:
                return [], "trust guard"
        if self.is_long_route(km):
            if len(self.long_orders_without_driver()) >= s.long_open_cap:
                return [], "long route capacity"
            options = [o for o in options if o["kind"] in s.long_options.split(",")
                       and self.slack(request, o) >= s.long_min_slack_minutes]
            if not options:
                return [], "no eligible long route option"
        return self.select_options(options), ""

    def select_options(self, options):
        mode = self.settings.quote_options
        if mode == "cheapest_only":
            return [min(options, key=lambda o: o["listPriceCents"])]
        if mode == "slowest_only":
            return [max(options, key=lambda o: o["deadline"])]
        if mode == "no_same_day" and any(o["kind"] != "same_day" for o in options):
            return [o for o in options if o["kind"] != "same_day"]
        return options

    # ---- pricing and feedback ----

    def tracker_for(self, request, km):
        if self.settings.markup_scope == "dealer":
            return request["dealerId"] if request["dealerId"] in self.big_dealers else "other"
        if self.settings.markup_scope == "km":
            return "under_100" if km < 100 else "100_to_300" if km <= 300 else "over_300"
        return "global"

    def tracker_markup(self, tracker):
        return self.markup if tracker == "global" else self.markups.setdefault(tracker, float(self.settings.start_markup_bps))

    def win_target(self):
        s = self.settings
        if not s.capacity_valve:
            return s.win_target_bps
        count = len(self.orders_without_driver())
        if count <= s.open_low:
            return s.win_target_high_bps
        return s.win_target_mid_bps if count <= s.open_high else s.win_target_low_bps

    def table_factors(self, request):
        s = self.settings
        pickup = request["legs"][0]["pickup"]["placeId"]
        delivery = request["legs"][-1]["delivery"]["placeId"]
        dealer = DEALER_FACTORS.get(request["dealerId"], 1) if s.dealer_table else 1
        place = LANE_FACTORS.get((pickup, delivery), DELIVERY_FACTORS.get(delivery, 1)) if s.place_table else 1
        strength = Fraction(s.table_strength, 100)
        dealer, place = (1 + (Fraction(str(value)) - 1) * strength for value in (dealer, place))
        return dealer, place, min(Fraction(115, 100), max(Fraction(88, 100), dealer * place))

    def option_factors(self, request, option, km, trust):
        s = self.settings
        build = bool(s.trust_build_bps and request["dealerId"] in self.big_dealers and trust < TRUST_CAP
                     and km <= 200 and self.slack(request, option) >= 720
                     and (s.trust_build_until_day == 7 or self.now // DAY < s.trust_build_until_day))
        return {"optionBps": getattr(s, option["kind"] + "_bps"),
                "shortBps": s.short_bps if km < s.short_km else 10000,
                "longBps": s.long_markup_bps if self.is_long_route(km) else 10000,
                "trustBuildBps": 10000 - s.trust_build_bps if build else 10000}

    def price_option(self, option, markup, trust, table, factors):
        # Exact factors and one final ceiling retain Beta's cent rounding.
        price = Fraction(option["listPriceCents"] * int(markup)
                         * (10000 + trust * self.settings.trust_bps_per_order), 100_000_000) * table
        for factor in factors.values():
            price *= Fraction(factor, 10000)
        return -(-price.numerator // price.denominator)

    def quote(self, request):
        if request["id"] in self.requests or self.now >= request["respondBy"]:
            return
        if self.level <= 3:
            super().quote(request)
            return
        self.requests[request["id"]] = request
        km = self.route_km(request)
        trust = self.trust.get(request["dealerId"], 0)
        options, reason = self.eligible_options(request, km, trust)
        if options:
            tracker = self.tracker_for(request, km)
            markup = self.tracker_markup(tracker)
            if self.day_starts.get(tracker, (-1, 0))[0] != self.now // DAY:
                self.day_starts[tracker] = self.now // DAY, markup
            dealer, place, table = self.table_factors(request)
            factors = {o["kind"]: self.option_factors(request, o, km, trust) for o in options}
            prices = {o["kind"]: self.price_option(o, markup, trust, table, factors[o["kind"]]) for o in options}
            self.pending.add(request["id"])
            self.quote_trackers[request["id"]] = tracker
            guard = bool(self.settings.trust_guard and request["dealerId"] in self.big_dealers and trust >= 10)
            self.journal.record("beta_quote", at=self.now, requestId=request["id"], dealerId=request["dealerId"],
                                trust=trust, markupBps=int(markup), routeKm=km, prices=prices,
                                pickupPlaceId=request["legs"][0]["pickup"]["placeId"],
                                deliveryPlaceId=request["legs"][-1]["delivery"]["placeId"],
                                dealerFactor=float(dealer), placeFactor=float(place), tableFactor=float(table),
                                optionFactors=factors, tracker=tracker, trackerMarkupBps=markup,
                                winTargetBps=self.win_target(), trustBuildApplied=any(f["trustBuildBps"] != 10000 for f in factors.values()),
                                trustGuardApplied=guard, trustGuardDropped=[o["kind"] for o in request["options"]
                                                                         if guard and self.slack(request, o) < 720],
                                longRoute=self.is_long_route(km), openOrders=len(self.orders_without_driver()),
                                longOpenOrders=len(self.long_orders_without_driver()))
        else:
            first = request["options"][0]
            prices = {first["kind"]: first["listPriceCents"] * 10}
            self.journal.record("beta_decline", at=self.now, requestId=request["id"], routeKm=km, reason=reason)
        self.outbox.append({"type": "quote", "requestId": request["id"], "prices": prices})

    def learn(self, request_id, won):
        if request_id not in self.pending:
            return
        self.pending.discard(request_id)
        tracker = self.quote_trackers.pop(request_id)
        target, step = self.win_target() / 10000, self.settings.learn_bps / 10000
        markup = self.tracker_markup(tracker) * (1 + step * (1 - target) if won else 1 - step * target)
        day, start = self.day_starts.get(tracker, (-1, 0))
        if self.settings.freeze_day_drop_bps and day == self.now // DAY:
            markup = max(markup, start * (1 - self.settings.freeze_day_drop_bps / 10000))
        markup = min(self.settings.markup_max_bps, max(self.settings.markup_min_bps, markup))
        if tracker == "global":
            self.markup = markup
        else:
            self.markups[tracker] = markup

    # ---- fee hooks and books ----

    def opening_fee_for(self, order):
        return (self.settings.long_opening_fee_bps if self.is_long_route(self.route_km(self.requests[order["id"]]))
                else self.settings.opening_fee_bps)

    def fees_for(self, order, cars):
        fee = self.requests[order["id"]]["referenceFeeCents"] * cars / len(order["legs"])
        if order["id"] in self.urgent or self.level == 1:
            return steep(self.now, fee, self.level)
        opening, steps = self.opening_fee_for(order), self.settings.fee_steps
        every = max(HOUR, (order["lastPickupAt"] - WARNING - self.now) // max(1, steps - 1))
        return [{"at": self.now + k * every,
                 "feeCents": max(1, int(fee * (opening + (self.settings.fee_cap_bps - opening) * k / max(1, steps - 1)) / 10000 + 0.5))}
                for k in range(steps)]

    def handle(self, event):
        dealer = None
        if event["kind"] == "ledger":
            dealer = self.dealers.get(event["line"].get("orderId") or "")
        before = self.trust.get(dealer, 0)
        super().handle(event)
        if dealer is not None and before != self.trust.get(dealer, 0):
            self.journal.record("gamma_trust", at=event["at"], dealer=dealer, before=before,
                                after=self.trust[dealer], cause=event["line"]["kind"])

    def read_results(self, actions, results):
        super().read_results(actions, results)
        for action, result in zip(actions, results):
            if action["type"] == "quote" and not result["ok"]:
                self.quote_trackers.pop(action["requestId"], None)


# Offers can compose as class GammaDesk(OffersMixin, GammaCoreDesk).
GammaCoreDesk = GammaDesk


def make_gamma(world, level, now, journal, **settings):
    return GammaDesk(world, level, now, journal, GammaSettings(**settings))
