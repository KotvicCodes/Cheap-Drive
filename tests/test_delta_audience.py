"""Audience matching must reject plans before withdrawing waiting singles."""
from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import patch

from dispatch import Journal, play_model
from models.delta import make_delta
from tests.test_gamma_pairs import PairWorld, pair_order
from tests.test_performance import LossWorld


class DeltaAudienceTests(unittest.TestCase):
    def desk(self, **settings):
        return make_delta(PairWorld(), 8, 600, Journal(io.StringIO()), pairs=1,
                          delta_pairing='extended', **settings)

    def test_explicit_off_preserves_actions_timers_and_journal(self):
        outcomes = []
        for knobs in ({}, {'delta_pair_same_audience': 0}):
            world, stream = LossWorld(), io.StringIO()
            with redirect_stdout(io.StringIO()):
                score = play_model(world, 8, Journal(stream),
                                   lambda w, l, n, j: make_delta(w, l, n, j, pairs=1, **knobs))
            outcomes.append((world.sent, world.calls, score, stream.getvalue()))
        self.assertEqual(*outcomes)

    def test_matching_audiences_keep_the_same_plan_and_fee_schedule(self):
        actions = []
        for enabled in (0, 1):
            desk = self.desk(delta_pair_same_audience=enabled)
            first = pair_order(desk, 'one', 'a', 'b')
            second = pair_order(desk, 'two', 'b', 'c')
            plan, reason = desk._plan(first, second)
            self.assertIsNone(reason)
            actions.append(plan.action)
        self.assertEqual(*actions)

    def test_manual_and_experienced_mismatches_reject_before_withdrawal(self):
        for requirement in ('manual', 'experienced'):
            desk = self.desk(delta_pair_same_audience=1)
            first = pair_order(desk, 'one', 'a', 'b')
            second = pair_order(desk, 'two', 'b', 'c')
            if requirement == 'manual':
                desk.requests['two']['note'] = {'text': 'manual car'}
            else:
                second['legs'][0]['car']['premium'] = True
            desk.orders = {'one': first, 'two': second}
            with patch.object(desk, '_withdraw_gigs', side_effect=AssertionError('withdrawal')):
                self.assertEqual(desk._plan(first, second), (None, 'audience_mismatch'))
                self.assertFalse(desk._try_pair(first))
            self.assertEqual(desk._outbox, [])

    def test_switch_requires_integer_zero_or_one(self):
        for value in (True, False, -1, 2, '1', None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'delta_pair_same_audience'):
                self.desk(delta_pair_same_audience=value)
