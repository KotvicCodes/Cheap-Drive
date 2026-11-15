"""Three-car planning and fallback contracts use an offline action recorder."""
from copy import deepcopy
import io
import json
import unittest

from dispatch import Journal
from models.delta import make_delta
from recovery import model_state, restore_state, _restore_pairs
from tests.test_gamma_pairs import PairWorld, pair_order


class ChainPlannerTests(unittest.TestCase):
    def desk(self, **settings):
        settings.setdefault('pair_chain3', 1)
        return make_delta(PairWorld(), 8, 600, Journal(io.StringIO()), pairs=1,
                          delta_wide_windows=1, delta_pairing='extended', **settings)

    def orders(self, desk):
        orders = [pair_order(desk, 'one', 'a', 'b', deadline=5000),
                  pair_order(desk, 'two', 'b', 'c', deadline=5000),
                  pair_order(desk, 'three', 'c', 'd', deadline=5000)]
        for order in orders:
            order['legs'][0]['car']['premium'] = False
        desk.orders.update({o['id']: o for o in orders})
        return orders

    def accept(self, desk):
        actions, desk.outbox = desk.outbox, []
        desk.read_results(actions, desk.world.act(actions))
        return actions

    def committed(self):
        desk = self.desk()
        orders = self.orders(desk)
        self.assertTrue(desk._try_pair(orders[0]))
        self.accept(desk)
        gig = desk.gigs_of('one')[0]
        return desk, orders, desk._pairs[gig], gig

    def test_three_sequential_cars_have_six_legal_stops_and_combined_offer(self):
        desk = self.desk()
        orders = self.orders(desk)
        plan, reason = desk._plan_chain(orders)
        self.assertIsNone(reason)
        self.assertEqual(plan.orders, ('one', 'two', 'three'))
        self.assertEqual([s['kind'] for s in plan.action['stops']], ['pickup', 'delivery'] * 3)
        self.assertEqual(plan.drive_minutes, 90)
        self.assertEqual(plan.action['schedule'][0]['feeCents'], round(plan.typical * .68))
        self.assertTrue(all(s['window']['from'] <= s['window']['to'] for s in plan.action['stops']))
        self.assertLess(plan.action['stops'][0]['window']['to'], 5000)

    def test_default_off_preserves_two_car_selection_and_individual_plans(self):
        for enabled, size in ((0, 4), (1, 6)):
            desk = self.desk(pair_chain3=enabled)
            orders = self.orders(desk)
            pair = deepcopy(desk._plan(*orders[:2]))
            self.assertTrue(desk._try_pair(orders[0]))
            self.assertEqual(len(desk.outbox[0]['stops']), size)
            self.assertEqual(desk._plan(*orders[:2]), pair)

    def test_premium_duplicates_drive_and_each_transfer_are_rejected(self):
        desk = self.desk()
        orders = self.orders(desk)
        orders[2]['legs'][0]['car']['premium'] = True
        self.assertEqual(desk._plan_chain(orders)[1], 'chain_ineligible')
        orders[2]['legs'][0]['car']['premium'] = False
        self.assertEqual(desk._plan_chain([orders[0]] * 3)[1], 'chain_ineligible')
        desk.roads['c', 'd']['minutes'] = 500
        self.assertEqual(desk._plan_chain(orders)[1], 'drive_too_long')
        desk.roads['c', 'd']['minutes'] = 30
        orders[2]['legs'][0]['pickup']['placeId'] = 'a'
        desk.roads['c', 'a']['km'] = 36
        self.assertEqual(desk._plan_chain(orders)[1], 'transfer_too_far')

    def test_third_pickup_wait_and_delivery_stop_spare_are_enforced(self):
        desk = self.desk()
        orders = self.orders(desk)
        orders[2]['legs'][0]['pickup']['window']['from'] = 2000
        self.assertEqual(desk._plan_chain(orders)[1], 'idle_too_long')
        orders[2]['legs'][0]['pickup']['window']['from'] = 480
        orders[2]['legs'][0]['delivery']['window']['to'] = 930
        plan, reason = desk._plan_chain(orders)
        self.assertIsNone(reason)
        self.assertEqual(plan.last_start - plan.latest_safe, 60)

    def test_chain_counts_self_roads_without_changing_pair_policy(self):
        desk = self.desk()
        orders = self.orders(desk)
        desk.roads['b', 'b'] = {'km':12, 'minutes':25}
        desk.roads['c', 'c'] = {'km':12, 'minutes':25}
        self.assertEqual(desk._plan_chain(orders)[0].drive_minutes, 140)
        self.assertEqual(desk._plan(*orders[:2])[0].drive_minutes, 60)

    def test_timer_splits_all_three_into_singles_and_never_releases_booked_chain(self):
        for booked in (False, True):
            desk, orders, plan, gig = self.committed()
            if booked:
                desk.booked.add(gig)
            desk.now += 60
            desk.poll_driver_side()
            self.assertEqual(plan.active, booked)
            self.assertEqual(len(desk.outbox), 0 if booked else 3)
            self.assertFalse(any(a['type'] == 'release' for a in desk.world.actions))

    def test_failed_chain_post_restores_all_singles(self):
        desk = self.desk()
        orders = self.orders(desk)
        self.assertTrue(desk._try_pair(orders[0]))
        action = desk.outbox.pop()
        desk.read_results([action], [{'ok':False, 'reason':'offline rejection'}])
        self.assertEqual({a['stops'][0]['orderId'] for a in desk.outbox}, {'one', 'two', 'three'})
        self.assertTrue(all(len(a['stops']) == 2 for a in desk.outbox))

    def test_withdrawal_race_does_not_post_chain_or_release_any_order(self):
        desk = self.desk()
        orders = self.orders(desk)
        for order in orders:
            desk._post_single(order['id'])
        self.accept(desk)
        desk.world.fail_withdraw = True
        self.assertFalse(desk._try_pair(orders[0]))
        self.assertEqual(desk.outbox, [])
        self.assertFalse(any(a['type'] == 'release' for a in desk.world.actions))

    def test_cancel_one_car_keeps_two_survivors_protected_then_drop_rescues_both(self):
        desk, orders, plan, gig = self.committed()
        desk.booked.add(gig)
        desk.handle(dict(kind='order_cancelled', at=600, seq=1, orderId='two',
                         gigs=[dict(gigId=gig, outcome='shortened')]))
        self.assertTrue(plan.active)
        self.assertEqual(plan.orders, ('one', 'three'))
        self.assertEqual({s['orderId'] for s in desk.posts[gig]['stops']}, {'one', 'three'})
        desk.handle(dict(kind='gig_dropped', at=600, seq=2, gigId=gig, driverId='d'))
        self.assertEqual({a['stops'][0]['orderId'] for a in desk.outbox}, {'one', 'three'})

    def test_failed_visit_only_retries_that_car(self):
        desk, orders, plan, gig = self.committed()
        desk.handle(dict(kind='gig_started', at=600, seq=1, gigId=gig, driverId='d'))
        desk.handle(dict(kind='visit_failed', at=600, seq=2, gigId=gig, orderId='two', leg=0, reason='closed'))
        self.assertEqual(desk.gigs_of('one'), [gig])
        self.assertEqual(desk.gigs_of('three'), [gig])
        self.assertEqual({s['orderId'] for s in desk.outbox[0]['stops']}, {'two'})

    def test_checkpoint_and_public_snapshot_restore_all_six_stops(self):
        desk, orders, plan, gig = self.committed()
        rebuilt = self.desk()
        restore_state(rebuilt, json.loads(json.dumps(model_state(desk))))
        self.assertEqual(rebuilt._pairs[gig].action, plan.action)
        rebuilt._pairs.clear()
        snapshot = dict(gigs=[dict(id=gig, postedAt=600, status='open', **deepcopy(plan.action))])
        self.assertEqual(_restore_pairs(rebuilt, snapshot), [])
        self.assertEqual(rebuilt._pairs[gig].orders, plan.orders)
        self.assertEqual(rebuilt._pairs[gig].latest_safe, plan.latest_safe)

    def test_chain_settings_validate_strictly(self):
        for name in ('pair_chain3', 'chain_transfer_km', 'chain_max_drive_minutes', 'chain_fee_bps'):
            for value in (True, -1, '1', None):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, name):
                    self.desk(**{name:value})
        for name, value in (('pair_chain3', 2), ('chain_max_drive_minutes', 721), ('chain_fee_bps', 0)):
            with self.assertRaisesRegex(ValueError, name):
                self.desk(**{name:value})
