"""Two isolated price controllers and exact quote-time feedback/recovery."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import unittest
from unittest.mock import patch

from dispatch import Journal, play_model
from models.delta import make_delta
from recovery import model_state, restore_state
from tests.test_performance import LossWorld
from tests.test_recovery import World, emit, new_desk, request, snapshot


class DeltaSegmentedTargetsTests(unittest.TestCase):
    def desk(self, **knobs):
        desk=new_desk(delta_segmented_targets=1,win_target_bps=4200,**knobs)
        desk.roads['a','b']['km']=100
        desk.near30={'a':0,'b':6}
        return desk

    def test_off_preserves_actions_calls_score_and_journal(self):
        outcomes=[]
        for knobs in ({},{'delta_segmented_targets':0}):
            world,stream=LossWorld(),io.StringIO()
            with redirect_stdout(io.StringIO()):
                score=play_model(world,8,Journal(stream),
                                 lambda w,l,n,j:make_delta(w,l,n,j,pairs=1,**knobs))
            outcomes.append((world.sent,world.calls,score,stream.getvalue()))
        self.assertEqual(*outcomes)

    def test_exact_distance_lead_and_delivery_supply_boundaries(self):
        desk,req=self.desk(),request(deadline=2760)
        safe,rest='delta_segmented:safe:5500','delta_segmented:rest:4200'
        for km,expected in ((0,safe),(300,safe),(301,rest)):
            self.assertEqual(desk.tracker_for(req,km),expected)
        req['options'][0]['deadline']=2759
        self.assertEqual(desk.tracker_for(req,100),rest)
        req['options'].append(dict(req['options'][0],kind='next_day',deadline=2760))
        self.assertEqual(desk.tracker_for(req,100),safe)
        for nearby in (None,0,5,6):
            desk.near30['b']=nearby
            self.assertEqual(desk.tracker_for(req,100),safe if nearby==6 else rest)
        # High pickup supply cannot substitute for delivery supply.
        desk.near30={'a':100,'b':0}
        self.assertEqual(desk.tracker_for(req,100),rest)
        desk.near30={'b':6}
        self.assertEqual(desk.tracker_for(req,100),safe)
        self.assertEqual(desk.win_target(),4200)

    def test_safe_and_rest_feedback_and_quotes_are_independent(self):
        desk=self.desk()
        safe,rest=request('safe'),request('rest',deadline=1800)
        desk.quote(safe);desk.quote(rest)
        keys=dict(desk.quote_trackers)
        safe_key,rest_key=keys['safe'],keys['rest']
        self.assertNotEqual(safe_key,rest_key)
        self.assertEqual(set(desk.markups),{safe_key,rest_key})
        rest_price=deepcopy(desk.outbox[-1]['prices'])
        desk.near30['b']=0  # Feedback uses the original safe classification.
        desk.brake_mode='brake'
        desk.learn('safe',False)
        self.assertAlmostEqual(desk.markups[safe_key],15000*(1-.02*.55))
        self.assertEqual(desk.markups[rest_key],15000)
        desk.quote(request('rest-again',deadline=1800))
        self.assertEqual(desk.outbox[-1]['prices'],rest_price)
        safe_markup=desk.markups[safe_key]
        desk.learn('rest',True)
        self.assertAlmostEqual(desk.markups[rest_key],15000*(1+.02*(1-.42)))
        self.assertEqual(desk.markups[safe_key],safe_markup)
        self.assertEqual(desk.markup,15000)
        desk.learn('rest',False)
        self.assertEqual(desk.markups[safe_key],safe_markup)
        self.assertEqual(desk.win_target(),4200)

    def test_rest_never_inherits_a_global_target_or_brake_stepdown(self):
        desk=new_desk(delta_segmented_targets=1,win_target_safe_bps=5000,
                      win_target_bps=4600,capacity_valve=1,brake=1)
        desk.near30={}
        desk.quote(request())
        tracker=desk.quote_trackers['one']
        self.assertEqual(tracker,'delta_segmented:rest:4200')
        desk.brake_mode='brake'
        desk.learn('one',False)
        self.assertAlmostEqual(desk.markups[tracker],15000*(1-.02*.42))
        self.assertEqual(desk.win_target(),4200)

    def test_both_targets_and_markup_states_survive_json_checkpoint(self):
        desk=self.desk(win_target_safe_bps=5000)
        desk.quote(request('safe'));desk.quote(request('rest',deadline=1800))
        other=self.desk(win_target_safe_bps=5000)
        restore_state(other,json.loads(json.dumps(model_state(desk))))
        self.assertEqual(other.quote_trackers,desk.quote_trackers)
        for identity in ('safe','rest'):
            other.learn(identity,False);desk.learn(identity,False)
        self.assertEqual(other.markups,desk.markups)
        self.assertNotEqual(other.markups['delta_segmented:safe:5000'],
                            other.markups['delta_segmented:rest:4200'])

    def test_rejected_quotes_do_not_train_and_receipts_restore_original_pool(self):
        desk=self.desk()
        history=[]
        emit(desk,history,600,'price_request',request=request())
        receipts=deepcopy(desk.recovery_quotes)
        self.assertEqual(receipts['one']['tracker'],'delta_segmented:safe:5500')
        world=World();world.recovery_quote_receipts=receipts
        other=new_desk(world,620,delta_segmented_targets=1,win_target_bps=4200)
        with patch('models.delta_segmented_targets.DeltaSegmentedTargetsMixin.tracker_for',
                   return_value='delta_segmented:rest:4200'):
            other.rejoin(snapshot(desk,at=620),history)
        other.learn('one',False)
        self.assertAlmostEqual(other.markups['delta_segmented:safe:5500'],15000*(1-.02*.55))
        self.assertEqual(other.world.actions,[])
        rejected=self.desk()
        rejected.quote(request())
        actions=rejected.outbox;rejected.outbox=[]
        rejected.read_results(actions,[{'ok':False,'error':'expired'}])
        before=deepcopy(rejected.markups)
        rejected.learn('one',False)
        self.assertEqual(before,rejected.markups)
        self.assertNotIn('one',rejected.quote_trackers)

    def test_flags_and_incompatible_experiments(self):
        for bad in (True,-1,2,'1'):
            with self.assertRaises(ValueError):new_desk(delta_segmented_targets=bad)
        for bad in (True,0,10000,'5500'):
            with self.assertRaises(ValueError):self.desk(win_target_safe_bps=bad)
        for knobs in ({'markup_scope':'dealer'},{'delta_safe_quote_bps':9800},
                      {'delta_safe_target_bps':4600}):
            with self.assertRaises(ValueError):self.desk(**knobs)
