"""High intake keeps its target while existing fee controls buy pickup time."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from recovery import model_state, restore_state
from tests.test_recovery import new_desk, request, emit
from tests.test_gamma_pairs import order_for


class VolumeFeeCompositionTests(unittest.TestCase):
    def test_fee_grid_keeps_volume_and_ages_urgent_fees_after_recovery(self):
        path = Path(__file__).resolve().parents[1] / 'docs/research/plans/epsilon/volume-buy-service-screen.json'
        plan = json.loads(path.read_text())
        for label, knobs in plan['variants'].items():
            with self.subTest(label=label):
                settings = {**plan['base'], **knobs}
                self.assertEqual(settings['premium_min_slack_minutes'], 1440)
                desk, history = new_desk(**settings), []
                # Exercise the general fee opening, outside the existing short-route floor.
                desk.roads['a', 'b'] = {**desk.roads['a', 'b'], 'km': 100}
                req = request(deadline=6000)
                req['note'] = {'text': ''}
                req['legs'][0]['car']['premium'] = False
                emit(desk, history, 600, 'price_request', request=req)
                order = order_for(req)
                emit(desk, history, 620, 'order_won', order=order)
                self.assertEqual(desk.win_target(), knobs['win_target_bps'])
                self.assertFalse(desk.settings.brake)
                self.assertFalse(desk.delta_service['delta_service_brake'])
                schedule = desk.fees_for(order, 1)
                reference = req['referenceFeeCents']
                self.assertEqual(schedule[0]['feeCents'], int(reference * settings['opening_fee_bps'] / 10000 + 0.5))
                if 'fasturgent' in label:
                    self.assertEqual(schedule[1], {'at': 800, 'feeCents': int(reference * 1.1 + 0.5)})
                    self.assertEqual(schedule[-1]['at'], desk.true_last_pickup(order) - 720)
                    # The first deadline warning, not the latest repost, owns this clock.
                    emit(desk, history, 1000, 'deadline_close', orderId=order['id'])
                    desk.now = 1060
                    state = deepcopy(model_state(desk))
                    recovered = new_desk(now=1060, **settings)
                    restore_state(recovered, state)
                    self.assertEqual(recovered.fees_for(order, 1)[0],
                                     {'at': 1060, 'feeCents': int(reference * 2 + 0.5)})
                    self.assertEqual(recovered.win_target(), knobs['win_target_bps'])
