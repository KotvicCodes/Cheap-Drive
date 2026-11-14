"""Pair-aware quote pricing must never post or withdraw during prediction."""
from copy import deepcopy
import io
import unittest
from unittest.mock import patch

from dispatch import Journal
from models.delta import make_delta
from tests.test_gamma_pairs import PairWorld, pair_order


class PairQuoteTests(unittest.TestCase):
    def desk(self, **settings):
        return make_delta(PairWorld(), 8, 600, Journal(io.StringIO()), pairs=1,
                          delta_pairing='extended', **settings)

    def setup_pair(self, desk):
        waiting = pair_order(desk, 'waiting', 'a', 'b')
        desk.orders['waiting'] = waiting
        desk.leg_gigs['waiting'] = {0: 'g'}
        pair_order(desk, 'candidate', 'b', 'c')
        request = desk.requests['candidate']
        option = {'kind': 'next_day', 'deadline': 3000, 'listPriceCents': 10000}
        return request, option

    def test_discount_requires_existing_unbooked_and_feasible_partner(self):
        desk = self.desk(delta_pair_quote_bps=9800)
        request, option = self.setup_pair(desk)
        factors = desk.option_factors(request, option, 100, 0)
        self.assertEqual(factors['deltaWaitingPairBps'], 9800)
        desk.booked.add('g')
        self.assertNotIn('deltaWaitingPairBps', desk.option_factors(request, option, 100, 0))
        desk.booked.clear()
        desk.leg_gigs.clear()
        self.assertNotIn('deltaWaitingPairBps', desk.option_factors(request, option, 100, 0))

    def test_prediction_preserves_books_queue_timers_and_makes_no_world_calls(self):
        desk = self.desk(delta_pair_quote_bps=9800)
        request, option = self.setup_pair(desk)
        before = deepcopy((desk.orders, desk.leg_gigs, desk._outbox, desk._pairs,
                           desk._pending_pairs, desk.first_posted, desk._busy))
        with patch.object(desk.world, 'act', side_effect=AssertionError('world mutation')), \
                patch.object(desk, 'poll_driver_side', side_effect=AssertionError('timer')):
            self.assertTrue(desk.quote_has_waiting_pair(request, option))
        after = (desk.orders, desk.leg_gigs, desk._outbox, desk._pairs,
                 desk._pending_pairs, desk.first_posted, desk._busy)
        self.assertEqual(before, after)

    def test_infeasible_and_audience_mismatch_keep_original_price(self):
        for mode in ('infeasible', 'audience'):
            desk = self.desk(delta_pair_quote_bps=9800, delta_pair_same_audience=1)
            request, option = self.setup_pair(desk)
            if mode == 'infeasible':
                option['deadline'] = 601
            else:
                request['note'] = {'text': 'manual car'}
            self.assertNotIn('deltaWaitingPairBps', desk.option_factors(request, option, 100, 0))

    def test_disabled_setting_does_not_even_plan_and_rounding_is_once(self):
        desk = self.desk()
        request, option = self.setup_pair(desk)
        with patch.object(desk, 'quote_has_waiting_pair', side_effect=AssertionError('prediction')):
            factors = desk.option_factors(request, option, 100, 0)
        self.assertNotIn('deltaWaitingPairBps', factors)
        factors['deltaWaitingPairBps'] = 9800
        self.assertEqual(desk.price_option(option, 15000, 0, 1, factors), 14700)

    def test_strict_integer_and_pairs_requirement(self):
        for value in (True, False, -1, 10001, '9800', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.desk(delta_pair_quote_bps=value)
        with self.assertRaisesRegex(ValueError, 'pairs=1'):
            make_delta(PairWorld(), 8, 600, Journal(io.StringIO()), delta_pair_quote_bps=9800)
