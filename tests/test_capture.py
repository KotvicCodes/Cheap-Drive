from contextlib import redirect_stdout
import io
import json
import unittest
from unittest.mock import patch

from capture import CapturedWorld, Journal
from demo import DemoWorld
from dispatch import FixedDesk, FixedPrices, play_practice


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.stream=io.StringIO();self.journal=Journal(self.stream)

    def records(self):
        return [json.loads(s) for s in self.stream.getvalue().splitlines()]

    def test_intent_exists_at_send_and_full_return_exists_before_processing(self):
        stream=self.stream
        class World:
            def act(self,actions):
                self_intent=json.loads(stream.getvalue().splitlines()[-1])
                assert self_intent['type']=='action_intent'
                assert self_intent['actions']==actions
                return [{'ok':True,'id':str(i)} for i in range(len(actions))]
            def advance(self,actions,**kwargs):
                assert json.loads(stream.getvalue().splitlines()[-1])['method']=='advance'
                return {'now':1,'events':[{'seq':0,'at':1,'kind':'future','unknown':[1,2]}],'results':[{'ok':True} for _ in actions]}
        world=CapturedWorld(World(),self.journal)
        actions=[{'type':'future','i':i} for i in range(121)]
        step=world.advance(actions=actions,max=1)
        records=self.records()
        self.assertEqual([len(r['actions']) for r in records if r['type']=='action_intent'],[50,21,50])
        self.assertEqual(records[-1]['response']['events'],step['events'])
        self.assertEqual(len(step['results']),121)

    def test_entire_event_batch_is_saved_even_when_handler_crashes(self):
        class Crash(FixedDesk):
            def handle(self,event):raise RuntimeError('fixture failure')
        with patch('dispatch.FixedDesk',Crash), self.assertRaises(RuntimeError):
            play_practice(DemoWorld(),4,FixedPrices(),self.journal)
        batches=[r for r in self.records() if r['type']=='advance_batch']
        self.assertEqual(batches[-1]['response']['events'][0]['kind'],'price_request')

    def test_starter_internal_sends_are_journaled_before_trade_in_post(self):
        from test_dispatch import RecordingWorld
        world=CapturedWorld(RecordingWorld(),self.journal)
        desk=FixedDesk(world,4,555,FixedPrices(),self.journal)
        from demo import sample_request
        request=sample_request();request['legs']*=2;desk.requests[request['id']]=request
        order={'id':request['id'],'dealerId':'d','option':'same_day','priceCents':100,'deadline':1200,'legs':request['legs'],'status':'waiting','deliveredAt':[None,None],'lastPickupAt':1080}
        desk.win(order)  # Starter sends immediately for multi-leg posts.
        self.assertEqual(self.records()[0]['type'],'action_intent')
        self.assertEqual(self.records()[1]['type'],'act_result')
        self.assertFalse(self.records()[1]['results'][0]['ok'])

    def test_lost_return_leaves_intent_with_unknown_outcome(self):
        class World:
            def act(self,actions):raise ConnectionError('fixture connection lost')
        world=CapturedWorld(World(),self.journal)
        with self.assertRaises(ConnectionError):world.act([{'type':'withdraw','gigId':'g'}])
        self.assertEqual([r['type'] for r in self.records()],['action_intent'])

    def test_journal_redacts_nested_credentials_and_does_not_log_exception_messages(self):
        self.journal.record('test',payload={'Authorization':'Bearer synthetic-fixture','note':'SPREAD_KEY=synthetic-fixture'})
        self.assertNotIn('synthetic-fixture',self.stream.getvalue())
        world=CapturedWorld(object(),self.journal)
        def fail():raise ValueError('sensitive exception text')
        world.optional('map',fail)
        self.assertNotIn('sensitive exception text',self.stream.getvalue())

if __name__=='__main__':unittest.main()
