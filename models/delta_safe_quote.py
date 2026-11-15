"""Default-off customer discount for the guarded 50–300 km pool."""


class DeltaSafeQuoteMixin:
    def __init__(self, *args, delta_safe_quote_bps=0,
                 delta_safe_quote_min_slack_minutes=720,
                 delta_safe_quote_max_backlog=15, **kwargs):
        for name, value in (
                ('delta_safe_quote_bps', delta_safe_quote_bps),
                ('delta_safe_quote_min_slack_minutes', delta_safe_quote_min_slack_minutes),
                ('delta_safe_quote_max_backlog', delta_safe_quote_max_backlog)):
            if type(value) is not int or value < 0:
                raise ValueError(name + ' must be a nonnegative integer')
        if delta_safe_quote_bps > 10000:
            raise ValueError('delta_safe_quote_bps must be in 0..10000')
        self.delta_safe_quote_bps = delta_safe_quote_bps
        self.delta_safe_quote_min_slack_minutes = delta_safe_quote_min_slack_minutes
        self.delta_safe_quote_max_backlog = delta_safe_quote_max_backlog
        super().__init__(*args, **kwargs)

    def option_factors(self, request, option, km, trust):
        factors = super().option_factors(request, option, km, trust)
        if (not self.delta_safe_quote_bps or self.level <= 3 or
                not 50 <= km <= 300 or len(request['legs']) != 1 or
                self.is_premium(request) or
                any(request['legs'][0][kind]['privateAddress'] for kind in ('pickup', 'delivery')) or
                self.slack(request, option) < self.delta_safe_quote_min_slack_minutes):
            return factors
        backlog = len(self.orders_without_driver())
        if backlog > self.delta_safe_quote_max_backlog:
            return factors
        # Use the exact same markup, factors and final cent ceiling as quote().
        # A failed floor retains the entire original quote, rather than clipping
        # to a new price that could distort the intended experiment strength.
        markup = self.tracker_markup(self.tracker_for(request, km))
        table = self.table_factors(request)[2]
        original = self.price_option(option, markup, trust, table, factors)
        discounted_factors = {**factors, 'deltaSafeQuoteBps': self.delta_safe_quote_bps}
        discounted = self.price_option(option, markup, trust, table, discounted_factors)
        floor = (request['referenceFeeCents'] * 11000 + 9999) // 10000
        applied = discounted >= floor
        self.journal.record('delta_safe_quote', at=self.now, requestId=request['id'],
                            option=option['kind'], routeKm=km, openOrders=backlog,
                            originalPriceCents=original, discountedPriceCents=discounted,
                            referenceFloorCents=floor, applied=applied,
                            factorBps=self.delta_safe_quote_bps)
        return discounted_factors if applied else factors
