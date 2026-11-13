"""Generate a private, standalone offline report from an existing JSONL journal."""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from capture import SECRET_KEY, SECRET_TEXT

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / 'VERSION').read_text().strip()
EVENT_KINDS = set('price_request order_won order_lost order_changed order_cancelled release gig_viewed gig_booked gig_dropped gig_started driver_late no_show gig_expired offer_answered picked_up visit_failed delivered deadline_close forecast ledger'.split())
INCIDENTS = set('order_cancelled gig_dropped no_show driver_late gig_expired visit_failed deadline_close release'.split())


class UnsafeSource(ValueError):
    pass


def credentials(value):
    if isinstance(value, dict):
        return any(SECRET_KEY.fullmatch(k) or credentials(v) for k, v in value.items())
    if isinstance(value, list):
        return any(credentials(v) for v in value)
    return isinstance(value, str) and bool(SECRET_TEXT.search(value))


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def mapping(value):
    return value if isinstance(value, dict) else {}


def array(value):
    return value if isinstance(value, list) else []


def identity(value):
    return value if isinstance(value, str) and value else None


def refs(value):
    found = {k: set() for k in ('order', 'gig', 'driver')}
    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                entity = {'orderId': 'order', 'requestId': 'order', 'gigId': 'gig', 'driverId': 'driver'}.get(k)
                if entity and identity(x):
                    found[entity].add(x)
                if k in ('request', 'order', 'gig', 'driver') and isinstance(x, dict) and identity(x.get('id')):
                    found['order' if k == 'request' else k].add(x['id'])
                plural = {'orders': 'order', 'openRequests': 'order', 'gigs': 'gig', 'roster': 'driver'}.get(k)
                if plural and isinstance(x, list):
                    for item in x:
                        if isinstance(item, dict) and identity(item.get('id')):
                            found[plural].add(item['id'])
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(value)
    return {k: sorted(v) for k, v in found.items()}


def load_source(source: bytes):
    """Never replace the original bytes with reserialized JSON, including invalid UTF-8."""
    records, diagnostics = [], []
    offset = 0
    def invalid_constant(_):
        raise ValueError('non JSON constant')
    for line_number, raw in enumerate(source.split(b'\n'), 1):
        if offset == len(source):
            break
        length = len(raw) + int(offset + len(raw) < len(source))
        record = {'line': line_number, 'offset': offset, 'length': length, 'value': None, 'error': None}
        scan = raw.decode('utf-8', errors='replace')
        raw_keys = re.findall(r'"((?:[^"\\]|\\.)*)"\s*:', scan)
        sensitive_key = False
        for raw_key in raw_keys:
            try:
                sensitive_key = sensitive_key or bool(SECRET_KEY.fullmatch(json.loads('"' + raw_key + '"')))
            except (ValueError, TypeError):
                pass
        if sensitive_key or SECRET_TEXT.search(scan):
            raise UnsafeSource('Credential-bearing input is refused. The original source has not been modified.')
        try:
            text = raw.decode('utf-8')
            if SECRET_TEXT.search(text) or re.search(r'(?i)"(?:authorization|api[_-]?key|spread[_-]?key|access_token|password)"\s*:', text):
                raise UnsafeSource('Credential-bearing input is refused. The original source has not been modified.')
            # Repeated JSON object keys are not silently collapsed.
            duplicate_keys = []
            def pairs(items):
                result = {}
                for key, value in items:
                    if SECRET_KEY.fullmatch(key) or credentials(value):
                        raise UnsafeSource('Credential-bearing input is refused. The original source has not been modified.')
                    if key in result:
                        duplicate_keys.append(True)
                    result[key] = value
                return result
            value = json.loads(text, parse_constant=invalid_constant, object_pairs_hook=pairs)
            if credentials(value):
                raise UnsafeSource('Credential-bearing input is refused. The original source has not been modified.')
            record['value'] = value
            if duplicate_keys:
                record['error'] = 'duplicate JSON keys; parsed view uses last value, exact source retained'
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            if isinstance(error, UnsafeSource):
                raise
            record['error'] = 'invalid UTF-8' if isinstance(error, UnicodeDecodeError) else ('blank line' if not raw.strip() else 'invalid JSON')
        if record['error']:
            diagnostics.append({'code': 'source_line', 'line': line_number, 'message': record['error']})
        records.append(record)
        offset += length
    if source and not source.endswith(b'\n'):
        diagnostics.append({'code': 'unterminated', 'message': 'Last line has no newline. It may be partial even if its JSON parses.'})
    if not source:
        diagnostics.append({'code': 'empty', 'message': 'Source is empty.'})
    return records, diagnostics


def analyze(source: bytes):
    records, diagnostics = load_source(source)
    timeline, candidates, intents, responses = [], [], {}, {}
    ambiguous_batches = set()
    captures = defaultdict(list)
    scores, runs = [], []

    def diag(code, message, line=None):
        diagnostics.append({'code': code, 'message': message, 'line': line})

    def row(kind, at, payload, line, **extra):
        item = {'kind': str(kind), 'at': at if integer(at) else None, 'line': line,
                'refs': refs(payload), **extra}
        timeline.append(item)
        return item

    for rec in records:
        r, line = mapping(rec['value']), rec['line']
        kind = r.get('type')
        if kind == 'run':
            runs.append(r)
        if kind in ('snapshot', 'map', 'roster', 'reveal'):
            captures[kind].append(line)
        if kind in ('score', 'daily_score') and isinstance(r.get('score'), dict):
            scores.append({'at': r.get('at'), 'score': r['score'], 'final': kind == 'score', 'line': line})
        if kind == 'event':
            candidates.append((r.get('event'), line, None))
        elif kind == 'advance_batch':
            response = mapping(r.get('response'))
            for index, event in enumerate(array(response.get('events'))):
                candidates.append((event, line, index))
            if integer(r.get('batchId')):
                if r['batchId'] in responses:
                    ambiguous_batches.add(r['batchId'])
                    diag('batch_conflict', 'Repeated return batch identifier; action results are ambiguous.', line)
                responses[r['batchId']] = (array(response.get('results')), line)
        elif kind == 'act_result' and integer(r.get('batchId')):
            if r['batchId'] in responses:
                ambiguous_batches.add(r['batchId'])
                diag('batch_conflict', 'Repeated return batch identifier; action results are ambiguous.', line)
            responses[r['batchId']] = (array(r.get('results')), line)
        elif kind == 'action_intent' and integer(r.get('batchId')):
            if r['batchId'] in intents:
                ambiguous_batches.add(r['batchId'])
                diag('batch_conflict', 'Repeated outgoing batch identifier; action association is ambiguous.', line)
            intents[r['batchId']] = (r, line)
        elif kind == 'action_result':
            action, result = mapping(r.get('action')), mapping(r.get('result'))
            row('action:' + str(action.get('type', 'unknown')), r.get('at'), r, line,
                action=action, result=result, status='accepted' if result.get('ok') is True else 'rejected' if result.get('ok') is False else 'unknown')
        elif kind not in ('score', 'daily_score'):
            row(kind or 'unknown record', r.get('at'), r, line)
    for batch, (intent, line) in intents.items():
        actions = array(intent.get('actions'))
        results, response_line = responses.get(batch, ([], None))
        if response_line is None:
            diag('pending_intent', 'Outgoing call has no captured response. Server outcome is unknown; do not assume rejection or retry safely.', line)
        elif len(results) != len(actions):
            diag('result_count', 'Action/result counts differ; unmatched payloads remain in raw records.', response_line)
        for index, action in enumerate(actions):
            action = mapping(action)
            result = mapping(results[index]) if index < len(results) and batch not in ambiguous_batches else {}
            row('action:' + str(action.get('type', 'unknown')), intent.get('at'), action, line,
                action=action, result=result, responseLine=response_line, batchId=batch, actionIndex=index,
                status='accepted' if result.get('ok') is True else 'rejected' if result.get('ok') is False else 'unknown')
    for batch, (_, line) in responses.items():
        if batch not in intents:
            diag('orphan_response', 'Captured response has no outgoing intent.', line)

    groups = defaultdict(list)
    unsequenced = []
    for event, line, index in candidates:
        if not isinstance(event, dict):
            diag('invalid_event', 'Event is not an object; retained in raw records.', line)
            continue
        if integer(event.get('seq')):
            groups[event['seq']].append((event, line, index))
        else:
            diag('missing_seq', 'Event has no integer sequence; cannot establish deduplication or continuity.', line)
            unsequenced.append((event, line, index))
    seqs = sorted(groups)
    gaps = []
    if seqs and seqs[0] > 0:
        gaps.append([0, seqs[0] - 1])
    for previous, current in zip(seqs, seqs[1:]):
        if current > previous + 1:
            gaps.append([previous + 1, current - 1])
    for start, end in gaps:
        diag('sequence_gap', f'Missing event sequence range {start} to {end}.')
    input_seqs = [e.get('seq') for e, _, _ in candidates if isinstance(e, dict) and integer(e.get('seq'))]
    if any(b < a for a, b in zip(input_seqs, input_seqs[1:])):
        diag('sequence_order', 'Event sequences arrive out of order; chronological views are sorted by world minute.')
    events, duplicate_count, conflict_count = [], 0, 0
    for seq, group in groups.items():
        variants = defaultdict(list)
        for e, line, index in group:
            variants[json.dumps(e, sort_keys=True, ensure_ascii=True)].append((e, line, index))
        duplicate_count += len(group) - len(variants)
        if len(variants) > 1:
            conflict_count += 1
            diag('sequence_conflict', f'Conflicting payloads for sequence {seq}; all variants shown, excluded from derived totals.')
        for entries in variants.values():
            event, line, index = entries[0]
            events.append((event, line, index, len(variants) > 1, [x[1] for x in entries]))
    if duplicate_count:
        diag('duplicate_events', f'{duplicate_count} repeated event copies retained in raw records and counted once in derived views.')
    events += [(e, line, index, False, [line]) for e, line, index in unsequenced]
    orders, gigs, drivers, ledger = {}, {}, {}, []

    def entity(book, id_):
        return book.setdefault(id_, {'id': id_, 'data': {}, 'history': [], 'ledger': [], 'related': []})

    def add_order(value, key, at=None):
        if isinstance(value, dict) and identity(value.get('id')):
            data = entity(orders, value['id'])['data']
            previous = data.get(key + 'ObservedAt')
            if integer(previous) and integer(at) and previous > at:
                return
            data[key] = value
            data[key + 'ObservedAt'] = at

    # Snapshots and reveal enrich only facts actually captured. Every version stays in raw.
    for line in captures['snapshot']:
        snap = mapping(mapping(records[line-1]['value']).get('snapshot'))
        for request in array(snap.get('openRequests')):
            add_order(request, 'request', snap.get('now'))
        for order in array(snap.get('orders')):
            add_order(order, 'order', snap.get('now'))
        for gig in array(snap.get('gigs')):
            if isinstance(gig, dict) and identity(gig.get('id')):
                data = entity(gigs, gig['id'])['data']
                data['snapshot'] = gig
                data['snapshotAt'] = snap.get('now')
                data['lastObservedStatus'] = gig.get('status', 'not captured')
    for line in captures['roster']:
        for driver in array(mapping(records[line-1]['value']).get('roster')):
            if isinstance(driver, dict) and identity(driver.get('id')):
                entity(drivers, driver['id'])['data']['profile'] = driver
    for line in captures['reveal']:
        reveal = mapping(mapping(records[line-1]['value']).get('reveal'))
        for request in array(reveal.get('requests')):
            request = mapping(request)
            add_order(request.get('request'), 'request')
            id_ = mapping(request.get('request')).get('id')
            if identity(id_):
                entity(orders, id_)['data']['reveal'] = request
        for order in array(reveal.get('orders')):
            order = mapping(order)
            if identity(order.get('orderId')):
                entity(orders, order['orderId'])['data']['truth'] = order
    # Event facts use chronological order, never physical line order.
    events.sort(key=lambda x: (x[0].get('at') if integer(x[0].get('at')) else -1, x[0].get('seq') if integer(x[0].get('seq')) else -1))
    for event, line, index, conflict, copies in events:
        kind = event.get('kind') if isinstance(event.get('kind'), str) else 'unknown event'
        item = row(kind, event.get('at'), event, line, event=event, eventIndex=index,
                   conflict=conflict, copies=copies, incident=kind in INCIDENTS)
        if not integer(event.get('at')):
            diag('invalid_time', 'Event has no integer world minute.', line)
        if kind not in EVENT_KINDS:
            diag('unknown_event', 'Unrecognized event kind retained in timeline and raw records.', line)
        if conflict:
            continue
        if kind == 'price_request':
            add_order(event.get('request'), 'request', event.get('at'))
        if kind in ('order_won', 'order_changed'):
            add_order(event.get('order'), 'order', event.get('at'))
        if kind == 'ledger':
            entry = mapping(event.get('line'))
            if integer(entry.get('cents')):
                ledger.append({**entry, 'sourceLine': line, 'seq': event.get('seq'), 'at': entry.get('at') if integer(entry.get('at')) else item['at']})
            else:
                diag('invalid_ledger', 'Ledger entry lacks integer cents; excluded from totals and retained in raw.', line)
    # Stable chronological timeline; unknown times last.
    timeline.sort(key=lambda x: (x['at'] if x['at'] is not None else float('inf'), x['line']))
    for index, item in enumerate(timeline):
        item['id'] = index
        if 'action' in item and item['action'].get('type') == 'post' and item['status'] == 'accepted' and identity(item['result'].get('id')):
            gig_id = item['result']['id']
            item['refs']['gig'] = sorted(set(item['refs']['gig'] + [gig_id]))
            entity(gigs, gig_id)['data']['post'] = item['action']
        for kind, book in [('order', orders), ('gig', gigs), ('driver', drivers)]:
            for id_ in item['refs'][kind]:
                obj = entity(book, id_)
                obj['history'].append(index)
                if item.get('conflict'):
                    continue
                if kind == 'order':
                    ek = item['kind']
                    if ek == 'price_request':
                        obj['data']['arrivedAt'] = item['at']
                    if ek in ('order_won', 'order_lost', 'order_cancelled'):
                        obj['data']['outcome'] = {'order_won': 'won', 'order_lost': 'lost', 'order_cancelled': 'cancelled'}[ek]
                    if ek == 'action:quote':
                        obj['data'].setdefault('quotes', []).append(index)
                newer_than_snapshot = not integer(obj['data'].get('snapshotAt')) or (integer(item['at']) and item['at'] >= obj['data']['snapshotAt'])
                if kind == 'gig' and newer_than_snapshot and item['kind'] in ('gig_booked', 'gig_started', 'gig_dropped', 'gig_expired', 'no_show'):
                    obj['data']['lastObservedStatus'] = item['kind'].removeprefix('gig_')
                if kind == 'gig' and newer_than_snapshot and item['kind'] == 'action:withdraw' and item.get('status') == 'accepted':
                    obj['data']['lastObservedStatus'] = 'withdrawn'
    for gig in gigs.values():
        post = gig['data'].get('post', gig['data'].get('snapshot', {}))
        order_ids = refs(post)['order']
        gig['related'] = order_ids
        for id_ in order_ids:
            entity(orders, id_)['related'].append(gig['id'])
    ledger.sort(key=lambda x: (x['at'] if integer(x['at']) else float('inf'), x['sourceLine']))
    totals = Counter()
    attribution = Counter()
    for index, entry in enumerate(ledger):
        totals[str(entry.get('kind', 'unknown'))] += entry['cents']
        oid, gid = identity(entry.get('orderId')), identity(entry.get('gigId'))
        # Never split a shared gig fee or assign it to an arbitrary order.
        if oid:
            entity(orders, oid)['ledger'].append(index)
            attribution['directOrderCents'] += entry['cents']
        else:
            attribution['gigOnlyCents' if gid else 'unattributedCents'] += entry['cents']
        if gid:
            entity(gigs, gid)['ledger'].append(index)
    for order in orders.values():
        data = order['data']
        if 'outcome' not in data:
            data['outcome'] = mapping(data.get('reveal')).get('outcome', 'no outcome captured')
        accepted_quotes = [timeline[i] for i in data.get('quotes', []) if timeline[i].get('status') == 'accepted']
        data['quoteStatus'] = 'accepted quote observed' if accepted_quotes else 'no accepted quote captured'
        # Absence in a legacy trace is not proof that a request was never quoted.
        if mapping(data.get('reveal')).get('outcome') == 'unquoted':
            data['quoteStatus'] = 'unquoted (reveal)'
        order['directNetCents'] = sum(ledger[i]['cents'] for i in order['ledger'])
    final = next((x for x in reversed(scores) if x['final']), None)
    end_snapshots = [mapping(records[line-1]['value']).get('snapshot') for line in captures['snapshot'] if mapping(records[line-1]['value']).get('phase') == 'end']
    verified_end = any(isinstance(s, dict) and integer(s.get('now')) and integer(s.get('endsAt')) and s['now'] >= s['endsAt'] for s in end_snapshots)
    if not final:
        diag('missing_final_score', 'No final score was captured; the simulated run may be unfinished.')
    if not verified_end:
        diag('unverified_end', 'No end snapshot verifies the world reached endsAt. A final score record alone does not prove a completed week.')
    for kind in ('map', 'roster', 'reveal'):
        if not captures[kind]:
            diag('unavailable_' + kind, kind.capitalize() + ' unavailable: no successful capture in this source.')
    if len(runs) > 1:
        diag('multiple_runs', 'Multiple run headers found. This report does not claim single-world reconciliation.')
    margin = sum(totals.values())
    recorded = final['score'] if final else {}
    reconciliation = {'ledgerMarginCents': margin, 'ledgerRevenueCents': totals.get('revenue', 0),
                      'recordedMarginCents': recorded.get('marginCents'), 'recordedRevenueCents': recorded.get('revenueCents'),
                      'marginDifferenceCents': margin - recorded['marginCents'] if integer(recorded.get('marginCents')) else None,
                      'revenueDifferenceCents': totals.get('revenue', 0) - recorded['revenueCents'] if integer(recorded.get('revenueCents')) else None,
                      'totals': dict(totals), 'attribution': dict(attribution)}
    uncertain = any(d['code'] in {'source_line', 'sequence_gap', 'sequence_conflict', 'missing_seq', 'invalid_ledger', 'multiple_runs', 'result_count', 'batch_conflict', 'pending_intent', 'orphan_response'} for d in diagnostics)
    reconciliation['status'] = 'matches' if not uncertain and reconciliation['marginDifferenceCents'] == 0 and reconciliation['revenueDifferenceCents'] == 0 else 'uncertain' if uncertain else 'mismatch' if final else 'no recorded final score'
    stats = Counter(x['kind'] for x in timeline if 'event' in x and not x.get('conflict'))
    return {'version': VERSION, 'source': {'base64': base64.b64encode(source).decode(), 'sha256': hashlib.sha256(source).hexdigest(), 'bytes': len(source), 'lines': len(records)},
            'records': records, 'timeline': timeline, 'orders': list(orders.values()), 'gigs': list(gigs.values()), 'drivers': list(drivers.values()),
            'ledger': ledger, 'scores': scores, 'run': runs[0] if runs else {}, 'captures': dict(captures),
            'diagnostics': diagnostics, 'reconciliation': reconciliation,
            'integrity': {'ingestedBytes': len(source), 'invalidLines': sum(bool(x['error']) for x in records), 'duplicates': duplicate_count,
                          'conflicts': conflict_count, 'gaps': gaps, 'verifiedEnd': verified_end, 'finalScoreCaptured': bool(final)},
            'stats': dict(stats)}


def render(model):
    template = (ROOT / 'report_assets/report.html').read_text()
    data = json.dumps(model, ensure_ascii=True, separators=(',', ':'), allow_nan=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    brand = (ROOT / 'assets/cheap-drive.svg').read_text()
    for id_ in re.findall(r'id="([^"]+)"', brand):
        brand = brand.replace('id="' + id_ + '"', 'id="brand-' + id_ + '"').replace('url(#' + id_ + ')', 'url(#brand-' + id_ + ')')
    brand = re.sub(r'aria-labelledby="([^"]+)"', lambda m: 'aria-labelledby="' + ' '.join('brand-' + x for x in m[1].split()) + '"', brand)
    return template.replace('/* REPORT_CSS */', (ROOT / 'report_assets/report.css').read_text()).replace('<!-- BRAND -->', brand).replace('/* REPORT_JS */', (ROOT / 'report_assets/report.js').read_text()).replace('REPORT_DATA', data)


def generate(source: Path, destination: Path):
    # Read and validate before creating any output. Exclusive creation protects inputs.
    model = analyze(source.read_bytes())
    html = render(model)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8') as out:
        out.write(html)
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='existing JSONL journal (never contacts Spread)')
    parser.add_argument('-o', '--output', type=Path, help='new HTML file; defaults alongside input')
    args = parser.parse_args()
    try:
        model = generate(args.source, args.output or args.source.with_suffix('.html'))
    except UnsafeSource:
        parser.exit(2, 'Input contains credential-like fields or text. No report was written; the source is unchanged.\n')
    except (OSError, ValueError, RecursionError):
        parser.exit(2, 'Report could not be generated. Check input readability, JSON nesting and that the output is a fresh writable file.\n')
    print(f"Generated offline report v{VERSION}: {model['source']['lines']} source records, {len(model['timeline'])} timeline entries, {len(model['diagnostics'])} diagnostics. Source bytes retained in full.")


if __name__ == '__main__':
    main()
