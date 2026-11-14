"""Default-off discount for a feasible pair with an existing waiting order."""


class DeltaPairQuoteMixin:
    def __init__(self, *args, delta_pair_quote_bps=0, **kwargs):
        if type(delta_pair_quote_bps) is not int or not 0 <= delta_pair_quote_bps <= 10000:
            raise ValueError('delta_pair_quote_bps must be an integer between 0 and 10000')
        self.delta_pair_quote_bps = delta_pair_quote_bps
        super().__init__(*args, **kwargs)
        if delta_pair_quote_bps and not self.driver_settings.pairs:
            raise ValueError('delta_pair_quote_bps requires pairs=1')

    def quote_has_waiting_pair(self, request, option):
        if len(request['legs']) != 1:
            return False
        latest = self._latest_note_route(request, option['deadline'])
        if latest is None:
            return False
        prospective = dict(id=request['id'], dealerId=request['dealerId'],
                           option=option['kind'], priceCents=0, deadline=option['deadline'],
                           legs=request['legs'], status='waiting', deliveredAt=[None],
                           lastPickupAt=latest[0])
        # _plan builds temporary single posts. Suppress outbox-driven timers
        # throughout this read-only calculation; the ordinary quote/send path
        # still processes them at its established boundary.
        self._busy += 1
        try:
            for other in self.orders.values():
                if not self.gigs_of(other['id']) or not self._eligible(other):
                    continue
                for first, second in ((prospective, other), (other, prospective)):
                    try:
                        plan, _ = self._plan(first, second)
                    except IndexError:  # a waiting order has no postable single window
                        continue
                    if plan is not None:
                        return True
            return False
        finally:
            self._busy -= 1

    def option_factors(self, request, option, km, trust):
        factors = super().option_factors(request, option, km, trust)
        if self.delta_pair_quote_bps and self.quote_has_waiting_pair(request, option):
            factors['deltaWaitingPairBps'] = self.delta_pair_quote_bps
        return factors
