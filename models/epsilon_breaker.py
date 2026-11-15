"""Default-off, week-long return to conservative intake after realized lateness."""
from dataclasses import replace


class EpsilonBreakerMixin:
    def __init__(self, *args, epsilon_breaker=0, epsilon_breaker_on_time_bps=9400,
                 epsilon_breaker_min_orders=20, **kwargs):
        if type(epsilon_breaker) is not int or epsilon_breaker not in (0, 1):
            raise ValueError('epsilon_breaker must be 0 or 1')
        if (type(epsilon_breaker_on_time_bps) is not int or
                not 0 < epsilon_breaker_on_time_bps <= 10000):
            raise ValueError('epsilon_breaker_on_time_bps must be in 1..10000')
        if type(epsilon_breaker_min_orders) is not int or epsilon_breaker_min_orders < 1:
            raise ValueError('epsilon_breaker_min_orders must be positive')
        self.epsilon_breaker = epsilon_breaker
        self.epsilon_breaker_on_time_bps = epsilon_breaker_on_time_bps
        self.epsilon_breaker_min_orders = epsilon_breaker_min_orders
        self.epsilon_breaker_active = False
        self.epsilon_breaker_at = None
        # One outcome per order: True is fully delivered on time, False is
        # already late (including an overdue order not yet fully delivered).
        self.epsilon_breaker_outcomes = {}
        super().__init__(*args, **kwargs)

    def apply_epsilon_breaker(self):
        """Also called after checkpoint restoration; never alters existing gigs."""
        if not (self.epsilon_breaker and self.epsilon_breaker_active):
            return
        self.settings = replace(self.settings, win_target_bps=min(self.settings.win_target_bps, 4200),
                                short_km=45, short_bps=9200, long_markup_bps=10000,
                                trade_ins=0)
        self.intake_settings = replace(self.intake_settings, delta_relaxed_slack_minutes=0,
                                       delta_corridor_open_cap=0)
        # Keep guarded trade routing/fees for previously accepted two-leg work.
        # trade_ins=0 prevents any new trade admission through Gamma's gate.

    def observe_history(self, event):
        super().observe_history(event)
        if not self.epsilon_breaker:
            return
        kind, identity = event['kind'], event.get('orderId')
        outcomes = self.epsilon_breaker_outcomes
        if kind == 'delivered' and identity in self.orders:
            order = self.orders[identity]
            if event['at'] > order['deadline']:
                outcomes[identity] = False
            elif all(at is not None or leg == event['leg']
                     for leg, at in enumerate(order['deliveredAt'])):
                outcomes.setdefault(identity, True)
        elif kind == 'ledger' and event['line']['kind'] == 'late_refund':
            identity = event['line'].get('orderId')
            if identity is not None:
                outcomes[identity] = False
        elif kind == 'order_cancelled':
            outcomes.pop(identity, None)
        count, on_time = len(outcomes), sum(outcomes.values())
        if (not self.epsilon_breaker_active and count >= self.epsilon_breaker_min_orders
                and on_time * 10000 < self.epsilon_breaker_on_time_bps * count):
            self.epsilon_breaker_active = True
            self.epsilon_breaker_at = event['at']
            self.apply_epsilon_breaker()
            self.journal.record('epsilon_breaker', at=event['at'], mode='conservative',
                                resolvedOrders=count, onTimeOrders=on_time,
                                thresholdBps=self.epsilon_breaker_on_time_bps)
