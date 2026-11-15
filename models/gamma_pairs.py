"""Opt-in driver fee review and two-order gigs; defaults preserve the base desk.

Factories take ordinary sweep keyword settings. No SDK requests occur at import.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, fields
from functools import wraps

from .beta import BetaDesk, BetaSettings, FEE_CAP, FEE_STEPS, WARNING, closing
from capture import CapturedWorld
from spread.starter import DAY, HOUR, Retry


@dataclass(frozen=True)
class DriverSideSettings:
    fee_shape: str = "ramp"
    review_after_minutes: int = 360
    review_fee_bps: int = 11000
    cap_before_last_pickup_minutes: int = 360
    review_skip_night: int = 1
    pairs: int = 0
    pair_transfer_km: int = 30
    pair_max_drive_minutes: int = 300
    pair_arrival_allowance_minutes: int = 180
    pair_spare_minutes: int = 60
    pair_max_idle_minutes: int = 60
    pair_fee_bps: int = 7200
    pair_rescue_fee_bps: int = 7800
    pair_rescue_flat_minutes: int = 60
    pair_with_waiting: int = 1
    pair_split_minutes: int = 60
    pair_once: int = 1
    pair_tight_windows: int = 0
    pair_rescue_floor_bps: int = 0
    pair_rescue_step_minutes: int = 0
    pair_rescue_step_bps: int = 600
    pair_retry_limit: int = 0
    pair_retry_transfer_km: int = 30
    pair_cancel_cleanup: int = 0
    pair_aged_guard_minutes: int = 0
    pair_aged_guard_bps: int = 10000
    pair_self_time: int = 0
    pair_economic_rank: int = 0
    pair_stop_spare: int = 0
    pair_earliest_finish: int = 0
    pair_finish_band_minutes: int = 0
    pair_chain3: int = 0
    chain_transfer_km: int = 35
    chain_max_drive_minutes: int = 540
    chain_fee_bps: int = 6800

    def __post_init__(self):
        if self.fee_shape not in ("ramp", "review"):
            raise ValueError("fee_shape must be ramp or review")
        for name, value in vars(self).items():
            if name != "fee_shape" and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a nonnegative integer")
        for name in ("review_skip_night", "pairs", "pair_with_waiting", "pair_once", "pair_tight_windows",
                     "pair_cancel_cleanup", "pair_self_time", "pair_economic_rank", "pair_stop_spare",
                     "pair_earliest_finish", "pair_chain3"):
            if getattr(self, name) not in (0, 1):
                raise ValueError(f"{name} must be 0 or 1")
        if not 0 < self.pair_max_drive_minutes <= 720:
            raise ValueError("pair_max_drive_minutes must be between 1 and 720")
        if not 0 < self.chain_max_drive_minutes <= 720:
            raise ValueError("chain_max_drive_minutes must be between 1 and 720")
        for name in ("review_fee_bps", "pair_fee_bps", "pair_rescue_fee_bps", "pair_split_minutes"):
            if getattr(self, name) == 0:
                raise ValueError(f"{name} must be positive")
        if self.pair_rescue_floor_bps > 10000:
            raise ValueError("pair_rescue_floor_bps must be <= 10000")
        if not self.chain_fee_bps:
            raise ValueError("chain_fee_bps must be positive")
        if sum(bool(value) for value in (self.pair_economic_rank, self.pair_earliest_finish,
                                        self.pair_finish_band_minutes)) > 1:
            raise ValueError("pair_earliest_finish, pair_economic_rank and pair_finish_band_minutes are mutually exclusive")


@dataclass
class _Pair:
    orders: tuple[str, ...]
    action: dict
    transfer_km: float
    drive_minutes: int
    finish: int
    last_start: int
    latest_safe: int
    typical: int
    posted_at: int
    fee_policy: str = "fresh"
    waiting_withdrawn: bool = False
    gig_id: str | None = None
    active: bool = True
    retry_at: int = 0


def _hours_on(place, day):
    hours = place["hours"]
    if day % 7 in hours["weekdays"]:
        return hours
    return hours["saturday"] if day % 7 == 5 else None


def _next_open(place, minute, end):
    if place["hours"] is None:
        return minute if minute <= end else None
    day = minute // DAY
    while day * DAY <= end:
        hours = _hours_on(place, day)
        if hours is not None:
            candidate = max(minute, day * DAY + hours["opens"])
            if candidate <= min(end, closing(place, day * DAY + hours["opens"])):
                return candidate
        day += 1
    return None


def _previous_open(place, minute, start):
    if place["hours"] is None:
        return minute if minute >= start else None
    day = minute // DAY
    while (day + 1) * DAY > start:
        hours = _hours_on(place, day)
        if hours is not None:
            candidate = min(minute, closing(place, day * DAY + hours["opens"]))
            if candidate >= max(start, day * DAY + hours["opens"]):
                return candidate
        day -= 1
    return None


class DriverSideMixin:
    """Cooperative hooks for BetaDesk and GammaCoreDesk."""

    def __init__(self, *args, driver_settings=DriverSideSettings(), **kwargs):
        self._busy = 1
        self.driver_settings = driver_settings
        self.first_posted: dict[str, int] = {}
        self._pairs: dict[str, _Pair] = {}
        self._pending_pairs: dict[int, _Pair] = {}
        self._split_orders: set[str] = set()
        self._failed_pairs: set[frozenset[str]] = set()
        self._pair_failures: Counter = Counter()
        self._failed_orders: set[str] = set()
        self._picked: set[str] = set()
        self._started: set[str] = set()
        self._skip_logged: set[str] = set()
        super().__init__(*args, **kwargs)
        if driver_settings.pairs:
            for name in ("pair_fee_bps", "pair_rescue_fee_bps"):
                if getattr(driver_settings, name) > self._fee_cap():
                    raise ValueError(f"{name} must be <= the base fee_cap_bps")
            if driver_settings.pair_chain3 and driver_settings.chain_fee_bps > self._fee_cap():
                raise ValueError("chain_fee_bps must be <= the base fee_cap_bps")
        self._busy = 0
        if driver_settings.pairs:
            # dispatch.play_model owns the clock. Limit its ordinary advance to
            # our next timer; no polling, synthetic SDK events, or extra requests.
            # Final runners can use next_pair_wake() and poll_driver_side().
            advance = getattr(self.world, "advance", None)
            if advance is not None:
                @wraps(advance)
                def advance_with_pair_timer(*args, **kwargs):
                    wake = self.next_pair_wake()
                    if wake is not None:
                        if kwargs.get("until") is not None:
                            kwargs["max"] = min(kwargs.get("max") or wake, wake)
                        elif kwargs.get("to") is not None:
                            kwargs["to"] = min(kwargs["to"], wake)
                        elif kwargs.get("by") is not None:
                            kwargs["by"] = min(kwargs["by"], max(0, wake - self.now))
                    return advance(*args, **kwargs)
                self.world.advance = advance_with_pair_timer

    @property
    def outbox(self):
        # The runner drains the outbox AFTER it has read results and handled the
        # whole event batch. In particular a booking in that batch beats a timer.
        if not self._busy and self.driver_settings.pairs:
            self.poll_driver_side()
        return self._outbox

    @outbox.setter
    def outbox(self, value):
        self._outbox = value

    def _fee_cap(self):
        return getattr(self.settings, "fee_cap_bps", FEE_CAP)

    def _opening_bps(self, order):
        hook = getattr(self, "opening_fee_for", None)
        return hook(order) if hook else self.settings.opening_fee_bps

    def _review_schedule(self, typical, opening_bps, first_at, last_pickup):
        s = self.driver_settings
        review_at = first_at + s.review_after_minutes
        if s.review_skip_night:
            clock = review_at % DAY
            if clock >= 23 * HOUR:
                review_at = (review_at // DAY + 1) * DAY + 7 * HOUR
            elif clock < 7 * HOUR:
                review_at = review_at // DAY * DAY + 7 * HOUR
        cap = max(opening_bps, self._fee_cap())
        steps = [(first_at, opening_bps),
                 (review_at, max(opening_bps, min(cap, s.review_fee_bps))),
                 (last_pickup - max(WARNING, s.cap_before_last_pickup_minutes), cap)]
        current, future = opening_bps, []
        for at, fee in sorted(steps):
            current = max(current, fee)
            if at <= self.now:
                continue
            future.append((at, current))
        # Evaluate the current step independently: a future cap must not leak into now.
        current = max([opening_bps, *(fee for at, fee in steps if at <= self.now)])
        result = [{"at": self.now, "feeCents": max(1, int(typical * current / 10000 + 0.5))}]
        for at, fee in future:
            cents = max(result[-1]["feeCents"], int(typical * fee / 10000 + 0.5))
            if cents > result[-1]["feeCents"]:
                if at == result[-1]["at"]:
                    result[-1]["feeCents"] = cents
                else:
                    result.append({"at": at, "feeCents": cents})
        return result

    def fees_for(self, order, cars):
        if order["id"] in self.urgent or self.level == 1:
            return super().fees_for(order, cars)
        if self.driver_settings.fee_shape == "ramp":
            if not self.driver_settings.pairs:
                return super().fees_for(order, cars)
            typical = self.requests[order["id"]]["referenceFeeCents"] * cars / len(order["legs"])
            return self._ramp_schedule(typical, self._opening_bps(order),
                                       self.first_posted.get(order["id"], self.now), order["lastPickupAt"])
        typical = self.requests[order["id"]]["referenceFeeCents"] * cars / len(order["legs"])
        return self._review_schedule(typical, self._opening_bps(order),
                                     self.first_posted.get(order["id"], self.now), order["lastPickupAt"])

    def post(self, order, legs, retry=Retry()):
        self.first_posted.setdefault(order["id"], self.now)
        self._busy += 1
        try:
            if self.driver_settings.pairs and retry == Retry() and legs == [0]:
                try:
                    if self._try_pair(order):
                        return
                except Exception as error:
                    self._pair_error("pairing", error=type(error).__name__, orderId=order["id"])
            return super().post(order, legs, retry)
        finally:
            self._busy -= 1

    def _ramp_schedule(self, typical, opening, first_at, last_pickup):
        steps = getattr(self.settings, "fee_steps", FEE_STEPS)
        every = max(HOUR, (last_pickup - WARNING - first_at) // max(1, steps - 1))
        schedule = [{"at": first_at + k * every,
                     "feeCents": max(1, int(typical * (opening + (self._fee_cap() - opening)
                                                                  * k / max(1, steps - 1)) / 10000 + 0.5))}
                    for k in range(steps)]
        current = max((step for step in schedule if step["at"] <= self.now),
                      key=lambda step: step["at"], default=schedule[0])
        return [{**current, "at": self.now}, *(step for step in schedule if step["at"] > self.now)]

    def _pair_error(self, phase, **details):
        self.journal.record("gamma_pair_error", at=self.now, phase=phase, **details)

    def _pair_schedule(self, typical, last_pickup, rescue, *, opening_bps=None):
        """A new gig starts a new fee clock; singles keep their fallback age."""
        s = self.driver_settings
        opening = (s.pair_rescue_fee_bps if rescue else s.pair_fee_bps) if opening_bps is None else opening_bps
        schedule = (self._review_schedule if s.fee_shape == "review" else self._ramp_schedule)(
            typical, opening, self.now, last_pickup)
        if not rescue or not s.pair_rescue_flat_minutes:
            return schedule
        # Hold the rescue opening even when an old single or a nearby cap
        # would have started at a higher fee. Merge delayed steps to keep
        # timestamps distinct and fees nondecreasing.
        result = [{"at": self.now, "feeCents": max(1, int(typical * opening / 10000 + 0.5))}]
        for step in schedule:
            if step["feeCents"] <= result[-1]["feeCents"]:
                continue
            at = max(step["at"], self.now + s.pair_rescue_flat_minutes)
            if at == result[-1]["at"]:
                result[-1]["feeCents"] = step["feeCents"]
            else:
                result.append({**step, "at": at})
        return result

    def _live_pairs(self):
        return [p for p in [*self._pairs.values(), *self._pending_pairs.values()] if p.active]

    def _pair_of(self, identity):
        # Keep committed-before-pending order, but stop at the first match
        # instead of allocating/scanning the full live-pair list each time.
        for pairs in (self._pairs, self._pending_pairs):
            for pair in pairs.values():
                if (pair.active and identity in pair.orders
                        and (pair.gig_id is None or self.leg_gigs.get(identity, {}).get(0) == pair.gig_id)):
                    return pair
        return None

    def _eligible(self, order):
        identity = order["id"]
        if not (self.level >= 3 and len(order["legs"]) == 1 and order["deliveredAt"] == [None]
                and order["status"] not in ("cancelled", "delivered", "moving")
                and identity not in self.urgent and identity not in self._failed_orders
                and identity not in self._picked and not self._pair_of(identity)):
            return False
        gigs = self.gigs_of(identity)
        if any(g in self.booked or g in self._started for g in gigs):
            return False
        s = self.driver_settings
        if (s.pair_aged_guard_minutes and gigs and
                self.now - self.first_posted.get(identity, self.now) > s.pair_aged_guard_minutes):
            current = self._single_action(order)["schedule"][0]["feeCents"]
            typical = self.requests[identity]["referenceFeeCents"]
            if current * 10000 >= typical * s.pair_aged_guard_bps:
                return False
        return ((self._pair_failures[identity] < s.pair_retry_limit if s.pair_retry_limit else
                     not s.pair_once or identity not in self._split_orders)
                and (self.driver_settings.pair_with_waiting or not gigs))

    def _single_action(self, order):
        # Let the base apply its exact note, audience, plates and charging logic.
        start = len(self._outbox)
        try:
            super().post(order, [0])
            return self._outbox[start]
        finally:
            del self._outbox[start:]

    def _road(self, start, end):
        return {"km": 0, "minutes": 0} if start == end else self.roads[start, end]

    def _plan(self, first, second):
        return self._plan_orders((first, second))

    def _plan_chain(self, orders):
        if (not self.driver_settings.pair_chain3 or len(orders) != 3
                or len({o['id'] for o in orders}) != 3
                or any(len(o['legs']) != 1 or o['legs'][0]['car']['premium'] for o in orders)):
            return None, "chain_ineligible"
        return self._plan_orders(orders, chain=True)

    def _plan_orders(self, orders, *, chain=False):
        """Return a feasible sequential-car post, its timing and diagnostics, or a reason.

        Search both directions outside this method. Forward planning waits for
        openings; backward planning recomputes the first pickup's last start.
        """
        s = self.driver_settings
        if s.pair_retry_limit and frozenset(o["id"] for o in orders) in self._failed_pairs:
            return None, "failed_pair"
        transfers = [self._road(a["legs"][0]["delivery"]["placeId"],
                                b["legs"][0]["pickup"]["placeId"])
                     for a, b in zip(orders, orders[1:])]
        limit = s.chain_transfer_km if chain else s.pair_transfer_km
        if any(t["km"] > limit for t in transfers):
            return None, "transfer_too_far"
        if (s.pair_retry_limit and any(self._pair_failures[o["id"]] for o in orders)
                and any(t["km"] > s.pair_retry_transfer_km for t in transfers)):
            return None, "retry_transfer_too_far"
        actions = [self._single_action(order) for order in orders]
        stops = [stop for action in actions for stop in action["stops"]]
        places = [o["legs"][0][kind] for o in orders for kind in ("pickup", "delivery")]
        durations = []
        for a, b in zip(places, places[1:]):
            route = (a["placeId"], b["placeId"])
            road = self._road(*route)
            if (s.pair_self_time or chain) and route[0] == route[1]:
                # Correct driving time without changing the transfer-distance
                # preference that favors two orders meeting in the same town.
                road = self.roads.get(route, road)
            durations.append(road["minutes"])
        drive = sum(durations)
        if drive > min(720, s.chain_max_drive_minutes if chain else s.pair_max_drive_minutes):
            return None, "drive_too_long"
        audience = {key: any(a["audience"][key] for a in actions) for key in ("experienced", "manualLicence")}
        roster = getattr(self.world, "initial_roster", None)
        if roster is not None and not any(
                (not audience["manualLicence"] or d["licence"] == "manual") and
                (not audience["experienced"] or d["rating"] >= 4.8 and d["completedGigs"] >= 50)
                for d in roster):
            return None, "audience"
        windows = []
        for index, (stop, place) in enumerate(zip(stops, places)):
            order = orders[index // 2]
            own = stop.get("window", place["window"])
            end = min(place["window"]["to"], own["to"], order["deadline"])
            if stop["kind"] == "pickup":
                end = min(end, order["lastPickupAt"])
            windows.append((max(place["window"]["from"], own["from"]), end))

        def forward(start, spare):
            minute = start
            for index, (place, (low, high)) in enumerate(zip(places, windows)):
                if index:
                    minute += durations[index - 1]
                # Plates are fetched on the way to pickup; charge is on the
                # pickup -> delivery leg, just as the starter flags the pickup.
                if stops[index].get("withPlates"):
                    minute += 30
                arrived = minute
                minute = _next_open(place, max(arrived, low), high)
                if minute is None or minute > high:
                    return None, "windows"
                if index >= 2 and index % 2 == 0 and minute - arrived > s.pair_max_idle_minutes:
                    return None, "idle_too_long"
                order = orders[index // 2]
                delivery_bound = min(order["deadline"], high) if s.pair_stop_spare or chain else order["deadline"]
                if index % 2 and minute > delivery_bound - spare:
                    return None, "windows"
                if stops[index].get("withCharging"):
                    minute += 40
            return minute, None

        finish, reason = forward(self.now + s.pair_arrival_allowance_minutes, s.pair_spare_minutes)
        if finish is None:
            return None, reason

        def latest(spare, bounds=None):
            minute = float("inf")
            for index in range(len(stops) - 1, -1, -1):
                low, high = windows[index]
                if index % 2:
                    deadline = orders[index // 2]["deadline"]
                    high = min(high, deadline) - spare if s.pair_stop_spare or chain else min(high, deadline - spare)
                # Charging takes time after pickup. Plates precede pickup.
                minute = min(minute - (40 if stops[index].get("withCharging") else 0), high)
                minute = _previous_open(places[index], int(minute), low)
                if minute is None:
                    return None
                if bounds is not None:
                    # Visit time includes plates fetched before pickup, but
                    # excludes charging performed after the pickup visit.
                    bounds[index] = minute
                if stops[index].get("withPlates"):
                    minute -= 30
                if index:
                    minute -= durations[index - 1]
            return minute

        bounds = [None] * len(stops) if s.pair_tight_windows or chain else None
        last, safe = latest(0, bounds), latest(s.pair_spare_minutes)
        if last is None or safe is None:
            return None, "windows"
        if bounds is not None:
            if any(high < low for (low, _), high in zip(windows, bounds)):
                return None, "tight_windows"
            stops = [{**stop, "window": {"from": windows[index][0], "to": bounds[index]}}
                     for index, stop in enumerate(stops)]
        typical = sum(self.requests[o["id"]]["referenceFeeCents"] for o in orders)
        rescue = any(self.gigs_of(o["id"]) for o in orders)
        schedule = (self._pair_schedule(typical, last, rescue, opening_bps=s.chain_fee_bps) if chain else
                    self._pair_schedule(typical, last, rescue))
        if rescue and (s.pair_rescue_floor_bps or s.pair_rescue_step_minutes):
            # Preserve a fraction of the actual singles' current combined
            # offer. Their schedules already include age and opening rules.
            current = sum(max((step["feeCents"] for step in action["schedule"]
                               if step["at"] <= self.now), default=action["schedule"][0]["feeCents"])
                          for action in actions)
            opening = max(schedule[0]["feeCents"],
                          (current * s.pair_rescue_floor_bps + 9999) // 10000)
            cap = max(opening, int(typical * self._fee_cap() / 10000 + 0.5))
            steps = [(step["at"], max(opening, step["feeCents"])) for step in schedule]
            if s.pair_rescue_step_minutes:
                steps.append((self.now + s.pair_rescue_step_minutes,
                              min(cap, opening + int(typical * s.pair_rescue_step_bps / 10000 + 0.5))))
            schedule = []
            for at, fee in sorted(steps):
                if not schedule or fee > schedule[-1]["feeCents"]:
                    if schedule and at == schedule[-1]["at"]:
                        schedule[-1]["feeCents"] = fee
                    else:
                        schedule.append({"at": at, "feeCents": fee})
        action = dict(type="post", stops=stops, audience=audience, schedule=schedule)
        return _Pair(tuple(o["id"] for o in orders), action, sum(t["km"] for t in transfers), drive,
                     finish, last, safe, typical, self.now,
                     fee_policy="rescue" if rescue else "fresh"), None

    def _try_pair(self, order):
        if not self._eligible(order):
            return False
        reasons, plans = Counter(), []
        candidates = [other for other in self.orders.values() if other["id"] != order["id"] and self._eligible(other)]
        if not candidates:
            reasons["no_partner"] += 1
        for other in candidates:
            for first, second in ((order, other), (other, order)):
                plan, reason = self._plan(first, second)
                if plan:
                    plans.append(plan)
                else:
                    reasons[reason] += 1
        if order["id"] not in self._skip_logged:
            self._skip_logged.add(order["id"])
            self.journal.record("gamma_pair_skip", at=self.now, orderId=order["id"], counts=dict(reasons))
        if not plans:
            return False
        if self.driver_settings.pair_chain3:
            chains, seen = [], set()
            for plan in plans:
                if (plan.drive_minutes > self.driver_settings.chain_max_drive_minutes
                        or plan.transfer_km > self.driver_settings.chain_transfer_km):
                    continue
                for other in candidates:
                    if other['id'] in plan.orders:
                        continue
                    for members in ((other['id'], *plan.orders), (*plan.orders, other['id'])):
                        if members in seen:
                            continue
                        seen.add(members)
                        chain, _ = self._plan_chain([self.orders[m] if m != order['id'] else order for m in members])
                        if chain:
                            chains.append(chain)
            if chains:
                plans = chains
        if self.driver_settings.pair_economic_rank:
            pair = min(plans, key=lambda p: (p.action["schedule"][0]["feeCents"] - p.typical,
                                             p.transfer_km, p.finish, p.orders))
        elif self.driver_settings.pair_earliest_finish:
            pair = min(plans, key=lambda p: (p.finish, p.transfer_km, p.orders))
        elif self.driver_settings.pair_finish_band_minutes:
            end = min(p.finish for p in plans) + self.driver_settings.pair_finish_band_minutes
            pair = min((p for p in plans if p.finish <= end),
                       key=lambda p: (p.transfer_km, p.finish, p.orders))
        else:
            pair = min(plans, key=lambda p: (p.transfer_km, p.finish, p.orders))
        # Build everything before touching existing singles. Confirm withdrawal
        # results before queuing a post, so a racing booking is never released.
        gigs = list(dict.fromkeys(g for identity in pair.orders for g in self.gigs_of(identity)))
        if gigs and not self._withdraw_gigs(gigs):
            for identity in pair.orders:
                self._post_single(identity)
            # A withdrawal batch may succeed for only one of TWO waiting
            # singles. Restore that car too, even when this is a drop handler
            # rather than post(); tell post() when its fallback is queued.
            return self._queued(order["id"])
        pair.waiting_withdrawn = bool(gigs)
        for identity in pair.orders:
            self.first_posted.setdefault(identity, self.now)
        self._outbox[:] = [a for a in self._outbox if not (a["type"] == "post" and
                            {s["orderId"] for s in a["stops"]} <= set(pair.orders))]
        self._pending_pairs[id(pair.action)] = pair
        self._outbox.append(pair.action)
        return True

    def _queued(self, identity):
        return any(a["type"] == "post" and any(s["orderId"] == identity for s in a["stops"])
                   for a in self._outbox)

    def _detach(self, gig_id):
        for books in self.leg_gigs.values():
            for leg in [leg for leg, gig in books.items() if gig == gig_id]:
                books.pop(leg)
        self.booked.discard(gig_id)

    def _withdraw_gigs(self, gigs):
        if not gigs:
            return True
        actions = [{"type": "withdraw", "gigId": g} for g in gigs]
        if any(g in self.booked or g in self._started for g in gigs):
            return False
        results = self.world.act(actions)
        # JournalDesk records every action result. Detach only successes.
        self.read_results(actions, results)
        return len(results) == len(actions) and all(r["ok"] for r in results)

    def send_post_of(self, order_id):
        if not self.driver_settings.pairs:
            return super().send_post_of(order_id)
        if self._queued(order_id):
            self.send()

    def withdraw(self, order_id):
        if not self.driver_settings.pairs:
            return super().withdraw(order_id)
        self.send_post_of(order_id)
        return self._withdraw_gigs(self.gigs_of(order_id))

    def _post_single(self, identity):
        order = self.orders.get(identity)
        if (order and order["deliveredAt"] == [None] and identity not in self._picked
                and not self.gigs_of(identity) and not self._queued(identity)):
            self.first_posted.setdefault(identity, self.now)
            super().post(order, [0])

    def _split_pair(self, pair, reason, *, gone=False, omit=()):
        if not pair.active:
            return False
        if pair.gig_id and (pair.gig_id in self.booked or pair.gig_id in self._started) and not gone:
            return False
        if pair.gig_id and not gone:
            if not self._withdraw_gigs([pair.gig_id]):
                pair.retry_at = self.now + HOUR
                return False
        elif pair.gig_id:
            self._detach(pair.gig_id)
        else:
            self._outbox[:] = [a for a in self._outbox if a is not pair.action]
            self._pending_pairs.pop(id(pair.action), None)
        pair.active = False
        if reason != "order_cancelled" or not self.driver_settings.pair_cancel_cleanup:
            self._record_failed_pair(pair)
        self.journal.record("gamma_pair_split", at=self.now, gigId=pair.gig_id,
                            orders=list(pair.orders), reason=reason)
        for identity in pair.orders:
            if identity not in omit:
                self._post_single(identity)
        return True

    def _record_failed_pair(self, pair):
        self._split_orders.update(pair.orders)
        if self.driver_settings.pair_retry_limit:
            self._remember_pair_failure(pair.orders)

    def _remember_pair_failure(self, members):
        key = frozenset(members)
        if key not in self._failed_pairs:
            self._failed_pairs.add(key)
            self._pair_failures.update(key)

    def _safe_split_pair(self, pair, reason, **kwargs):
        try:
            return self._split_pair(pair, reason, **kwargs)
        except Exception as error:
            pair.retry_at = self.now + HOUR
            self._pair_error("split", gigId=pair.gig_id, error=type(error).__name__)
            return False

    def _record_intercepted(self, event):
        # An intercepted event does not traverse JournalDesk.handle. Captured
        # worlds already persist the original event batch; bare desks need it.
        if not isinstance(self.world, CapturedWorld):
            self.journal.record("event", event=event)

    def next_pair_wake(self):
        wakes = []
        s = self.driver_settings
        for pair in self._live_pairs():
            if pair.gig_id not in self.booked and pair.gig_id not in self._started:
                due = min(pair.posted_at + s.pair_split_minutes,
                          pair.latest_safe - s.pair_arrival_allowance_minutes + 1)
                wakes.append(max(pair.retry_at, due, self.now))
        return min(wakes) if wakes else None

    def poll_driver_side(self):
        """Process timers after the entire batch; also usable by a final runner."""
        self._busy += 1
        try:
            for pair in self._live_pairs():
                if pair.gig_id in self.booked or pair.gig_id in self._started or self.now < pair.retry_at:
                    continue
                reason = None
                if self.now >= pair.posted_at + self.driver_settings.pair_split_minutes:
                    reason = "time"
                elif self.now + self.driver_settings.pair_arrival_allowance_minutes > pair.latest_safe:
                    reason = "windows"
                if reason:
                    try:
                        self._split_pair(pair, reason)
                    except Exception as error:
                        pair.retry_at = self.now + HOUR
                        self._pair_error("split", gigId=pair.gig_id, error=type(error).__name__)
        finally:
            self._busy -= 1

    def handle(self, event):
        if not self.driver_settings.pairs:
            return super().handle(event)
        self._busy += 1
        try:
            kind, identity = event["kind"], event.get("orderId")
            gig_id = event.get("gigId")
            pair = self._pairs.get(gig_id) if gig_id else self._pair_of(identity) if identity else None
            if kind == "order_changed":
                identity = event["order"]["id"]
                pair = self._pair_of(identity)
            if kind == "visit_failed":
                self._failed_orders.add(identity)
            elif kind == "picked_up":
                self._picked.add(identity)
            elif kind == "gig_started":
                self._started.add(gig_id)
                self.booked.add(gig_id)
            if pair and pair.active:
                if kind == "gig_booked":
                    self.journal.record("gamma_pair_booked", at=event["at"], gigId=gig_id,
                                        orders=list(pair.orders), feeCents=event["feeCents"],
                                        typicalFeeCents=pair.typical,
                                        feeRatio=event["feeCents"] / pair.typical if pair.typical else None,
                                        minutesSincePosted=event["at"] - pair.posted_at)
                elif kind in ("gig_expired", "gig_dropped", "no_show"):
                    if kind != "gig_expired":
                        self.booked.discard(gig_id)
                        self._started.discard(gig_id)
                    # Expiry has already withdrawn the gig. Drops/no-shows
                    # reopen it, so a confirmed withdrawal is still necessary.
                    self._record_intercepted(event)
                    self._safe_split_pair(pair, kind, gone=kind == "gig_expired")
                    return
                elif kind == "deadline_close":
                    self.urgent.add(identity)
                    self._safe_split_pair(pair, kind)
                    # Do not let starter.raise_fees reprice TWO cars using
                    # just one order's typical fee if a withdrawal raced.
                    if pair.active:
                        self._record_intercepted(event)
                        return
                elif kind == "order_changed":
                    self.orders[identity] = event["order"]
                    self._record_intercepted(event)
                    self._safe_split_pair(pair, kind)
                    return  # a booked/working pair follows the world's change
                elif kind == "order_cancelled":
                    outcomes = {g["gigId"]: g["outcome"] for g in event["gigs"]}
                    outcome = outcomes.get(pair.gig_id)
                    if (self.driver_settings.pair_cancel_cleanup or self.driver_settings.pair_chain3) and outcome in ("shortened", "continues"):
                        pair.orders = tuple(m for m in pair.orders if m != identity)
                        pair.active = len(pair.orders) > 1
                        pair.action["stops"] = [stop for stop in pair.action["stops"] if stop["orderId"] != identity]
                        if pair.gig_id in self.posts:
                            self.posts[pair.gig_id]["stops"] = [
                                stop for stop in self.posts[pair.gig_id]["stops"]
                                if stop["orderId"] != identity]
                    elif outcome in ("withdrawn", "released"):
                        self._safe_split_pair(pair, kind, gone=True, omit=(identity,))
                    elif pair.gig_id not in self.booked and pair.gig_id not in self._started:
                        self._safe_split_pair(pair, kind, omit=(identity,))
                    # shortened/continues keep the other order and booked fee.
                elif kind == "visit_failed":
                    # starter.retry removes only the failed car and preserves
                    # the surviving car's link to the working pair gig.
                    self._started.add(gig_id)
                    self.booked.add(gig_id)
            # A single gig can return to open too. The starter only clears its
            # booked flag for drops; our post hook considers waiting partners.
            elif kind in ("gig_dropped", "no_show"):
                self.booked.discard(gig_id)
                self._started.discard(gig_id)
                members = {s["orderId"] for s in self.posts.get(gig_id, {}).get("stops", [])
                           if self.leg_gigs.get(s["orderId"], {}).get(s["leg"]) == gig_id}
                for member in members:
                    try:
                        if self._try_pair(self.orders[member]):
                            break
                    except Exception as error:
                        self._pair_error("reopened", orderId=member, error=type(error).__name__)
            super().handle(event)
        finally:
            self._busy -= 1

    def repost(self, gig_id):
        if not self.driver_settings.pairs:
            return super().repost(gig_id)
        action = self.posts.get(gig_id)
        if action is None:
            return
        members = list(dict.fromkeys(s["orderId"] for s in action["stops"]
                                    if self.leg_gigs.get(s["orderId"], {}).get(s["leg"]) == gig_id))
        if not members:
            return
        # Expiry has already removed the gig; consider pairing the single anew.
        self._detach(gig_id)
        for identity in members:
            order = self.orders.get(identity)
            if order and len(order["legs"]) == 1:
                self.post(order, [0])
            elif order:
                # Trade-ins stay on the base's normal multi-leg expiry path.
                self.carry(action, gig_id)
                super().repost(gig_id)
                break

    def read_results(self, actions, results):
        self._busy += 1
        try:
            super().read_results(actions, results)
            if not self.driver_settings.pairs:
                return
            for action, result in zip(actions, results):
                pair = self._pending_pairs.pop(id(action), None) if action["type"] == "post" else None
                if action["type"] == "withdraw":
                    if result["ok"]:
                        self._detach(action["gigId"])
                    else:
                        self._pair_error("withdraw", gigId=action["gigId"], reason=result.get("reason"))
                if pair:
                    if result["ok"]:
                        pair.gig_id = result["id"]
                        self._pairs[pair.gig_id] = pair
                        self.journal.record("gamma_pair", at=pair.posted_at, gigId=pair.gig_id,
                                            orders=list(pair.orders), stops=pair.action["stops"],
                                            transferKm=pair.transfer_km, driveMinutes=pair.drive_minutes,
                                            typicalFeeCents=pair.typical,
                                            openingFeeCents=pair.action["schedule"][0]["feeCents"],
                                            feePolicy=pair.fee_policy,
                                            waitingWithdrawn=pair.waiting_withdrawn)
                    else:
                        pair.active = False
                        self._record_failed_pair(pair)
                        self._pair_error("post", orders=list(pair.orders), reason=result.get("reason"))
                        for identity in pair.orders:
                            self._post_single(identity)
        finally:
            self._busy -= 1


def _split_settings(base_type, settings):
    driver_names = {f.name for f in fields(DriverSideSettings)}
    base_names = {f.name for f in fields(base_type)}
    unknown = settings.keys() - driver_names - base_names
    if unknown:
        raise TypeError(f"unknown settings: {', '.join(sorted(unknown))}")
    return (base_type(**{k: v for k, v in settings.items() if k in base_names}),
            DriverSideSettings(**{k: v for k, v in settings.items() if k in driver_names}))


def make_pairs_beta(world, level, now, journal, **settings):
    class PairsBetaDesk(DriverSideMixin, BetaDesk):
        # Timers and pair bookkeeping require every existing dispatcher wake.
        passive_wake_events = frozenset() if settings.get("pairs", 0) else BetaDesk.passive_wake_events

    base, driver = _split_settings(BetaSettings, settings)
    return PairsBetaDesk(world, level, now, journal, base, driver_settings=driver)


def make_gamma_pairs(world, level, now, journal, **settings):
    # Gamma may be updated independently while a sweep imports this module.
    from .gamma import GammaCoreDesk, GammaSettings

    class GammaPairsDesk(DriverSideMixin, GammaCoreDesk):
        passive_wake_events = frozenset() if settings.get("pairs", 0) else GammaCoreDesk.passive_wake_events

    base, driver = _split_settings(GammaSettings, settings)
    return GammaPairsDesk(world, level, now, journal, base, driver_settings=driver)
