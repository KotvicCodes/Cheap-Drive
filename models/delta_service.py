"""Default-off intake protection using the remaining pickup opportunity."""
class DeltaServiceMixin:
    def __init__(self, *args, delta_service_brake=0,
                 delta_service_horizon_minutes=360, delta_service_soft_orders=3,
                 delta_service_hard_orders=6, delta_service_target_bps=3000,
                 delta_service_hard_target_bps=2400, **kwargs):
        values = dict(delta_service_brake=delta_service_brake,
                      delta_service_horizon_minutes=delta_service_horizon_minutes,
                      delta_service_soft_orders=delta_service_soft_orders,
                      delta_service_hard_orders=delta_service_hard_orders,
                      delta_service_target_bps=delta_service_target_bps,
                      delta_service_hard_target_bps=delta_service_hard_target_bps)
        for name, value in values.items():
            if type(value) is not int or value < 0:
                raise ValueError(name + ' must be a nonnegative integer')
        if delta_service_brake not in (0, 1):
            raise ValueError('delta_service_brake must be 0 or 1')
        if not 0 < delta_service_soft_orders <= delta_service_hard_orders:
            raise ValueError('service order thresholds must be positive and ordered')
        if not 0 < delta_service_hard_target_bps <= delta_service_target_bps < 10000:
            raise ValueError('service targets must be ordered between 1 and 9999')
        self.delta_service = values
        super().__init__(*args, **kwargs)

    def service_risk_orders(self, *, horizon=None):
        """Count unbooked work whose last legal pickup opportunity is near.

        Derive this from current orders and gigs, so recovery needs no new
        checkpoint fields. Business closures and note bounds can make an
        order urgent well before its absolute lastPickupAt.
        """
        risky = set()
        horizon = self.delta_service['delta_service_horizon_minutes'] if horizon is None else horizon
        for identity in self.orders_without_driver():
            order = self.orders[identity]
            remaining = [i for i in range(len(order['legs']))
                         if order['deliveredAt'][i] is None and
                         self.leg_gigs.get(identity, {}).get(i) not in self.booked]
            request = {**self.requests[identity], 'legs': order['legs']}
            latest = self._latest_note_route(request, order['deadline'],
                                             floor=self.now, legs=remaining)
            if latest is None or min(order['lastPickupAt'], latest[1]) <= self.now + horizon:
                risky.add(identity)
        return risky

    def win_target(self):
        target = super().win_target()
        s = self.delta_service
        if not s['delta_service_brake']:
            return target
        count = len(self.service_risk_orders())
        if count >= s['delta_service_hard_orders']:
            return min(target, s['delta_service_hard_target_bps'])
        if count >= s['delta_service_soft_orders']:
            return min(target, s['delta_service_target_bps'])
        return target
