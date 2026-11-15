from copy import deepcopy
import unittest
from recovery import model_state, restore_state
from spread.starter import steep
from tests.test_recovery import new_desk, request, emit, rebuild, snapshot, paired
from tests.test_gamma_pairs import order_for


class UrgentFeeTests(unittest.TestCase):
    def fixture(self, **settings):
        desk, history = new_desk(delta_urgent_fee_memory=1, **settings), []
        req=request()
        emit(desk,history,600,'price_request',request=req)
        order=order_for(req)
        emit(desk,history,620,'order_won',order=order)
        emit(desk,history,700,'deadline_close',orderId=order['id'])
        return desk,history,order

    def test_elapsed_original_curve_and_repeated_warnings(self):
        desk,history,order=self.fixture()
        reference=desk.requests[order['id']]['referenceFeeCents']
        for elapsed in (0,29,30,60,119,120,400):
            desk.now=700+elapsed
            schedule=desk.fees_for(order,1)
            original=steep(700,reference,8)
            current=max(s['feeCents'] for s in original if s['at']<=desk.now)
            self.assertEqual(schedule,[{'at':desk.now,'feeCents':current},*[s for s in original if s['at']>desk.now]])
        emit(desk,history,1150,'deadline_close',orderId=order['id'])
        self.assertEqual(desk.delta_urgent_since,{order['id']:700})
        self.assertEqual(desk.fees_for(order,1),[{'at':1150,'feeCents':int(reference*2.5+0.5)}])

    def test_pair_warning_is_remembered_before_split(self):
        desk,history,pair_id=paired(delta_urgent_fee_memory=1)
        emit(desk,history,700,'deadline_close',orderId='one')
        self.assertEqual(desk.delta_urgent_since,{'one':700})
        singles=[a for a in desk.world.actions if a['type']=='post' and {s['orderId'] for s in a['stops']}=={'one'}]
        self.assertTrue(singles)
        desk.now=850
        self.assertEqual(len(desk.fees_for(desk.orders['one'],1)),1)

    def test_drop_expiry_and_moved_private_window_keep_age(self):
        for event in ('gig_dropped','gig_expired'):
            desk,history,order=self.fixture()
            gig=desk.leg_gigs[order['id']][0]
            emit(desk,history,850,event,gigId=gig,driverId='fixture')
            self.assertEqual(desk.delta_urgent_since[order['id']],700)
            changed=deepcopy(desk.orders[order['id']]);changed['legs'][0]['pickup']['privateAddress']=True
            changed['legs'][0]['pickup']['window']={'from':2000,'to':2100}
            emit(desk,history,860,'order_changed',order=changed)
            self.assertEqual(desk.delta_urgent_since[order['id']],700)
            self.assertEqual(len(desk.fees_for(changed,1)),1)

    def test_checkpoint_and_receipt_free_recovery(self):
        desk,history,order=self.fixture(pairs=1)
        state=model_state(desk);copy=new_desk(delta_urgent_fee_memory=1,pairs=1)
        restore_state(copy,state)
        self.assertEqual(copy.delta_urgent_since,desk.delta_urgent_since)
        resumed=rebuild(desk,history,snapshot(desk,at=850),pairs=1,delta_urgent_fee_memory=1)
        self.assertEqual(resumed.delta_urgent_since,{order['id']:700})
        reprices=[a for a in resumed.world.actions if a['type']=='reprice']
        self.assertTrue(reprices)
        self.assertEqual(len(reprices[-1]['schedule']),1)
        snap=snapshot(desk,at=850)
        desk.world.recovery_checkpoint={'worldId':snap['worldId'],'lastSeq':history[-1]['seq'],'state':state}
        # Checkpoint directly on the reconstructed world's public fixture.
        world=type(desk.world)();world.gigs=deepcopy(desk.world.gigs);world.serial=desk.world.serial
        world.recovery_checkpoint=desk.world.recovery_checkpoint
        restored=new_desk(world,850,pairs=1,delta_urgent_fee_memory=1)
        restored.rejoin(snap,history)
        self.assertEqual(restored.delta_urgent_since,{order['id']:700})

    def test_stronger_current_evidence_but_no_booked_offer_inference(self):
        desk,history,order=self.fixture()
        gig=desk.leg_gigs[order['id']][0]
        desk.posts[gig]['schedule']=[{'at':700,'feeCents':100000}]
        desk.now=730
        self.assertEqual(desk.fees_for(order,1),[{'at':730,'feeCents':100000}])
        desk.delta_urgent_since.clear()
        self.assertEqual(desk.fees_for(order,1),steep(730,desk.requests[order['id']]['referenceFeeCents'],8))

    def test_nonurgent_pair_and_off_state_unchanged(self):
        desk,history,pair_id=paired(delta_urgent_fee_memory=1)
        baseline,_,_=paired()
        self.assertEqual(desk.posts,baseline.posts)
        self.assertNotIn('delta_urgent_since',model_state(baseline))
        for value in (True,False,-1,2,None,'1'):
            with self.subTest(value=value),self.assertRaises(ValueError):new_desk(delta_urgent_fee_memory=value)
