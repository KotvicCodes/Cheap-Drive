"""Default-off, week-long return to conservative intake and future pairing."""
from dataclasses import replace


class EpsilonBreakerMixin:
    def __init__(self, *args, epsilon_breaker=0, epsilon_breaker_on_time_bps=9400,
                 epsilon_breaker_min_orders=20, epsilon_breaker_window_minutes=0,
                 epsilon_breaker_risk_orders=3, epsilon_breaker_risk_horizon_minutes=360,
                 epsilon_breaker_restore_pairing=1, **kwargs):
        if type(epsilon_breaker) is not int or epsilon_breaker not in (0, 1):
            raise ValueError('epsilon_breaker must be 0 or 1')
        if type(epsilon_breaker_restore_pairing) is not int or epsilon_breaker_restore_pairing not in (0, 1):
            raise ValueError('epsilon_breaker_restore_pairing must be 0 or 1')
        if (type(epsilon_breaker_on_time_bps) is not int or
                not 0 < epsilon_breaker_on_time_bps <= 10000):
            raise ValueError('epsilon_breaker_on_time_bps must be in 1..10000')
        if type(epsilon_breaker_min_orders) is not int or epsilon_breaker_min_orders < 1:
            raise ValueError('epsilon_breaker_min_orders must be positive')
        if type(epsilon_breaker_window_minutes) is not int or epsilon_breaker_window_minutes < 0:
            raise ValueError('epsilon_breaker_window_minutes must be nonnegative')
        for name, value in (('epsilon_breaker_risk_orders', epsilon_breaker_risk_orders),
                            ('epsilon_breaker_risk_horizon_minutes', epsilon_breaker_risk_horizon_minutes)):
            if type(value) is not int or value < 0:
                raise ValueError(name + ' must be nonnegative')
        self.epsilon_breaker = epsilon_breaker
        self.epsilon_breaker_on_time_bps = epsilon_breaker_on_time_bps
        self.epsilon_breaker_min_orders = epsilon_breaker_min_orders
        self.epsilon_breaker_window_minutes = epsilon_breaker_window_minutes
        self.epsilon_breaker_risk_orders = epsilon_breaker_risk_orders
        self.epsilon_breaker_risk_horizon_minutes = epsilon_breaker_risk_horizon_minutes
        self.epsilon_breaker_restore_pairing = epsilon_breaker_restore_pairing
        self.epsilon_breaker_active = False
        self.epsilon_breaker_at = None
        # One outcome per order: True is fully delivered on time, False is
        # already late (including an overdue order not yet fully delivered).
        self.epsilon_breaker_outcomes = {}
        self.epsilon_breaker_resolved_at = {}
        super().__init__(*args, **kwargs)

    def trip_epsilon_breaker(self, at, **signal):
        if self.epsilon_breaker_active:
            return
        self.epsilon_breaker_active = True
        self.epsilon_breaker_at = at
        self.apply_epsilon_breaker()
        self.journal.record('epsilon_breaker', at=at, mode='conservative', **signal)

    def check_epsilon_pickup_risk(self, at):
        # Decide before admitting more work, using only the current public books.
        # The route calculation includes notes, site closures and missing posts;
        # booked legs and already delivered legs never count as unserved risk.
        if self.epsilon_breaker and not self.epsilon_breaker_active and self.epsilon_breaker_risk_orders:
            risky = self.service_risk_orders(horizon=self.epsilon_breaker_risk_horizon_minutes)
            if len(risky) >= self.epsilon_breaker_risk_orders:
                self.trip_epsilon_breaker(at, signal='unbooked_pickup_risk',
                                          riskyOrders=len(risky), orderIds=sorted(risky),
                                          horizonMinutes=self.epsilon_breaker_risk_horizon_minutes)

    def quote(self, request):
        self.check_epsilon_pickup_risk(self.now)
        return super().quote(request)

    def apply_epsilon_breaker(self):
        """Also called after checkpoint restoration; never alters existing gigs."""
        if not (self.epsilon_breaker and self.epsilon_breaker_active):
            return
        self.settings = replace(self.settings, win_target_bps=min(self.settings.win_target_bps, 4200),
                                short_km=45, short_bps=9200, long_markup_bps=10000,
                                trade_ins=0)
        self.intake_settings = replace(self.intake_settings, delta_relaxed_slack_minutes=0,
                                       delta_corridor_open_cap=0)
        # These gates affect future pair search only. Active pairs retain their
        # stored route, deadlines, fees and timers; no gig is withdrawn here.
        if self.epsilon_breaker_restore_pairing:
            self.driver_settings = replace(self.driver_settings, pair_once=1, pair_max_idle_minutes=60)
            self.delta_pair_max_wait_minutes = 0
            self.delta_pair_min_slack_minutes = 0
        # Keep guarded trade routing/fees for previously accepted two-leg work.
        # trade_ins=0 prevents any new trade admission through Gamma's gate.

    def observe_history(self, event):
        super().observe_history(event)
        if not self.epsilon_breaker:
            return
        kind, identity = event['kind'], event.get('orderId')
        if kind == 'price_request':
            # Recovery may have no durable receipt for this historical quote.
            # Observe the signal anyway, so replay cannot forget a week latch.
            self.check_epsilon_pickup_risk(event['at'])
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
            self.epsilon_breaker_resolved_at.pop(identity, None)
        if identity in outcomes:
            # Keep the first observed resolution time. Duplicate refunds or
            # later legs must not make an old failure look recent again.
            self.epsilon_breaker_resolved_at.setdefault(identity, event['at'])
        window = self.epsilon_breaker_window_minutes
        recent = [good for identity, good in outcomes.items()
                  if not window or event['at'] - window < self.epsilon_breaker_resolved_at[identity]]
        count, on_time = len(recent), sum(recent)
        if (not self.epsilon_breaker_active and count >= self.epsilon_breaker_min_orders
                and on_time * 10000 < self.epsilon_breaker_on_time_bps * count):
            self.trip_epsilon_breaker(event['at'], signal='realized_service',
                                      resolvedOrders=count, onTimeOrders=on_time,
                                      thresholdBps=self.epsilon_breaker_on_time_bps,
                                      windowMinutes=window)
