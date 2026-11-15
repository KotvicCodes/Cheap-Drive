from copy import deepcopy
import io
import json
import unittest
from dispatch import Journal
from models.delta import make_delta
from models.delta_note_urgency import maximum_schedule
from spread.starter import steep
from tests.test_gamma import GammaWorld, request


class NoteUrgencyTests(unittest.TestCase):
    def fixture(self, enabled=1, note='Deliver before tomorrow 12:00', **settings):
        stream=io.StringIO()
        desk=make_delta(GammaWorld(),8,500,Journal(stream),pairs=1,
                        delta_note_urgency=enabled,**settings)
        req=request(slacks=(7000,));req['referenceFeeCents']=10001;req['note']={'text':note}
        desk.requests[req['id']]=req
        order=dict(id=req['id'],legs=deepcopy(req['legs']),deadline=7000,lastPickupAt=6820,
                   status='waiting',deliveredAt=[None])
        return desk,order,stream

    def test_curve_is_anchored_before_note_cutoff_and_reposts_do_not_reset(self):
        desk,order,_=self.fixture()
        cutoff=1440+720-180
        anchor=cutoff-180
        for elapsed in (0,30,120,400):
            desk.now=anchor+elapsed
            result=desk.fees_for(order,1)
            expected=max(s['feeCents'] for s in steep(anchor,10001,8) if s['at']<=desk.now)
            self.assertEqual(result[0],{'at':desk.now,'feeCents':expected})
            self.assertEqual(result,desk.fees_for(order,1))
            self.assertEqual(sorted({s['at'] for s in result}),[s['at'] for s in result])
            self.assertEqual(sorted(s['feeCents'] for s in result),[s['feeCents'] for s in result])
        self.assertEqual(result,[{'at':anchor+400,'feeCents':25003}])

    def test_before_trigger_preserves_normal_curve_and_actual_warning_policy(self):
        desk,order,_=self.fixture();base,original,_=self.fixture(enabled=0)
        for now in (500,1000,1799):
            desk.now=base.now=now
            a,b=desk.fees_for(order,1),base.fees_for(original,1)
            times={now,*(s['at'] for s in a+b if now<=s['at']<1800)}
            for at in times:
                self.assertEqual(max(s['feeCents'] for s in a if s['at']<=at),
                                 max(s['feeCents'] for s in b if s['at']<=at))
        desk.urgent.add(order['id']);base.urgent.add(original['id'])
        desk.now=base.now=2200
        self.assertEqual(desk.fees_for(order,1),base.fees_for(original,1))

    def test_neutral_site_calendars_normal_notes_and_infeasible_route(self):
        for note in ('','Manual, plates','Ready after Friday 12:00; Deliver before tomorrow 12:00'):
            desk,order,stream=self.fixture(note=note)
            base,original,_=self.fixture(enabled=0,note=note)
            desk.now=base.now=2200
            self.assertEqual(desk.fees_for(order,1),base.fees_for(original,1))
            if 'Friday'in note:
                rows=[json.loads(x) for x in stream.getvalue().splitlines()]
                self.assertTrue(any(r.get('reason')=='no_stable_route' for r in rows))
        desk,order,_=self.fixture(note='')
        for leg in order['legs']:
            leg['delivery']['hours']=dict(opens=540,closes=720,weekdays=[0,1,2,3,4],saturday=None)
        base,original,_=self.fixture(enabled=0,note='');original['legs']=deepcopy(order['legs'])
        self.assertEqual(desk.fees_for(order,1),base.fees_for(original,1))

    def test_current_order_version_and_plates_use_visit_cutoff(self):
        desk,order,_=self.fixture(note='Destination closes at 12:00; Needs plates')
        order['deadline']=4000;order['lastPickupAt']=3820
        first=desk.fees_for(order,1)
        order['deadline']=7000;order['lastPickupAt']=6820
        order['legs'][0]['pickup'].update(privateAddress=True,window={'from':6000,'to':6500})
        second=desk.fees_for(order,1)
        self.assertNotEqual(first,second)
        self.assertGreater(second[-1]['at'],first[-1]['at'])
        # Changing now cannot erase the stable cutoff used for an old version.
        order['deadline']=4000;order['lastPickupAt']=3820
        order['legs'][0]['pickup'].update(privateAddress=False,window={'from':0,'to':20000})
        desk.now=5000
        self.assertEqual(desk.fees_for(order,1)[0]['feeCents'],25003)

    def test_pairs_trade_ins_and_schedule_merge(self):
        desk,order,_=self.fixture()
        pair=desk._pair_schedule(10001,6820,False)
        base,_,_=self.fixture(enabled=0)
        self.assertEqual(pair,base._pair_schedule(10001,6820,False))
        order['legs']*=2
        self.assertEqual(desk._note_urgency_schedule(order,1,pair),pair)
        normal=[{'at':0,'feeCents':100},{'at':30,'feeCents':150},{'at':90,'feeCents':150}]
        anticipated=[{'at':60,'feeCents':120},{'at':90,'feeCents':200}]
        self.assertEqual(maximum_schedule(normal,anticipated,45),
                         [{'at':45,'feeCents':150},{'at':90,'feeCents':200}])

    def test_validation(self):
        for value in (True,False,-1,None,2,'1'):
            with self.subTest(value=value),self.assertRaises(ValueError):self.fixture(enabled=value)
