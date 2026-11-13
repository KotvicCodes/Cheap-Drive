"""Write a clearly synthetic, high-volume offline fixture for browser checks."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from demo import sample_request
from week_report import analyze, render


def fixture():
    records=[{'type':'run','mode':'demo','level':4}]
    seq=0
    def event(kind,**fields):
        nonlocal seq
        records.append({'type':'event','event':{'seq':seq,'at':480+seq*10,'kind':kind,**fields}})
        seq+=1
    attack='</script><img src=x onerror="globalThis.__xss=true">'
    for i in range(125):
        request=sample_request();request['id']=f'synthetic-{i:03}';request['note']={'text':attack if i==0 else 'Synthetic pickup note '+str(i),'language':'en'}
        event('price_request',request=request)
        if i>1:event('order_lost',requestId=request['id'])
        else:event('order_won',order={'id':request['id'],'dealerId':'demo-dealer','legs':request['legs'],'deadline':1200,'priceCents':10000,'option':'same_day'})
        records.append({'type':'action_result','at':480+i*10,'action':{'type':'quote','requestId':request['id'],'prices':{'same_day':10000}},'result':{'ok':True,'id':request['id']}})
    records.append({'type':'action_result','at':500,'action':{'type':'post','stops':[{'orderId':'synthetic-000','leg':0,'kind':'pickup'},{'orderId':'synthetic-001','leg':0,'kind':'delivery'}],'schedule':[{'at':500,'feeCents':15000}]},'result':{'ok':True,'id':'shared-gig'}})
    event('gig_booked',gigId='shared-gig',driverId='synthetic-driver',feeCents=15000)
    event('no_show',gigId='shared-gig',driverId='synthetic-driver')
    event('future_kind',payload={'unknown':'future-marker','html':attack})
    for kind,cents,oid,gid in [('revenue',20000,'synthetic-000',None),('driver_fee',-15000,None,'shared-gig')]:
        event('ledger',line={'at':3000,'kind':kind,'cents':cents,'orderId':oid,'gigId':gid})
    records.extend([
        {'type':'roster','phase':'initial','roster':[{'id':'synthetic-driver','homePlaceId':'demo-helsinki','rating':4.8}]},
        {'type':'map','map':{'places':[{'id':'demo-helsinki','name':'Synthetic Helsinki','lat':60,'lon':24},{'id':'demo-tampere','name':'Synthetic Tampere','lat':61,'lon':23}],'roads':[{'from':'demo-helsinki','to':'demo-tampere','minutes':100,'km':150}]}},
        {'type':'reveal','reveal':{'requests':[{'request':{'id':'revealed-unquoted'},'outcome':'unquoted'}]}},
        {'type':'score','at':4000,'score':{'marginCents':5000,'revenueCents':20000,'wonOrders':2,'onTimeShare':0.5,'undeliveredShare':0.5,'ranked':False}},
        {'type':'snapshot','phase':'end','snapshot':{'now':4000,'endsAt':4000}},
        {'type':'future_record','nested':{'arbitrary':['preserved',attack]}}
    ])
    return b''.join(json.dumps(r).encode()+b'\n' for r in records)+b'{"incomplete":'


if __name__=='__main__':
    output=ROOT/'.cache/browser-fixture.html'
    output.write_text(render(analyze(fixture())))
    print('Synthetic browser fixture generated.')
