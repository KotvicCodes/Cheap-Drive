from copy import deepcopy
import io
import unittest

from dispatch import Journal
from models.delta import make_delta
from tests.test_gamma import GammaWorld, request


class ReadinessFeeTests(unittest.TestCase):
    def fixture(self, cut=600, readiness=720, level=8, **settings):
        desk = make_delta(GammaWorld(), level, 500, Journal(io.StringIO()), pairs=1,
                          delta_readiness_early_cut_bps=cut, **settings)
        req = request(slacks=(7000,))
        req['note'] = {'text': ''}
        req['referenceFeeCents'] = 10000
        req['legs'][0]['pickup']['window']['from'] = desk.now + readiness
        desk.requests[req['id']] = req
        order = dict(id=req['id'], legs=deepcopy(req['legs']), lastPickupAt=7000,
                     deadline=7200, status='waiting', deliveredAt=[None])
        return desk, req, order

    def test_readiness_boundary_and_only_first_two_rungs_change(self):
        for readiness in (719, 720):
            desk, req, order = self.fixture(readiness=readiness)
            base, _, baseline_order = self.fixture(cut=0, readiness=readiness)
            original = base.fees_for(baseline_order, 1)
            result = desk.fees_for(order, 1)
            expected = deepcopy(original)
            if readiness == 720:
                for step in expected[:2]:step['feeCents'] -= 600
            self.assertEqual(result, expected)
            self.assertEqual(result[2:], original[2:])
            self.assertEqual(sorted(set(x['at'] for x in result)), [x['at'] for x in result])
            self.assertEqual(sorted(x['feeCents'] for x in result), [x['feeCents'] for x in result])

    def test_segment_floors_and_collapsed_schedules(self):
        desk, req, order = self.fixture(town_starved_near30=2, town_starved_opening_fee_bps=7900)
        desk.near30[req['legs'][0]['pickup']['placeId']] = 1
        schedule = [{'at':500, 'feeCents':8000}, {'at':600, 'feeCents':8100}, {'at':700,'feeCents':15000}]
        self.assertEqual(desk._readiness_fee_schedule(order,1,schedule),
                         [{'at':500,'feeCents':7900},{'at':700,'feeCents':15000}])
        self.assertEqual(desk._readiness_fee_schedule(order,1,schedule[:2]),schedule[:2])
        desk.now = 6900
        self.assertEqual(desk.fees_for(order,1)[-1]['at'],6900)

    def test_exclusions_keep_original_schedule(self):
        for kind in ('urgent','level1','short','long','premium','private','manual','plates','trade_in'):
            desks=[]
            for cut in (0,800):
                desk, req, order = self.fixture(cut=cut, level=1 if kind=='level1' else 8)
                if kind=='urgent':desk.urgent.add(order['id'])
                if kind in ('short','long'):
                    desk.roads['helsinki','tampere']['km'] = 44 if kind=='short' else 501
                if kind=='premium':order['legs'][0]['car']['premium']=True
                if kind=='private':order['legs'][0]['pickup']['privateAddress']=True
                if kind in ('manual','plates'):req['note']['text']='Manual licence' if kind=='manual' else 'Needs plates'
                if kind=='trade_in':order['legs']*=2
                desks.append(desk.fees_for(order,1))
            with self.subTest(kind=kind):self.assertEqual(*desks)

    def test_parsed_readiness_and_post_age(self):
        desk, req, order = self.fixture(readiness=0)
        req['note']['text']='Ready tomorrow at 12:00'
        desk.first_posted[order['id']]=0
        base, other, baseline_order=self.fixture(cut=0,readiness=0)
        other['note']['text']=req['note']['text'];base.first_posted[order['id']]=0
        original=base.fees_for(baseline_order,1);result=desk.fees_for(order,1)
        self.assertLess(result[0]['feeCents'], original[0]['feeCents'])
        self.assertEqual(result[-1],original[-1])
        self.assertEqual(desk.first_posted[order['id']],0)

    def test_validation(self):
        for value in (True,False,-1,None,'600',0.5):
            with self.subTest(value=value),self.assertRaises(ValueError):self.fixture(cut=value)
