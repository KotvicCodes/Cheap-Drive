"""Guarded intake preserves defaults and respects combined/split visits."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import unittest

from dispatch import Journal, play_model
from models.delta import make_delta
from models.notes import NoteFacts
from recovery import model_state, restore_state
from spread.starter import DAY, Retry
from tests.test_gamma_pairs import PairWorld, pair_order
from tests.test_performance import LossWorld


class DeltaIntakeTests(unittest.TestCase):
    def desk(self, **settings):
        return make_delta(PairWorld(), 8, 600, Journal(io.StringIO()),
                          delta_rescue_windows=1, delta_private_delivery_rescue=1,
                          **settings)

    def trade(self, desk, identity='trade'):
        order = pair_order(desk, identity, deadline=3 * DAY)
        first = order['legs'][0]
        first['delivery'].update(privateAddress=True, window={'from': DAY + 900, 'to': DAY + 960})
        second = deepcopy(first)
        second['pickup'], second['delivery'] = deepcopy(first['delivery']), deepcopy(first['pickup'])
        order['legs'].append(second)
        order['deliveredAt'].append(None)
        req = desk.requests[identity]
        req['legs'] = deepcopy(order['legs'])
        req['options'] = [dict(kind='next_day', deadline=3 * DAY, listPriceCents=30000)]
        return req, order

    def test_off_keeps_actions_calls_score_journal_identical(self):
        results = []
        for knobs in ({}, {'delta_guarded_trade_ins': 0, 'delta_corridor_open_cap': 0}):
            world, stream = LossWorld(), io.StringIO()
            with redirect_stdout(io.StringIO()):
                score = play_model(world, 8, Journal(stream),
                                   lambda w, l, n, j: make_delta(w, l, n, j, pairs=1, **knobs))
            results.append((world.sent, world.calls, score, stream.getvalue()))
        self.assertEqual(*results)

    def test_round_trip_gate_and_unbooked_capacity(self):
        desk = self.desk(trade_ins=1, delta_guarded_trade_ins=1, delta_trade_open_cap=1)
        req, order = self.trade(desk)
        self.assertTrue(desk.eligible_options(req, 20, 0)[0])
        desk.roads['a', 'b']['minutes'] = 541
        self.assertEqual(desk.eligible_options(req, 20, 0)[1], 'guarded trade-in route')
        desk.roads['a', 'b']['minutes'] = 30
        desk.orders[order['id']] = order
        self.assertEqual(desk.eligible_options(req, 20, 0)[1], 'guarded trade-in capacity')
        desk.leg_gigs[order['id']] = {0: 'g', 1: 'g'}
        desk.booked.add('g')
        self.assertTrue(desk.eligible_options(req, 20, 0)[0])
        req['legs'][1]['delivery']['placeId'] = 'c'
        self.assertEqual(desk.eligible_options(req, 20, 0)[1], 'guarded trade-in route')
        req['legs'].append(deepcopy(req['legs'][0]))
        self.assertEqual(desk.eligible_options(req, 30, 0)[1], 'guarded trade-in route')

    def test_shared_pickup_omits_window_and_scopes_note_plates(self):
        desk = self.desk(trade_ins=1, delta_guarded_trade_ins=1)
        req, order = self.trade(desk)
        facts = NoteFacts(plates=True, ready_at=DAY + 600,
                          pickup_closes=840, delivery_closes=1000)
        stops = desk._post_windows(order, [0, 1], facts, Retry())
        self.assertGreaterEqual(stops[0]['window']['from'], DAY)
        self.assertLessEqual(stops[0]['window']['to'], DAY + 840)
        self.assertTrue(stops[0]['withPlates'])
        self.assertFalse(stops[2]['withPlates'])
        self.assertNotIn('window', stops[2])
        self.assertEqual(desk.opening_fee_for(order), 10000)
        split = desk._post_windows(order, [1], facts, Retry())
        self.assertEqual(split[0]['window'], {'from': DAY + 900, 'to': DAY + 960})
        retry = desk._post_windows(order, [1], facts, Retry(plates=True))
        self.assertTrue(retry[0]['withPlates'])

    def test_shared_slot_is_protected_but_split_slot_is_strict(self):
        desk = self.desk(trade_ins=1, delta_guarded_trade_ins=1)
        req, order = self.trade(desk)
        # Independent old-car slot ends earlier than the new-car appointment.
        req['legs'][1]['pickup']['window'] = {'from': 600, 'to': 700}
        self.assertIsNotNone(desk._latest_note_route(req, order['deadline']))
        self.assertIsNone(desk._latest_note_route(req, order['deadline'], floor=DAY, legs=[1]))

    def test_outgoing_windows_leave_time_for_the_return(self):
        desk = self.desk(trade_ins=1, delta_guarded_trade_ins=1)
        req, order = self.trade(desk)
        order['legs'][1]['delivery']['window']['to'] = DAY + 970
        stops = desk._post_windows(order, [0, 1], NoteFacts(), Retry())
        self.assertEqual(stops[1]['window']['to'], DAY + 940)
        self.assertEqual(stops[0]['window']['to'], DAY + 910)

    def test_corridor_roster_guard_requires_known_sufficient_supply(self):
        desk = self.desk(delta_intake_min_roster=700)
        self.assertFalse(desk._intake_headroom())
        for roster, expected in ((699, False), (700, True), (701, True)):
            desk.supply_roster_size = roster
            self.assertEqual(desk._intake_headroom(), expected)

    def test_slack_relaxation_only_recovers_unquoted_ordinary_short_work(self):
        desk = self.desk(delta_relaxed_slack_minutes=240, delta_intake_max_backlog=0)
        order = pair_order(desk, 'short', deadline=1000)
        req = desk.requests['short']
        req['options'] = [dict(kind='same_day', deadline=1000, listPriceCents=30000)]
        self.assertTrue(desk.eligible_options(req, 10, 0)[0])
        self.assertEqual(desk.settings.min_slack_minutes, 480)
        self.assertFalse(desk.eligible_options(req, 151, 0)[0])
        req['legs'][0]['car']['premium'] = True
        self.assertFalse(desk.eligible_options(req, 10, 0)[0])
        req['legs'][0]['car']['premium'] = False
        req['legs'][0]['pickup']['privateAddress'] = True
        self.assertFalse(desk.eligible_options(req, 10, 0)[0])
        req['legs'][0]['pickup']['privateAddress'] = False
        desk.orders[order['id']] = order
        self.assertFalse(desk.eligible_options(req, 10, 0)[0])

    def test_trade_booking_restore_and_separate_failed_visit(self):
        desk = self.desk(trade_ins=1, delta_guarded_trade_ins=1, pairs=1)
        req, order = self.trade(desk)
        desk.handle(dict(seq=1, at=600, kind='order_won', order=order))
        self.assertEqual(len(desk.world.actions[-1]['stops']), 4)
        gig = desk.leg_gigs[order['id']][0]
        self.assertEqual(desk.leg_gigs[order['id']][1], gig)
        desk.handle(dict(seq=2, at=600, kind='gig_booked', gigId=gig))
        other = self.desk(trade_ins=1, delta_guarded_trade_ins=1, pairs=1)
        restore_state(other, deepcopy(model_state(desk)))
        self.assertEqual(other.leg_gigs, desk.leg_gigs)
        self.assertEqual(other.booked, desk.booked)
        self.assertEqual(other.fees_for(other.orders[order['id']], 2), desk.fees_for(order, 2))
        other.handle(dict(seq=3, at=DAY + 900, kind='visit_failed',
                          orderId=order['id'], leg=1, gigId=gig, reason='no_plates'))
        action = other.outbox[-1]
        self.assertEqual(len(action['stops']), 2)
        self.assertEqual(action['stops'][0]['leg'], 1)
        self.assertTrue(action['stops'][0]['withPlates'])
        self.assertIn('window', action['stops'][0])

    def test_corridor_expansion_closes_on_backlog_and_never_changes_settings(self):
        desk = self.desk(max_km=500, long_max_km=700, delta_corridor_open_cap=5,
                         delta_intake_max_backlog=3)
        desk.roads['a', 'b']['km'] = 600
        for index in range(3):
            order = pair_order(desk, str(index), deadline=5 * DAY)
            desk.orders[str(index)] = order
        req = deepcopy(desk.requests['0'])
        req['options'] = [dict(kind='next_day', deadline=5 * DAY, listPriceCents=30000)]
        self.assertTrue(desk.eligible_options(req, 600, 0)[0])
        self.assertEqual(desk.settings.long_open_cap, 3)
        order = pair_order(desk, 'extra', deadline=5 * DAY)
        desk.orders['extra'] = order
        self.assertEqual(desk.eligible_options(req, 600, 0)[1], 'long route capacity')
        other = self.desk(max_km=500, long_max_km=700, delta_corridor_open_cap=5,
                          delta_intake_max_backlog=3)
        other.roads['a', 'b']['km'] = 600
        restore_state(other, deepcopy(model_state(desk)))
        self.assertEqual(other.eligible_options(req, 600, 0), desk.eligible_options(req, 600, 0))

    def test_validation(self):
        for knobs in ({'delta_guarded_trade_ins': True}, {'delta_guarded_trade_ins': 1},
                      {'delta_trade_max_drive_minutes': 721}, {'delta_trade_open_cap': 0},
                      {'delta_intake_min_roster': -1}, {'delta_corridor_open_cap': True}):
            with self.subTest(knobs=knobs), self.assertRaises(ValueError):
                self.desk(**knobs)
