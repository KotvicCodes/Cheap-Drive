"""Aggregate realized car pooling without reopening saved sweep traces."""
from collections import Counter, defaultdict


class PairMetricsMixin:
    """Cooperative, read-only journal instrumentation for ordinary sweeps.

    Pooling requires two distinct orders actually delivered by the same gig.
    A booked pair that splits, drops, or loses one car to cancellation therefore
    does not count as two pooled deliveries. Fees use net ledger charges rather
    than booking offers, which may be released or changed later.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool_deliveries = defaultdict(set)
        self.pool_fees = Counter()
        self.pool_events = Counter()

    def record(self, kind, **fields):
        super().record(kind, **fields)
        if kind in ('gamma_pair', 'gamma_pair_booked', 'gamma_pair_split'):
            self.pool_events[kind] += 1
        events = ([fields['event']] if kind == 'event' else
                  fields['response']['events'] if kind == 'advance_batch' else [])
        for event in events:
            if event['kind'] == 'delivered':
                self.pool_deliveries[event['gigId']].add((event['orderId'], event['leg']))
            elif event['kind'] == 'ledger' and event['line']['kind'] == 'driver_fee':
                line = event['line']
                self.pool_fees[line.get('gigId')] -= line['cents']

    def metrics(self):
        shared = {gig for gig, members in self.pool_deliveries.items()
                  if len({order for order, leg in members}) >= 2}
        delivered = set().union(*self.pool_deliveries.values()) if self.pool_deliveries else set()
        pooled = set().union(*(self.pool_deliveries[gig] for gig in shared)) if shared else set()
        cars, shared_cars = len(delivered), len(pooled)
        fees, shared_fees = sum(self.pool_fees.values()), sum(self.pool_fees[gig] for gig in shared)
        return {**super().metrics(), 'pairing': {
            'delivered_cars': cars, 'pooled_delivered_cars': shared_cars,
            'pooled_delivery_share': shared_cars / cars if cars else 0,
            'pooled_completed_gigs': len(shared),
            'net_driver_fee_cents': fees,
            'driver_fee_per_car_cents': fees / cars if cars else None,
            'pooled_net_driver_fee_cents': shared_fees,
            'pooled_driver_fee_per_car_cents': shared_fees / shared_cars if shared_cars else None,
            'pair_posts': self.pool_events['gamma_pair'],
            'pair_bookings': self.pool_events['gamma_pair_booked'],
            'pair_splits': self.pool_events['gamma_pair_split'],
        }}
