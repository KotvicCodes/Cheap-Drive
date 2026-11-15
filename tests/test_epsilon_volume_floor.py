"""Volume targets remain bounded by each brake and premium admission after recovery."""
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


class VolumeFloorCompositionTests(unittest.TestCase):
    def test_volume_combinations_keep_premium_guard_brake_and_recovery(self):
        folder=Path(__file__).resolve().parents[1]/'docs/research/plans/epsilon'
        plans=[json.loads((folder/name).read_text()) for name in
               ('volume-floor-screen.json','volume-floor-milder-screen.json',
                'volume-floor-early-screen.json')]
        cases=[(plan,label,knobs) for plan in plans for label,knobs in plan['variants'].items()]
        for plan,label,knobs in cases:
            with self.subTest(label=label):
                settings={**plan['base'],**knobs}
                self.assertEqual(plan['base']['premium_min_slack_minutes'],1440)
                desk=make_delta(GammaWorld(),8,500,Journal(io.StringIO()),**settings)
                self.assertEqual(desk.win_target(),knobs['win_target_bps'])
                premium=request(slacks=(1439,1440,1441))
                premium['note']={'text':''};premium['legs'][0]['car']['premium']=True
                desk.quote(premium)
                self.assertEqual(set(desk._outbox[-1]['prices']),{'next_day','within_3_days'})
                if 'projected350'in label:
                    # Two actual late outcomes among40 gives500bps;three750.
                    desk.orders.update({str(i):dict(id=str(i),status='delivered',deliveredAt=[100]) for i in range(40)})
                    desk.brake_late.update(('0','1'));desk.update_brake()
                    self.assertEqual(desk.win_target(),knobs['brake_caution_target_bps'])
                    desk.brake_late.add('2');desk.update_brake()
                    self.assertEqual(desk.win_target(),knobs['brake_target_bps'])
                else:
                    for i in range(4):
                        req=request(identity='near'+str(i));req['note']={'text':''}
                        desk.requests[req['id']]=req
                        desk.orders[req['id']]=order_for(req,deadline=1000)
                        if i==1:self.assertEqual(desk.win_target(),knobs.get('delta_service_target_bps',3000))
                    self.assertEqual(desk.win_target(),knobs.get('delta_service_hard_target_bps',2400))
                recovered=make_delta(GammaWorld(),8,500,Journal(io.StringIO()),**settings)
                restore_state(recovered,deepcopy(model_state(desk)))
                self.assertEqual(recovered.win_target(),desk.win_target())
                if 'projected350'in label:
                    for order in recovered.orders.values():order['status']='cancelled'
                    recovered.now+=121;recovered.update_brake()
                else:
                    for identity in recovered.orders:
                        recovered.leg_gigs[identity]={0:'g-'+identity};recovered.booked.add('g-'+identity)
                self.assertEqual(recovered.win_target(),knobs['win_target_bps'])
