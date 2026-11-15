"""Public-data offers, quota safety and quote isolation; no network clients."""
from copy import deepcopy
import io
import unittest
from unittest.mock import patch

from dispatch import Journal
from models.delta import make_delta
from models.epsilon_offers import distance_km
from spread.starter import DAY
from tests.test_gamma_pairs import PairWorld, pair_order


class OffersWorld(PairWorld):
    def __init__(self):
        super().__init__()
        self.initial_map['places'] = [dict(id=p, lat=60, lon=24 + i) for i, p in enumerate('abcd')]
        self.initial_roster = [dict(id=f'd{i}', homePlaceId='b', licence='manual', rating=4.9,
                                   completedGigs=80, drops=0) for i in range(8)]


def desk_for(**settings):
    return make_delta(OffersWorld(), 8, 600, Journal(io.StringIO()), **settings)


def post(desk, identity='one', latest=1200):
    order = pair_order(desk, identity, deadline=latest + 180)
    order['lastPickupAt'] = latest
    desk.orders[identity] = order
    desk.post(order, [0])
    actions, desk._outbox = desk._outbox, []
    desk.read_results(actions, desk.world.act(actions))
    return desk.leg_gigs[identity][0]


def poll(desk, now):
    desk.now = now
    desk.poll_driver_side()
    actions, desk._outbox = desk._outbox, []
    return [a for a in actions if a['type'] == 'offer']


class OffersTests(unittest.TestCase):
    def test_settings_reject_invalid_values(self):
        for key, value in [('epsilon_offers', True), ('epsilon_offers', 2), ('offer_after_minutes', -1),
                           ('offer_interval_minutes', 0), ('offer_interval_minutes', 181),
                           ('offer_fee_bps', 0), ('offer_fee_bps', 15001),
                           ('offer_max_eta_minutes', 481)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                desk_for(**{key: value})

    def test_default_off_preserves_actions_timers_and_bookkeeping(self):
        desks = [desk_for(), desk_for(epsilon_offers=0)]
        for desk in desks:
            post(desk)
            self.assertIsNone(desk.next_pair_wake())
            self.assertEqual(poll(desk, 900), [])
        self.assertEqual(desks[0].posts, desks[1].posts)
        self.assertEqual(desks[0].booked, desks[1].booked)
        self.assertEqual(desks[0].world.actions, desks[1].world.actions)

    def test_notification_uses_air_distance_even_when_road_is_short(self):
        desk = desk_for(epsilon_offers=1)
        post(desk)
        self.assertLess(desk.roads['b', 'a']['km'], 30)
        self.assertGreater(distance_km(desk._offer_places['b'], desk._offer_places['a']), 30)
        self.assertEqual(len(poll(desk, 720)), 3)
        # A nearby home must be excluded even when the road happens to be long.
        world = OffersWorld()
        world.initial_map['places'][1]['lon'] = 24.01
        for road in world.initial_map['roads']:
            road['km'] = 100
        nearby = make_delta(world, 8, 600, Journal(io.StringIO()), epsilon_offers=1)
        post(nearby)
        self.assertEqual(poll(nearby, 720), [])

    def test_age_and_pickup_risk_are_independent_triggers(self):
        desk = desk_for(epsilon_offers=1)
        post(desk, latest=2400)
        self.assertEqual(poll(desk, 600), [])
        self.assertEqual(len(poll(desk, 720)), 3)
        urgent = desk_for(epsilon_offers=1, offer_after_minutes=1000)
        post(urgent, latest=900)
        self.assertEqual(len(poll(urgent, 600)), 3)

    def test_no_reads_no_driver_scan_in_direct_quote_or_price_handler(self):
        for handler in (False, True):
            desk = desk_for(epsilon_offers=1)
            post(desk)
            request = deepcopy(desk.requests['one'])
            request.update(id='quote', arrivedAt=700, respondBy=735)
            desk.now = 720
            with patch.object(desk, '_poll_offers', side_effect=AssertionError('offer scan')), \
                 patch.object(desk.world, 'act', side_effect=AssertionError('network')):
                if handler:
                    desk.handle(dict(seq=1, at=720, kind='price_request', request=request))
                else:
                    desk.quote(request)
                self.assertEqual([a['type'] for a in desk.outbox], ['quote'])
        self.assertEqual(desk._offer_next, 721)

    def test_open_limit_daily_limit_expiry_and_no_repeat_same_gig(self):
        desk = desk_for(epsilon_offers=1, offer_after_minutes=0, offer_interval_minutes=10)
        gig = post(desk)
        self.assertEqual(len(poll(desk, 600)), 3)
        # Conservative eleven-minute reservation includes queued sends.
        self.assertEqual(poll(desk, 610), [])
        second = poll(desk, 620)
        self.assertEqual(len(second), 3)
        first_drivers = {a['driverId'] for a in second}
        third = poll(desk, 640)
        self.assertFalse(first_drivers & {a['driverId'] for a in third})
        self.assertEqual(poll(desk, 660), [])
        for index in range(4):
            post(desk, f'next{index}')
            poll(desk, 680 + index * 20)
        self.assertLessEqual(max(desk._offer_counts.values()), 3)
        self.assertTrue(all(a['gigId'] == gig for a in second))

    def test_three_actions_per_tick_even_with_many_gigs_and_failed_sends(self):
        desk = desk_for(epsilon_offers=1, offer_after_minutes=0)
        for i in range(5):
            post(desk, str(i))
        actions = poll(desk, 600)
        self.assertEqual(len(actions), 3)
        desk.read_results(actions, [dict(ok=False, reason='rejected')] * 3)
        self.assertEqual(sum(desk._offer_counts.values()), 3)
        self.assertEqual(poll(desk, 601), [])

    def test_blackout_and_day_reset(self):
        desk = desk_for(epsilon_offers=1, offer_after_minutes=0)
        gig = post(desk, latest=3 * DAY)
        for stop in desk.posts[gig]['stops']:
            stop['window']['to'] = 3 * DAY
        self.assertEqual(poll(desk, 1370), [])
        self.assertEqual(desk.next_pair_wake(), DAY + 420)
        self.assertEqual(poll(desk, DAY + 419), [])
        self.assertEqual(len(poll(desk, DAY + 420)), 3)
        self.assertEqual(desk._offer_day, 1)
        self.assertEqual(poll(desk, DAY + 1380), [])

    def test_audience_and_unknown_geography(self):
        desk = desk_for(epsilon_offers=1, offer_after_minutes=0)
        gig = post(desk)
        desk.posts[gig]['audience'] = dict(experienced=True, manualLicence=True)
        for d in desk._offer_roster.values():
            d['rating'] = 4.7
        self.assertEqual(poll(desk, 600), [])
        for d in desk._offer_roster.values():
            d.update(rating=4.9, licence='automatic_only')
        self.assertEqual(poll(desk, 630), [])
        world = PairWorld()  # missing home IDs and place coordinates fail closed
        unknown = make_delta(world, 8, 600, Journal(io.StringIO()), epsilon_offers=1)
        post(unknown)
        self.assertEqual(poll(unknown, 720), [])

    def test_eta_window_delivery_deadline_and_expired_gig_filters(self):
        for mode in ('eta', 'window', 'delivery', 'expired', 'booked', 'withdraw'):
            desk = desk_for(epsilon_offers=1, offer_after_minutes=0)
            gig = post(desk)
            if mode == 'eta':
                desk.roads['b', 'a']['minutes'] = 500
            elif mode == 'window':
                desk.posts[gig]['stops'][0]['window'] = {'from': 600, 'to': 610}
            elif mode == 'delivery':
                desk.orders['one']['deadline'] = 620
            elif mode == 'expired':
                desk._offer_closed.add(gig)
            elif mode == 'booked':
                desk.booked.add(gig)
            else:
                desk._outbox.append(dict(type='withdraw', gigId=gig))
            self.assertEqual(poll(desk, 600), [], mode)

    def test_uses_current_and_queued_reprice_fee(self):
        desk = desk_for(epsilon_offers=1)
        gig = post(desk)
        desk._outbox.append(dict(type='reprice', gigId=gig, schedule=[dict(at=700, feeCents=12345)]))
        actions = poll(desk, 720)
        self.assertEqual({a['feeCents'] for a in actions}, {12345})
        desk.read_results([dict(type='reprice', gigId=gig, schedule=[dict(at=700, feeCents=9876)])], [dict(ok=True)])
        self.assertEqual(desk._offer_schedules[gig][0]['feeCents'], 9876)

    def test_delivered_driver_position_and_busy_finish(self):
        desk = desk_for(epsilon_offers=1, offer_after_minutes=0)
        old = post(desk, 'old')
        desk.handle(dict(seq=1, at=600, kind='gig_booked', gigId=old, driverId='d0', feeCents=10000))
        desk.handle(dict(seq=2, at=610, kind='picked_up', gigId=old, orderId='old', leg=0, placeId='a'))
        free, origin, finishing = desk._offer_origins()['d0']
        self.assertEqual((free, origin, finishing), (630, 'b', True))
        desk.now = 640
        desk.handle(dict(seq=3, at=640, kind='delivered', gigId=old, orderId='old', leg=0, placeId='b'))
        self.assertEqual(desk._offer_origins()['d0'], (640, 'b', True))
        # It finishes at b, but its home is d and next pickup is b: no app notice.
        desk._offer_roster['d0']['homePlaceId'] = 'd'
        desk._offer_outside['b'].append(desk._offer_roster['d0'])
        order = pair_order(desk, 'next', 'b', 'c', deadline=1500)
        desk.orders['next'] = order
        desk.post(order, [0])
        actions, desk._outbox = desk._outbox, []
        desk.read_results(actions, desk.world.act(actions))
        offers = poll(desk, 640)
        self.assertEqual(offers[0]['driverId'], 'd0')

    def test_answer_accepts_booking_and_clears_pending(self):
        desk = desk_for(epsilon_offers=1, offer_after_minutes=0)
        gig = post(desk)
        actions = poll(desk, 600)
        driver = actions[0]['driverId']
        desk.handle(dict(seq=1, at=601, kind='offer_answered', gigId=gig, driverId=driver, answer='accepted'))
        self.assertIn(gig, desk.booked)
        self.assertNotIn(driver, desk._offer_pending[gig])
        self.assertEqual(poll(desk, 630), [])

    def test_timer_works_with_and_without_pairs(self):
        for pairs in (0, 1):
            desk = desk_for(epsilon_offers=1, pairs=pairs, offer_after_minutes=0)
            post(desk)
            _ = desk.outbox  # runner's batch boundary
            self.assertEqual(desk.next_pair_wake(), 630)
            step = desk.world.advance(until=['price_request'], max=1000)
            self.assertEqual(step['now'], 630)

    def test_rejoin_quarantines_unknown_daily_quota(self):
        desk = desk_for(epsilon_offers=1)
        gig = post(desk, latest=3 * DAY)
        for stop in desk.posts[gig]['stops']:
            stop['window']['to'] = 3 * DAY
        snapshot = dict(now=720, orders=list(desk.orders.values()), gigs=[], openRequests=[], driverPositions=[])
        with patch('recovery.rejoin_model'):
            desk.rejoin(snapshot, [])
        self.assertEqual(poll(desk, 800), [])
        self.assertEqual(len(poll(desk, DAY + 420)), 3)

    def test_offer_diagnostics_are_saved_without_reading_traces(self):
        from compare import MetricsJournal
        journal = MetricsJournal(io.StringIO())
        journal.record('epsilon_offer_result', ok=True)
        journal.record('epsilon_offer_result', ok=False)
        journal.record('event', event=dict(kind='offer_answered', answer='accepted'))
        self.assertEqual(journal.metrics()['offers'], dict(sent=2, ok=1, rejected=1, accepted=1))

    def test_full_practice_loop_sends_offers_and_reaches_end_with_pairs_on_or_off(self):
        from dispatch import play_model
        from tests.test_dispatch_performance import SyntheticWeek

        class Week(SyntheticWeek):
            def __init__(self):
                super().__init__()
                self.initial_map['places'] = [dict(id=p, lat=60, lon=24 + i) for i, p in enumerate('abcd')]
                self.initial_roster[0]['homePlaceId'] = 'd'

        for pairs in (0, 1):
            with self.subTest(pairs=pairs):
                world = Week()
                play_model(world, 8, Journal(io.StringIO()),
                           lambda w, l, n, j: make_delta(w, l, n, j, epsilon_offers=1, pairs=pairs), fast=True)
                self.assertTrue(any(a['type'] == 'offer' for a in world.actions))
                self.assertEqual(world.now, 1200)
