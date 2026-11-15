"""Bounded, opt-in direct offers; all inputs are public and cached.

Public transport times and driver workdays are hidden. Road time * 1.5 + 30m
is an estimate, not a promise; the server still checks the driver's actual day.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from math import asin, ceil, cos, radians, sin, sqrt

from spread.starter import DAY
from .gamma_pairs import _next_open


@dataclass(frozen=True)
class OfferSettings:
    epsilon_offers: int = 0
    offer_after_minutes: int = 120
    offer_before_pickup_minutes: int = 360
    offer_interval_minutes: int = 30
    offer_max_eta_minutes: int = 240
    offer_fee_bps: int = 10000

    def __post_init__(self):
        for name, value in vars(self).items():
            if type(value) is not int or value < 0:
                raise ValueError(name + ' must be a nonnegative integer')
        if self.epsilon_offers not in (0, 1):
            raise ValueError('epsilon_offers must be 0 or 1')
        if not 10 <= self.offer_interval_minutes <= 180:
            raise ValueError('offer_interval_minutes must be between 10 and 180')
        if not 1 <= self.offer_fee_bps <= 15000:
            raise ValueError('offer_fee_bps must be between 1 and 15000')
        if not 1 <= self.offer_max_eta_minutes <= 480:
            raise ValueError('offer_max_eta_minutes must be between 1 and 480')


def distance_km(a, b):
    """Notification radius is straight-line distance, not road kilometres."""
    lat1, lat2 = radians(a['lat']), radians(b['lat'])
    dlat, dlon = lat2 - lat1, radians(b['lon'] - a['lon'])
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 12742 * asin(min(1, sqrt(h)))


class EpsilonOffersMixin:
    def __init__(self, *args, offer_settings=OfferSettings(), **kwargs):
        self.offer_settings = offer_settings
        self._offer_handling = 1
        self._offer_posted = {}
        self._offer_closed = set()
        self._offer_schedules = {}
        self._offer_pending = {}  # gig -> {driver: expiry}, includes queued sends
        self._offer_counts = {}
        self._offer_attempted = set()
        self._offer_day = None
        self._offer_next = 0
        self._offer_resume_day = 0
        self._offer_drivers = {}
        self._offer_locations = {}
        self._offer_progress = {}
        super().__init__(*args, **kwargs)
        self._offer_handling = 0
        self._offer_places = {}
        self._offer_roster = {}
        self._offer_outside = {}
        self._offer_near = {}
        if not offer_settings.epsilon_offers:
            return
        self._offer_places = {p['id']: p for p in (getattr(self.world, 'initial_map', None) or {}).get('places', [])
                              if all(k in p for k in ('lat', 'lon'))}
        self._offer_roster = {d['id']: d for d in (getattr(self.world, 'initial_roster', None) or [])}
        for place, coordinates in self._offer_places.items():
            nearby = {other for other, c in self._offer_places.items() if distance_km(coordinates, c) <= 30}
            self._offer_near[place] = nearby
            self._offer_outside[place] = [d for d in self._offer_roster.values()
                                          if d.get('homePlaceId') in self._offer_places and d['homePlaceId'] not in nearby]
        # DriverSideMixin already installs this timer wrapper when pairs=1.
        if not self.driver_settings.pairs and hasattr(self.world, 'advance'):
            advance = self.world.advance

            @wraps(advance)
            def advance_with_offers(*args, **kwargs):
                wake = self.next_pair_wake()
                if wake is not None:
                    if kwargs.get('until') is not None:
                        kwargs['max'] = min(kwargs.get('max') or wake, wake)
                    elif kwargs.get('to') is not None:
                        kwargs['to'] = min(kwargs['to'], wake)
                    elif kwargs.get('by') is not None:
                        kwargs['by'] = min(kwargs['by'], max(0, wake - self.now))
                return advance(*args, **kwargs)
            self.world.advance = advance_with_offers

    @property
    def outbox(self):
        if not self.offer_settings.epsilon_offers:
            return super().outbox
        if not self._busy and not self._offer_handling:
            self.poll_driver_side()
        return self._outbox

    @outbox.setter
    def outbox(self, value):
        self._outbox = value

    def quote(self, request):
        # Accessing outbox from quote must never trigger an offer/driver scan.
        self._offer_handling += 1
        try:
            return super().quote(request)
        finally:
            self._offer_handling -= 1

    def carry(self, action, gig_id):
        super().carry(action, gig_id)
        if self.offer_settings.epsilon_offers:
            self._offer_posted.setdefault(gig_id, self.now)
            self._offer_schedules[gig_id] = action['schedule']

    def read_results(self, actions, results):
        self._offer_handling += 1
        try:
            super().read_results(actions, results)
            if not self.offer_settings.epsilon_offers:
                return
            for action, result in zip(actions, results):
                if result['ok'] and action['type'] == 'reprice':
                    self._offer_schedules[action['gigId']] = action['schedule']
                elif result['ok'] and action['type'] in ('withdraw', 'release'):
                    self._offer_closed.add(action['gigId'])
                elif action['type'] == 'offer':
                    self.journal.record('epsilon_offer_result', at=self.now, ok=result['ok'],
                                        gigId=action['gigId'], driverId=action['driverId'])
                    # Failed attempts still reserve quota: a timeout/retry must
                    # never make our local count more optimistic than the API.
        finally:
            self._offer_handling -= 1

    def handle(self, event):
        self._offer_handling += 1
        try:
            super().handle(event)
            if not self.offer_settings.epsilon_offers:
                return
            kind, gig = event['kind'], event.get('gigId')
            if kind in ('gig_booked', 'gig_started'):
                self._offer_drivers[gig] = event['driverId']
            elif kind in ('gig_dropped', 'no_show', 'gig_expired'):
                self._offer_drivers.pop(gig, None)
                self._offer_progress.pop(gig, None)
                if kind == 'gig_expired':
                    self._offer_closed.add(gig)
            elif kind == 'offer_answered':
                self._offer_pending.get(gig, {}).pop(event['driverId'], None)
                if event['answer'] == 'accepted':
                    self.booked.add(gig)
                    self._offer_drivers[gig] = event['driverId']
            elif kind in ('picked_up', 'delivered'):
                driver = self._offer_drivers.get(gig)
                stops = self.posts.get(gig, {}).get('stops', [])
                for index, stop in enumerate(stops):
                    if (stop['orderId'], stop['leg'], stop['kind']) == (event['orderId'], event['leg'],
                                                                          'pickup' if kind == 'picked_up' else 'delivery'):
                        self._offer_progress[gig] = index + 1
                        break
                if driver and event.get('placeId'):
                    self._offer_locations[driver] = (event['placeId'], event['at'])
            elif kind == 'deadline_close' and event['orderId'] in self.orders:
                self.orders[event['orderId']]['lastPickupAt'] = event['lastPickupAt']
        finally:
            self._offer_handling -= 1

    def rejoin(self, snapshot, history):
        self._offer_handling += 1
        try:
            super().rejoin(snapshot, history)
            if self.offer_settings.epsilon_offers:
                # History/snapshot omit outgoing offers. There is no safe way
                # to recover today's quota after losing local state. Resume on
                # the next world day; no extra reads on the live quote path.
                self._offer_resume_day = snapshot['now'] // DAY + 1
                self._offer_drivers = {g['id']: g['driverId'] for g in snapshot['gigs']
                                       if g.get('driverId') and g['status'] in ('booked', 'working')}
                for position in snapshot.get('driverPositions', []):
                    self._offer_locations[position['driverId']] = (position['placeId'], snapshot['now'])
        finally:
            self._offer_handling -= 1

    def next_pair_wake(self):
        pair = super().next_pair_wake()
        if not self.offer_settings.epsilon_offers:
            return pair
        wake = max(self.now, self._offer_next)
        return min(pair, wake) if pair is not None else wake

    def poll_driver_side(self):
        super().poll_driver_side()
        if (not self.offer_settings.epsilon_offers or self._offer_handling or self._busy
                or self.now < self._offer_next):
            return
        # Quotes leave first. The next advance returns quickly to this timer;
        # offers never add action tokens or CPU work to a quote's send batch.
        if any(a['type'] == 'quote' for a in self._outbox):
            self._offer_next = self.now + 1
            return
        self._poll_offers()

    def _offer_route(self, action, minute, *, start=0, position=None):
        """Estimated finish with explicit stop windows, stated hours and promises."""
        for stop in action['stops'][start:]:
            order = self.orders.get(stop['orderId'])
            if order is None:
                return None
            place = order['legs'][stop['leg']][stop['kind']]
            target = place['placeId']
            if position is not None and position != target:
                road = self.roads.get((position, target))
                if road is None:
                    return None
                minute += road['minutes']
            window = stop.get('window', place['window'])
            latest = min(window['to'], order['deadline'])
            minute = _next_open(place, max(minute, window['from']), latest)
            if minute is None:
                return None
            if stop['kind'] == 'pickup':
                minute += 30 * bool(stop.get('withPlates')) + 40 * bool(stop.get('withCharging'))
            position = target
        return minute, position

    def _offer_origins(self):
        origins = {}
        for driver, profile in self._offer_roster.items():
            origins[driver] = (self.now, profile.get('homePlaceId'), False)
            location = self._offer_locations.get(driver)
            if location and 0 <= self.now - location[1] <= 180 and location[1] // DAY == self.now // DAY:
                origins[driver] = (self.now, location[0], True)
        for gig, driver in self._offer_drivers.items():
            action = self.posts.get(gig)
            if action is None or gig in self._offer_closed:
                continue
            progress = self._offer_progress.get(gig, 0)
            if progress >= len(action['stops']):
                continue
            location = self._offer_locations.get(driver)
            position = location[0] if progress and location else None
            finish = self._offer_route(action, self.now, start=progress, position=position)
            if finish is None:
                origins[driver] = (float('inf'), None, False)
            elif finish[0] >= origins.get(driver, (0,))[0]:
                origins[driver] = (*finish, True)
        return origins

    def _poll_offers(self):
        s, day = self.offer_settings, self.now // DAY
        self._offer_next = self.now + s.offer_interval_minutes
        if self.level < 3:
            return
        if day < self._offer_resume_day:
            self._offer_next = self._offer_resume_day * DAY + 420
            return
        # Last ten minutes are excluded so an offer never spans the blackout.
        if not 420 <= self.now % DAY < 1370:
            self._offer_next = day * DAY + 420 if self.now % DAY < 420 else (day + 1) * DAY + 420
            return
        if day != self._offer_day:
            self._offer_day, self._offer_counts, self._offer_attempted = day, {}, set()
        for gig, pending in list(self._offer_pending.items()):
            self._offer_pending[gig] = {d: end for d, end in pending.items() if end > self.now}
        excluded = {a.get('gigId') for a in self._outbox if a['type'] in ('withdraw', 'release')}
        risks = []
        for gig, posted in self._offer_posted.items():
            action = self.posts.get(gig)
            if not action or gig in self.booked or gig in self._offer_closed or gig in excluded:
                continue
            if not all(self.leg_gigs.get(t['orderId'], {}).get(t['leg']) == gig for t in action['stops']):
                continue
            orders = [self.orders.get(t['orderId']) for t in action['stops']]
            if any(o is None for o in orders):
                continue
            latest = min([o['lastPickupAt'] for o in orders] +
                         [t['window']['to'] for t in action['stops'] if 'window' in t])
            if self.now + 10 > latest:
                continue
            if self.now - posted >= s.offer_after_minutes or latest - self.now <= s.offer_before_pickup_minutes:
                risks.append((latest, posted, gig))
        if not risks:
            return
        origins, budget = self._offer_origins(), min(3, max(0, 40 - len(self._outbox)))
        for latest, _, gig in sorted(risks)[:8]:
            if not budget:
                break
            action = self.posts[gig]
            pickup_stop, final_stop = action['stops'][0], action['stops'][-1]
            pickup = self.orders[pickup_stop['orderId']]['legs'][pickup_stop['leg']]['pickup']['placeId']
            delivery = self.orders[final_stop['orderId']]['legs'][final_stop['leg']]['delivery']['placeId']
            pending = self._offer_pending.setdefault(gig, {})
            candidates = []
            for driver in self._offer_outside.get(pickup, []):
                identity = driver['id']
                if self._offer_counts.get(identity, 0) >= 3 or (gig, identity) in self._offer_attempted:
                    continue
                if action['audience'].get('manualLicence') and driver.get('licence') != 'manual':
                    continue
                if action['audience'].get('experienced') and (driver.get('rating', 0) < 4.8 or driver.get('completedGigs', 0) < 50):
                    continue
                free, origin, finishing = origins[identity]
                road = self.roads.get((origin, pickup))
                if origin is None or (origin != pickup and road is None):
                    continue
                transit = 0 if origin == pickup else ceil(road['minutes'] * 1.5) + 30
                arrival = max(self.now + 10, free) + transit
                if arrival - self.now > s.offer_max_eta_minutes or arrival > latest:
                    continue
                finish = self._offer_route(action, arrival)
                if finish is None:
                    continue
                homeward = driver['homePlaceId'] in self._offer_near.get(delivery, set())
                candidates.append(((not finishing, not homeward, arrival, driver.get('drops', 0), identity), identity))
            for _, driver in sorted(candidates)[:min(budget, 3 - len(pending))]:
                schedule = self._offer_schedules.get(gig, action['schedule'])
                # Include a reprice queued in this very batch, without sending it.
                for queued in self._outbox:
                    if queued['type'] == 'reprice' and queued['gigId'] == gig:
                        schedule = queued['schedule']
                fee = next((step['feeCents'] for step in reversed(schedule) if step['at'] <= self.now), None)
                if fee is None:
                    continue
                fee = max(1, (fee * s.offer_fee_bps + 5000) // 10000)
                self._outbox.append(dict(type='offer', gigId=gig, driverId=driver, feeCents=fee))
                pending[driver] = self.now + 11
                self._offer_counts[driver] = self._offer_counts.get(driver, 0) + 1
                self._offer_attempted.add((gig, driver))
                budget -= 1
