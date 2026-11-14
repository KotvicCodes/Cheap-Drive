#!/usr/bin/env python3
"""Build the standalone multi-run live demo HTML bundle (runs/live-demo/index.html)."""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from week_report import analyze, render

WORKTREES = Path('/home/agent/.t3/worktrees/Cheap-Drive')
MAIN_RUNS = Path('/Users/kotvic/Desktop/GitHub/Cheap-Drive/runs')

RUN_SPECS = [
    {
        'id': 'alpha',
        'badge': 'α',
        'tone': 'alpha',
        'title': 'Alpha',
        'margin': '€5,488',
        'meta': '98.1% · 154 won',
        'trace': MAIN_RUNS / 'archives/alpha-2026-11-14/alpha-tune/traces/t0007-alpha-night-05.jsonl.gz',
        'reveal': MAIN_RUNS / 'archives/alpha-2026-11-14/alpha-tune/reveals/t0007-alpha-night-05.reveal.json.gz',
        'map': MAIN_RUNS / 'archives/alpha-2026-11-14/alpha-research/map.json',
    },
    {
        'id': 'beta-early',
        'badge': 'β',
        'tone': 'beta',
        'title': 'Beta Early',
        'margin': '€7,635',
        'meta': '97.6% · 210 won',
        'trace': WORKTREES / 't3-437fb841-d1220585f744b28e/runs/speed-baseline/gamma-speed-01-full.jsonl',
        'reveal': None,
    },
    {
        'id': 'beta-late',
        'badge': 'β',
        'tone': 'beta',
        'title': 'Beta Late',
        'margin': '€8,529',
        'meta': '94.7% · 246 won',
        'trace': WORKTREES / 't3-9a1daff8-628ee799c13b40c1/runs/gamma/recovery/beta-validation/traces/beta--gamma-v04.jsonl.gz',
        'reveal': WORKTREES / 't3-9a1daff8-628ee799c13b40c1/runs/gamma/recovery/beta-validation/reveals/beta--gamma-v04.reveal.json.gz',
    },
    {
        'id': 'gamma-early',
        'badge': 'γ',
        'tone': 'gamma',
        'title': 'Gamma Early',
        'margin': '€10,165',
        'meta': '94.6% · 258 won',
        'trace': WORKTREES / 't3-9a1daff8-628ee799c13b40c1/runs/gamma/recovery/screen-notes/weeks/notes-pairs-segments--gamma-v04/traces/notes-pairs-segments--gamma-v04.jsonl.gz',
        'reveal': WORKTREES / 't3-9a1daff8-628ee799c13b40c1/runs/gamma/recovery/screen-notes/weeks/notes-pairs-segments--gamma-v04/reveals/notes-pairs-segments--gamma-v04.reveal.json.gz',
    },
    {
        'id': 'gamma-late',
        'badge': 'γ',
        'tone': 'gamma',
        'title': 'Gamma Late',
        'margin': '€16,139',
        'meta': '98.2% · 275 won',
        'trace': WORKTREES / 't3-94dc0dd7-f7cb1a8ad1e3f596/runs/board/20261114T145051Z-level8-wf9f88cfd3ce1a2c5ea44.jsonl.gz',
        'reveal': None,
    },
    {
        'id': 'delta-early',
        'badge': 'δ',
        'tone': 'delta',
        'title': 'Delta Early',
        'margin': '€16,631',
        'meta': '97.0% · 271 won',
        'trace': WORKTREES / 't3-4d9ed6f5-d50ae2340a835fbb/runs/delta-final/b6/traces/rescue-notes--delta-f1-s06.jsonl.gz',
        'reveal': WORKTREES / 't3-4d9ed6f5-d50ae2340a835fbb/runs/delta-final/b6/reveals/rescue-notes--delta-f1-s06.reveal.json.gz',
    },
    {
        'id': 'delta-late',
        'badge': 'δ',
        'tone': 'delta',
        'title': 'Delta Late',
        'margin': '€18,058',
        'meta': '98.4% · 374 won',
        'trace': WORKTREES / 't3-4d9ed6f5-d50ae2340a835fbb/runs/queue/src/589daf7ad8b17d6c2402bb45f7cab7856cd777b9/runs/board/20261114T211547Z-level8-w1da3b90c477fb654f429.jsonl.gz',
        'reveal': None,
        'default': True,
    },
]


def load_raw(trace_path: Path, reveal_path: Path | None, map_path: Path | None = None) -> bytes:
    raw = gzip.open(trace_path, 'rb').read() if trace_path.suffix == '.gz' else trace_path.read_bytes()
    if map_path is not None and map_path.exists():
        map_obj = json.loads(map_path.read_text())
        raw += (json.dumps({'type': 'map', 'at': 0, 'map': map_obj}, separators=(',', ':')) + '\n').encode('utf-8')
    if reveal_path is not None and reveal_path.exists():
        rev_obj = json.loads(gzip.open(reveal_path, 'rb').read())
        raw += (json.dumps({'type': 'reveal', 'at': 10080, 'reveal': rev_obj}, separators=(',', ':')) + '\n').encode('utf-8')
    return raw


def compact_model(m: dict) -> dict:
    m['source']['base64'] = ''
    for g in m['gigs']:
        g['viewsCount'] = sum(1 for i in g['history'] if m['timeline'][i]['kind'] == 'gig_viewed')
    for d in m['drivers']:
        d['counts'] = {k: sum(1 for i in d['history'] if m['timeline'][i]['kind'] == k) for k in ('gig_viewed', 'gig_booked', 'gig_dropped', 'no_show')}

    seen_gig_view = set()
    new_timeline = []
    old_to_new = {}
    for idx, t in enumerate(m['timeline']):
        if t['kind'] == 'gig_viewed':
            gid = (t.get('refs') or {}).get('gig', [None])[0]
            if gid in seen_gig_view:
                continue
            seen_gig_view.add(gid)
        elif t['kind'] in ('beta_quote', 'beta_decline', 'gamma_trust', 'gamma_pair_skip', 'gamma_pair', 'action_intent', 'advance_batch'):
            continue
        old_to_new[idx] = len(new_timeline)
        item = dict(t)
        item['id'] = len(new_timeline)
        item.pop('copies', None)
        ev = item.get('event')
        if isinstance(ev, dict):
            ev = dict(ev)
            if item['kind'] == 'price_request' and isinstance(ev.get('request'), dict):
                req = ev['request']
                ev['request'] = {k: req[k] for k in ('id', 'dealerId', 'note') if k in req}
            elif item['kind'] == 'order_won' and isinstance(ev.get('order'), dict):
                o = ev['order']
                ev['order'] = {k: o[k] for k in ('id', 'option', 'priceCents') if k in o}
            item['event'] = ev
        new_timeline.append(item)

    m['timeline'] = new_timeline
    for book in (m['orders'], m['gigs'], m['drivers']):
        for ent in book:
            ent['history'] = [old_to_new[i] for i in ent['history'] if i in old_to_new]
            if 'quotes' in ent['data']:
                ent['data']['quotes'] = [old_to_new[i] for i in ent['data']['quotes'] if i in old_to_new]

    cap_lines = {ln for k, lines in m['captures'].items() if k in ('map', 'roster') for ln in lines}
    for rec in m['records']:
        v = rec.get('value')
        if isinstance(v, dict) and rec['line'] not in cap_lines:
            rec['value'] = {k: v[k] for k in ('type', 'at', 'mode', 'level', 'batchId', 'score', 'phase') if k in v}
    return m


def main():
    runs_payload = []
    first_model = None
    default_idx = next((i for i, s in enumerate(RUN_SPECS) if s.get('default')), len(RUN_SPECS) - 1)
    for idx, spec in enumerate(RUN_SPECS):
        raw = load_raw(spec['trace'], spec.get('reveal'), spec.get('map'))
        model = compact_model(analyze(raw))
        is_default = idx == default_idx
        if is_default:
            first_model = model
        runs_payload.append({
            'id': spec['id'],
            'badge': spec['badge'],
            'tone': spec['tone'],
            'title': spec['title'],
            'margin': spec['margin'],
            'meta': spec['meta'],
            'default': is_default,
            'model': None if is_default else model,
        })
        print(f"Loaded {spec['id']} ({spec['title']}): {spec['margin']} · {len(model['orders'])} orders · {len(model['gigs'])} gigs")

    out_path = ROOT / 'runs/live-demo/index.html'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = render(first_model, runs=runs_payload)
    out_path.write_text(html, encoding='utf-8')
    print(f"Wrote {out_path} ({len(html) / 1024 / 1024:.2f} MB)")


if __name__ == '__main__':
    main()
