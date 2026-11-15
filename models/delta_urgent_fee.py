"""Keep an urgent single's escalation clock across reposts and recovery."""
from spread.starter import steep


class DeltaUrgentFeeMixin:
    def __init__(self, *args, delta_urgent_fee_memory=0, **kwargs):
        if type(delta_urgent_fee_memory) is not int or delta_urgent_fee_memory not in (0, 1):
            raise ValueError('delta_urgent_fee_memory must be 0 or 1')
        self.delta_urgent_fee_memory = delta_urgent_fee_memory
        if delta_urgent_fee_memory:
            self.delta_urgent_since = {}
        super().__init__(*args, **kwargs)

    def _remember_urgency(self, event):
        if self.delta_urgent_fee_memory and event['kind'] == 'deadline_close':
            identity = event['orderId']
            self.delta_urgent_since[identity] = min(event['at'], self.delta_urgent_since.get(identity, event['at']))

    def handle(self, event):
        # DriverSideMixin may intercept a paired warning before Gamma sees it.
        self._remember_urgency(event)
        return super().handle(event)

    def observe_history(self, event):
        # Receipt-free reconstruction calls this before rebuilding schedules.
        self._remember_urgency(event)
        return super().observe_history(event)

    def _urgent_memory_schedule(self, order, cars, schedule):
        if not self.delta_urgent_fee_memory or order['id'] not in self.urgent:
            return schedule
        since = self.delta_urgent_since.get(order['id'])
        if since is None:
            # A booked offer is not evidence that a warning has occurred.
            return schedule
        reference = self.requests[order['id']]['referenceFeeCents'] * cars / len(order['legs'])
        original = steep(since, reference, self.level)
        current = max(step['feeCents'] for step in original if step['at'] <= self.now)
        # Accepted single schedules can carry stronger current evidence on
        # recovery; never scale a two-order pair fee as one order's reference.
        for action in self.posts.values():
            if {stop['orderId'] for stop in action['stops']} == {order['id']}:
                current = max([current, *(step['feeCents'] for step in action['schedule'] if step['at'] <= self.now)])
        result = [{'at': self.now, 'feeCents': current}]
        for step in original:
            if step['at'] > self.now and step['feeCents'] > result[-1]['feeCents']:
                result.append(dict(step))
        self.journal.record('delta_urgent_fee_memory', at=self.now, orderId=order['id'],
                            urgentSince=since, ageMinutes=self.now - since,
                            resetPrevented=result[0]['feeCents'] > schedule[0]['feeCents'])
        return result
