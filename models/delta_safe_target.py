"""Default-off separate learner for requests whose whole quoted menu is safe.

The target is encoded in the tracker name, so existing checkpoints and durable
quote receipts retain the quote-time target without recomputing congestion at
feedback time. A 4200 target provides the split-learner experimental control.
"""


class DeltaSafeTargetMixin:
    _SAFE_PREFIX = 'delta_safe_target:'

    def __init__(self, *args, delta_safe_target_bps=0,
                 delta_safe_target_min_slack_minutes=720,
                 delta_safe_target_max_backlog=15, **kwargs):
        for name, value in (
                ('delta_safe_target_bps', delta_safe_target_bps),
                ('delta_safe_target_min_slack_minutes', delta_safe_target_min_slack_minutes),
                ('delta_safe_target_max_backlog', delta_safe_target_max_backlog)):
            if type(value) is not int or value < 0:
                raise ValueError(name + ' must be a nonnegative integer')
        if delta_safe_target_bps >= 10000:
            raise ValueError('delta_safe_target_bps must be in 0..9999')
        self.delta_safe_target_bps = delta_safe_target_bps
        self.delta_safe_target_min_slack_minutes = delta_safe_target_min_slack_minutes
        self.delta_safe_target_max_backlog = delta_safe_target_max_backlog
        self._delta_safe_target_context = None
        self._delta_safe_quoting = False
        super().__init__(*args, **kwargs)
        if delta_safe_target_bps and (self.settings.markup_scope != 'global' or
                                      self.delta_safe_quote_bps):
            raise ValueError('safe target requires global scope and no fixed safe discount')

    def tracker_for(self, request, km):
        ordinary = super().tracker_for(request, km)
        if (not self.delta_safe_target_bps or self.level <= 3 or self.brake_mode != 'normal' or
                not 50 <= km <= 300 or len(request['legs']) != 1 or self.is_premium(request) or
                any(request['legs'][0][kind]['privateAddress'] for kind in ('pickup', 'delivery')) or
                len(self.orders_without_driver()) > self.delta_safe_target_max_backlog):
            return ordinary
        trust = self.trust.get(request['dealerId'], 0)
        options, _ = self.eligible_options(request, km, trust)
        # Feedback resolves a request, not every offered option. Requiring the
        # entire admitted menu prevents a high target affecting a tight option.
        if not options or any(self.slack(request, o) < self.delta_safe_target_min_slack_minutes
                              for o in options):
            return ordinary
        tracker = self._SAFE_PREFIX + str(self.delta_safe_target_bps)
        markup = self.tracker_markup(tracker)
        table = self.table_factors(request)[2]
        floor = (request['referenceFeeCents'] * 11000 + 9999) // 10000
        if any(self.price_option(o, markup, trust, table, self.option_factors(request, o, km, trust))
               < floor for o in options):
            return ordinary
        if self._delta_safe_quoting:
            self._delta_safe_target_context = self.delta_safe_target_bps
        return tracker

    def _quote_request(self, request):
        if not self.delta_safe_target_bps:
            return super()._quote_request(request)
        previous = self._delta_safe_target_context
        quoting = self._delta_safe_quoting
        self._delta_safe_target_context = None
        self._delta_safe_quoting = True
        try:
            return super()._quote_request(request)
        finally:
            self._delta_safe_target_context = previous
            self._delta_safe_quoting = quoting

    def win_target(self):
        if self._delta_safe_target_context is not None:
            return self._delta_safe_target_context
        return super().win_target()

    def learn(self, request_id, won):
        tracker = self.quote_trackers.get(request_id, '')
        if not self.delta_safe_target_bps or not tracker.startswith(self._SAFE_PREFIX):
            return super().learn(request_id, won)
        previous = self._delta_safe_target_context
        self._delta_safe_target_context = int(tracker[len(self._SAFE_PREFIX):])
        try:
            return super().learn(request_id, won)
        finally:
            self._delta_safe_target_context = previous
