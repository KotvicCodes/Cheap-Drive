"""Anticipate a note-tightened single pickup cutoff without a mutable clock."""
from .notes import NoteFacts
from spread.starter import steep


def maximum_schedule(normal, anticipated, now):
    times = sorted({now, *(s['at'] for s in normal if s['at'] > now),
                    *(s['at'] for s in anticipated if s['at'] > now)})
    result = []
    for at in times:
        fee = max(s['feeCents'] for s in normal if s['at'] <= at)
        fee = max([fee, *(s['feeCents'] for s in anticipated if s['at'] <= at)])
        if not result or fee > result[-1]['feeCents']:
            result.append({'at': at, 'feeCents': fee})
    return result


class DeltaNoteUrgencyMixin:
    def __init__(self, *args, delta_note_urgency=0, **kwargs):
        if type(delta_note_urgency) is not int or delta_note_urgency not in (0, 1):
            raise ValueError('delta_note_urgency must be 0 or 1')
        self.delta_note_urgency = delta_note_urgency
        super().__init__(*args, **kwargs)

    def _note_urgency_schedule(self, order, cars, schedule):
        if (not self.delta_note_urgency or self.level == 1 or order['id'] in self.urgent
                or len(order['legs']) != 1 or cars != 1):
            return schedule
        request = {**self.requests[order['id']], 'legs': order['legs']}
        facts = self.note_facts(request)
        floor = max(request['respondBy'], facts.ready_at or 0, facts.released_at or 0)
        route = self._latest_note_route(request, order['deadline'], floor=floor)
        neutral = self._latest_note_route(request, order['deadline'],
                                          floor=request['respondBy'], facts=NoteFacts())
        if route is None or neutral is None:
            self.journal.record('delta_note_urgency', at=self.now, orderId=order['id'],
                                armed=False, reason='no_stable_route')
            return schedule
        cutoff = min(order['lastPickupAt'], route[0])
        if cutoff >= min(order['lastPickupAt'], neutral[0]):
            return schedule
        anchor = cutoff - 180
        anticipated = steep(anchor, request['referenceFeeCents'], self.level)
        result = maximum_schedule(schedule, anticipated, self.now)
        self.journal.record('delta_note_urgency', at=self.now, orderId=order['id'],
                            armed=True, cutoff=cutoff, anchor=anchor,
                            crossed=self.now >= anchor, elapsedMinutes=max(0, self.now-anchor))
        return result
