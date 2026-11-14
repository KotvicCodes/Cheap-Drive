"""Optional rescue-pair gates that preserve young, nonurgent waiting singles."""


class DeltaPairGuardMixin:
    def __init__(self, *args, delta_pair_max_wait_minutes=0,
                 delta_pair_min_slack_minutes=0, **kwargs):
        for name, value in (('delta_pair_max_wait_minutes', delta_pair_max_wait_minutes),
                            ('delta_pair_min_slack_minutes', delta_pair_min_slack_minutes)):
            if type(value) is not int or value < 0:
                raise ValueError(name + ' must be a nonnegative integer')
        self.delta_pair_max_wait_minutes = delta_pair_max_wait_minutes
        self.delta_pair_min_slack_minutes = delta_pair_min_slack_minutes
        super().__init__(*args, **kwargs)

    def _eligible(self, order):
        if not super()._eligible(order):
            return False
        identity = order['id']
        if not self.gigs_of(identity):
            return True
        if (self.delta_pair_max_wait_minutes and
                self.now - self.first_posted.get(identity, self.now) > self.delta_pair_max_wait_minutes):
            return False
        if self.delta_pair_min_slack_minutes:
            request = {**self.requests[identity], 'legs': order['legs']}
            latest = self._latest_note_route(request, order['deadline'], floor=self.now)
            if latest is None or min(order['lastPickupAt'], latest[1]) < self.now + self.delta_pair_min_slack_minutes:
                return False
        return True
