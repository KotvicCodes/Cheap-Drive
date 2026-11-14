"""Offline, scripted SDK contracts; these tests never construct a network client."""
from copy import deepcopy
import io
import json
import unittest

from beta import BetaDesk
from demo import sample_request
from dispatch import Journal
from gamma import GammaCoreDesk
from gamma_pairs import DriverSideSettings, make_gamma_pairs, make_pairs_beta
from spread.starter import steep
from tests.test_alpha import MarketWorld


def order_for(request, deadline=6000):
    order = dict(id=request['id'], dealerId=request['dealerId'], option='same_day',
                 priceCents=30000, deadline=deadline, legs=deepcopy(request['legs']),
                 status='waiting', deliveredAt=[None] * len(request['legs']), lastPickupAt=deadline - 180)
    for leg in order['legs']:
        for kind in ('pickup', 'delivery'):
            leg[kind]['window'] = {'from': 480, 'to': deadline}
    return order


def new_desk(factory=make_pairs_beta, now=600, **settings):
    stream = io.StringIO()
    return factory(MarketWorld(), 8, now, Journal(stream), **settings), stream


def seed(desk, identity='one', deadline=6000):
    request = sample_request()
    request['id'] = identity
    desk.requests[identity] = request
    return order_for(request, deadline)


class ReviewTests(unittest.TestCase):
    def test_defaults_equivalent_for_both_factories_through_scripted_events(self):
        for factory, base_type in ((make_pairs_beta, BetaDesk), (make_gamma_pairs, GammaCoreDesk)):
            with self.subTest(factory=factory.__name__):
                actual, _ = new_desk(factory)
                base = base_type(MarketWorld(), 8, 600, Journal(io.StringIO()))
                request = sample_request()
                request.update(arrivedAt=400, respondBy=700)
                order = order_for(request)
                events = [dict(kind='price_request', request=request), dict(kind='order_won', order=order),
                          dict(kind='gig_booked', gigId='g', driverId='d', feeCents=9600),
                          dict(kind='gig_dropped', gigId='g', driverId='d'),
                          dict(kind='no_show', gigId='g', driverId='d'),
                          dict(kind='gig_expired', gigId='g'),
                          dict(kind='deadline_close', orderId=request['id'], lastPickupAt=5820),
                          dict(kind='visit_failed', gigId='g', orderId=request['id'], leg=0, reason='no_plates'),
                          dict(kind='delivered', gigId='g', orderId=request['id'], leg=0),
                          dict(kind='order_cancelled', orderId=request['id'], gigs=[])]
                for index, event in enumerate(events):
                    for desk in (actual, base):
                        desk.now = 600 + index * 10
                        desk.handle(dict(seq=index, at=desk.now, **deepcopy(event)))
                    self.assertEqual(actual.outbox, base.outbox)
                    if index == 1:
                        for desk in (actual, base):
                            actions, desk.outbox = desk.outbox, []
                            results = [dict(ok=True, id='g' if a['type'] == 'post' else request['id']) for a in actions]
                            desk.read_results(actions, results)
                self.assertEqual(actual.leg_gigs, base.leg_gigs)
                self.assertEqual(actual.booked, base.booked)

    def test_review_at_posting_ages_and_repost_continuity(self):
        desk, _ = new_desk(fee_shape='review', review_skip_night=0)
        order = seed(desk, deadline=3000)
        desk.post(order, [0])
        self.assertEqual(desk.outbox.pop()['schedule'],
                         [{'at': 600, 'feeCents': 9600}, {'at': 960, 'feeCents': 13200},
                          {'at': 2460, 'feeCents': 18000}])
        for now, expected in ((959, 9600), (960, 13200), (2459, 13200), (2460, 18000), (2900, 18000)):
            desk.now = now
            desk.post(order, [0])
            self.assertEqual(desk.outbox.pop()['schedule'][0], {'at': now, 'feeCents': expected})
        self.assertEqual(desk.first_posted['one'], 600)

    def test_expiry_keeps_age(self):
        desk, _ = new_desk(fee_shape='review', review_skip_night=0)
        order = seed(desk)
        desk.orders['one'] = order
        desk.post(order, [0])
        action = desk.outbox.pop()
        desk.read_results([action], [{'ok': True, 'id': 'g'}])
        desk.now = 1100
        desk.handle({'seq': 1, 'at': 1100, 'kind': 'gig_expired', 'gigId': 'g'})
        self.assertEqual(desk.outbox[-1]['schedule'][0]['feeCents'], 13200)

    def test_warning_floor_urgent_and_level_one_unchanged(self):
        desk, _ = new_desk(fee_shape='review', cap_before_last_pickup_minutes=20, review_skip_night=0)
        order = seed(desk, deadline=3000)
        self.assertEqual(desk.fees_for(order, 1)[-1]['at'], order['lastPickupAt'] - 180)
        desk.urgent.add('one')
        self.assertEqual(desk.fees_for(order, 1), steep(desk.now, 12000, 8))
        desk.urgent.clear()
        desk.level = 1
        self.assertEqual(desk.fees_for(order, 1), steep(desk.now, 12000, 1))

    def test_night_skip_and_monotone_with_cap_before_review(self):
        for first, reviewed in ((1100, 1860), (1200, 1860), (600, 960)):
            desk, _ = new_desk(now=first, fee_shape='review')
            order = seed(desk)
            self.assertEqual(desk.fees_for(order, 1)[1]['at'], reviewed)
        desk, _ = new_desk(fee_shape='review', review_after_minutes=5000, review_skip_night=0)
        order = seed(desk, deadline=1600)
        self.assertEqual(desk.fees_for(order, 1),
                         [{'at': 600, 'feeCents': 9600}, {'at': 1060, 'feeCents': 18000}])

    def test_gamma_opening_and_cap_are_respected(self):
        desk, _ = new_desk(make_gamma_pairs, fee_shape='review', max_km=100, long_max_km=300,
                           long_opening_fee_bps=13000, fee_cap_bps=14000)
        order = seed(desk)
        self.assertEqual([s['feeCents'] for s in desk.fees_for(order, 1)], [15600, 16800])

    def test_settings_validation_and_factory_keyword_split(self):
        for settings in ({'fee_shape': 'bad'}, {'pairs': True}, {'pairs': 2}, {'review_after_minutes': -1},
                         {'pair_max_drive_minutes': 721}, {'pair_split_minutes': 0}, {'pair_fee_bps': 0}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                DriverSideSettings(**settings)
        for factory in (make_pairs_beta, make_gamma_pairs):
            with self.assertRaises(TypeError):
                new_desk(factory, unknown=1)
            desk, _ = new_desk(factory, opening_fee_bps=9000, fee_shape='review')
            self.assertEqual(desk.settings.opening_fee_bps, 9000)
            self.assertEqual(desk.driver_settings.fee_shape, 'review')


if __name__ == '__main__':
    unittest.main()
