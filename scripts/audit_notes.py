"""Read captured traces offline and audit facts for unique failed-visit orders.

Only identities, reason codes and parsed constraints are emitted; note prose
and access/booking codes are never included in the report. Coverage means the
parser found a relevant constraint, not that a new policy would avoid a visit.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.notes import parse_note


def audit(paths):
    findings = []
    for path in paths:
        requests, failures = {}, {}
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf-8') as source:
            for line in source:
                row = json.loads(line)
                if row.get('type') == 'event':
                    events = [row['event']]
                else:
                    events = row.get('response', {}).get('events', [])
                for event in events:
                    if event['kind'] == 'price_request':
                        requests[event['request']['id']] = event['request']
                    elif event['kind'] == 'visit_failed':
                        failures.setdefault(event['orderId'], set()).add(event['reason'])
        for identity, reasons in sorted(failures.items()):
            request = requests.get(identity)
            if request is None:
                findings.append(dict(trace=path.name, orderId=identity, reasons=sorted(reasons),
                                     relevantFacts=False, missingRequest=True))
                continue
            facts = parse_note(request.get('note'), request['arrivedAt'])
            covered = {
                'not_ready': facts.ready_at is not None or facts.released_at is not None,
                'closed': facts.pickup_closes is not None or facts.delivery_closes is not None,
                'licence': facts.manual,
                'no_plates': facts.plates,
            }
            findings.append(dict(trace=path.name, orderId=identity, reasons=sorted(reasons),
                                 relevantFacts=all(covered.get(reason, False) for reason in reasons),
                                 facts={key: value for key, value in asdict(facts).items()
                                        if value is not None and value is not False}))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('traces', type=Path, nargs='+')
    parser.add_argument('--details', action='store_true', help='Include parsed facts, without note prose')
    args = parser.parse_args(argv)
    findings = audit(args.traces)
    result = dict(uniqueFailedOrders=len(findings),
                  ordersWithRelevantFacts=sum(row['relevantFacts'] for row in findings),
                  reasons=dict(Counter(reason for row in findings for reason in row['reasons'])))
    if args.details:
        result['orders'] = findings
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
