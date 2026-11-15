"""Discount only early single-order offers while preserving segment floors."""


class DeltaReadinessFeeMixin:
    def __init__(self, *args, delta_readiness_early_cut_bps=0, **kwargs):
        if type(delta_readiness_early_cut_bps) is not int or delta_readiness_early_cut_bps < 0:
            raise ValueError('delta_readiness_early_cut_bps must be a nonnegative integer')
        self.delta_readiness_early_cut_bps = delta_readiness_early_cut_bps
        super().__init__(*args, **kwargs)

    def _readiness_fee_schedule(self, order, cars, schedule):
        cut = self.delta_readiness_early_cut_bps
        if not cut or self.level == 1 or order['id'] in self.urgent or len(order['legs']) != 1 or cars != 1:
            return schedule
        request = self.requests[order['id']]
        facts = self.note_facts(request)
        km = self.route_km(request)
        if (not 45 <= km <= 500 or self.is_premium(order) or facts.plates or facts.manual
                or any(leg[k].get('privateAddress') for leg in order['legs'] for k in ('pickup', 'delivery'))):
            return schedule
        ready = max(request['legs'][0]['pickup']['window']['from'], facts.ready_at or 0,
                    facts.released_at or 0)
        if ready - self.now < 720 or len(schedule) < 3:
            return schedule
        s = self.settings
        nearby = self.near30.get(request['legs'][0]['pickup']['placeId'])
        floor_bps = max(0, s.long_opening_fee_bps if self.is_long_route(km) else 0,
                        s.short_opening_fee_bps if km < s.short_fee_km else 0,
                        s.premium_opening_fee_bps if self.is_premium(order) else 0,
                        s.town_starved_opening_fee_bps if nearby is not None and nearby <= s.town_starved_near30 else 0)
        reference = request['referenceFeeCents']
        floor = max(1, int(reference * floor_bps / 10000 + 0.5))
        reduction = int(reference * cut / 10000 + 0.5)
        result = []
        for index, step in enumerate(schedule):
            cents = max(floor, step['feeCents'] - reduction) if index < 2 else step['feeCents']
            if result and cents == result[-1]['feeCents']:
                continue
            result.append({'at': step['at'], 'feeCents': cents})
        self.journal.record('delta_readiness_fee', at=self.now, orderId=order['id'],
                            readyAt=ready, firstPostedAt=self.first_posted.get(order['id'], self.now),
                            original=schedule, discounted=result)
        return result
