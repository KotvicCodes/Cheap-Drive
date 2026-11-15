"""Default-off quote floor anchored to the raw single-order reference fee."""


class DeltaReferenceFloorMixin:
    def __init__(self, *args, delta_reference_quote_floor_bps=0, **kwargs):
        if type(delta_reference_quote_floor_bps) is not int or delta_reference_quote_floor_bps < 0:
            raise ValueError('delta_reference_quote_floor_bps must be a nonnegative integer')
        self.delta_reference_quote_floor_bps = delta_reference_quote_floor_bps
        self._delta_reference_request = None
        super().__init__(*args, **kwargs)

    def quote(self, request):
        if not self.delta_reference_quote_floor_bps:
            return super().quote(request)
        previous = self._delta_reference_request
        self._delta_reference_request = request
        try:
            return super().quote(request)
        finally:
            self._delta_reference_request = previous

    def price_option(self, option, markup, trust, table, factors):
        base = super().price_option(option, markup, trust, table, factors)
        request = self._delta_reference_request
        if (not self.delta_reference_quote_floor_bps or request is None or self.level < 4
                or len(request['legs']) != 1 or self.route_km(request) < 45):
            return base
        # Practical decline quotes bypass price_option in the inherited path.
        floor = (request['referenceFeeCents'] * self.delta_reference_quote_floor_bps + 9999) // 10000
        final = max(base, floor)
        self.journal.record('delta_reference_quote_floor', at=self.now,
                            requestId=request['id'], option=option['kind'],
                            referenceFeeCents=request['referenceFeeCents'],
                            baseCents=base, floorCents=floor, finalCents=final,
                            binding=final > base)
        return final
