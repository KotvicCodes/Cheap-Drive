"""Gamma's pricing and admission controls; defaults reproduce Beta."""
from __future__ import annotations

from collections import deque
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
    short_fee_km: int = 45  # independent of the quote discount's short_km
    short_opening_fee_bps: int = 0  # zero leaves the existing fee floor unchanged
    premium_opening_fee_bps: int = 0
    premium_min_slack_minutes: int = 0
    quote_options: str = "all"
    markup_scope: str = "global"
    freeze_day_drop_bps: int = 0
    same_day_min_slack_minutes: int | None = None  # omission follows min_slack_minutes
    brake: int = 0
    brake_soft_bps: int = 500
    brake_hard_bps: int = 750
    brake_soft_warnings: int = 6
    brake_hard_warnings: int = 12
    brake_soft_drops: int = 100000
    brake_warned_weight_pct: int = 50
    brake_min_orders: int = 40
    brake_hold_minutes: int = 240
    brake_caution_target_bps: int = 3000
    brake_target_bps: int = 2200
    brake_caution_bump_bps: int = 10300
    brake_bump_bps: int = 10800
    brake_caution_same_day_slack_minutes: int = 720
    brake_drop_same_day: int = 1
    brake_min_slack_minutes: int = 720
    brake_blocks_long: int = 1
    brake_max_km: int = 0

    def __post_init__(self):
        if self.long_max_km is None:
            object.__setattr__(self, "long_max_km", self.max_km)
        if self.same_day_min_slack_minutes is None:
            object.__setattr__(self, "same_day_min_slack_minutes", self.min_slack_minutes)
        strings = {"long_options", "quote_options", "markup_scope"}
        for name, value in vars(self).items():
            if name in strings:
                if type(value) is not str:
                    raise ValueError(f"{name} must be a string")
            elif type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        for name in ("trade_ins", "dealer_table", "place_table", "trust_guard", "capacity_valve",
                     "brake", "brake_drop_same_day", "brake_blocks_long"):
            if getattr(self, name) not in (0, 1):
                raise ValueError(f"{name} must be 0 or 1")
        for name in ("win_target_bps", "win_target_low_bps", "win_target_mid_bps", "win_target_high_bps",
                     "brake_caution_target_bps", "brake_target_bps"):
            if not 0 < getattr(self, name) < 10000:
                raise ValueError(f"{name} must be between 1 and 9999")
        for name, maximum in (("table_strength", 100), ("learn_bps", 10000),
                              ("trust_build_bps", 9999), ("freeze_day_drop_bps", 10000),
                              ("trust_build_until_day", 7), ("brake_warned_weight_pct", 100)):
            if getattr(self, name) > maximum or (name == "trust_build_until_day" and getattr(self, name) < 1):
                raise ValueError(f"{name} outside its allowed range")
        if self.brake_min_orders < 1:
            raise ValueError("brake_min_orders must be positive")
        for name in ("brake_caution_bump_bps", "brake_bump_bps"):
            if getattr(self, name) == 0:
                raise ValueError(f"{name} must be positive; use 10000 for no bump")
        if not 0 < self.markup_min_bps <= self.start_markup_bps <= self.markup_max_bps:
            raise ValueError("markup bounds must contain a positive start_markup_bps")
        if not 0 < self.opening_fee_bps <= self.fee_cap_bps or self.fee_steps < 1:
            raise ValueError("opening_fee_bps must be positive and <= fee_cap_bps; fee_steps must be >= 1")
        if not 0 < self.long_opening_fee_bps <= self.fee_cap_bps:
            raise ValueError("long_opening_fee_bps must be positive and <= fee_cap_bps")
        for name in ("short_opening_fee_bps", "premium_opening_fee_bps"):
            if getattr(self, name) > self.fee_cap_bps:
                raise ValueError(f"{name} must be <= fee_cap_bps; use 0 for no override")
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
        self.brake_mode = "normal"
        self.brake_last_held: dict[str, int] = {}
        self.brake_warned: set[str] = set()
        self.brake_late: set[str] = set()
        self.brake_warnings: deque[int] = deque()
        self.brake_drops: deque[int] = deque()
        table_places = set(DELIVERY_FACTORS) | {place for lane in LANE_FACTORS for place in lane}
        unknown = table_places - PLACE_IDS
        if settings.place_table:
            # Disabled tables also work with the starter's small synthetic demo map.
            map_places = {place for lane in self.roads for place in lane}
            unknown |= table_places - map_places
        if unknown:
            raise ValueError(f"unknown table place ids: {', '.join(sorted(unknown))}")

    # ---- on-time brake ----

    def brake_inputs(self, at=None):
        at = self.now if at is None else at
        # Trailing window is (now - DAY, now]; repeated warnings count as events,
        # but each open warned or refunded order contributes only once.
        for history in (self.brake_warnings, self.brake_drops):
            while history and history[0] <= at - DAY:
                history.popleft()
        won = {identity for identity, order in self.orders.items() if order["status"] != "cancelled"}
        late = len(won & self.brake_late)
        warned_open = sum(identity not in self.brake_late and self.orders[identity]["status"] != "delivered"
                          and bool(undelivered(self.orders[identity])) for identity in won & self.brake_warned)
        projected = 100 * (100 * late + self.settings.brake_warned_weight_pct * warned_open) / max(
            len(won), self.settings.brake_min_orders)
        return {"projectedLateBps": projected, "warn24": len(self.brake_warnings),
                "drops24": len(self.brake_drops), "late": late, "warnedOpen": warned_open, "won": len(won)}

    def observe_brake(self, at):
        """Refresh hold clocks before books change, including between-quote expiries."""
        s = self.settings
        if not s.brake:
            return
        # Before pruning, the Nth newest event tells us when a rolling count
        # last met its threshold, even if there was no quote at its expiry.
        def last_signal(history, threshold):
            if threshold == 0:
                return at
            return min(at, history[-threshold] + DAY) if len(history) >= threshold else None
        hard_at = last_signal(self.brake_warnings, s.brake_hard_warnings)
        soft_times = [hard_at, last_signal(self.brake_warnings, s.brake_soft_warnings),
                      last_signal(self.brake_drops, s.brake_soft_drops)]
        projected = self.brake_inputs(at)["projectedLateBps"]
        if projected >= s.brake_hard_bps:
            hard_at = at
        if projected >= s.brake_soft_bps:
            soft_times.append(at)
        soft_times.append(hard_at)
        for severity, times in (("brake", [hard_at]), ("caution", soft_times)):
            held = [t for t in times if t is not None]
            if held:
                self.brake_last_held[severity] = max(self.brake_last_held.get(severity, 0), max(held))

    def update_brake(self):
        """Recompute the mode at each quote from the desk's own event history."""
        self.observe_brake(self.now)
        s, inputs = self.settings, self.brake_inputs()
        mode = "normal"
        if s.brake:
            hard = inputs["projectedLateBps"] >= s.brake_hard_bps or inputs["warn24"] >= s.brake_hard_warnings
            soft = (hard or inputs["projectedLateBps"] >= s.brake_soft_bps
                    or inputs["warn24"] >= s.brake_soft_warnings or inputs["drops24"] >= s.brake_soft_drops)
            if hard or self.now < self.brake_last_held.get("brake", -s.brake_hold_minutes) + s.brake_hold_minutes:
                mode = "brake"
            elif soft or self.now < self.brake_last_held.get("caution", -s.brake_hold_minutes) + s.brake_hold_minutes:
                mode = "caution"
        if mode != self.brake_mode:
            previous, self.brake_mode = self.brake_mode, mode
            severity = {"normal": 0, "caution": 1, "brake": 2}
            if severity[mode] > severity[previous]:
                self.bump_markups(s.brake_bump_bps if mode == "brake" else s.brake_caution_bump_bps)
            self.journal.record("gamma_brake", at=self.now, **{"from": previous, "to": mode}, **inputs)
        return {"mode": mode, **inputs}

    def bump_markups(self, factor_bps):
        s = self.settings
        def bumped(value):
            return min(s.markup_max_bps, max(s.markup_min_bps, value * factor_bps / 10000))
        self.markup = bumped(self.markup)
        # Include not-yet-used trackers so a new dealer/distance bucket gets the
        # entry bump too, rather than starting at the unbraked opening price.
        trackers = set(self.markups)
        if s.markup_scope == "dealer":
            trackers.update((*self.big_dealers, "other"))
        elif s.markup_scope == "km":
            trackers.update(("under_100", "100_to_300", "over_300"))
        for tracker in trackers:
            self.markups[tracker] = bumped(self.tracker_markup(tracker))

    # ---- admission ----

    def route_km(self, request):
        return sum(self.roads[leg["pickup"]["placeId"], leg["delivery"]["placeId"]]["km"]
                   for leg in request["legs"])

    def is_long_route(self, km):
        return bool(self.settings.max_km and self.settings.max_km < km <= self.settings.long_max_km)

    def is_premium(self, request):
        return any(leg["car"]["premium"] for leg in request["legs"])

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
        if ((self.brake_mode == "brake" and s.brake_blocks_long and self.is_long_route(km))
                or (self.brake_mode == "brake" and s.brake_max_km and km > s.brake_max_km)):
            return [], "on-time brake"
        options = [o for o in request["options"] if self.slack(request, o) >= (
            s.same_day_min_slack_minutes if o["kind"] == "same_day" else s.min_slack_minutes)]
        if not options:
            return [], "no option leaves a driver enough time"
        if s.premium_min_slack_minutes and self.is_premium(request):
            options = [o for o in options if self.slack(request, o) >= s.premium_min_slack_minutes]
            if not options:
                return [], "premium slack"
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
        if self.brake_mode == "caution":
            options = [o for o in options if o["kind"] != "same_day"
                       or self.slack(request, o) >= s.brake_caution_same_day_slack_minutes]
        elif self.brake_mode == "brake":
            options = [o for o in options if not (s.brake_drop_same_day and o["kind"] == "same_day")
                       and (o["kind"] == "same_day" or self.slack(request, o) >= s.brake_min_slack_minutes)]
        if not options:
            return [], "on-time brake"
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
        if self.brake_mode == "brake":
            return s.brake_target_bps
        if self.brake_mode == "caution":
            return s.brake_caution_target_bps
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
        brake = self.update_brake()
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
                                longOpenOrders=len(self.long_orders_without_driver()), **brake)
        else:
            first = request["options"][0]
            prices = {first["kind"]: first["listPriceCents"] * 10}
            self.journal.record("beta_decline", at=self.now, requestId=request["id"], routeKm=km, reason=reason, **brake)
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
        s = self.settings
        km = self.route_km(self.requests[order["id"]])
        # Segment floors combine by maximum, including configurable overlaps.
        return max(s.opening_fee_bps,
                   s.long_opening_fee_bps if self.is_long_route(km) else 0,
                   s.short_opening_fee_bps if km < s.short_fee_km else 0,
                   s.premium_opening_fee_bps if self.is_premium(order) else 0)

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
        kind = event["kind"]
        if kind in ("order_won", "order_cancelled", "order_changed", "delivered", "deadline_close",
                    "gig_dropped", "no_show", "ledger"):
            self.observe_brake(event["at"])
        if kind == "deadline_close":
            self.brake_warned.add(event["orderId"])
            self.brake_warnings.append(event["at"])
        elif kind in ("gig_dropped", "no_show"):
            self.brake_drops.append(event["at"])
        elif kind == "ledger" and event["line"]["kind"] == "late_refund":
            if event["line"].get("orderId") is not None:
                self.brake_late.add(event["line"]["orderId"])
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
