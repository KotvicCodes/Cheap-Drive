"""Opt-in admission experiments; public roster counts are not availability."""
from dataclasses import dataclass, replace

from .gamma_notes import visit_window
from .notes import NoteFacts
from spread.starter import DAY


@dataclass(frozen=True)
class DeltaIntakeSettings:
    delta_guarded_trade_ins: int = 0
    delta_trade_max_drive_minutes: int = 540
    delta_trade_max_leg_km: int = 500
    delta_trade_open_cap: int = 2
    delta_trade_opening_fee_bps: int = 10000
    delta_corridor_open_cap: int = 0
    delta_relaxed_slack_minutes: int = 0
    delta_relaxed_slack_max_km: int = 150
    delta_intake_max_backlog: int = 20
    delta_intake_min_roster: int = 0

    def __post_init__(self):
        for name, value in vars(self).items():
            if type(value) is not int or value < 0:
                raise ValueError(name + ' must be a nonnegative integer')
        if self.delta_guarded_trade_ins not in (0, 1):
            raise ValueError('delta_guarded_trade_ins must be 0 or 1')
        if not 0 < self.delta_trade_max_drive_minutes <= 720:
            raise ValueError('delta_trade_max_drive_minutes must be in 1..720')
        if not 0 < self.delta_trade_max_leg_km <= 500:
            raise ValueError('delta_trade_max_leg_km must be in 1..500')
        if not self.delta_trade_open_cap or not self.delta_trade_opening_fee_bps:
            raise ValueError('trade-in cap and opening fee must be positive')
        if self.delta_relaxed_slack_minutes and self.delta_relaxed_slack_minutes < 240:
            raise ValueError('delta_relaxed_slack_minutes must be zero or at least 240')


class DeltaIntakeMixin:
    def __init__(self, *args, intake_settings=DeltaIntakeSettings(), **kwargs):
        self.intake_settings = intake_settings
        super().__init__(*args, **kwargs)
        if intake_settings.delta_guarded_trade_ins and not self.settings.trade_ins:
            raise ValueError('delta_guarded_trade_ins requires trade_ins=1')
        if (intake_settings.delta_guarded_trade_ins and
                intake_settings.delta_trade_opening_fee_bps > self.settings.fee_cap_bps):
            raise ValueError('delta_trade_opening_fee_bps exceeds fee_cap_bps')

    def _guarded_trade(self, request):
        return self.intake_settings.delta_guarded_trade_ins and len(request['legs']) == 2

    def _intake_headroom(self):
        s = self.intake_settings
        return (len(self.orders_without_driver()) <= s.delta_intake_max_backlog and
                (not s.delta_intake_min_roster or
                 self.supply_roster_size is not None and
                 self.supply_roster_size >= s.delta_intake_min_roster))

    def eligible_options(self, request, km, trust):
        s = self.intake_settings
        if s.delta_guarded_trade_ins and len(request['legs']) > 2:
            return [], 'guarded trade-in route'
        if self._guarded_trade(request):
            first, second = request['legs']
            roads = [self.roads[leg['pickup']['placeId'], leg['delivery']['placeId']]
                     for leg in request['legs']]
            round_trip = (first['delivery']['placeId'] == second['pickup']['placeId'] and
                          first['pickup']['placeId'] == second['delivery']['placeId'] and
                          first['delivery']['privateAddress'] and second['pickup']['privateAddress'])
            if (not round_trip or sum(r['minutes'] for r in roads) > s.delta_trade_max_drive_minutes or
                    max(r['km'] for r in roads) > s.delta_trade_max_leg_km):
                return [], 'guarded trade-in route'
            trades = sum(len(self.orders[i]['legs']) > 1 for i in self.orders_without_driver())
            if trades >= s.delta_trade_open_cap or not self._intake_headroom():
                return [], 'guarded trade-in capacity'
            # Total round-trip km is not a single long corridor. The dedicated
            # driving gate above controls it, while normal slack/premium rules apply.
            return super().eligible_options(request, min(km, self.settings.max_km), trust)
        options, reason = super().eligible_options(request, km, trust)
        relax_slack = (reason == 'no option leaves a driver enough time' and
                       s.delta_relaxed_slack_minutes and len(request['legs']) == 1 and
                       km <= s.delta_relaxed_slack_max_km and not self.is_premium(request) and
                       not any(request['legs'][0][kind]['privateAddress']
                               for kind in ('pickup', 'delivery')) and self._intake_headroom())
        if (reason == 'long route capacity' and s.delta_corridor_open_cap and
                self._intake_headroom() and
                len(self.long_orders_without_driver()) < s.delta_corridor_open_cap) or relax_slack:
            # Reuse all existing option/slack/brake rules. No state survives this
            # synchronous admission decision; the model's settings stay frozen.
            original = self.settings
            try:
                changes = (dict(min_slack_minutes=min(original.min_slack_minutes, s.delta_relaxed_slack_minutes),
                                same_day_min_slack_minutes=min(original.same_day_min_slack_minutes,
                                                              s.delta_relaxed_slack_minutes))
                           if relax_slack else dict(long_open_cap=s.delta_corridor_open_cap))
                self.settings = replace(original, **changes)
                return super().eligible_options(request, km, trust)
            finally:
                self.settings = original
        return options, reason

    def opening_fee_for(self, order):
        fee = super().opening_fee_for(order)
        if self._guarded_trade(order):
            fee = max(fee, self.intake_settings.delta_trade_opening_fee_bps)
        return fee

    @staticmethod
    def _trade_facts(facts, index):
        # The note describes the dealer's outgoing car/customer delivery.
        # The return car retains its own site calendar and private slot.
        return facts if index == 0 else NoteFacts()

    def _trade_start(self, leg):
        travel = self.roads[leg['pickup']['placeId'], leg['delivery']['placeId']]['minutes']
        charge = 40 if self._needs_charging(leg) else 0
        return (leg['delivery']['window']['from'] - travel - charge) // DAY * DAY

    def _latest_note_route(self, request, deadline, *, floor=None, legs=None):
        if not self._guarded_trade(request):
            return super()._latest_note_route(request, deadline, floor=floor, legs=legs)
        indices = list(range(2)) if legs is None else list(legs)
        facts = self.note_facts(request)
        floor = request['respondBy'] if floor is None else floor
        minute, pickup = deadline, None
        for index in reversed(indices):
            leg, scoped = request['legs'][index], self._trade_facts(facts, index)
            delivery = visit_window(leg['delivery'], 'delivery', scoped, floor, minute, latest=True)
            if delivery is None:
                return None
            travel = self.roads[leg['pickup']['placeId'], leg['delivery']['placeId']]['minutes']
            charge = 40 if self._needs_charging(leg) else 0
            if index == 1 and indices == [0, 1]:
                # Shared visit: the old pickup follows the outgoing delivery;
                # its independent private slot cannot invalidate that visit.
                minute = delivery[1] - travel - charge
                continue
            low = max(floor, self._trade_start(leg)) if index == 0 else floor
            window = visit_window(leg['pickup'], 'pickup', scoped, low,
                                  delivery[1] - travel - charge, latest=True)
            if window is None:
                return None
            pickup = window[1]
            minute = pickup - (30 if scoped.plates else 0)
        return (pickup, minute) if pickup is not None and minute >= floor else None

    def _post_windows(self, order, legs, facts, retry):
        if not self._guarded_trade(order):
            return super()._post_windows(order, legs, facts, retry)
        stops, minute = [], self.now
        horizon = max(order['deadline'], self.now + 14 * DAY)
        for index in legs:
            leg, scoped = order['legs'][index], self._trade_facts(facts, index)
            plates = bool(retry.plates or (index == 0 and scoped.plates))
            charge = 40 if self._needs_charging(leg) else 0
            travel = self.roads[leg['pickup']['placeId'], leg['delivery']['placeId']]['minutes']
            shared = index == 1 and legs == [0, 1]
            start = max(minute + (30 if plates else 0), retry.pickup_from,
                        self._trade_start(leg) if index == 0 else 0)
            if shared:
                pickup = (start, horizon)
            else:
                pickup = self._dispatch_window(leg['pickup'], 'pickup', scoped, start, horizon)
            if pickup is None:
                return None
            earliest = pickup[0] + travel + charge
            delivery = self._dispatch_window(leg['delivery'], 'delivery', scoped, earliest, order['deadline'])
            if delivery is None:
                delivery = self._dispatch_window(leg['delivery'], 'delivery', scoped, earliest, horizon)
            if delivery is None or delivery[1] - travel - charge < pickup[0]:
                return None
            first = dict(orderId=order['id'], leg=index, kind='pickup',
                         withPlates=plates, withCharging=bool(charge))
            if not shared:
                first['window'] = {'from': pickup[0], 'to': min(pickup[1], delivery[1] - travel - charge)}
            stops.extend([first, dict(orderId=order['id'], leg=index, kind='delivery',
                                      window={'from': delivery[0], 'to': delivery[1]})])
            minute = delivery[0]
        if legs == [0, 1]:
            # A legal outgoing appointment must also leave time to return the
            # old car. Tighten both earlier stops from the final delivery.
            durations = [self.roads[leg['pickup']['placeId'], leg['delivery']['placeId']]['minutes'] +
                         (40 if self._needs_charging(leg) else 0) for leg in order['legs']]
            delivery_end = min(stops[1]['window']['to'], stops[3]['window']['to'] - durations[1])
            pickup_end = min(stops[0]['window']['to'], delivery_end - durations[0])
            if (delivery_end < stops[1]['window']['from'] or
                    pickup_end < stops[0]['window']['from']):
                return None
            stops[1]['window']['to'] = delivery_end
            stops[0]['window']['to'] = pickup_end
        return stops
