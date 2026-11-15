"""Synthetic model contracts; no network clients or simulated worlds."""
from copy import deepcopy
from dataclasses import fields
import io
import json
from pathlib import Path
import unittest

from dispatch import Journal
from models.delta import make_delta
from models.gamma import GammaSettings, make_gamma
from models.gamma_notes import make_gamma_notes
from models.notes import NoteFacts
from recovery import model_state, replay_history, restore_state
from spread.starter import DAY, Retry
from tests.test_gamma import GammaWorld, request
from tests.test_gamma_pairs import PairWorld, pair_order
from tests.test_notes import order_for


ROOT = Path(__file__).resolve().parents[1]
EARLY = json.loads((ROOT / 'models/epsilon-early.json').read_text())['settings']


def desk_for(factory=make_delta, world=None, **settings):
    return factory(world or GammaWorld(), 8, 500, Journal(io.StringIO()), **settings)


def scripted_early_actions(**overrides):
    """Also used to capture the golden actions from the untouched base commit."""
    desk = desk_for(**{**EARLY, **overrides})
    actions = []

    def event(at, kind, **data):
        desk.now = at
        desk.handle(dict(seq=0, at=at, kind=kind, **deepcopy(data)))
        queued, desk.outbox = desk.outbox, []
        actions.extend(deepcopy(queued))
        desk.read_results(queued, [dict(ok=True, id=f'g-{len(actions)}') for _ in queued])

    req = request(slacks=(600, 2200, 3600))
    event(500, 'price_request', request=req)
    event(515, 'order_won', order=order_for(req, deadline=1295))
    gig = desk.leg_gigs[req['id']][0]
    event(520, 'gig_booked', gigId=gig, driverId='d', feeCents=9600)
    event(530, 'gig_dropped', gigId=gig, driverId='d')
    event(540, 'price_request', request=request(identity='two', slacks=(600, 2200)))
    event(550, 'order_lost', requestId='two')
    event(560, 'ledger', line=dict(kind='revenue', orderId=req['id']))
    event(700, 'delivered', orderId=req['id'], leg=0, gigId=gig, placeId='tampere')
    event(710, 'price_request', request={**request(identity='three', slacks=(600, 2200)),
                                      'arrivedAt': 710, 'respondBy': 725})
    return dict(actions=actions, markup=desk.markup, trust=desk.trust)


class SupplyRiskTests(unittest.TestCase):
    def desk(self, count=0, **settings):
        world = GammaWorld()
        world.initial_roster = [dict(id=f'd-{i}', homePlaceId='helsinki') for i in range(count)]
        return desk_for(make_gamma_notes, world, **settings)

    def test_radius_is_directed_configurable_and_counts_unique_drivers(self):
        world = GammaWorld()
        world.initial_roster = [dict(id='one', homePlaceId='espoo')] * 2
        for road in world.initial_map['roads']:
            if (road['from'], road['to']) == ('espoo', 'helsinki'):
                road['km'] = 60
        desk = desk_for(make_gamma, world, supply_risk=1)
        self.assertEqual(desk.supply_risk_nearby['helsinki'], 1)
        self.assertEqual(desk.near30['helsinki'], 0)
        smaller = desk_for(make_gamma, world, supply_risk=1, supply_risk_radius_km=59)
        self.assertEqual(smaller.supply_risk_nearby['helsinki'], 0)
        self.assertEqual(smaller.supply_risk_nearby['espoo'], 1)

    def test_risk_tracks_supply_pickup_day_slack_and_drive(self):
        req = request(slacks=(600, 2200))
        thin, covered = self.desk(supply_risk=1), self.desk(6, supply_risk=1)
        same, future = req['options']
        self.assertEqual(thin.option_late_risk_bps(req, same), 1840)
        self.assertEqual(covered.option_late_risk_bps(req, same), 1120)
        self.assertEqual(covered.option_late_risk_bps(req, future), 260)
        covered.roads['helsinki', 'tampere']['minutes'] = 240
        self.assertEqual(covered.option_late_risk_bps(req, future), 300)
        req['legs'][0]['pickup']['window']['to'] = 1200
        self.assertGreater(covered.option_late_risk_bps(req, future), 300)

    def test_prices_risky_options_declines_extreme_and_discounts_safe(self):
        req = request(slacks=(600, 2200))
        base, thin, covered = self.desk(), self.desk(supply_risk=1), self.desk(6, supply_risk=1)
        for desk in (base, thin, covered):
            desk.quote(deepcopy(req))
        original = base.outbox[-1]['prices']
        self.assertNotIn('same_day', thin.outbox[-1]['prices'])
        self.assertGreater(thin.outbox[-1]['prices']['next_day'], original['next_day'])
        self.assertGreater(covered.outbox[-1]['prices']['same_day'], original['same_day'])
        self.assertLess(covered.outbox[-1]['prices']['next_day'], original['next_day'])
        self.assertGreaterEqual(covered.outbox[-1]['prices']['next_day'], original['next_day'] * .98)

    def test_disabled_and_unknown_supply_leave_quotes_unchanged(self):
        req = request(slacks=(600, 2200))
        baseline = self.desk()
        desks = [self.desk(supply_risk=0, supply_risk_max_bps=0, supply_risk_safe_bps=0),
                 desk_for(make_gamma_notes, supply_risk=1)]
        baseline.quote(deepcopy(req))
        for desk in desks:
            desk.quote(deepcopy(req))
            self.assertEqual(desk.outbox, baseline.outbox)
        world = GammaWorld()
        world.initial_roster = [dict(id='one')]
        unknown = desk_for(make_gamma_notes, world, supply_risk=1)
        unknown.quote(deepcopy(req))
        self.assertEqual(unknown.outbox, baseline.outbox)

    def test_thresholds_and_price_strength_can_be_tuned(self):
        req = request(slacks=(600,))
        desk = self.desk(supply_risk=1, supply_risk_max_bps=1840,
                         supply_risk_price_bps_per_1000=1000)
        desk.quote(req)
        self.assertEqual(desk.outbox[-1]['prices']['same_day'], 44400)
        desk = self.desk(supply_risk=1, supply_risk_max_bps=1839)
        self.assertEqual(desk.eligible_options(req, 200, 0), ([], 'supply timing risk'))


class ArrivalBufferTests(unittest.TestCase):
    def windows(self, desk, req, **changes):
        desk.requests[req['id']] = req
        order = order_for(req, deadline=req['options'][0]['deadline'])
        order.update(changes)
        return desk._post_windows(order, list(range(len(order['legs']))), desk.note_facts(req), Retry())

    def test_buffer_uses_deadline_note_and_site_close_on_gamma_and_early(self):
        for factory, base in ((make_gamma_notes, {}), (make_delta, EARLY)):
            for bound in ('deadline', 'note', 'site'):
                with self.subTest(factory=factory.__name__, bound=bound):
                    req = request(slacks=(1200,))
                    if bound == 'note':
                        req['note'] = dict(text='Destination closes at 18:00', language='en')
                    elif bound == 'site':
                        req['legs'][0]['delivery']['hours'] = dict(opens=0, closes=1080,
                                                                  weekdays=list(range(7)), saturday=None)
                    original = self.windows(desk_for(factory, **base), deepcopy(req))
                    buffered = self.windows(desk_for(factory, **base, arrival_buffer=1), deepcopy(req))
                    self.assertEqual(buffered[-1]['window']['to'], original[-1]['window']['to'] - 30)
                    self.assertLessEqual(buffered[0]['window']['to'], buffered[1]['window']['to'] - 180)
                    self.assertEqual(buffered[-1]['window']['from'], original[-1]['window']['from'])

    def test_infeasible_buffer_falls_back_and_does_not_mutate_order(self):
        req = request(slacks=(10,))
        req['options'][0]['deadline'] = 690  # earliest arrival is 680
        before = deepcopy(req)
        original = self.windows(desk_for(**EARLY), req)
        buffered = self.windows(desk_for(**EARLY, arrival_buffer=1), req)
        self.assertIsNotNone(original)
        self.assertEqual(buffered, original)
        self.assertEqual(req, before)
        shorter = self.windows(desk_for(**EARLY, arrival_buffer=1, arrival_buffer_minutes=5), req)
        self.assertEqual(shorter[-1]['window']['to'], 685)

    def test_disabled_buffer_and_zero_minutes_preserve_windows(self):
        req = request(slacks=(1200,))
        original = self.windows(desk_for(**EARLY), req)
        self.assertEqual(self.windows(desk_for(**EARLY, arrival_buffer=0, arrival_buffer_minutes=9999), req), original)
        self.assertEqual(self.windows(desk_for(**EARLY, arrival_buffer=1, arrival_buffer_minutes=0), req), original)

    def test_wide_window_buffer_moves_latest_visit_out_of_a_closed_night(self):
        req = request(slacks=(1200,))
        req['options'][0]['deadline'] = DAY + 550
        req['legs'][0]['delivery']['hours'] = dict(opens=540, closes=1080,
                                                  weekdays=list(range(7)), saturday=None)
        original = self.windows(desk_for(**EARLY), req)
        buffered = self.windows(desk_for(**EARLY, arrival_buffer=1), req)
        self.assertEqual(original[-1]['window']['to'], DAY + 550)
        self.assertEqual(buffered[-1]['window']['to'], 1050)

    def test_multileg_buffer_propagates_transfer_plates_and_charging(self):
        desk = desk_for(world=PairWorld(), arrival_buffer=1, delta_wide_windows=1)
        desk.now = 600
        order = pair_order(desk, 'trade', deadline=1200)
        order['legs'][0]['car'].update(electric=True, chargePercent=10)
        second = deepcopy(order['legs'][0])
        second['car']['electric'] = False
        second['pickup']['placeId'], second['delivery']['placeId'] = 'c', 'd'
        order['legs'].append(second)
        order['deliveredAt'].append(None)
        facts = NoteFacts(plates=True)
        stops = desk._post_windows(order, [0, 1], facts, Retry())
        self.assertIsNotNone(stops)
        self.assertEqual(stops[-1]['window']['to'], 1170)
        self.assertLessEqual(stops[0]['window']['to'] + 30 + 40, stops[1]['window']['to'])
        self.assertLessEqual(stops[1]['window']['to'] + 30 + 30, stops[2]['window']['to'])
        self.assertLessEqual(stops[2]['window']['to'] + 30, stops[3]['window']['to'])
        desk.settings = GammaSettings(arrival_buffer=1, arrival_buffer_minutes=1000)
        self.assertEqual(desk._post_windows(order, [0, 1], facts, Retry()),
                         desk._build_post_windows(order, [0, 1], facts, Retry()))

    def test_buffer_falls_back_for_whole_pair_when_singles_fit_but_pair_does_not(self):
        def plan(enabled):
            desk = desk_for(world=PairWorld(), pairs=1, arrival_buffer=enabled,
                            pair_arrival_allowance_minutes=0, pair_spare_minutes=0)
            desk.now = 600
            one = pair_order(desk, 'one', deadline=1000)
            two = pair_order(desk, 'two', 'b', 'c', deadline=670)
            one['lastPickupAt'], two['lastPickupAt'] = 970, 640
            return desk._plan(one, two)
        original, reason = plan(0)
        buffered, buffered_reason = plan(1)
        self.assertIsNotNone(original, reason)
        self.assertIsNotNone(buffered, buffered_reason)
        self.assertEqual(buffered.action, original.action)


class StuckWorkTests(unittest.TestCase):
    def seed(self, desk, count=1, *, at=500, pickup='helsinki', dealer='D01', prefix='work'):
        for index in range(count):
            req = request(identity=f'{prefix}-{index}', pickup=pickup, dealer=dealer)
            desk.requests[req['id']] = req
            desk.orders[req['id']] = order_for(req)
            desk.stuck_work_progress[req['id']] = at

    def test_age_is_inclusive_and_limits_are_exceeded_strictly(self):
        desk = desk_for(stuck_work=1)
        self.seed(desk, 16)
        desk.now = 544
        self.assertEqual(desk.stuck_work_counts(request())['local'], 0)
        desk.now = 545
        self.assertEqual(desk.stuck_work_counts(request())['local'], 16)
        self.assertFalse(desk.stuck_work_at_cap(request()))
        self.seed(desk, prefix='extra')
        self.assertTrue(desk.stuck_work_at_cap(request()))
        self.assertEqual(desk.eligible_options(request(), 200, 0), ([], 'aged workload capacity'))

    def test_national_yard_and_broad_backlog_gates_independently(self):
        for setting, count, at in (('stuck_work_national_limit', 60, 500),
                                   ('stuck_work_yard_limit', 20, 500),
                                   ('stuck_work_backlog_limit', 120, 600)):
            with self.subTest(setting=setting):
                settings = dict(stuck_work=1, stuck_work_national_limit=1000, stuck_work_local_limit=1000,
                                stuck_work_yard_limit=1000, stuck_work_backlog_limit=1000)
                settings[setting] = count
                desk = desk_for(**settings)
                self.seed(desk, count, at=at)
                desk.now = 600
                self.assertFalse(desk.stuck_work_at_cap(request()))
                self.seed(desk, prefix='extra', at=at)
                self.assertTrue(desk.stuck_work_at_cap(request()))

    def test_local_radius_yard_identity_and_finished_work(self):
        desk = desk_for(stuck_work=1)
        self.seed(desk, pickup='espoo')
        desk.now = 600
        self.assertEqual(desk.stuck_work_counts(request())['local'], 0)
        desk.roads['espoo', 'helsinki']['km'] = 120
        self.assertEqual(desk.stuck_work_counts(request())['local'], 1)
        self.assertEqual(desk.stuck_work_counts(request())['yard'], 0)
        self.assertEqual(desk.stuck_work_counts(request(pickup='espoo', dealer='D02'))['yard'], 0)
        desk.settings = GammaSettings(stuck_work=1, stuck_work_radius_km=119)
        self.assertEqual(desk.stuck_work_counts(request())['local'], 0)
        for status in ('cancelled', 'delivered'):
            desk.orders['work-0']['status'] = status
            self.assertEqual(desk.stuck_work_counts(request())['national'], 0)

    def test_pending_quotes_half_weight_and_outcomes_release_reservations(self):
        desk = desk_for(stuck_work=1, stuck_work_backlog_limit=1, stuck_work_yard_limit=1)
        for i in range(3):
            req = request(identity=f'pending-{i}')
            desk.quote(req)
        counts = desk.stuck_work_counts(request())
        self.assertEqual(counts['backlog'], 1.5)
        self.assertEqual(counts['yard'], 1.5)
        self.assertTrue(desk.stuck_work_at_cap(request()))
        desk.handle(dict(seq=0, at=500, kind='order_lost', requestId='pending-0'))
        self.assertFalse(desk.stuck_work_at_cap(request()))
        desk.read_results([dict(type='quote', requestId='pending-1')], [dict(ok=False, reason='expired')])
        self.assertEqual(desk.stuck_work_counts(request())['backlog'], .5)

    def test_real_progress_resets_age_but_reposts_and_changes_do_not(self):
        desk = desk_for(stuck_work=1, stuck_work_age_minutes=10)
        self.seed(desk)
        desk.posts['gig'] = dict(stops=[dict(orderId='work-0')])
        for kind, data in [('gig_booked', dict(gigId='gig')), ('gig_started', dict(gigId='gig')),
                           ('picked_up', dict(orderId='work-0')), ('delivered', dict(orderId='work-0'))]:
            desk.observe_history(dict(at=600, kind=kind, **data))
            desk.now = 609
            self.assertEqual(desk.stuck_work_counts(request())['national'], 0)
            desk.now = 610
            self.assertEqual(desk.stuck_work_counts(request())['national'], 1)
        for kind in ('gig_dropped', 'order_changed'):
            desk.observe_work_progress(dict(at=620, kind=kind))
        desk.first_posted = {'work-0': 620}
        self.assertEqual(desk.stuck_work_counts(request())['national'], 1)

    def test_booked_stalled_orders_count_as_stuck_but_not_unassigned_backlog(self):
        desk = desk_for(stuck_work=1)
        self.seed(desk)
        desk.leg_gigs['work-0'] = {0: 'gig'}
        desk.booked.add('gig')
        desk.now = 600
        counts = desk.stuck_work_counts(request())
        self.assertEqual(counts['national'], 1)
        self.assertEqual(counts['backlog'], 0)

    def test_partial_delivery_moves_locality_to_the_remaining_pickup(self):
        desk = desk_for(stuck_work=1)
        self.seed(desk)
        order = desk.orders['work-0']
        second = deepcopy(order['legs'][0])
        second['pickup']['placeId'] = 'espoo'
        order['legs'].append(second)
        order['deliveredAt'] = [550, None]
        desk.now = 600
        counts = desk.stuck_work_counts(request())
        self.assertEqual(counts['national'], 1)
        self.assertEqual(counts['local'], 0)
        self.assertEqual(counts['backlog'], 1)

    def test_disabled_gate_is_noop_even_with_zero_thresholds(self):
        desk = desk_for(stuck_work=0, stuck_work_local_limit=0, stuck_work_national_limit=0,
                        stuck_work_yard_limit=0, stuck_work_backlog_limit=0)
        self.seed(desk, 121, at=0)
        desk.now = 500
        self.assertFalse(desk.stuck_work_at_cap(request()))
        self.assertTrue(desk.eligible_options(request(), 200, 0)[0])

    def test_progress_survives_checkpoint_and_side_effect_free_replay(self):
        desk = desk_for(stuck_work=1)
        req = request()
        order = order_for(req)
        history = [dict(seq=0, at=500, kind='price_request', request=req),
                   dict(seq=1, at=515, kind='order_won', order=order),
                   dict(seq=2, at=600, kind='picked_up', orderId=req['id'], leg=0, gigId='g')]
        replay_history(desk, dict(gigs=[]), history)
        self.assertEqual(desk.stuck_work_progress, {req['id']: 600})
        self.assertFalse(desk.outbox)
        restored = desk_for(stuck_work=1)
        restore_state(restored, json.loads(json.dumps(model_state(desk))))
        self.assertEqual(restored.stuck_work_progress, desk.stuck_work_progress)
        restored.now = 645
        self.assertEqual(restored.stuck_work_counts(request())['national'], 1)


class FinaleRegressionTests(unittest.TestCase):
    def test_early_epsilon_matches_golden_base_actions_with_flags_off(self):
        expected = json.loads((ROOT / 'tests/fixtures/epsilon_early_actions.json').read_text())
        self.assertEqual(scripted_early_actions(), expected)
        self.assertEqual(scripted_early_actions(supply_risk=0, arrival_buffer=0, stuck_work=0), expected)

    def test_model_and_sweep_arms_are_exact_early_overlays(self):
        model = json.loads((ROOT / 'models/epsilon-finale.json').read_text())
        self.assertEqual(model['name'], 'Epsilon Finale')
        self.assertEqual({k: model['settings'][k] for k in EARLY}, EARLY)
        desk_for(**model['settings'])
        plan = json.loads((ROOT / 'docs/research/plans/epsilon/epsilon-finale.json').read_text())
        self.assertEqual(plan['base'], EARLY)
        self.assertEqual(len(plan['seeds']), 8)
        self.assertEqual(len(set(plan['seeds'])), 8)
        self.assertTrue({'eps-sp-s001', 'eps-bf-s002'} <= set(plan['seeds']))
        for settings in plan['variants'].values():
            desk_for(**{**plan['base'], **settings})

    def test_flags_default_off_and_settings_reject_invalid_values(self):
        defaults = GammaSettings()
        for flag in ('supply_risk', 'arrival_buffer', 'stuck_work'):
            self.assertEqual(getattr(defaults, flag), 0)
            with self.assertRaises(ValueError):
                GammaSettings(**{flag: 2})
        for setting in fields(defaults):
            if setting.name.startswith(('supply_risk_', 'arrival_buffer_', 'stuck_work_')):
                with self.subTest(setting=setting.name), self.assertRaises(ValueError):
                    GammaSettings(**{setting.name: -1})
        for settings in (dict(supply_risk_max_bps=299), dict(supply_risk_safe_quote_bps=0),
                         dict(stuck_work_pending_weight_pct=101)):
            with self.assertRaises(ValueError):
                GammaSettings(**settings)


if __name__ == '__main__':
    unittest.main()
