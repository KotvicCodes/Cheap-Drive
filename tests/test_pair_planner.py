"""Pair-specific promises and rescue offers; all worlds here are offline."""
from copy import deepcopy
import io
import unittest

from dispatch import Journal
from models.delta import make_delta
from tests.test_gamma_pairs import PairWorld, pair_order


class PairPlannerTests(unittest.TestCase):
    def desk(self, **settings):
        return make_delta(PairWorld(), 8, 600, Journal(io.StringIO()), pairs=1,
                          delta_wide_windows=1, delta_pairing='extended', **settings)

    def orders(self, desk):
        return pair_order(desk, 'one', deadline=5000), pair_order(desk, 'two', 'b', 'c', deadline=1200)

    def test_backward_bounds_protect_second_order_and_leave_solo_unchanged(self):
        desk = self.desk(pair_tight_windows=1)
        first, second = self.orders(desk)
        solo = deepcopy(desk._single_action(first))
        plan, reason = desk._plan(first, second)
        self.assertIsNone(reason)
        bounds = [s['window']['to'] for s in plan.action['stops']]
        self.assertEqual(bounds, [990, 1020, 1020, 1200])
        self.assertEqual(desk._single_action(first), solo)
        self.assertGreater(solo['stops'][0]['window']['to'], bounds[0])
        self.assertEqual(plan.last_start, bounds[0])

    def test_zero_spare_bounds_keep_feasible_last_hour(self):
        desk = self.desk(pair_tight_windows=1)
        first = pair_order(desk, 'one', deadline=1200)
        second = pair_order(desk, 'two', 'b', 'c', deadline=1200)
        first['lastPickupAt'] = second['lastPickupAt'] = 1200
        plan, _ = desk._plan(first, second)
        self.assertEqual(plan.action['stops'][0]['window']['to'], 1140)
        self.assertGreater(plan.last_start, plan.latest_safe)
        self.assertEqual(plan.action['stops'][3]['window']['to'], 1200)

    def test_plates_and_charge_are_applied_on_correct_sides_of_visit(self):
        desk = self.desk(pair_tight_windows=1)
        first, second = self.orders(desk)
        original = desk._single_action
        def action(order):
            result = original(order)
            result['stops'][0].update(withPlates=True, withCharging=True)
            return result
        desk._single_action = action
        plan, reason = desk._plan(first, second)
        self.assertIsNone(reason)
        bounds = [s['window']['to'] for s in plan.action['stops']]
        self.assertEqual(bounds, [920, 990, 1020, 1200])
        self.assertEqual(plan.last_start, bounds[0] - 30)

    def test_default_retains_original_wide_pair_windows(self):
        desk = self.desk()
        first, second = self.orders(desk)
        plan, _ = desk._plan(first, second)
        self.assertEqual(plan.action['stops'], desk._single_action(first)['stops'] + desk._single_action(second)['stops'])

    def test_rescue_floor_uses_both_current_single_offers_and_steps_before_split(self):
        desk = self.desk(pair_rescue_floor_bps=8500, pair_rescue_step_minutes=25)
        first, second = self.orders(desk)
        desk.orders.update(one=first, two=second)
        desk.leg_gigs['one'] = {0: 'old'}
        desk.first_posted['one'] = -3000
        actions = [desk._single_action(o) for o in (first, second)]
        current = sum(a['schedule'][0]['feeCents'] for a in actions)
        plan, _ = desk._plan(first, second)
        schedule = plan.action['schedule']
        self.assertEqual(schedule[0]['feeCents'], max(round(plan.typical * .78), (current * 8500 + 9999) // 10000))
        self.assertEqual(schedule[1]['at'], 625)
        self.assertGreater(schedule[1]['feeCents'], schedule[0]['feeCents'])
        self.assertTrue(all(a['at'] < b['at'] and a['feeCents'] < b['feeCents'] for a, b in zip(schedule, schedule[1:])))

    def test_rescue_changes_do_not_change_fresh_pair_schedule(self):
        for settings in ({}, {'pair_rescue_floor_bps':8500, 'pair_rescue_step_minutes':25}):
            desk = self.desk(**settings)
            first, second = self.orders(desk)
            plan, _ = desk._plan(first, second)
            self.assertEqual(plan.action['schedule'], desk._pair_schedule(plan.typical, plan.last_start, False))

    def test_strict_validation(self):
        for name in ('pair_tight_windows', 'pair_rescue_floor_bps', 'pair_rescue_step_minutes', 'pair_rescue_step_bps'):
            for value in (True, -1, '1', None):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, name):
                    self.desk(**{name:value})
        for name, value in (('pair_tight_windows',2), ('pair_rescue_floor_bps',10001)):
            with self.assertRaisesRegex(ValueError, name):
                self.desk(**{name:value})


class PairRescueTests(unittest.TestCase):
    def desk(self, **settings):
        return make_delta(PairWorld(), 8, 600, Journal(io.StringIO()), pairs=1,
                          delta_wide_windows=1, delta_pairing='extended', **settings)

    def failed(self, desk, first, second):
        desk.orders.update({o['id']: o for o in (first, second)})
        pair, reason = desk._plan(first, second)
        self.assertIsNone(reason)
        desk._split_pair(pair, 'time')
        desk._outbox.clear()
        return pair

    def test_retry_uses_different_partner_and_stops_after_two_failures(self):
        desk = self.desk(pair_retry_limit=2)
        one = pair_order(desk, 'one')
        two = pair_order(desk, 'two', 'b', 'c')
        three = pair_order(desk, 'three', 'b', 'd')
        self.failed(desk, one, two)
        self.assertTrue(desk._eligible(one))
        self.assertEqual(desk._plan(two, one), (None, 'failed_pair'))
        self.failed(desk, one, three)
        self.assertFalse(desk._eligible(one))
        self.assertTrue(desk._eligible(two))
        self.assertEqual(desk._pair_failures['one'], 2)

    def test_retry_transfer_is_restricted_and_default_still_bans_all_partners(self):
        for limit in (0, 2):
            desk = self.desk(pair_retry_limit=limit)
            one = pair_order(desk, 'one')
            two = pair_order(desk, 'two', 'b', 'c')
            three = pair_order(desk, 'three', 'd', 'c')
            desk.roads['b', 'd'] = {'km':31, 'minutes':30}
            self.failed(desk, one, two)
            self.assertEqual(desk._eligible(one), bool(limit))
            if limit:
                self.assertEqual(desk._plan(one, three), (None, 'retry_transfer_too_far'))
                desk.roads['b', 'd']['km'] = 30
                self.assertIsNotNone(desk._plan(one, three)[0])

    def test_aged_guard_requires_both_age_and_fee_conditions(self):
        desk = self.desk(pair_aged_guard_minutes=180)
        one = pair_order(desk, 'one')
        desk.orders['one'] = one
        desk.leg_gigs['one'] = {0:'old'}
        desk.first_posted['one'] = 420
        original = desk._single_action
        def action(order):
            result = original(order)
            result['schedule'] = [{'at':desk.now, 'feeCents':desk.requests['one']['referenceFeeCents']}]
            return result
        desk._single_action = action
        self.assertTrue(desk._eligible(one))
        desk.now = 601
        self.assertFalse(desk._eligible(one))
        desk._single_action = original
        self.assertTrue(desk._eligible(one))

    def test_shortened_pair_becomes_single_and_survivor_can_repair_after_drop(self):
        for outcome in ('shortened', 'continues'):
            desk = self.desk(pair_cancel_cleanup=1)
            one = pair_order(desk, 'one')
            two = pair_order(desk, 'two', 'b', 'c')
            desk.orders.update(one=one, two=two)
            pair, _ = desk._plan(one, two)
            desk._pending_pairs[id(pair.action)] = pair
            desk.read_results([pair.action], [{'ok':True, 'id':'g'}])
            desk.booked.add('g')
            desk.handle({'kind':'order_cancelled','at':600,'seq':1,'orderId':'one',
                         'gigs':[{'gigId':'g','outcome':outcome}]})
            self.assertFalse(pair.active)
            self.assertEqual({s['orderId'] for s in desk.posts['g']['stops']}, {'two'})
            self.assertNotIn('two', desk._split_orders)
            desk.booked.discard('g')
            desk._started.discard('g')
            self.assertTrue(desk._eligible(two))

    def test_new_rescue_controls_validate_strictly(self):
        for name in ('pair_retry_limit','pair_retry_transfer_km','pair_cancel_cleanup',
                     'pair_aged_guard_minutes','pair_aged_guard_bps'):
            for value in (True, -1, '1', None):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, name):
                    self.desk(**{name:value})

    def test_cancelled_partner_does_not_consume_survivor_retry_budget(self):
        desk = self.desk(pair_retry_limit=2, pair_cancel_cleanup=1)
        one = pair_order(desk, 'one')
        two = pair_order(desk, 'two', 'b', 'c')
        desk.orders.update(one=one, two=two)
        pair, _ = desk._plan(one, two)
        desk._split_pair(pair, 'order_cancelled', omit=('one',))
        self.assertEqual(desk._pair_failures['two'], 0)
        self.assertNotIn('two', desk._split_orders)

    def test_rejected_post_records_failed_combination_and_restores_singles(self):
        desk = self.desk(pair_retry_limit=2)
        one = pair_order(desk, 'one')
        two = pair_order(desk, 'two', 'b', 'c')
        desk.orders.update(one=one, two=two)
        pair, _ = desk._plan(one, two)
        desk._pending_pairs[id(pair.action)] = pair
        desk.read_results([pair.action], [{'ok':False, 'reason':'rejected'}])
        self.assertEqual(desk._failed_pairs, {frozenset(('one','two'))})
        self.assertEqual([len(a['stops']) for a in desk._outbox], [2,2])
        self.assertTrue(desk._eligible(one))
        self.assertEqual(desk._plan(one,two), (None,'failed_pair'))

    def test_self_time_counts_map_minutes_without_changing_transfer_preference(self):
        desk = self.desk(pair_self_time=1, pair_tight_windows=1)
        desk.roads['b','b'] = {'km':12, 'minutes':25}
        one = pair_order(desk, 'one')
        two = pair_order(desk, 'two', 'b', 'c')
        plan, _ = desk._plan(one,two)
        self.assertEqual(plan.drive_minutes,85)
        self.assertEqual(plan.transfer_km,0)
        self.assertEqual(desk._road('b','b'), {'km':0,'minutes':0})

    def test_economic_rank_favors_larger_reference_savings_when_feasible(self):
        for enabled, expected in ((0,'cheap'),(1,'rich')):
            desk = self.desk(pair_economic_rank=enabled)
            new = pair_order(desk,'new')
            cheap = pair_order(desk,'cheap','b','c')
            rich = pair_order(desk,'rich','b','d')
            desk.requests['cheap']['referenceFeeCents'] = 3000
            desk.requests['rich']['referenceFeeCents'] = 20000
            desk.orders.update(new=new, cheap=cheap, rich=rich)
            self.assertTrue(desk._try_pair(new))
            self.assertIn(expected, next(iter(desk._pending_pairs.values())).orders)

    def test_planner_toggles_validate_strictly(self):
        for name in ('pair_self_time','pair_economic_rank'):
            for value in (True,-1,2,'1',None):
                with self.subTest(name=name,value=value), self.assertRaisesRegex(ValueError,name):
                    self.desk(**{name:value})

    def test_delta_latest0_alias_and_checkpoint_reconstruction(self):
        from recovery import model_state, restore_state, _restore_pairs
        desk = self.desk(delta_pair_latest0_windows=1)
        one = pair_order(desk,'one',deadline=5000)
        two = pair_order(desk,'two','b','c',deadline=1200)
        desk.orders.update(one=one,two=two)
        pair, _ = desk._plan(one,two)
        desk._pending_pairs[id(pair.action)] = pair
        desk.read_results([pair.action],[{'ok':True,'id':'g'}])
        state = json_roundtrip(model_state(desk))
        rebuilt = self.desk(delta_pair_latest0_windows=1)
        restore_state(rebuilt,state)
        self.assertEqual(rebuilt._pairs['g'].action['stops'],pair.action['stops'])
        # Also reconstruct from the public gig without the pair checkpoint.
        rebuilt._pairs.clear()
        gig = dict(id='g',postedAt=600,status='open',**deepcopy(pair.action))
        self.assertEqual(_restore_pairs(rebuilt,{'gigs':[gig]}),[])
        self.assertEqual(rebuilt._pairs['g'].action['stops'],pair.action['stops'])

    def test_delta_alias_rejects_nonbinary_values(self):
        for value in (True,-1,2,'1',None):
            with self.assertRaisesRegex(ValueError,'delta_pair_latest0_windows'):
                self.desk(delta_pair_latest0_windows=value)


def json_roundtrip(value):
    import json
    return json.loads(json.dumps(value))
