"""Opt-in Delta experiments; supported Gamma remains unchanged."""
from __future__ import annotations

from dataclasses import replace
import re

from .gamma import GammaCoreDesk, GammaSettings
from .delta_b1 import DeltaB1Mixin, validate_b1
from .delta_lanes import DeltaLanesMixin, validate_lanes
from .delta_option_spread import DeltaOptionSpreadMixin, validate_option_spread
from .delta_safe_quote import DeltaSafeQuoteMixin
from .delta_safe_target import DeltaSafeTargetMixin
from .delta_segmented_targets import DeltaSegmentedTargetsMixin
from .delta_service import DeltaServiceMixin
from .epsilon_breaker import EpsilonBreakerMixin
from .delta_intake import DeltaIntakeMixin, DeltaIntakeSettings
from .delta_pair_quote import DeltaPairQuoteMixin
from .delta_pair_guard import DeltaPairGuardMixin
from .delta_reference_floor import DeltaReferenceFloorMixin
from .delta_readiness_fee import DeltaReadinessFeeMixin
from .delta_urgent_fee import DeltaUrgentFeeMixin
from .delta_note_urgency import DeltaNoteUrgencyMixin
from .gamma_notes import GammaNotesMixin, _daily_window, visit_window
from .gamma_pairs import DriverSideMixin, _split_settings
from .notes import NoteFacts, parse_note
from spread.starter import DAY


_TYPOS = re.compile(r'\b(huoomenna|friay|aikaisiintaan)\b', re.I)
_CORRECTIONS = {'huoomenna': 'huomenna', 'friay': 'Friday', 'aikaisiintaan': 'aikaisintaan'}
PAIRING_PROFILES = {'off': None, 'regional': (60, 480), 'extended': (90, 720)}
_NO_PICKUPS = re.compile(
    r'(^|[;,\n!?]\s*|\.(?!\d)\s*)\s*klo\s+'
    r'(\d{1,2}(?:[.:]\d{2})?)\s+j[aä]lkeen\s+ei\s+en[aä]{2}\s+luovutuksia\b', re.I)
_EN_NO_PICKUPS = re.compile(
    r'(^|[;,\n!?]\s*|\.(?!\d)\s*)\s*no\s+(?:pickups?|collections?)\s+after\s+'
    r'(\d{1,2}[.:]\d{2})(?![\w:])', re.I)
_FI_CLOSED_AFTER = re.compile(
    r'\bkiinni\s+(?:klo\s+)?(\d{1,2}[.:]\d{2})\s+j[aä]lkeen\b', re.I)


def parse_delta_note(note, arrived_at, *, english_pickup_close=False, finnish_close_fixes=False, weekday_saturday=False):
    """Correct only observed whole-word typos and a standalone closing clause."""
    text = note.get('text', '') if isinstance(note, dict) else note or ''
    def correct_word(match):
        # Do not turn an unrecognized negative aside into a competing date.
        if re.search(r'\b(?:not|ei|inte)\s*$', text[:match.start()], re.I):
            return match[0]
        return _CORRECTIONS[match[0].lower()]
    text = _TYPOS.sub(correct_word, text)
    text = _NO_PICKUPS.sub(lambda match: match[1] + 'Nouto ennen klo ' + match[2], text)
    if english_pickup_close:
        text = _EN_NO_PICKUPS.sub(lambda match: match[1] + 'Collect before ' + match[2], text)
    if finnish_close_fixes:
        text = _FI_CLOSED_AFTER.sub(lambda match: 'kiinni klo ' + match[1], text)
    return parse_note(text, arrived_at, weekday_saturday=weekday_saturday)


def rescue_window(place, kind, facts, low, high, *, private_delivery=False):
    """Prefer original promises; keep private pickups inside their booked slot.

    A future absolute end can already be unreachable after the site closes.
    Search the requested horizon if its strict intersection has no open minute.
    Readiness, recurring calendars and private pickup slots remain constraints.
    """
    window = visit_window(place, kind, facts, low, high)
    if window is not None or (place.get('privateAddress') and
                              (kind == 'pickup' or not private_delivery)):
        return window
    relaxed_place = {**place, 'window': {**place['window'], 'to': high}}
    relaxed_facts = replace(facts, **{'pickup_deadline' if kind == 'pickup' else 'deadline': None})
    return visit_window(relaxed_place, kind, relaxed_facts, low, high)


def wide_visit_window(place, kind, facts, low, high):
    """Keep the first feasible span, bridging only server-enforced closures.

    The server checks stated site hours throughout a multi-day stop window.
    It does not check parsed note hours, so stop before the first stated-open
    minute excluded by a recurring note. A single API window cannot encode
    that hole. Absolute bounds, readiness and private slots remain strict.
    """
    first = visit_window(place, kind, facts, low, high)
    if first is None:
        return None
    last = visit_window(place, kind, facts, low, high, latest=True)
    low, high = first[0], last[1]
    end = first[1]
    for day in range(low // DAY, high // DAY + 1):
        stated = _daily_window(place, kind, NoteFacts(), day)
        if stated is None:
            continue
        start, close = max(low, stated[0]), min(high, stated[1])
        if start > close:
            continue
        allowed = _daily_window(place, kind, facts, day)
        if allowed is None or allowed[0] > start:
            break
        end = min(close, allowed[1])
        if end < close:
            break
    return low, end


class DeltaNotesMixin(GammaNotesMixin):
    def __init__(self, *args, delta_note_fixes=0, delta_rescue_windows=0,
                 delta_ev_rule=0, delta_private_delivery_rescue=0,
                 delta_wide_windows=0, delta_english_pickup_close=0,
                 delta_wide_pickup_buffer_minutes=0, delta_finnish_close_fixes=0,
                 delta_note_weekday_saturday=0, **kwargs):
        for name, value in (('delta_note_fixes', delta_note_fixes),
                            ('delta_rescue_windows', delta_rescue_windows),
                            ('delta_ev_rule', delta_ev_rule),
                            ('delta_private_delivery_rescue', delta_private_delivery_rescue),
                            ('delta_wide_windows', delta_wide_windows),
                            ('delta_english_pickup_close', delta_english_pickup_close),
                            ('delta_finnish_close_fixes', delta_finnish_close_fixes),
                            ('delta_note_weekday_saturday', delta_note_weekday_saturday)):
            if type(value) is not int or value not in (0, 1):
                raise ValueError(name + ' must be 0 or 1')
        self.delta_note_fixes = delta_note_fixes
        self.delta_rescue_windows = delta_rescue_windows
        self.delta_ev_rule = delta_ev_rule
        self.delta_private_delivery_rescue = delta_private_delivery_rescue
        self.delta_wide_windows = delta_wide_windows
        self.delta_english_pickup_close = delta_english_pickup_close
        self.delta_finnish_close_fixes = delta_finnish_close_fixes
        self.delta_note_weekday_saturday = delta_note_weekday_saturday
        if type(delta_wide_pickup_buffer_minutes) is not int or delta_wide_pickup_buffer_minutes < 0:
            raise ValueError('delta_wide_pickup_buffer_minutes must be a nonnegative integer')
        self.delta_wide_pickup_buffer_minutes = delta_wide_pickup_buffer_minutes
        super().__init__(*args, **kwargs)

    def _needs_charging(self, leg):
        low_battery = super()._needs_charging(leg)
        if not self.delta_ev_rule or not low_battery:
            return low_battery
        # Rules §5.3: a low-charge EV needs charging only over 200 road km.
        return self.roads[leg['pickup']['placeId'], leg['delivery']['placeId']]['km'] > 200

    def note_facts(self, request):
        if not (self.delta_note_fixes or self.delta_english_pickup_close or self.delta_finnish_close_fixes or self.delta_note_weekday_saturday):
            return super().note_facts(request)
        note = request.get('note')
        text = note.get('text', '') if note else ''
        key = (request['id'], request['arrivedAt'], text)
        if key not in self._note_cache:
            if self.delta_note_fixes:
                facts = parse_delta_note(note, request['arrivedAt'],
                                         english_pickup_close=bool(self.delta_english_pickup_close),
                                         finnish_close_fixes=bool(self.delta_finnish_close_fixes),
                                         weekday_saturday=bool(self.delta_note_weekday_saturday))
            else:
                corrected = text
                if self.delta_english_pickup_close:
                    corrected = _EN_NO_PICKUPS.sub(lambda m: m[1] + 'Collect before ' + m[2], corrected)
                if self.delta_finnish_close_fixes:
                    corrected = _FI_CLOSED_AFTER.sub(lambda m: 'kiinni klo ' + m[1], corrected)
                facts = parse_note(corrected, request['arrivedAt'],
                                   weekday_saturday=bool(self.delta_note_weekday_saturday))
            self._note_cache[key] = facts
        return self._note_cache[key]

    def _dispatch_window(self, place, kind, facts, low, high):
        if self.delta_wide_windows and kind == 'pickup' and place.get('privateAddress'):
            return visit_window(place, kind, facts, low, high)
        if self.delta_rescue_windows or (self.delta_private_delivery_rescue and place.get('privateAddress')):
            return rescue_window(place, kind, facts, low, high,
                                 private_delivery=bool(self.delta_private_delivery_rescue))
        return visit_window(place, kind, facts, low, high, rescue=True)

    def _post_windows(self, order, legs, facts, retry):
        if self.delta_wide_windows:
            stops = self._wide_post_windows(order, legs, facts, retry)
            if stops is not None:
                return stops
            # Already impossible promises retain the existing rescue policy;
            # the widening experiment itself never relaxes an absolute end.
        if not (self.delta_rescue_windows or self.delta_private_delivery_rescue or self.delta_wide_windows):
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
                pickup = self._dispatch_window(leg['pickup'], 'pickup', facts, start, horizon)
                if pickup is None:
                    return None
                earliest = pickup[0] + travel + charge
                deadline = min(order['deadline'], facts.deadline if facts.deadline is not None else order['deadline'])
                delivery = self._dispatch_window(leg['delivery'], 'delivery', facts, earliest, deadline)
                if delivery is None:
                    delivery = self._dispatch_window(leg['delivery'], 'delivery', facts, earliest, horizon)
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

    def _wide_post_windows(self, order, legs, facts, retry):
        stops, minute, previous = [], self.now, None
        deadline = min(order['deadline'], facts.deadline if facts.deadline is not None else order['deadline'])
        for index in legs:
            leg = order['legs'][index]
            if previous is not None and previous != leg['pickup']['placeId']:
                minute += self.roads[previous, leg['pickup']['placeId']]['minutes']
            start = max(minute + (30 if retry.plates or facts.plates else 0), retry.pickup_from)
            travel = self.roads[leg['pickup']['placeId'], leg['delivery']['placeId']]['minutes']
            charge = 40 if self._needs_charging(leg) else 0
            while start <= deadline:
                pickup = wide_visit_window(leg['pickup'], 'pickup', facts, start, deadline)
                if pickup is None:
                    return None
                delivery = wide_visit_window(leg['delivery'], 'delivery', facts,
                                             pickup[0] + travel + charge, deadline)
                if delivery is not None:
                    end = min(pickup[1], delivery[1] - travel - charge)
                    if end >= pickup[0]:
                        buffered = min(pickup[1], delivery[1] - travel - charge -
                                       self.delta_wide_pickup_buffer_minutes)
                        if buffered >= pickup[0]:
                            end = buffered
                        end = visit_window(leg['pickup'], 'pickup', facts,
                                           pickup[0], end, latest=True)[1]
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
               delta_ev_rule=0, delta_private_delivery_rescue=0, delta_wide_windows=0,
               delta_english_pickup_close=0,
               delta_finnish_close_fixes=0, delta_note_weekday_saturday=0,
               delta_wide_pickup_buffer_minutes=0,
               delta_b1="off", delta_lanes="off", delta_option_spread="off",
               delta_pairing="off", delta_pair_same_audience=0, delta_pair_quote_bps=0,
               delta_pair_self_roads=0,
               delta_pair_max_wait_minutes=0, delta_pair_min_slack_minutes=0,
               delta_reference_quote_floor_bps=0, delta_readiness_early_cut_bps=0,
               delta_urgent_fee_memory=0, delta_note_urgency=0,
               delta_safe_target_bps=0, delta_safe_target_min_slack_minutes=720,
               delta_safe_target_max_backlog=15,
               delta_segmented_targets=0, win_target_safe_bps=5500,
               delta_safe_quote_bps=0, delta_safe_quote_min_slack_minutes=720,
               delta_safe_quote_max_backlog=15,
               delta_service_brake=0,
               delta_service_horizon_minutes=360, delta_service_soft_orders=3,
               delta_service_hard_orders=6, delta_service_target_bps=3000,
               delta_service_hard_target_bps=2400,
               epsilon_breaker=0, epsilon_breaker_on_time_bps=9400,
               epsilon_breaker_min_orders=20, epsilon_breaker_window_minutes=0,
               epsilon_breaker_risk_orders=3, epsilon_breaker_risk_horizon_minutes=360,
               epsilon_breaker_restore_pairing=1, **settings):
    if not isinstance(delta_pairing, str) or delta_pairing not in PAIRING_PROFILES:
        raise ValueError('delta_pairing must be off, regional or extended')
    if type(delta_pair_same_audience) is not int or delta_pair_same_audience not in (0, 1):
        raise ValueError('delta_pair_same_audience must be 0 or 1')
    if type(delta_pair_self_roads) is not int or delta_pair_self_roads not in (0, 1):
        raise ValueError('delta_pair_self_roads must be 0 or 1')
    intake = DeltaIntakeSettings(**{k: settings.pop(k) for k in list(settings)
                                  if k in DeltaIntakeSettings.__dataclass_fields__})
    class DeltaDesk(EpsilonBreakerMixin, DeltaSegmentedTargetsMixin, DeltaSafeTargetMixin, DeltaSafeQuoteMixin, DeltaIntakeMixin, DeltaReferenceFloorMixin, DeltaReadinessFeeMixin, DeltaUrgentFeeMixin, DeltaNoteUrgencyMixin, DeltaServiceMixin, DeltaPairQuoteMixin, DeltaOptionSpreadMixin,
                    DeltaB1Mixin, DeltaLanesMixin,
                    DeltaPairGuardMixin, DriverSideMixin, DeltaNotesMixin, GammaCoreDesk):
        passive_wake_events = frozenset() if settings.get('pairs', 0) else GammaCoreDesk.passive_wake_events

        def fees_for(self, order, cars):
            schedule = self._note_fees(order, cars, super().fees_for)
            schedule = self._note_urgency_schedule(order, cars, schedule)
            schedule = self._urgent_memory_schedule(order, cars, schedule)
            return self._readiness_fee_schedule(order, cars, schedule)

        def _plan(self, first, second):
            if delta_pair_same_audience:
                audiences = [self._single_action(order)['audience'] for order in (first, second)]
                if audiences[0] != audiences[1]:
                    return None, 'audience_mismatch'
            return super()._plan(first, second)

        def _road(self, start, end):
            if delta_pair_self_roads and start == end and (start, end) in self.roads:
                return self.roads[start, end]
            return super()._road(start, end)

        def repost(self, gig_id):
            action = self.posts.get(gig_id)
            if action and len({stop['orderId'] for stop in action['stops']}) == 1:
                return GammaNotesMixin.repost(self, gig_id)
            return super().repost(gig_id)

    base, driver = _split_settings(GammaSettings, settings)
    validate_option_spread(delta_option_spread, base, driver, b1=delta_b1, lanes=delta_lanes,
                           note_fixes=delta_note_fixes, rescue_windows=delta_rescue_windows)
    validate_b1(delta_b1, base, driver, note_fixes=delta_note_fixes, rescue_windows=delta_rescue_windows)
    validate_lanes(delta_lanes, base, driver, b1=delta_b1,
                   note_fixes=delta_note_fixes, rescue_windows=delta_rescue_windows)
    if delta_pairing != 'off':
        # Widen only route search. Keep the established audience, calendars,
        # arrival allowance, deadline spare and timed single-order fallback.
        # Explicitly require pairs rather than silently enabling another policy.
        if not driver.pairs:
            raise ValueError('delta_pairing requires pairs=1')
        transfer, drive = PAIRING_PROFILES[delta_pairing]
        driver = replace(driver, pair_transfer_km=transfer, pair_max_drive_minutes=drive)
    return DeltaDesk(world, level, now, journal, base, driver_settings=driver, intake_settings=intake,
                     epsilon_breaker=epsilon_breaker,
                     epsilon_breaker_on_time_bps=epsilon_breaker_on_time_bps,
                     epsilon_breaker_min_orders=epsilon_breaker_min_orders,
                     epsilon_breaker_window_minutes=epsilon_breaker_window_minutes,
                     epsilon_breaker_risk_orders=epsilon_breaker_risk_orders,
                     epsilon_breaker_risk_horizon_minutes=epsilon_breaker_risk_horizon_minutes,
                     epsilon_breaker_restore_pairing=epsilon_breaker_restore_pairing,
                     delta_note_fixes=delta_note_fixes, delta_rescue_windows=delta_rescue_windows,
                     delta_ev_rule=delta_ev_rule,
                     delta_private_delivery_rescue=delta_private_delivery_rescue,
                     delta_wide_windows=delta_wide_windows,
                     delta_english_pickup_close=delta_english_pickup_close,
                     delta_finnish_close_fixes=delta_finnish_close_fixes,
                     delta_note_weekday_saturday=delta_note_weekday_saturday,
                     delta_wide_pickup_buffer_minutes=delta_wide_pickup_buffer_minutes,
                     delta_pair_quote_bps=delta_pair_quote_bps,
                     delta_pair_max_wait_minutes=delta_pair_max_wait_minutes,
                     delta_pair_min_slack_minutes=delta_pair_min_slack_minutes,
                     delta_reference_quote_floor_bps=delta_reference_quote_floor_bps,
                     delta_readiness_early_cut_bps=delta_readiness_early_cut_bps,
                     delta_urgent_fee_memory=delta_urgent_fee_memory,
                     delta_note_urgency=delta_note_urgency,
                     delta_safe_target_bps=delta_safe_target_bps,
                     delta_safe_target_min_slack_minutes=delta_safe_target_min_slack_minutes,
                     delta_safe_target_max_backlog=delta_safe_target_max_backlog,
                     delta_segmented_targets=delta_segmented_targets,
                     win_target_safe_bps=win_target_safe_bps,
                     delta_safe_quote_bps=delta_safe_quote_bps,
                     delta_safe_quote_min_slack_minutes=delta_safe_quote_min_slack_minutes,
                     delta_safe_quote_max_backlog=delta_safe_quote_max_backlog,
                     delta_service_brake=delta_service_brake,
                     delta_service_horizon_minutes=delta_service_horizon_minutes,
                     delta_service_soft_orders=delta_service_soft_orders,
                     delta_service_hard_orders=delta_service_hard_orders,
                     delta_service_target_bps=delta_service_target_bps,
                     delta_service_hard_target_bps=delta_service_hard_target_bps,
                     delta_b1=delta_b1, delta_lanes=delta_lanes,
                     delta_option_spread=delta_option_spread)
