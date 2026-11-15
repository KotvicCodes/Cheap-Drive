"""Opt-in SAFE/REST learners; REST always targets 4200 basis points.

SAFE follows the requested public request/supply definition exactly: total
route <=300 km, maximum offered deadline >=36h after arrival, and >5 initial
home drivers within 30 road km of the final delivery. This is a hypothesis,
not a guarantee about current driver availability or the chosen option.
"""


class DeltaSegmentedTargetsMixin:
    _SEGMENT_PREFIX = 'delta_segmented:'

    def __init__(self, *args, delta_segmented_targets=0, win_target_safe_bps=5500, **kwargs):
        if type(delta_segmented_targets) is not int or delta_segmented_targets not in (0, 1):
            raise ValueError('delta_segmented_targets must be 0 or 1')
        if type(win_target_safe_bps) is not int or not 1 <= win_target_safe_bps < 10000:
            raise ValueError('win_target_safe_bps must be in 1..9999')
        self.delta_segmented_targets = delta_segmented_targets
        self.win_target_safe_bps = win_target_safe_bps
        self._segmented_quote = False
        self._segmented_target = None
        super().__init__(*args, **kwargs)
        if delta_segmented_targets and (self.settings.markup_scope != 'global' or
                                        self.delta_safe_target_bps or self.delta_safe_quote_bps):
            raise ValueError('segmented targets require global scope and no other safe-price experiment')

    def tracker_for(self, request, km):
        if not self.delta_segmented_targets or self.level <= 3:
            return super().tracker_for(request, km)
        delivery = request['legs'][-1]['delivery']['placeId']
        nearby = self.near30.get(delivery)
        lead = max(o['deadline'] for o in request['options']) - request['arrivedAt']
        safe = km <= 300 and lead >= 2160 and nearby is not None and nearby > 5
        target = self.win_target_safe_bps if safe else 4200
        if self._segmented_quote:
            self._segmented_target = target
        # The target travels with durable quote receipts and pending feedback.
        # Gamma already keeps markup and day-start state independently by key.
        return f'{self._SEGMENT_PREFIX}{"safe" if safe else "rest"}:{target}'

    def _quote_request(self, request):
        if not self.delta_segmented_targets or self.level <= 3:
            return super()._quote_request(request)
        previous = self._segmented_quote, self._segmented_target
        self._segmented_quote, self._segmented_target = True, None
        try:
            return super()._quote_request(request)
        finally:
            self._segmented_quote, self._segmented_target = previous

    def win_target(self):
        if not self.delta_segmented_targets or self.level <= 3:
            return super().win_target()
        return self._segmented_target if self._segmented_target is not None else 4200

    def learn(self, request_id, won):
        tracker = self.quote_trackers.get(request_id, '')
        if not self.delta_segmented_targets or not tracker.startswith(self._SEGMENT_PREFIX):
            return super().learn(request_id, won)
        previous = self._segmented_target
        self._segmented_target = int(tracker.rsplit(':', 1)[1])
        try:
            return super().learn(request_id, won)
        finally:
            self._segmented_target = previous
