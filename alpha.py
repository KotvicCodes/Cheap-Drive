"""Alpha: route costs, estimated driver supply and per-dealer quote feedback."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING

from dispatch import Journal, JournalDesk
from spread import World
from spread.starter import DAY, window_from_note
from spread.types import Action, ActionResult, DeskEvent, PriceRequest


@dataclass(frozen=True)
class AlphaSettings:
    distance_cents_per_km: int = 45
    pickup_cents_per_km: int = 30
    scarcity_cents: int = 4_000
    initial_margin_bps: int = 2_500
    min_margin_bps: int = 1_500
    max_margin_bps: int = 6_000
    feedback_step_bps: int = 300
    min_margin_cents: int = 2_000
    nearby_km: int = 50

    def __post_init__(self):
        for name, value in vars(self).items():
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if not self.min_margin_bps <= self.initial_margin_bps <= self.max_margin_bps:
            raise ValueError("require min_margin_bps <= initial_margin_bps <= max_margin_bps")
        if not self.feedback_step_bps or not self.nearby_km:
            raise ValueError("feedback_step_bps and nearby_km must be positive")


def quote_cents(reference_cents, route_km, pickup_km, nearby, margin_bps, settings):
    """Evaluate the discussed formula, rounding only the final quote upward."""
    cost = max(Decimal(reference_cents), Decimal(str(route_km)) * settings.distance_cents_per_km)
    cost += Decimal(str(pickup_km)) * settings.pickup_cents_per_km
    margin = max(Decimal(settings.min_margin_cents), cost * margin_bps / 10_000)
    scarcity = Decimal(settings.scarcity_cents) / (nearby + 1)
    price = int((cost + margin + scarcity).to_integral_value(rounding=ROUND_CEILING))
    return max(1, price), float(cost)


def open_at(stop, arrival, deadline, note, kind, protected_pickup=False):
    """Earliest visit fitting public windows/hours and the starter's note parser."""
    window = dict(stop["window"])
    window["to"] = min(window["to"], deadline)
    if protected_pickup:
        window["to"] = deadline
    window = window_from_note(note, window, kind)
    earliest, latest = max(arrival, window["from"]), window["to"]
    hours = stop["hours"]
    if hours is None:
        return earliest if earliest <= latest else None
    for day in range(earliest // DAY, latest // DAY + 1):
        weekday = day % 7
        if weekday in hours["weekdays"]:
            opening = hours
        elif weekday == 5 and hours["saturday"] is not None:
            opening = hours["saturday"]
        else:
            continue
        visit = max(earliest, day * DAY + opening["opens"])
        if visit <= min(latest, day * DAY + opening["closes"]):
            return visit
    return None


class AlphaDesk(JournalDesk):
    """Use public data only; home locations and availability are estimates.

    Delivery execution and driver fee schedules remain the starter's. Reserve
    one plausible driver for each outstanding quote/unbooked order so bursts
    cannot all count the same estimated capacity. No real driver is assigned.
    """

    def __init__(self, world: World, level: int, now: int, journal: Journal,
                 settings: AlphaSettings = AlphaSettings()):
        super().__init__(world, level, now, journal)
        self.settings = settings
        self.dealer_margins: dict[str, int] = {}
        self.pending_quotes: dict[str, str] = {}
        self.reservations: dict[str, str] = {}
        self.gig_drivers: dict[str, str] = {}
        self.positions: dict[str, tuple[str, int]] = {}
        # play_model wraps the SDK world in CapturedWorld, which already journals
        # the initial map, roster and snapshot; read the same public data directly.
        source = getattr(world, "world", world)
        self.roads = {(road["from"], road["to"]): road for road in source.client.map()["roads"]}
        self.drivers = {driver["id"]: driver for driver in source.roster()}
        snapshot = source.snapshot()
        for position in snapshot["driverPositions"]:
            self.positions[position["driverId"]] = (position["placeId"], now)
        for gig in snapshot["gigs"]:
            if gig["driverId"] is not None and gig["status"] in ("booked", "working"):
                self.gig_drivers[gig["id"]] = gig["driverId"]

    def route_distance(self, request):
        places = [leg[kind]["placeId"] for leg in request["legs"] for kind in ("pickup", "delivery")]
        roads = [self.roads[a, b] for a, b in zip(places, places[1:])]
        return sum(road["km"] for road in roads), sum(road["minutes"] for road in roads)

    def fits(self, request, option, position):
        # Leave time after the dealer decides for posting/viewing/booking.
        minute = max(self.now, request["respondBy"]) + 30
        previous_delivery = None
        for index, leg in enumerate(request["legs"]):
            pickup, delivery = leg["pickup"], leg["delivery"]
            minute += self.roads[position, pickup["placeId"]]["minutes"]
            protected = index > 0 and pickup["privateAddress"] and previous_delivery == pickup["placeId"]
            minute = open_at(pickup, minute, option["deadline"], request["note"], "pickup", protected)
            if minute is None:
                return False
            car = leg["car"]
            if car["electric"] and car["chargePercent"] is not None and car["chargePercent"] < 30:
                minute += 40  # Matches the starter's charging choice.
            minute += self.roads[pickup["placeId"], delivery["placeId"]]["minutes"]
            minute = open_at(delivery, minute, option["deadline"], request["note"], "delivery")
            if minute is None:
                return False
            position = previous_delivery = delivery["placeId"]
        return True

    def candidates(self, request, option):
        unavailable = set(self.gig_drivers.values()) | set(self.reservations.values())
        premium = any(leg["car"]["premium"] for leg in request["legs"])
        pickup = request["legs"][0]["pickup"]["placeId"]
        candidates = []
        for driver_id, driver in self.drivers.items():
            if driver_id in unavailable:
                continue
            if premium and (driver["rating"] < 4.8 or driver["completedGigs"] < 50):
                continue
            known = self.positions.get(driver_id)
            # A completed gig gives a last-seen position, not permanent tracking.
            position = known[0] if known and self.now - known[1] <= 120 else driver["homePlaceId"]
            if self.fits(request, option, position):
                candidates.append((self.roads[position, pickup]["km"], driver_id))
        return sorted(candidates)

    def quote(self, request: PriceRequest) -> None:
        if request["id"] in self.requests or self.now >= request["respondBy"]:
            return
        if self.level <= 3:
            super().quote(request)
            return
        self.requests[request["id"]] = request
        settings = self.settings
        margin = self.dealer_margins.get(request["dealerId"], settings.initial_margin_bps)
        distance, road_minutes = self.route_distance(request)
        prices, options = {}, []
        # Alpha only plans combined trade-ins that fit the game's 12-hour cap.
        if len(request["legs"]) == 1 or road_minutes <= 720:
            for option in request["options"]:
                candidates = self.candidates(request, option)
                if not candidates:
                    continue
                pickup_km, driver_id = candidates[0]
                nearby = sum(km <= settings.nearby_km for km, _ in candidates)
                price, cost = quote_cents(request["referenceFeeCents"], distance, pickup_km, nearby, margin, settings)
                prices[option["kind"]] = price
                options.append((pickup_km, driver_id))
                self.journal.record("alpha_quote", at=self.now, requestId=request["id"],
                                    dealerId=request["dealerId"], option=option["kind"],
                                    routeKm=distance, pickupKm=pickup_km, nearbyDrivers=nearby,
                                    estimatedCostCents=cost, marginBps=margin, priceCents=price)
        if prices:
            self.reservations[request["id"]] = min(options)[1]
            self.pending_quotes[request["id"]] = request["dealerId"]
        else:
            # Losing a quote avoids the goodwill cost of silence. It is not
            # market feedback, and a very high price is not a guaranteed decline.
            first = request["options"][0]
            prices[first["kind"]] = max(1_000_000, first["listPriceCents"] * 100)
            self.journal.record("alpha_decline", at=self.now, requestId=request["id"],
                                reason="no estimated feasible unreserved driver or combined route too long")
        self.outbox.append({"type": "quote", "requestId": request["id"], "prices": prices})

    def read_results(self, actions: list[Action], results: list[ActionResult]) -> None:
        super().read_results(actions, results)
        for action, result in zip(actions, results):
            if action["type"] == "quote" and not result["ok"]:
                self.pending_quotes.pop(action["requestId"], None)
                self.reservations.pop(action["requestId"], None)

    def handle(self, event: DeskEvent) -> None:
        kind = event["kind"]
        if kind in ("gig_booked", "gig_started"):
            self.gig_drivers[event["gigId"]] = event["driverId"]
            for stop in self.posts.get(event["gigId"], {}).get("stops", []):
                self.reservations.pop(stop["orderId"], None)
        elif kind in ("gig_dropped", "no_show"):
            self.gig_drivers.pop(event["gigId"], None)
        elif kind in ("picked_up", "delivered"):
            driver_id = self.gig_drivers.get(event["gigId"])
            if driver_id:
                self.positions[driver_id] = (event["placeId"], event["at"])
            if kind == "delivered":
                stops = self.posts.get(event["gigId"], {}).get("stops", [])
                if stops and all(stop["kind"] == "delivery" and stop["orderId"] == event["orderId"]
                                 and stop["leg"] == event["leg"] for stop in stops[-1:]):
                    self.gig_drivers.pop(event["gigId"], None)
        elif kind == "order_cancelled":
            self.reservations.pop(event["orderId"], None)
            for gig in event["gigs"]:
                if gig["outcome"] in ("withdrawn", "released"):
                    self.gig_drivers.pop(gig["gigId"], None)
        super().handle(event)
        if kind not in ("order_won", "order_lost"):
            return
        won = kind == "order_won"
        request_id = event["order"]["id"] if won else event["requestId"]
        if not won:
            self.reservations.pop(request_id, None)
        dealer_id = self.pending_quotes.pop(request_id, None)
        if dealer_id is None:
            return
        settings = self.settings
        previous = self.dealer_margins.get(dealer_id, settings.initial_margin_bps)
        adjustment = settings.feedback_step_bps if won else -settings.feedback_step_bps
        current = max(settings.min_margin_bps, min(settings.max_margin_bps, previous + adjustment))
        self.dealer_margins[dealer_id] = current
        self.journal.record("alpha_feedback", at=event["at"], requestId=request_id,
                            dealerId=dealer_id, outcome="won" if won else "lost",
                            previousBps=previous, nextBps=current)


def make_alpha(world, level, now, journal, *, distance_cents_per_km=45,
               pickup_cents_per_km=30, scarcity_cents=4_000, initial_margin_bps=2_500,
               min_margin_bps=1_500, max_margin_bps=6_000, feedback_step_bps=300,
               min_margin_cents=2_000, nearby_km=50):
    return AlphaDesk(world, level, now, journal, AlphaSettings(
        distance_cents_per_km=distance_cents_per_km, pickup_cents_per_km=pickup_cents_per_km,
        scarcity_cents=scarcity_cents, initial_margin_bps=initial_margin_bps,
        min_margin_bps=min_margin_bps, max_margin_bps=max_margin_bps,
        feedback_step_bps=feedback_step_bps, min_margin_cents=min_margin_cents,
        nearby_km=nearby_km))
