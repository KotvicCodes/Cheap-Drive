"""Raw-reference floors preserve admission and quote feedback bookkeeping."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import unittest
from unittest.mock import patch

from dispatch import Journal, play_model
from models.delta import make_delta
from models.gamma import GammaDesk
from tests.test_gamma import GammaWorld, request
from tests.test_performance import LossWorld


class ReferenceFloorTests(unittest.TestCase):
    def desk(self, level=8, **settings):
        stream = io.StringIO()
        desk = make_delta(GammaWorld(), level, 500, Journal(stream), **settings)
        desk.trace = stream
        return desk

    def req(self):
        req = request(slacks=(900, 3000))
        req['referenceFeeCents'] = 10001
        req['note'] = {'text': ''}
        for option in req['options']:
            option['listPriceCents'] = 100
        return req

    def offer(self, desk, req):
        desk.quote(req)
        return desk._outbox[-1]['prices']

    def test_raw_cent_ceiling_and_binding_are_applied_after_existing_rounding(self):
        desk = self.desk(delta_reference_quote_floor_bps=11000)
        req = self.req()
        original = deepcopy(req)
        self.assertEqual(set(self.offer(desk, req).values()), {11002})
        self.assertEqual(req, original)
        self.assertIsNone(desk._delta_reference_request)
        rows = [r for r in map(json.loads, desk.trace.getvalue().splitlines())
                if r['type'] == 'delta_reference_quote_floor']
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r['binding'] and r['baseCents'] == 150 and r['floorCents'] == 11002
                            for r in rows))
        req['id'] = 'two'
        req['options'][0]['listPriceCents'] = 7335
        self.assertEqual(self.offer(desk, req)['same_day'], 11003)

    def test_short_trade_in_low_level_and_practical_declines_keep_original_quotes(self):
        for case in ('short', 'trade_in', 'level1', 'level3', 'decline'):
            settings = {'trade_ins': 1} if case == 'trade_in' else {}
            if case == 'decline':settings.update(max_km=50, long_max_km=50)
            level = int(case[-1]) if case.startswith('level') else 8
            desks = [self.desk(level, **settings), self.desk(level, delta_reference_quote_floor_bps=11500, **settings)]
            req = self.req()
            if case == 'trade_in':req['legs'] *= 2
            if case == 'short':
                for d in desks:d.roads['helsinki', 'tampere']['km'] = 44
            with self.subTest(case=case):
                self.assertEqual(*[self.offer(d, deepcopy(req)) for d in desks])

    def test_inclusive_route_and_level_boundaries_and_context_cleanup_on_exception(self):
        desk = self.desk(4, delta_reference_quote_floor_bps=11000)
        desk.roads['helsinki', 'tampere']['km'] = 45
        self.assertEqual(set(self.offer(desk, self.req()).values()), {11002})
        with patch.object(GammaDesk, 'price_option', side_effect=RuntimeError('fixture')):
            req = self.req()
            req['id'] = 'exception'
            with self.assertRaises(RuntimeError):desk.quote(req)
        self.assertIsNone(desk._delta_reference_request)

    def test_quote_feedback_is_once_for_acceptance_and_absent_for_rejection(self):
        for accepted in (True, False):
            desk = self.desk(delta_reference_quote_floor_bps=11000)
            self.offer(desk, self.req())
            actions, desk.outbox = desk._outbox, []
            result = {'ok': True, 'id': 'one'} if accepted else {'ok': False, 'reason': 'expired'}
            desk.read_results(actions, [result])
            before = desk.markup
            desk.handle(dict(kind='order_lost', requestId='one', seq=1, at=515))
            after = desk.markup
            desk.handle(dict(kind='order_lost', requestId='one', seq=2, at=516))
            self.assertEqual(desk.markup, after)
            self.assertEqual(after != before, accepted)

    def test_exact_off_parity_includes_actions_clocks_scores_and_journal(self):
        outcomes = []
        for knobs in ({}, {'delta_reference_quote_floor_bps': 0}):
            world, stream = LossWorld(), io.StringIO()
            with redirect_stdout(io.StringIO()):
                score = play_model(world, 8, Journal(stream),
                                   lambda w, l, n, j: make_delta(w, l, n, j, pairs=1, **knobs), fast=True)
            outcomes.append((world.sent, world.calls, score, stream.getvalue()))
        self.assertEqual(*outcomes)

    def test_strict_nonnegative_integer(self):
        for value in (True, False, -1, '11000', None, 1.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.desk(delta_reference_quote_floor_bps=value)
