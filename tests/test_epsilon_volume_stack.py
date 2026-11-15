"""The complete volume stack retains its fee, quote and recovery boundaries."""
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest

from dispatch import Journal
from models.delta import make_delta
from recovery import model_state, restore_state
from tests.test_gamma import GammaWorld, request
from tests.test_gamma_pairs import order_for


class VolumeStackTests(unittest.TestCase):
    def test_combined_settings_keep_floor_fee_distance_and_recovery(self):
        path = Path(__file__).resolve().parents[1] / 'docs/research/plans/epsilon/volume-stack-screen.json'
        plan = json.loads(path.read_text())
        self.assertEqual(len(plan['variants']), 4)
        for label, knobs in plan['variants'].items():
            with self.subTest(label=label):
                settings = {**plan['base'], **knobs}
                make = lambda: make_delta(GammaWorld(), 8, 500, Journal(io.StringIO()), **settings)
                desk = make()
                req = request(slacks=(800, 1440, 3000))
                req['note'] = {'text': ''}
                req['referenceFeeCents'] = 50000
                desk.quote(req)
                prices = desk._outbox[-1]['prices']
                floor = settings.get('delta_reference_quote_floor_bps', 0)
                if floor:
                    self.assertTrue(all(p >= 55000 for p in prices.values()))
                else:
                    self.assertTrue(all(p < 55000 for p in prices.values()))
                # Broad quote discounts must not broaden the expensive short-fee floor.
                self.assertEqual(desk.settings.short_fee_km, 45)
                self.assertEqual(desk.opening_fee_for(order_for(req)), settings['opening_fee_bps'])
                if 'tilt' in label:
                    option = req['options'][0]
                    self.assertEqual(desk.option_factors(req, option, 299, 0)['shortBps'], 9300)
                    self.assertEqual(desk.option_factors(req, option, 300, 0)['shortBps'], 10000)
                    self.assertEqual(desk.option_factors(req, option, 500, 0)['longBps'], 10000)
                    self.assertEqual(desk.option_factors(req, option, 501, 0)['longBps'], 10500)
                recovered = make()
                restore_state(recovered, deepcopy(model_state(desk)))
                self.assertEqual(recovered.win_target(), knobs['win_target_bps'])
                self.assertEqual(recovered.settings.premium_min_slack_minutes, 1440)
                self.assertEqual(recovered.delta_reference_quote_floor_bps, floor)
                self.assertEqual(recovered.intake_settings.delta_relaxed_slack_minutes, 300)
                self.assertFalse(recovered.settings.brake)
