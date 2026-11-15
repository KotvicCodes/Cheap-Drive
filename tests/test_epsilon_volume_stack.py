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
    def test_deep_queue_replaces_old_admission_overrides_in_combo(self):
        folder = Path(__file__).resolve().parents[1] / 'docs/research/plans/epsilon'
        plan = json.loads((folder / 'volume-long.json').read_text())
        self.assertEqual(len(plan['variants']) - 1, 4)  # plus the paired fresh control
        self.assertEqual(len(plan['seeds']), 27)
        self.assertEqual(plan['base']['premium_min_slack_minutes'], 1440)
        settings = {**plan['base'], **plan['variants']['volume-stack-tilt-admit360-win4600']}
        desk = make_delta(GammaWorld(), 8, 500, Journal(io.StringIO()), **settings)
        self.assertEqual(desk.win_target(), 4600)
        self.assertEqual(desk.intake_settings.delta_relaxed_slack_minutes, 0)
        self.assertEqual(desk.intake_settings.delta_corridor_open_cap, 0)
        self.assertEqual(desk.settings.long_open_cap, 4)
        for slack in (350, 470, 490):
            req = request(slacks=(slack,))
            req['note'] = {'text': ''}
            options, _ = desk.eligible_options(req, 100, 0)
            self.assertEqual(bool(options), slack >= 480)

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

    def test_medium_loads_exact_full_champion_and_preserves_early_baseline(self):
        root = Path(__file__).resolve().parents[1]
        model = json.loads((root / 'models/epsilon-medium.json').read_text())
        plan = json.loads((root / 'docs/research/plans/epsilon/volume-long.json').read_text())
        self.assertEqual(model['name'], 'Epsilon Medium')
        self.assertEqual(model['factory'], plan['factory'])
        self.assertEqual(model['settings'], {**plan['base'], **plan['variants']['volume-stack-tilt-win4400']})
        from models import resolve_factory
        desk = resolve_factory(model['factory'])(GammaWorld(), 8, 500, Journal(io.StringIO()), **model['settings'])
        self.assertEqual(desk.win_target(), 4400)
        self.assertEqual(desk.intake_settings.delta_intake_max_backlog, 12)
        self.assertEqual(desk.driver_settings.pair_once, 0)
