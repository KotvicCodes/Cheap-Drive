"""Split learning, quote-time feedback, and durable-receipt recovery contracts."""
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


class DeltaSafeTargetTests(unittest.TestCase):
    def desk(self, target=4600, **knobs):
        desk=new_desk(win_target_bps=4200, delta_safe_target_bps=target, **knobs)
        desk.roads['a','b']['km']=100
        return desk

    def test_off_preserves_actions_score_calls_journal_and_learning(self):
        results=[]
        for knobs in ({}, {'delta_safe_target_bps':0}):
            world, stream = LossWorld(), io.StringIO()
            with redirect_stdout(io.StringIO()):
                score=play_model(world,8,Journal(stream),
                                 lambda w,l,n,j:make_delta(w,l,n,j,pairs=1,**knobs))
            results.append((world.sent,world.calls,score,stream.getvalue()))
        self.assertEqual(*results)

    def test_distance_backlog_slack_whole_menu_and_floor_gates(self):
        desk, req = self.desk(), request()
        safe = 'delta_safe_target:4600'
        for km,expected in ((49,'global'),(50,safe),(300,safe),(301,'global')):
            self.assertEqual(desk.tracker_for(req,km),expected)
        for count,expected in ((15,safe),(16,'global')):
            with patch.object(desk,'orders_without_driver',return_value=set(range(count))):
                self.assertEqual(desk.tracker_for(req,100),expected)
        for slack,expected in ((719,'global'),(720,safe)):
            with patch.object(desk,'slack',return_value=slack):
                self.assertEqual(desk.tracker_for(req,100),expected)
        req['options'].append(dict(req['options'][0],kind='next_day'))
        with patch.object(desk,'slack',side_effect=lambda r,o:719 if o['kind']=='same_day' else 1440):
            self.assertEqual(desk.tracker_for(req,100),'global')
        req['options'].pop()
        req['referenceFeeCents']=10000
        desk.markups[safe]=10000
        for price,expected in ((11000,safe),(10999,'global')):
            req['options'][0]['listPriceCents']=price
            self.assertEqual(desk.tracker_for(req,100),expected)
        self.assertEqual(desk.win_target(),4200)  # Gate inspection has no target side effect.

    def test_private_premium_tradein_low_level_and_brake_exclusions(self):
        desk, req = self.desk(), request()
        for kind in ('pickup','delivery'):
            req['legs'][0][kind]['privateAddress']=True
            self.assertEqual(desk.tracker_for(req,100),'global')
            req['legs'][0][kind]['privateAddress']=False
        req['legs'][0]['car']['premium']=True
        self.assertEqual(desk.tracker_for(req,100),'global')
        req['legs'][0]['car']['premium']=False
        req['legs'].append(deepcopy(req['legs'][0]))
        self.assertEqual(desk.tracker_for(req,100),'global')
        req['legs'].pop()
        desk.level=3
        self.assertEqual(desk.tracker_for(req,100),'global')
        desk.level=8
        for brake in ('caution','brake'):
            desk.brake_mode=brake
            self.assertEqual(desk.tracker_for(req,100),'global')

    def test_split_control_and_higher_target_have_same_first_price_and_independent_learning(self):
        prices=[]
        for target in (4200,4600,5000):
            desk=self.desk(target=target)
            req=request()
            desk.quote(req)
            prices.append(desk.outbox[0]['prices'])
            tracker=desk.quote_trackers[req['id']]
            self.assertEqual(tracker,'delta_safe_target:'+str(target))
            self.assertEqual(desk.win_target(),4200)
            quote=[r for r in map(json.loads,desk.journal.output.getvalue().splitlines())
                   if r['type']=='beta_quote'][0]
            self.assertEqual(quote['winTargetBps'],target)
            start=desk.tracker_markup(tracker)
            # Congestion/brake may change before the outcome. Use the quoted target.
            desk.brake_mode='brake'
            with patch.object(desk,'orders_without_driver',return_value=set(range(100))):
                desk.learn(req['id'],False)
            self.assertAlmostEqual(desk.markups[tracker],start*(1-.02*target/10000))
            self.assertEqual(desk.markup,15000)
            after=desk.markups[tracker]
            desk.learn(req['id'],True)
            self.assertEqual(desk.markups[tracker],after)
        self.assertEqual(prices,[prices[0]]*3)

    def test_checkpoint_and_rejected_receipts(self):
        desk=self.desk()
        req=request()
        desk.quote(req)
        other=self.desk()
        restore_state(other,deepcopy(model_state(desk)))
        tracker=other.quote_trackers[req['id']]
        other.learn(req['id'],True)
        self.assertAlmostEqual(other.markups[tracker],15000*(1+.02*(1-.46)))
        actions=desk.outbox
        desk.outbox=[]
        desk.read_results(actions,[{'ok':False,'error':'expired'}])
        self.assertNotIn(req['id'],desk.pending)
        self.assertNotIn(req['id'],desk.quote_trackers)
        before=deepcopy(desk.markups)
        desk.learn(req['id'],False)
        self.assertEqual(desk.markups,before)

    def test_receipts_and_history_restore_quote_time_target(self):
        desk=self.desk()
        history=[]
        emit(desk,history,600,'price_request',request=request())
        receipts=deepcopy(desk.recovery_quotes)
        self.assertEqual(receipts['one']['tracker'],'delta_safe_target:4600')
        # Receipt wins when history-only admission is reconstructed differently.
        world=World()
        world.recovery_quote_receipts=receipts
        other=new_desk(world,620,win_target_bps=4200,delta_safe_target_bps=4600)
        with patch('models.delta_safe_target.DeltaSafeTargetMixin.tracker_for',return_value='global'):
            other.rejoin(snapshot(desk,at=620),history)
        self.assertEqual(other.quote_trackers['one'],'delta_safe_target:4600')
        other.brake_mode='brake'
        other.learn('one',False)
        self.assertAlmostEqual(other.markups['delta_safe_target:4600'],15000*(1-.02*.46))
        self.assertEqual(other.world.actions,[])

    def test_validation_and_no_discount_or_alternate_scope_bundle(self):
        for bad in (-1,True,10000,'4600'):
            with self.assertRaises(ValueError):new_desk(delta_safe_target_bps=bad)
        for knobs in ({'delta_safe_target_min_slack_minutes':-1},
                      {'delta_safe_target_max_backlog':True},
                      {'delta_safe_quote_bps':9800}, {'markup_scope':'dealer'}):
            with self.assertRaises(ValueError):self.desk(**knobs)
