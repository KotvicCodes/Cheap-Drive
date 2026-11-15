"""Guarded customer prices, exact rounding, and unchanged default feedback."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import unittest
from unittest.mock import patch

from dispatch import Journal, play_model
from models.delta import make_delta
from recovery import model_state, restore_state
from tests.test_gamma_pairs import PairWorld, pair_order
from tests.test_performance import LossWorld


class DeltaSafeQuoteTests(unittest.TestCase):
    def desk(self, **knobs):
        return make_delta(PairWorld(), 8, 600, Journal(io.StringIO()),
                          win_target_bps=4200, **knobs)

    def request(self, desk):
        pair_order(desk, 'candidate', deadline=6000)
        req = desk.requests['candidate']
        req['referenceFeeCents'] = 10000
        option = dict(kind='next_day', deadline=6000, listPriceCents=10000)
        req['options'] = [option]
        return req, option

    def test_off_preserves_complete_actions_calls_score_and_journal(self):
        outcomes = []
        for knobs in ({}, {'delta_safe_quote_bps': 0}):
            world, stream = LossWorld(), io.StringIO()
            with redirect_stdout(io.StringIO()):
                score = play_model(world, 8, Journal(stream),
                                   lambda w,l,n,j: make_delta(w,l,n,j,pairs=1,**knobs))
            outcomes.append((world.sent, world.calls, score, stream.getvalue()))
        self.assertEqual(*outcomes)

    def test_distance_slack_and_backlog_boundaries(self):
        desk = self.desk(delta_safe_quote_bps=9800)
        req, option = self.request(desk)
        for km, allowed in ((49,False),(50,True),(300,True),(301,False)):
            with self.subTest(km=km):
                self.assertEqual('deltaSafeQuoteBps' in desk.option_factors(req,option,km,0),allowed)
        for slack, allowed in ((719,False),(720,True)):
            with patch.object(desk,'slack',return_value=slack):
                self.assertEqual('deltaSafeQuoteBps' in desk.option_factors(req,option,100,0),allowed)
        for count, allowed in ((15,True),(16,False)):
            with patch.object(desk,'orders_without_driver',return_value=set(range(count))):
                self.assertEqual('deltaSafeQuoteBps' in desk.option_factors(req,option,100,0),allowed)

    def test_private_premium_trade_in_and_low_levels_keep_original_factors(self):
        desk = self.desk(delta_safe_quote_bps=9600)
        req, option = self.request(desk)
        original = deepcopy(req)
        for kind in ('pickup','delivery'):
            req['legs'][0][kind]['privateAddress'] = True
            self.assertNotIn('deltaSafeQuoteBps',desk.option_factors(req,option,100,0))
            req = deepcopy(original)
        req['legs'][0]['car']['premium'] = True
        self.assertNotIn('deltaSafeQuoteBps',desk.option_factors(req,option,100,0))
        req = deepcopy(original)
        req['legs'].append(deepcopy(req['legs'][0]))
        self.assertNotIn('deltaSafeQuoteBps',desk.option_factors(req,option,100,0))
        desk.level = 3
        self.assertNotIn('deltaSafeQuoteBps',desk.option_factors(original,option,100,0))

    def test_reference_floor_uses_final_integer_price_and_skips_whole_discount(self):
        desk = self.desk(delta_safe_quote_bps=9800)
        req, option = self.request(desk)
        desk.markup = 10000
        for list_price, applies, final in ((11224,True,11000),(11223,False,11223)):
            option['listPriceCents'] = list_price
            factors = desk.option_factors(req,option,100,0)
            self.assertEqual('deltaSafeQuoteBps' in factors,applies)
            self.assertEqual(desk.price_option(option,10000,0,1,factors),final)

    def test_per_option_scope_and_recovery_preserve_global_learning_and_inputs(self):
        desk = self.desk(delta_safe_quote_bps=9800)
        req, option = self.request(desk)
        before = deepcopy((req,desk.orders,desk._outbox,desk.markup))
        with patch.object(desk,'slack',side_effect=[719,720]):
            self.assertNotIn('deltaSafeQuoteBps',desk.option_factors(req,option,100,0))
            self.assertEqual(desk.option_factors(req,option,100,0)['deltaSafeQuoteBps'],9800)
        self.assertEqual(before,(req,desk.orders,desk._outbox,desk.markup))
        self.assertEqual(desk.win_target(),4200)
        other = self.desk(delta_safe_quote_bps=9800)
        restore_state(other,deepcopy(model_state(desk)))
        self.assertEqual(other.option_factors(req,option,100,0),desk.option_factors(req,option,100,0))

    def test_strict_validation(self):
        for knobs in ({'delta_safe_quote_bps':True},{'delta_safe_quote_bps':10001},
                      {'delta_safe_quote_bps':-1},{'delta_safe_quote_bps':'9800'},
                      {'delta_safe_quote_min_slack_minutes':-1},
                      {'delta_safe_quote_max_backlog':False}):
            with self.subTest(knobs=knobs),self.assertRaises(ValueError):
                self.desk(**knobs)
