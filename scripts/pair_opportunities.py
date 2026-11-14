"""Evaluate pairing limits on observed waiting-order states, entirely offline.

This is a feasibility probe, not a simulator: it holds the observed orders and
driver bookings fixed. Opportunity counts overlap and cannot be added to wins.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace
import gzip
import io
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delta import make_delta
from dispatch import Journal


class ObservedWorld:
    def __init__(self, rows):
        self.initial_map = next(r['map'] for r in rows if r['type'] == 'map')
        self.initial_roster = next(r['roster'] for r in rows if r['type'] == 'roster')

    def act(self, *args, **kwargs):
        raise AssertionError('offline probe must never send actions')

    def advance(self, *args, **kwargs):
        raise AssertionError('offline probe must never advance a world')


PROFILES = {'baseline': (30, 300), 'drive480': (30, 480),
            'regional': (60, 480), 'extended': (90, 720)}


def probe(path, settings):
    with gzip.open(path, 'rt') as source:
        rows = [json.loads(line) for line in source]
    desk = make_delta(ObservedWorld(rows), 8, 0, Journal(io.StringIO()), **settings)
    base = desk.driver_settings
    intents, seen, active_pairs = {}, set(), {}
    counts, reasons, connections = Counter(), defaultdict(Counter), defaultdict(set)
    lengths = defaultdict(list)
    admission = Counter()

    def detach(gig):
        for legs in desk.leg_gigs.values():
            for leg in list(legs):
                if legs[leg] == gig:
                    del legs[leg]

    def results(row):
        intent = intents[row['batchId']]
        response = row.get('response', row)
        for action, result in zip(intent['actions'], response.get('results', [])):
            if not result.get('ok'):
                continue
            if action['type'] == 'post':
                gig = result['id']
                desk.posts[gig] = action
                for stop in action['stops']:
                    desk.leg_gigs.setdefault(stop['orderId'], {})[stop['leg']] = gig
            elif action['type'] == 'withdraw':
                detach(action['gigId'])

    def event(e):
        if e['seq'] in seen:
            return
        seen.add(e['seq'])
        kind, gig, identity = e['kind'], e.get('gigId'), e.get('orderId')
        if kind == 'price_request':
            desk.requests[e['request']['id']] = e['request']
        elif kind in ('order_won', 'order_changed'):
            desk.orders[e['order']['id']] = deepcopy(e['order'])
        elif kind == 'order_cancelled':
            desk.orders[identity]['status'] = 'cancelled'
        elif kind == 'deadline_close':
            desk.urgent.add(identity)
        elif kind == 'visit_failed':
            desk._failed_orders.add(identity)
        elif kind == 'picked_up':
            desk._picked.add(identity)
        elif kind == 'delivered':
            desk.orders[identity]['deliveredAt'][e['leg']] = e['at']
        elif kind == 'gig_booked':
            desk.booked.add(gig)
        elif kind == 'gig_started':
            desk._started.add(gig)
        elif kind in ('gig_dropped', 'no_show', 'gig_expired'):
            desk.booked.discard(gig)
            desk._started.discard(gig)
            if kind == 'gig_expired':
                detach(gig)

    for row in rows:
        kind = row['type']
        if kind == 'action_intent':
            intents[row['batchId']] = row
        elif kind in ('act_result', 'advance_batch'):
            results(row)
            for e in row.get('response', {}).get('events', []):
                event(e)
        elif kind == 'gamma_pair':
            active_pairs[row['gigId']] = set(row['orders'])
        elif kind == 'gamma_pair_split':
            active_pairs.pop(row['gigId'], None)
            desk._split_orders.update(row['orders'])
        elif kind == 'beta_decline' and row['reason'] == 'no option leaves a driver enough time':
            request = desk.requests[row['requestId']]
            slack = max(desk.slack(request, option) for option in request['options'])
            admission['declines'] += 1
            admission['no_feasible_route'] += slack < 0
            for minutes in (60, 120, 180, 240, 360):
                admission['at_least_' + str(minutes)] += slack >= minutes
        elif kind == 'gamma_pair_skip':
            desk.now = row['at']
            paired = {o for gig, orders in active_pairs.items() for o in orders
                      if desk.leg_gigs.get(o, {}).get(0) == gig}
            order = desk.orders[row['orderId']]
            candidates = [o for o in desk.orders.values() if o['id'] != order['id']
                          and o['id'] not in paired and desk._eligible(o)]
            counts['decisions'] += 1
            for profile, (km, minutes) in PROFILES.items():
                desk.driver_settings = replace(base, pair_transfer_km=km, pair_max_drive_minutes=minutes)
                feasible = []
                for other in candidates:
                    for first, second in ((order, other), (other, order)):
                        try:
                            plan, reason = desk._plan(first, second)
                        except IndexError:
                            plan, reason = None, 'no_post_window'
                        if plan:
                            feasible.append(plan)
                            connections[profile].add(tuple(sorted(plan.orders)))
                        else:
                            reasons[profile][reason] += 1
                if feasible:
                    counts[profile] += 1
                    best = min(feasible, key=lambda p: (p.transfer_km, p.finish, p.orders))
                    lengths[profile].append(best.drive_minutes)
            desk.driver_settings = base
    return dict(counts=counts, uniqueFeasiblePairs={k: len(v) for k, v in connections.items()},
                reasons=reasons, driveMinutes=lengths, admissionSlack=admission)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batches', type=Path, nargs='+')
    args = parser.parse_args()
    output = []
    for batch in args.batches:
        for line in (batch / 'runs.jsonl').read_text().splitlines():
            run = json.loads(line)
            if run['label'] == 'rescue-notes':
                output.append(dict(seed=run['seed'], **probe(batch / 'traces' / run['trace'], run['settings'])))
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
