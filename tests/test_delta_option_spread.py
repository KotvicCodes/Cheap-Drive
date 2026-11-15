"""B4 offline quote and integration contracts; no market/economic claims."""
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from compare import load_model
from models.delta import make_delta
from models.delta_b1 import B1_MODES
from models.delta_lanes import LANE_MODES
from dispatch import Journal, play_model
from models.gamma_notes import make_gamma_notes_pairs
from tests.test_delta_lanes import BASELINE, LaneWorld
from tests.test_gamma import request
from tests.test_notes import order_for
from tests.test_performance import LossWorld


ACTIVE = 'dual_10400_9800'


class DeltaOptionSpreadTests(unittest.TestCase):
    def desk(self, mode=ACTIVE, *, factory=make_delta, level=8, **settings):
        stream = io.StringIO()
        switches = {'delta_option_spread': mode} if factory is make_delta else {}
        desk = factory(LaneWorld(), level, 500, Journal(stream),
                       **{**BASELINE, **settings, **switches})
        desk.trace = stream
        # Avoid short/long factors unless a test requests them explicitly.
        for road in desk.roads.values():
            if road['km']:
                road['km'] = 120
        return desk

    def req(self, identity='one', **kwargs):
        return request(identity, slacks=(900, 3000, 5000), **kwargs)

    def rows(self, desk, kind='delta_option_spread_quote'):
        return [row for row in map(json.loads, desk.trace.getvalue().splitlines())
                if row['type'] == kind]

    def offer(self, desk, req):
        desk.quote(req)
        return desk._outbox[-1]['prices']

    def event(self, desk, kind, **data):
        desk.handle(dict(seq=1, at=desk.now, kind=kind, **data))

    def flush(self, desk):
        actions, desk.outbox = desk.outbox, []
        desk.read_results(actions, desk.world.act(actions))
        return deepcopy(actions)

    def test_final_menu_combinations_and_order_preserve_third_option(self):
        for selection in ((0,), (1,), (2,), (0, 1), (0, 2), (1, 2), (0, 1, 2), (2, 1, 0)):
            with self.subTest(selection=selection):
                desk, control = self.desk(), self.desk(factory=make_gamma_notes_pairs)
                req = self.req()
                req['options'] = [req['options'][index] for index in selection]
                original = deepcopy(req)
                actual = self.offer(desk, req)
                neutral = self.offer(control, deepcopy(req))
                dual = 0 in selection and 1 in selection
                self.assertEqual(list(actual), [o['kind'] for o in req['options']])
                for option in req['options']:
                    factor = {'same_day': 10400, 'next_day': 9800}.get(option['kind'], 10000) if dual else 10000
                    exact = Fraction(option['listPriceCents'] * 15000 * factor, 10000 ** 2)
                    self.assertEqual(actual[option['kind']], -(-exact.numerator // exact.denominator))
                    if factor == 10000:
                        self.assertEqual(actual[option['kind']], neutral[option['kind']])
                self.assertEqual(req, original)
                self.assertIsNone(desk._delta_option_spread_context)
                cohort = ('dual_menu' if dual else 'same_day_without_next_day' if 0 in selection
                          else 'next_day_without_same_day' if 1 in selection else 'neither')
                self.assertEqual(self.rows(desk)[0]['cohort'], cohort)

    def test_original_dual_request_gated_to_each_lone_option_is_gamma(self):
        for survivor in (0, 1):
            desk, control = self.desk(), self.desk(factory=make_gamma_notes_pairs)
            req = self.req()
            req['options'] = req['options'][:2]
            req['options'][1 - survivor]['deadline'] = 600
            actual = self.offer(desk, req)
            self.assertEqual(list(actual), [req['options'][survivor]['kind']])
            self.assertEqual(actual, self.offer(control, deepcopy(req)))
            self.assertEqual(set(self.rows(desk)[0]['spreadFactorsBps'].values()), {10000})

    def test_real_readiness_premium_slack_and_long_guards_control_treatment(self):
        for settings, guard in (({}, 'readiness'), ({'premium_min_slack_minutes': 1400}, 'premium'),
                                ({'same_day_min_slack_minutes': 1800}, 'slack'),
                                ({'max_km': 100, 'long_max_km': 700}, 'long')):
            with self.subTest(guard=guard):
                desks = [self.desk(**settings), self.desk(factory=make_gamma_notes_pairs, **settings)]
                req = self.req()
                if guard == 'readiness':
                    req['note'] = {'text': 'Ready tomorrow at 10:00', 'language': 'en'}
                if guard == 'premium':
                    req['legs'][0]['car']['premium'] = True
                prices = [self.offer(desk, deepcopy(req)) for desk in desks]
                self.assertNotIn('same_day', prices[0])
                self.assertIn('next_day', prices[0])
                self.assertEqual(*prices)
                self.assertEqual(self.rows(desks[0])[0]['cohort'], 'next_day_without_same_day')

    def test_single_fractional_ceiling_and_existing_gamma_factors(self):
        desk = self.desk(start_markup_bps=10001, markup_min_bps=1)
        req = self.req()
        req['options'] = [{**o, 'listPriceCents': 1} for o in req['options'][:2]]
        self.assertEqual(self.offer(desk, req), {'same_day': 2, 'next_day': 1})
        # Rounding Gamma first and discounting its 2-cent result would yield 2.
        control = self.desk(factory=make_gamma_notes_pairs, start_markup_bps=10001, markup_min_bps=1)
        self.assertEqual(self.offer(control, deepcopy(req))['next_day'], 2)
        for short in (False, True):
            desk = self.desk()
            desk.markup = 15001.9  # retain Gamma's integer markup conversion
            desk.trust['D01'] = 7
            if short:
                desk.roads['helsinki', 'tampere']['km'] = 44
            req = self.req()
            prices = self.offer(desk, req)
            for option in req['options']:
                factor = {'same_day': 10400, 'next_day': 9800}.get(option['kind'], 10000)
                exact = (Fraction(option['listPriceCents'] * 15001 * 10700, 10000 ** 2)
                         * Fraction(9200 if short else 10000, 10000) * Fraction(factor, 10000))
                self.assertEqual(prices[option['kind']], -(-exact.numerator // exact.denominator))

    def test_sanitized_diagnostics_match_gamma_journal_and_actual_action(self):
        desk, req = self.desk(), self.req()
        req['note'] = {'text': 'Private reference SENTINEL_2784', 'language': 'en'}
        prices = self.offer(desk, req)
        row, gamma = self.rows(desk)[0], self.rows(desk, 'beta_quote')[0]
        self.assertEqual(row['optionKeys'], list(prices))
        self.assertEqual(row['prices'], gamma['prices'])
        self.assertEqual(row['prices'], prices)
        self.assertEqual(row['optionFactors'], gamma['optionFactors'])
        self.assertEqual(row['spreadFactorsBps'], {'same_day': 10400, 'next_day': 9800, 'within_3_days': 10000})
        self.assertNotIn('deltaOptionSpreadBps', gamma['optionFactors']['within_3_days'])
        self.assertNotIn('SENTINEL_2784', json.dumps(row))

    def test_declines_duplicate_expiry_and_low_levels_retain_behavior(self):
        for cause in ('route', 'time', 'trade_in', 'town'):
            desks = [self.desk(), self.desk(factory=make_gamma_notes_pairs)]
            req = self.req()
            if cause == 'time':
                for option in req['options']:
                    option['deadline'] = 600
            elif cause == 'trade_in':
                req['legs'] *= 2
            for desk in desks:
                if cause == 'route':
                    desk.roads['helsinki', 'tampere']['km'] = 701
                with patch.object(desk, 'town_at_cap', return_value=cause == 'town'):
                    self.offer(desk, deepcopy(req))
            self.assertEqual(desks[0]._outbox, desks[1]._outbox)
            self.assertEqual(desks[0].trace.getvalue(), desks[1].trace.getvalue())
            self.assertFalse(self.rows(desks[0]))
        for level in (1, 2, 3):
            desks = [self.desk(level=level), self.desk(factory=make_gamma_notes_pairs, level=level)]
            self.assertEqual(*(self.offer(desk, self.req()) for desk in desks))
            self.assertEqual(desks[0].trace.getvalue(), desks[1].trace.getvalue())
        desk, req = self.desk(), self.req()
        desk.now = req['respondBy']
        desk.quote(req)
        self.assertEqual(desk._outbox, [])
        desk.now = 500
        self.offer(desk, req)
        before = desk.trace.getvalue()
        desk.quote(req)
        self.assertEqual(len(desk._outbox), 1)
        self.assertEqual(desk.trace.getvalue(), before)

    def test_exception_context_cleanup_and_no_cross_request_leakage(self):
        for hook in ('eligible_options', 'price_option'):
            desk = self.desk()
            with patch.object(desk, hook, side_effect=RuntimeError('offline failure')):
                with self.assertRaisesRegex(RuntimeError, 'offline failure'):
                    desk.quote(self.req('failed'))
            self.assertIsNone(desk._delta_option_spread_context)
            self.assertNotIn('failed', desk.pending)
            self.assertEqual(desk._outbox, [])
            self.assertFalse(self.rows(desk))
            req = self.req('next')
            req['options'] = req['options'][1:2]
            control = self.desk(factory=make_gamma_notes_pairs)
            self.assertEqual(self.offer(desk, req), self.offer(control, deepcopy(req)))
            self.assertIsNone(desk._delta_option_spread_context)
            # Calling the hook outside a quote must not activate or retain B4.
            desk.eligible_options(self.req('inspect'), 120, 0)
            factors = desk.option_factors(req, req['options'][0], 120, 0)
            self.assertNotIn('deltaOptionSpreadBps', factors)

    def test_rejected_receipt_and_scripted_feedback_match_gamma(self):
        desks = [self.desk(), self.desk(factory=make_gamma_notes_pairs)]
        for index, outcome in enumerate(('reject', 'lost', 'won')):
            for desk in desks:
                req = self.req(str(index))
                self.offer(desk, req)
                if outcome == 'reject':
                    actions, desk.outbox = desk.outbox, []
                    with self.assertLogs('cheap-drive', level='WARNING'):
                        desk.read_results(actions, [{'ok': False, 'reason': 'offline rejection'}])
                    desk.learn(req['id'], False)
                else:
                    self.flush(desk)
                    if outcome == 'lost':
                        self.event(desk, 'order_lost', requestId=req['id'])
                    else:
                        self.event(desk, 'order_won', order=order_for(req))
                        self.event(desk, 'ledger', line={'kind': 'revenue', 'orderId': req['id'], 'cents': 30000})
                        self.event(desk, 'ledger', line={'kind': 'late_refund', 'orderId': req['id'], 'cents': -300})
                self.assertIsNone(getattr(desk, '_delta_option_spread_context', None))
            for name in ('markup', 'markups', 'pending', 'quote_trackers', 'town_pending', 'trust', 'day_starts'):
                self.assertEqual(getattr(desks[0], name), getattr(desks[1], name))
        self.assertEqual(len(self.rows(desks[0])), 3)  # constructed, not accepted quotes

    def test_pair_interception_booking_change_cancel_and_delivery_remain_gamma(self):
        runs = []
        for mode in (ACTIVE, 'off', None):
            desk = self.desk(mode) if mode is not None else self.desk(factory=make_gamma_notes_pairs)
            for index, origin, destination in ((0, 'tampere', 'vantaa'), (1, 'vantaa', 'pori')):
                req = self.req(str(index), pickup=origin, delivery=destination)
                self.offer(desk, req)
                self.flush(desk)
                self.event(desk, 'order_won', order=order_for(req))
            posts = deepcopy([a for a in desk._outbox if a['type'] == 'post'])
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(posts[0]['stops']), 4)
            self.flush(desk)
            gig = desk.leg_gigs['0'][0]
            self.event(desk, 'gig_booked', gigId=gig, driverId='driver', feeCents=12000)
            changed = deepcopy(desk.orders['0'])
            changed['deadline'] += 30
            self.event(desk, 'order_changed', order=changed)  # DriverSideMixin returns early
            self.assertEqual(desk.orders['0']['deadline'], changed['deadline'])
            self.event(desk, 'order_cancelled', orderId='0', gigs=[{'gigId': gig, 'outcome': 'continues'}])
            self.assertEqual(desk.leg_gigs['1'][0], gig)
            self.event(desk, 'delivered', orderId='1', leg=0)
            runs.append((posts, desk._outbox, desk.booked, desk.leg_gigs, desk.pending,
                         desk.quote_trackers, desk.markup, self.rows(desk, 'gamma_pair'),
                         self.rows(desk, 'gamma_pair_booked')))
        self.assertTrue(all(run == runs[-1] for run in runs))

    def test_off_exact_action_and_event_parity_in_both_dispatch_clocks(self):
        for pairs in (0, 1):
            for fast in (False, True):
                results = []
                for factory in (make_delta, make_gamma_notes_pairs):
                    world, stream = LossWorld(), io.StringIO()
                    with redirect_stdout(io.StringIO()):
                        score = play_model(world, 8, Journal(stream),
                                           lambda *args: factory(*args, **{**BASELINE, 'pairs': pairs}), fast=fast)
                    results.append((world.sent, score, stream.getvalue()))
                self.assertEqual(*results)
        desks = [self.desk('off'), self.desk(factory=make_gamma_notes_pairs)]
        self.assertEqual(*(self.offer(desk, self.req()) for desk in desks))
        self.assertEqual(desks[0].trace.getvalue(), desks[1].trace.getvalue())
        self.assertFalse(self.rows(desks[0]))

    def test_quote_append_pair_timer_keeps_actual_menu_and_lifecycle_neutral(self):
        runs = []
        for factory in (make_delta, make_gamma_notes_pairs):
            desk = self.desk(factory=factory)
            for index, origin, destination in ((0, 'tampere', 'vantaa'), (1, 'vantaa', 'pori')):
                req = self.req(str(index), pickup=origin, delivery=destination)
                self.offer(desk, req)
                self.flush(desk)
                self.event(desk, 'order_won', order=order_for(req))
            self.assertEqual(len(desk._pending_pairs), 1)
            # Leave the pair unsubmitted. Gamma's outbox getter processes its
            # due timer while appending this fresh quote, replacing its post.
            desk.now += desk.driver_settings.pair_split_minutes
            req = self.req('after_timer')
            req['respondBy'] = desk.now + 15
            prices = self.offer(desk, req)
            self.assertFalse(desk._pending_pairs)
            self.assertEqual(len(self.rows(desk, 'gamma_pair_split')), 1)
            posts = [a for a in desk._outbox if a['type'] == 'post']
            self.assertEqual(len(posts), 2)
            if factory is make_delta:
                row = self.rows(desk)[-1]
                self.assertEqual(row['requestId'], 'after_timer')
                self.assertEqual(row['prices'], prices)
                self.assertEqual(row['cohort'], 'dual_menu')
                self.assertIsNone(desk._delta_option_spread_context)
            runs.append((posts, desk.leg_gigs, desk.pending, desk.markup,
                         self.rows(desk, 'gamma_pair_split')))
        self.assertEqual(*runs)

    def test_factory_configuration_load_and_invalid_modes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'b4.json'
            path.write_text(json.dumps(dict(name='B4 offline', factory='delta:make_delta',
                                            settings={**BASELINE, 'delta_option_spread': ACTIVE})))
            model = load_model(path)
            desk = model.factory(LaneWorld(), 8, 500, Journal(io.StringIO()))
            self.assertEqual(desk.delta_option_spread, ACTIVE)
            # The loaded factory also composes selected Gamma's short discount.
            self.assertEqual(self.offer(desk, self.req()),
                             {'same_day': 35880, 'next_day': 27050, 'within_3_days': 24840})
        for mode in (True, False, 0, 1, None, '', 'dual', [], {}, ['off', ACTIVE]):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'delta_option_spread'):
                self.desk(mode)
        with self.assertRaises(TypeError):
            self.desk(delta_option_spread_bps=10400)

    def test_unqualified_combinations_rejected_but_off_preserves_existing_arms(self):
        invalid = [dict(delta_note_fixes=1), dict(delta_rescue_windows=1), dict(dealer_table=1),
                   dict(place_table=1), dict(capacity_valve=1), dict(supply_scale=1), dict(town_caps=1),
                   dict(town_reserve_pending=1), dict(trust_build_bps=100), dict(trust_guard=1),
                   dict(brake=1), dict(trade_ins=1), dict(freeze_day_drop_bps=25),
                   dict(markup_scope='dealer'), dict(markup_scope='km'), dict(learn_bps=201),
                   dict(win_target_bps=3100), dict(trust_bps_per_order=50), dict(quote_options='no_same_day'),
                   dict(same_day_bps=10400), dict(next_day_bps=9800), dict(within_3_days_bps=10001),
                   dict(table_strength=99), dict(trust_build_until_day=6), dict(fee_shape='review'),
                   dict(review_after_minutes=361), dict(review_fee_bps=11001),
                   dict(cap_before_last_pickup_minutes=361), dict(review_skip_night=0)]
        invalid += [dict(delta_b1=mode) for mode in B1_MODES[1:]]
        invalid += [dict(delta_lanes=mode) for mode in LANE_MODES if mode != 'off']
        for settings in invalid:
            with self.subTest(settings=settings):
                # Validation must happen before any desk/world initialization.
                with self.assertRaisesRegex(ValueError, 'delta_option_spread'):
                    make_delta(None, 8, 500, Journal(io.StringIO()), delta_option_spread=ACTIVE, **settings)
                self.desk('off', **settings)


if __name__ == '__main__':
    unittest.main()
