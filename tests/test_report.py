import base64
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from capture import CapturedWorld, Journal
from demo import DemoWorld
from dispatch import FixedDesk, FixedPrices, play_practice
from week_report import UnsafeSource, analyze, generate, render


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache' / 'tmp'
CACHE.mkdir(parents=True, exist_ok=True)


def journal(*records):
    return b''.join(json.dumps(r, ensure_ascii=False).encode() + b'\n' for r in records)


def event(seq, kind='ledger', **fields):
    return {'type': 'event', 'event': {'seq': seq, 'at': seq + 10, 'kind': kind, **fields}}


def entry(seq, cents, kind='revenue', order=None, gig=None):
    return event(seq, line={'at': seq+10, 'kind': kind, 'cents': cents, 'orderId': order, 'gigId': gig})


class SourceTests(unittest.TestCase):
    def test_original_bytes_survive_invalid_utf8_crlf_blank_and_partial_records(self):
        source = b'{"type":"future","payload":{"unknown":true}}\r\n\n\xff\n{"partial":'
        model = analyze(source)
        self.assertEqual(base64.b64decode(model['source']['base64']), source)
        self.assertEqual(len(model['records']), 4)
        self.assertEqual(model['records'][0]['value']['payload'], {'unknown': True})
        for rec in model['records']:
            self.assertEqual(source[rec['offset']:rec['offset']+rec['length']], source.splitlines(keepends=True)[rec['line']-1])
        self.assertEqual(model['integrity']['invalidLines'], 3)
        self.assertIn('unterminated', {d['code'] for d in model['diagnostics']})

    def test_unknown_scalars_arrays_and_bad_event_shapes_remain_inspectable(self):
        source = journal(42, None, ['future'], {'type':'event','event':False}, event(0, 'future', newField={'nested':['x']}))
        model = analyze(source)
        self.assertEqual([r['value'] for r in model['records'][:3]], [42,None,['future']])
        self.assertEqual(model['timeline'][-1]['kind'], 'unknown record')
        self.assertTrue(any(x.get('event',{}).get('newField') for x in model['timeline']))

    def test_duplicate_object_keys_and_non_json_numbers_are_diagnosed(self):
        m=analyze(b'{"type":"future","x":1,"x":2}\n{"x":NaN}\n')
        self.assertEqual(m['integrity']['invalidLines'],2)
        self.assertEqual(base64.b64decode(m['source']['base64']),b'{"type":"future","x":1,"x":2}\n{"x":NaN}\n')

    def test_overflowing_json_numbers_preserve_source_without_breaking_report(self):
        source=b'{"type":"future","value":1e400}\n{"type":"future","value":-1e400}\n'
        model=analyze(source)
        self.assertEqual(base64.b64decode(model['source']['base64']),source)
        self.assertEqual(model['integrity']['invalidLines'],2)
        self.assertIn('report-data',render(model))

    def test_duplicate_events_count_once_conflicts_are_quarantined_and_gaps_flagged(self):
        a=entry(0,1000)
        m=analyze(journal(a,a,entry(2,-100,'driver_fee'),entry(2,-200,'driver_fee')))
        self.assertEqual(m['integrity']['duplicates'],1)
        self.assertEqual(m['integrity']['conflicts'],1)
        self.assertEqual(m['integrity']['gaps'],[[1,1]])
        self.assertEqual(m['reconciliation']['ledgerMarginCents'],1000)
        self.assertEqual(len(m['records']),4)
        self.assertEqual(len([t for t in m['timeline'] if t.get('conflict')]),2)
        self.assertEqual(m['reconciliation']['status'],'uncertain')

    def test_reconcile_shared_gig_and_unattributed_fees_without_order_allocation(self):
        post={'type':'action_result','at':0,'action':{'type':'post','stops':[{'orderId':'a','leg':0},{'orderId':'b','leg':0}]},'result':{'ok':True,'id':'g'}}
        m=analyze(journal(post,entry(0,1000,order='a'),entry(1,1000,order='b'),entry(2,-800,'driver_fee',gig='g'),entry(3,-50,'fine'),{'type':'score','score':{'marginCents':1150,'revenueCents':2000}}))
        self.assertEqual(m['reconciliation']['status'],'matches')
        self.assertEqual(m['reconciliation']['attribution'],{'directOrderCents':2000,'gigOnlyCents':-800,'unattributedCents':-50})
        self.assertEqual([o['directNetCents'] for o in m['orders']],[1000,1000])
        self.assertEqual(m['gigs'][0]['related'],['a','b'])
        self.assertEqual(len(m['ledger']),4)

    def test_end_snapshot_is_not_overwritten_by_earlier_win_events(self):
        m=analyze(journal(event(0,'order_won',order={'id':'r','status':'waiting','deliveredAt':[None]}),{'type':'snapshot','phase':'end','at':100,'snapshot':{'now':100,'endsAt':100,'orders':[{'id':'r','status':'delivered','deliveredAt':[90]}],'gigs':[{'id':'g','status':'done','stops':[{'orderId':'r','leg':0}]}]}},event(1,'gig_started',gigId='g')))
        order=m['orders'][0]
        self.assertEqual(order['data']['order']['status'],'delivered')
        self.assertEqual(order['data']['order']['deliveredAt'],[90])
        self.assertEqual(m['gigs'][0]['data']['lastObservedStatus'],'done')
        self.assertTrue(any(m['timeline'][i]['kind']=='snapshot' for i in order['history']))

    def test_final_score_does_not_prove_completed_simulation(self):
        m=analyze(journal({'type':'score','score':{'marginCents':0,'revenueCents':0}}))
        self.assertFalse(m['integrity']['verifiedEnd'])
        self.assertTrue(m['integrity']['finalScoreCaptured'])
        m=analyze(journal({'type':'snapshot','phase':'end','snapshot':{'now':20,'endsAt':20}}))
        self.assertTrue(m['integrity']['verifiedEnd'])
        self.assertFalse(m['integrity']['finalScoreCaptured'])

    def test_pending_intent_and_mismatched_results_are_never_assumed_successful(self):
        m=analyze(journal({'type':'action_intent','batchId':1,'actions':[{'type':'quote','requestId':'a'}]}, {'type':'action_intent','batchId':2,'actions':[{'type':'withdraw','gigId':'g'}]}, {'type':'act_result','batchId':2,'results':[]}))
        self.assertTrue(all(x.get('status')=='unknown' for x in m['timeline'] if x.get('action')))
        self.assertTrue({'pending_intent','result_count'}.issubset({d['code'] for d in m['diagnostics']}))

    def test_unquoted_is_only_inferred_from_reveal(self):
        m=analyze(journal(event(0,'price_request',request={'id':'r'})))
        self.assertEqual(m['orders'][0]['data']['quoteStatus'],'no accepted quote captured')
        self.assertEqual(m['orders'][0]['data']['outcome'],'no outcome captured')

    def test_brand_svg_ids_do_not_collide_with_report_navigation(self):
        from html.parser import HTMLParser
        class IDs(HTMLParser):
            def __init__(self):super().__init__();self.ids=[]
            def handle_starttag(self,tag,attrs):
                self.ids.extend(v for k,v in attrs if k=='id')
        parser=IDs();parser.feed(render(analyze(b'')))
        self.assertEqual(len(parser.ids),len(set(parser.ids)))
        self.assertIn('brand-title',parser.ids)
        self.assertIn('title',parser.ids)

    def test_xss_strings_cannot_escape_data_script_or_enter_html_markup(self):
        attack='</script><script>globalThis.pwned=true</script><img src=x onerror=alert(1)>\u2028&'
        m=analyze(journal(event(0,'future',newField=attack)))
        html=render(m)
        self.assertNotIn(attack,html)
        embedded=html.split('<script id="report-data" type="application/json">')[1].split('</script>')[0]
        restored=json.loads(embedded)
        self.assertEqual(restored['records'][0]['value']['event']['newField'],attack)
        self.assertIn("connect-src 'none'",html)
        self.assertNotIn('innerHTML', (ROOT/'report_assets/report.js').read_text())

    def test_credentials_are_refused_without_modifying_input_or_creating_output(self):
        samples=[{'unknown':{'Authorization':'Bearer synthetic-fixture'}}, {'apiKey':'synthetic-fixture'}, {'note':'Authorization: synthetic-fixture'}]
        for value in samples:
            with self.subTest(value=value), tempfile.TemporaryDirectory(dir=CACHE) as directory:
                p=Path(directory)/'input.jsonl';p.write_bytes(journal(value));out=Path(directory)/'report.html'
                with self.assertRaises(UnsafeSource):generate(p,out)
                self.assertFalse(out.exists());self.assertEqual(p.read_bytes(),journal(value))

    def test_malformed_credential_records_are_refused_even_with_invalid_utf8(self):
        for source in (b'{"password":"fixture",\xff', b'{"api\\u004bey":"fixture",\xff', b'{"x":"Bearer fixture","x":0}\n'):
            with self.subTest(source=source), self.assertRaises(UnsafeSource):analyze(source)

    def test_duplicate_batch_returns_do_not_create_false_accepted_actions(self):
        m=analyze(journal({'type':'action_intent','batchId':1,'actions':[{'type':'post','stops':[]}]}, {'type':'act_result','batchId':1,'results':[{'ok':True,'id':'first'}]}, {'type':'act_result','batchId':1,'results':[{'ok':True,'id':'second'}]}))
        actions=[x for x in m['timeline'] if x.get('action')]
        self.assertEqual(actions[0]['status'],'unknown')
        self.assertEqual(m['gigs'],[])
        self.assertIn('batch_conflict',{d['code'] for d in m['diagnostics']})

    def test_existing_output_or_source_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(dir=CACHE) as directory:
            p=Path(directory)/'input.jsonl';p.write_bytes(b'{}\n')
            with self.assertRaises(FileExistsError):generate(p,p)
            self.assertEqual(p.read_bytes(),b'{}\n')


class ReportIntegrationTests(unittest.TestCase):
    def test_demo_capture_round_trip_has_verified_end_and_reconciled_ledger(self):
        stream=io.StringIO()
        journal_=Journal(stream)
        journal_.record('run',mode='demo')
        with redirect_stdout(io.StringIO()):play_practice(DemoWorld(),4,FixedPrices(),journal_)
        m=analyze(stream.getvalue().encode())
        self.assertTrue(m['integrity']['verifiedEnd'])
        self.assertEqual(m['reconciliation']['status'],'matches')
        self.assertEqual(m['reconciliation']['ledgerMarginCents'],-5000)
        self.assertEqual(len(m['ledger']),2)


if __name__=='__main__':unittest.main()
