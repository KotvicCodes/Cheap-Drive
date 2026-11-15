"""Note-aware Gamma variants; the historical Beta and Gamma factories stay intact."""
from __future__ import annotations

from .gamma import GammaCoreDesk, GammaSettings
from .notes import parse_note
from spread.starter import DAY, Retry
from .beta import WARNING


def _daily_window(place, kind, facts, day):
    hours = place['hours']
    if hours is not None:
        if day % 7 not in hours['weekdays']:
            hours = hours['saturday'] if day % 7 == 5 else None
            if hours is None:
                return None
        low, high = hours['opens'], hours['closes']
    else:
        low, high = 0, DAY - 1
    weekdays = getattr(facts, kind + '_weekdays')
    if weekdays is not None and day % 7 not in weekdays:
        return None
    opens, closes = getattr(facts, kind + '_opens'), getattr(facts, kind + '_closes')
    low, high = max(low, opens or 0), min(high, closes if closes is not None else DAY - 1)
    return (day * DAY + low, day * DAY + high) if low <= high else None


def visit_window(place, kind, facts, low, high, *, latest=False, rescue=False):
    """Intersect a real business day, recurring note hours and absolute limits.

    Rescue may move beyond an already expired order window/promise, as the
    official runner permits for overdue orders. Recurring hours never expire.
    """
    low = max(low, place['window']['from'])
    if not rescue or place['window']['to'] >= low:
        high = min(high, place['window']['to'])
    if kind == 'pickup':
        low = max(low, facts.ready_at or 0, facts.released_at or 0)
        limit = facts.pickup_deadline
    else:
        low = max(low, facts.delivery_ready_at or 0)
        limit = facts.deadline
    if limit is not None and (not rescue or limit >= low):
        high = min(high, limit)
    if low > high:
        return None
    days = range(low // DAY, high // DAY + 1)
    if latest:
        days = reversed(days)
    for day in days:
        window = _daily_window(place, kind, facts, day)
        if window is None:
            continue
        start, end = max(low, window[0]), min(high, window[1])
        if start <= end:
            return start, end
    return None


class GammaNotesMixin:
    """Read the note once per text/arrival and use its facts for all planning."""

    def __init__(self, *args, **kwargs):
        self._note_cache = {}
        super().__init__(*args, **kwargs)

    def note_facts(self, request):
        note = request.get('note')
        text = note.get('text', '') if note else ''
        key = (request['id'], request['arrivedAt'], text)
        if key not in self._note_cache:
            self._note_cache[key] = parse_note(note, request['arrivedAt'])
        return self._note_cache[key]

    def _latest_note_route(self, request, deadline, *, floor=None, legs=None):
        facts = self.note_facts(request)
        floor = request['respondBy'] if floor is None else floor
        floor = max(floor, facts.ready_at or 0, facts.released_at or 0)
        minute = min(deadline, facts.deadline if facts.deadline is not None else deadline)
        indices = list(range(len(request['legs']))) if legs is None else list(legs)
        pickup = None
        for position in reversed(range(len(indices))):
            index = indices[position]
            leg = request['legs'][index]
            window = visit_window(leg['delivery'], 'delivery', facts, floor, minute, latest=True)
            if window is None:
                return None
            charge = 40 if self._needs_charging(leg) else 0
            travel = self.roads[leg['pickup']['placeId'], leg['delivery']['placeId']]['minutes']
            window = visit_window(leg['pickup'], 'pickup', facts, floor, window[1] - travel - charge, latest=True)
            if window is None:
                return None
            pickup = window[1]
            minute = pickup - (30 if facts.plates else 0)
            if position:
                previous = request['legs'][indices[position - 1]]['delivery']['placeId']
                current = leg['pickup']['placeId']
                if previous != current:
                    minute -= self.roads[previous, current]['minutes']
        return (pickup, minute) if pickup is not None and minute >= floor else None

    @staticmethod
    def _needs_charging(leg):
        car = leg['car']
        return car['electric'] and car['chargePercent'] is not None and car['chargePercent'] < 30

    def slack(self, request, option):
        facts = self.note_facts(request)
        # A slow option must not turn an explicit Friday promise into Monday.
        if facts.deadline_explicit_day and option['deadline'] // DAY > facts.deadline // DAY:
            return -1
        route = self._latest_note_route(request, option['deadline'])
        if route is None:
            return -1
        return route[1] - max(request['respondBy'], facts.ready_at or 0, facts.released_at or 0)

    def true_last_pickup(self, order, legs=None):
        request = {**self.requests[order['id']], 'legs': order['legs']}
        route = self._latest_note_route(request, order['deadline'], floor=self.now, legs=legs)
        return min(order['lastPickupAt'], route[0]) if route is not None else self.now

    def _note_fees(self, order, cars, fee_builder):
        last = self.true_last_pickup(order)
        effective = {**order, 'lastPickupAt': last}
        schedule = fee_builder(effective, cars)
        if order['id'] in self.urgent or self.level == 1:
            return schedule
        # Short windows must not inherit the starter's one-hour step floor:
        # collapse steps so the configured cap is offered by the true warning.
        cap_at = max(self.now, last - WARNING)
        result = []
        for step in schedule:
            at = max(self.now, min(step['at'], cap_at))
            cents = max(step['feeCents'], result[-1]['feeCents'] if result else 1)
            if result and result[-1]['at'] == at:
                result[-1]['feeCents'] = cents
            else:
                result.append({'at': at, 'feeCents': cents})
        return result

    def fees_for(self, order, cars):
        return self._note_fees(order, cars, super().fees_for)

    def _post_windows(self, order, legs, facts, retry):
        stops, minute, previous = [], self.now, None
        # A booked order still needs a driver after a missed promise. Keep its
        # physical restrictions when rolling forward into the rescue horizon.
        horizon = max(order['deadline'], self.now + 14 * DAY)
        for index in legs:
            leg = order['legs'][index]
            if previous is not None and previous != leg['pickup']['placeId']:
                minute += self.roads[previous, leg['pickup']['placeId']]['minutes']
            start = max(minute + (30 if retry.plates or facts.plates else 0), retry.pickup_from)
            travel = self.roads[leg['pickup']['placeId'], leg['delivery']['placeId']]['minutes']
            charge = 40 if self._needs_charging(leg) else 0
            while start <= horizon:
                pickup = visit_window(leg['pickup'], 'pickup', facts, start, horizon, rescue=True)
                if pickup is None:
                    return None
                earliest = pickup[0] + travel + charge
                # Prefer delivery by the real promise. If it is already
                # impossible, a late delivery obeys the business calendar.
                deadline = min(order['deadline'], facts.deadline if facts.deadline is not None else order['deadline'])
                delivery = visit_window(leg['delivery'], 'delivery', facts, earliest, deadline, rescue=True)
                if delivery is None:
                    delivery = visit_window(leg['delivery'], 'delivery', facts, earliest, horizon, rescue=True)
                if delivery is not None:
                    end = min(pickup[1], delivery[1] - travel - charge)
                    if end >= pickup[0]:
                        break
                start = pickup[1] + 1
            else:
                return None
            stops.extend([
                {'orderId': order['id'], 'leg': index, 'kind': 'pickup',
                 'withPlates': retry.plates or facts.plates, 'withCharging': bool(charge),
                 'window': {'from': pickup[0], 'to': end}},
                {'orderId': order['id'], 'leg': index, 'kind': 'delivery',
                 'window': {'from': delivery[0], 'to': delivery[1]}},
            ])
            minute = delivery[0]
            previous = leg['delivery']['placeId']
        return stops

    def post(self, order, legs, retry=Retry()):
        facts = self.note_facts(self.requests[order['id']])
        stops = self._post_windows(order, legs, facts, retry)
        if stops is None:
            self.journal.record('gamma_note_no_window', at=self.now, orderId=order['id'], legs=legs)
            return
        audience = {'experienced': any(leg['car']['premium'] for leg in order['legs']),
                    'manualLicence': retry.manual_licence or facts.manual}
        self.outbox.append({'type': 'post', 'stops': stops, 'audience': audience,
                            'schedule': self.fees_for(order, len(legs))})
        if len(legs) > 1:
            # Preserve the starter's API-driven split when a combined trade-in
            # exceeds the two-car drive limit.
            self.send()
            if not self.gigs_of(order['id']):
                for leg in legs:
                    self.post(order, [leg], retry)

    def repost(self, gig_id):
        action = self.posts.get(gig_id)
        if action is None:
            return
        own = [stop for stop in action['stops']
               if self.leg_gigs.get(stop['orderId'], {}).get(stop['leg']) == gig_id]
        if not own:
            return
        order = self.orders.get(own[0]['orderId'])
        if order is None:
            return
        legs = list(dict.fromkeys(stop['leg'] for stop in own))
        for leg in legs:
            self.leg_gigs.get(order['id'], {}).pop(leg, None)
        # Closing is inclusive for a first visit, but an expired window must
        # never be reposted as the same zero-width [close, close] window.
        retry = Retry(self.now + 1, action['audience']['manualLicence'],
                      any(stop.get('withPlates') for stop in own))
        self.post(order, legs, retry)


class GammaNotesDesk(GammaNotesMixin, GammaCoreDesk):
    passive_wake_events = GammaCoreDesk.passive_wake_events


def make_gamma_notes(world, level, now, journal, **settings):
    return GammaNotesDesk(world, level, now, journal, GammaSettings(**settings))


def make_gamma_notes_pairs(world, level, now, journal, **settings):
    from .gamma_pairs import DriverSideMixin, _split_settings

    class GammaNotesPairsDesk(DriverSideMixin, GammaNotesMixin, GammaCoreDesk):
        passive_wake_events = frozenset() if settings.get('pairs', 0) else GammaCoreDesk.passive_wake_events

        def fees_for(self, order, cars):
            # The outer driver mixin owns the selected ramp/review shape; pass
            # its builder an effective pickup and then enforce the true cap.
            return self._note_fees(order, cars, super().fees_for)

        def repost(self, gig_id):
            action = self.posts.get(gig_id)
            if action and len({s['orderId'] for s in action['stops']}) == 1:
                return GammaNotesMixin.repost(self, gig_id)
            return super().repost(gig_id)

    base, driver = _split_settings(GammaSettings, settings)
    return GammaNotesPairsDesk(world, level, now, journal, base, driver_settings=driver)
