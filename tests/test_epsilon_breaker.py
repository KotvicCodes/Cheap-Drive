"""Realized-service breaker, effective admission/quotes, and durable recovery."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest

from dispatch import Journal, play_model
from models.delta import make_delta
from recovery import model_state, restore_state, replay_history
from tests.test_gamma import GammaWorld, request
from tests.test_gamma_pairs import order_for
from tests.test_performance import LossWorld


class EpsilonBreakerTests(unittest.TestCase):
    def desk(self, **knobs):
        medium = json.loads((Path(__file__).resolve().parents[1] /
                             'models/epsilon-medium.json').read_text())['settings']
        return make_delta(GammaWorld(), 8, 500, Journal(io.StringIO()),
                          **{**medium, 'epsilon_breaker': 1, **knobs})

    def delivery(self, desk, identity, *, late=False, legs=1, leg=0):
        desk.orders.setdefault(identity, dict(id=identity, deadline=600,
                                              deliveredAt=[None] * legs))
        event = dict(seq=len(desk.epsilon_breaker_outcomes), kind='delivered',
                     orderId=identity, leg=leg, at=601 if late else 600)
        desk.handle(event)
        return event

    def test_minimum_sample_strict_threshold_and_week_latch(self):
        desk = self.desk(epsilon_breaker_on_time_bps=9500)
        self.delivery(desk, 'late', late=True)
        for n in range(19):
            self.delivery(desk, str(n))
        self.assertEqual(len(desk.epsilon_breaker_outcomes), 20)
        self.assertFalse(desk.epsilon_breaker_active)  # exactly 95% is allowed
        self.delivery(desk, 'late2', late=True)
        self.assertTrue(desk.epsilon_breaker_active)
        self.assertEqual(desk.epsilon_breaker_at, 601)
        for n in range(100):
            self.delivery(desk, f'recovered-{n}')
        self.assertTrue(desk.epsilon_breaker_active)
        self.assertEqual(desk.win_target(), 4200)

    def test_leading_pickup_risk_switches_before_any_delivery_or_new_quote(self):
        desk = self.desk(epsilon_breaker_risk_orders=2)
        for identity in ('risk1', 'risk2'):
            req = request(identity)
            req['note'] = {'text': ''}
            desk.requests[identity] = req
            desk.orders[identity] = order_for(req, deadline=1000)
        self.assertEqual(desk.epsilon_breaker_outcomes, {})
        desk.quote(request('new'))
        self.assertTrue(desk.epsilon_breaker_active)
        self.assertEqual(desk.epsilon_breaker_at, 500)
        self.assertEqual(desk.win_target(), 4200)
        restored = self.desk(epsilon_breaker_risk_orders=2)
        restore_state(restored, deepcopy(model_state(desk)))
        self.assertEqual(restored.settings, desk.settings)

    def test_booked_and_far_work_do_not_fire_leading_breaker(self):
        desk = self.desk(epsilon_breaker_risk_orders=2)
        for identity, deadline in (('booked', 1000), ('near', 1000), ('far', 6000)):
            req = request(identity)
            req['note'] = {'text': ''}
            desk.requests[identity] = req
            desk.orders[identity] = order_for(req, deadline=deadline)
        desk.leg_gigs['booked'] = {0: 'booked-gig'}
        desk.booked.add('booked-gig')
        desk.quote(request('new'))
        self.assertFalse(desk.epsilon_breaker_active)
        self.assertEqual(desk.win_target(), 4400)

    def test_history_rebuilds_leading_latch_without_quote_receipts(self):
        desk = self.desk(epsilon_breaker_risk_orders=2)
        for identity in ('risk1', 'risk2'):
            req = request(identity)
            req['note'] = {'text': ''}
            desk.requests[identity] = req
            desk.orders[identity] = order_for(req, deadline=1000)
        history = [dict(seq=1, at=500, kind='price_request', request=request('new'))]
        replay_history(desk, dict(gigs=[]), history, after=-1)
        self.assertTrue(desk.epsilon_breaker_active)
        self.assertEqual(desk.win_target(), 4200)
        self.assertFalse(desk.recovery_quotes)

    def test_quote_and_intake_only_fallback_preserves_pairing_screen(self):
        desk = self.desk(epsilon_breaker_restore_pairing=0, epsilon_breaker_min_orders=1)
        original_driver = desk.driver_settings
        self.delivery(desk, 'late', late=True)
        self.assertTrue(desk.epsilon_breaker_active)
        self.assertEqual(desk.win_target(), 4200)
        self.assertEqual(desk.driver_settings, original_driver)
        self.assertEqual(desk.delta_pair_max_wait_minutes, 180)
        self.assertEqual(desk.delta_pair_min_slack_minutes, 480)

    def test_switch_changes_quote_tilt_slack_corridor_and_new_trade_intake(self):
        desk = self.desk(epsilon_breaker_min_orders=1)
        req = request(slacks=(350,))
        req['note'] = {'text': ''}
        self.assertTrue(desk.eligible_options(req, 100, 0)[0])
        self.assertEqual(desk.win_target(), 4400)
        self.assertEqual(desk.option_factors(req, req['options'][0], 200, 0)['shortBps'], 9300)
        self.delivery(desk, 'late', late=True)
        self.assertFalse(desk.eligible_options(req, 100, 0)[0])
        self.assertEqual(desk.settings.short_km, 45)
        self.assertEqual(desk.option_factors(req, req['options'][0], 200, 0)['shortBps'], 10000)
        self.assertEqual(desk.settings.short_bps, 9200)
        self.assertEqual(desk.settings.long_markup_bps, 10000)
        self.assertEqual(desk.intake_settings.delta_corridor_open_cap, 0)
        self.assertEqual(desk.settings.trade_ins, 0)
        # Already admitted trade work retains its guarded routing and fee policy.
        trade = deepcopy(req)
        trade['legs'].append(deepcopy(trade['legs'][0]))
        self.assertTrue(desk._guarded_trade(trade))
        self.assertFalse(desk.eligible_options(trade, 200, 0)[0])
        self.assertEqual(desk.driver_settings.pair_once, 1)
        self.assertEqual(desk.driver_settings.pair_max_idle_minutes, 60)
        self.assertEqual(desk.delta_pair_max_wait_minutes, 0)
        self.assertEqual(desk.delta_pair_min_slack_minutes, 0)

    def test_partial_delivery_and_duplicate_late_refunds_count_orders_once(self):
        desk = self.desk(epsilon_breaker_min_orders=2)
        self.delivery(desk, 'trade', legs=2)
        self.assertEqual(desk.epsilon_breaker_outcomes, {})
        self.delivery(desk, 'trade', legs=2, leg=1)
        refund = dict(kind='ledger', at=601,
                      line=dict(kind='late_refund', orderId='overdue'))
        desk.observe_history(refund)
        desk.observe_history(refund)
        self.assertEqual(desk.epsilon_breaker_outcomes, {'trade': True, 'overdue': False})
        self.assertTrue(desk.epsilon_breaker_active)
        self.delivery(desk, 'overdue')
        self.assertFalse(desk.epsilon_breaker_outcomes['overdue'])

    def test_checkpoint_and_history_replay_restore_latched_settings(self):
        desk = self.desk(epsilon_breaker_min_orders=1)
        desk.orders['late'] = dict(id='late', deadline=600, deliveredAt=[None])
        before = deepcopy(model_state(desk))
        event = self.delivery(desk, 'late', late=True)
        checkpoint = self.desk(epsilon_breaker_min_orders=1)
        restore_state(checkpoint, deepcopy(model_state(desk)))
        replay = self.desk(epsilon_breaker_min_orders=1)
        restore_state(replay, before)
        replay_history(replay, dict(gigs=[]), [event], after=-1)
        for restored in (checkpoint, replay):
            self.assertTrue(restored.epsilon_breaker_active)
            self.assertEqual(restored.settings, desk.settings)
            self.assertEqual(restored.intake_settings, desk.intake_settings)
            self.assertEqual(restored.driver_settings, desk.driver_settings)
            self.assertEqual(restored.delta_pair_max_wait_minutes, 0)
            self.assertEqual(restored.delta_pair_min_slack_minutes, 0)
            self.assertEqual(restored.epsilon_breaker_outcomes, desk.epsilon_breaker_outcomes)

    def test_default_off_keeps_actions_and_journal_identical(self):
        outcomes = []
        for knobs in ({}, {'epsilon_breaker': 0}):
            world, stream = LossWorld(), io.StringIO()
            with redirect_stdout(io.StringIO()):
                score = play_model(world, 8, Journal(stream),
                                   lambda w, l, n, j: make_delta(w, l, n, j, pairs=1, **knobs))
            outcomes.append((world.sent, world.calls, score, stream.getvalue()))
        self.assertEqual(*outcomes)

    def test_rolling_service_detects_degradation_hidden_by_earlier_success(self):
        desk = self.desk(epsilon_breaker_min_orders=20, epsilon_breaker_window_minutes=1440)
        cumulative = self.desk(epsilon_breaker_min_orders=20)
        for target in (desk, cumulative):
            for n in range(100):
                self.delivery(target, f'old-{n}')
            for n in range(20):
                identity = f'recent-{n}'
                target.orders[identity] = dict(id=identity, deadline=3000, deliveredAt=[None])
                target.handle(dict(kind='delivered', orderId=identity, leg=0,
                                   at=3001 if n < 2 else 3000))
        self.assertTrue(desk.epsilon_breaker_active)
        self.assertFalse(cumulative.epsilon_breaker_active)

    def test_duplicate_refund_does_not_refresh_old_failure_in_window(self):
        desk = self.desk(epsilon_breaker_min_orders=1, epsilon_breaker_window_minutes=60)
        self.delivery(desk, 'old')
        refund = dict(kind='ledger', at=700,
                      line=dict(kind='late_refund', orderId='old'))
        desk.observe_history(refund)
        self.assertFalse(desk.epsilon_breaker_active)
        self.assertEqual(desk.epsilon_breaker_resolved_at['old'], 600)

    def test_invalid_settings(self):
        for knobs in ({'epsilon_breaker': True}, {'epsilon_breaker': 2},
                      {'epsilon_breaker_on_time_bps': 0},
                      {'epsilon_breaker_on_time_bps': 10001},
                      {'epsilon_breaker_on_time_bps': 9400.0},
                      {'epsilon_breaker_window_minutes': -1},
                      {'epsilon_breaker_risk_orders': -1},
                      {'epsilon_breaker_risk_horizon_minutes': True},
                      {'epsilon_breaker_restore_pairing': 2},
                      {'epsilon_breaker_min_orders': 0}):
            with self.subTest(knobs=knobs), self.assertRaises(ValueError):
                self.desk(**knobs)
