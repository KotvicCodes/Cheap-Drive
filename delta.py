"""Opt-in Delta experiments; supported Gamma remains unchanged."""
from __future__ import annotations

from dataclasses import replace
import re

from gamma import GammaCoreDesk, GammaSettings
from delta_b1 import DeltaB1Mixin, validate_b1
from gamma_notes import GammaNotesMixin, visit_window
from gamma_pairs import DriverSideMixin, _split_settings
from notes import parse_note
from spread.starter import DAY


_TYPOS = re.compile(r'\b(huoomenna|friay|aikaisiintaan)\b', re.I)
_CORRECTIONS = {'huoomenna': 'huomenna', 'friay': 'Friday', 'aikaisiintaan': 'aikaisintaan'}
_NO_PICKUPS = re.compile(
    r'(^|[;,\n!?]\s*|\.(?!\d)\s*)\s*klo\s+'
    r'(\d{1,2}(?:[.:]\d{2})?)\s+j[aä]lkeen\s+ei\s+en[aä]{2}\s+luovutuksia\b', re.I)


def parse_delta_note(note, arrived_at):
    """Correct only observed whole-word typos and a standalone closing clause."""
    text = note.get('text', '') if isinstance(note, dict) else note or ''
    def correct_word(match):
        # Do not turn an unrecognized negative aside into a competing date.
        if re.search(r'\b(?:not|ei|inte)\s*$', text[:match.start()], re.I):
            return match[0]
        return _CORRECTIONS[match[0].lower()]
    text = _TYPOS.sub(correct_word, text)
    text = _NO_PICKUPS.sub(lambda match: match[1] + 'Nouto ennen klo ' + match[2], text)
    return parse_note(text, arrived_at)


def rescue_window(place, kind, facts, low, high):
    """Prefer original promises; only dealer rescue may relax absolute ends.

    A future absolute end can already be unreachable after the site closes.
    Search the requested horizon if its strict intersection has no open minute.
    Readiness, recurring calendars and private booked slots remain constraints.
    """
    window = visit_window(place, kind, facts, low, high)
    if window is not None or place.get('privateAddress'):
        return window
    relaxed_place = {**place, 'window': {**place['window'], 'to': high}}
    relaxed_facts = replace(facts, **{'pickup_deadline' if kind == 'pickup' else 'deadline': None})
    return visit_window(relaxed_place, kind, relaxed_facts, low, high)


class DeltaNotesMixin(GammaNotesMixin):
    def __init__(self, *args, delta_note_fixes=0, delta_rescue_windows=0, **kwargs):
        for name, value in (('delta_note_fixes', delta_note_fixes),
                            ('delta_rescue_windows', delta_rescue_windows)):
            if type(value) is not int or value not in (0, 1):
                raise ValueError(name + ' must be 0 or 1')
        self.delta_note_fixes = delta_note_fixes
        self.delta_rescue_windows = delta_rescue_windows
        super().__init__(*args, **kwargs)

    def note_facts(self, request):
        if not self.delta_note_fixes:
            return super().note_facts(request)
        note = request.get('note')
        text = note.get('text', '') if note else ''
        key = (request['id'], request['arrivedAt'], text)
        if key not in self._note_cache:
            self._note_cache[key] = parse_delta_note(note, request['arrivedAt'])
        return self._note_cache[key]

    def _post_windows(self, order, legs, facts, retry):
        if not self.delta_rescue_windows:
            return super()._post_windows(order, legs, facts, retry)
        # Retain Gamma's sequential route construction, using the repaired
        # window intersection for this experiment only. Fee policy is unchanged.
        stops, minute, previous = [], self.now, None
        horizon = max(order['deadline'], self.now + 14 * DAY)
        for index in legs:
            leg = order['legs'][index]
            if previous is not None and previous != leg['pickup']['placeId']:
                minute += self.roads[previous, leg['pickup']['placeId']]['minutes']
            start = max(minute + (30 if retry.plates or facts.plates else 0), retry.pickup_from)
            travel = self.roads[leg['pickup']['placeId'], leg['delivery']['placeId']]['minutes']
            charge = 40 if self._needs_charging(leg) else 0
            while start <= horizon:
                pickup = rescue_window(leg['pickup'], 'pickup', facts, start, horizon)
                if pickup is None:
                    return None
                earliest = pickup[0] + travel + charge
                deadline = min(order['deadline'], facts.deadline if facts.deadline is not None else order['deadline'])
                delivery = rescue_window(leg['delivery'], 'delivery', facts, earliest, deadline)
                if delivery is None:
                    delivery = rescue_window(leg['delivery'], 'delivery', facts, earliest, horizon)
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
            minute, previous = delivery[0], leg['delivery']['placeId']
        return stops


def make_delta(world, level, now, journal, *, delta_note_fixes=0, delta_rescue_windows=0,
               delta_b1="off", **settings):
    class DeltaDesk(DeltaB1Mixin, DriverSideMixin, DeltaNotesMixin, GammaCoreDesk):
        passive_wake_events = frozenset() if settings.get('pairs', 0) else GammaCoreDesk.passive_wake_events

        def fees_for(self, order, cars):
            return self._note_fees(order, cars, super().fees_for)

        def repost(self, gig_id):
            action = self.posts.get(gig_id)
            if action and len({stop['orderId'] for stop in action['stops']}) == 1:
                return GammaNotesMixin.repost(self, gig_id)
            return super().repost(gig_id)

    base, driver = _split_settings(GammaSettings, settings)
    validate_b1(delta_b1, base, driver, note_fixes=delta_note_fixes, rescue_windows=delta_rescue_windows)
    return DeltaDesk(world, level, now, journal, base, driver_settings=driver,
                     delta_note_fixes=delta_note_fixes, delta_rescue_windows=delta_rescue_windows,
                     delta_b1=delta_b1)
