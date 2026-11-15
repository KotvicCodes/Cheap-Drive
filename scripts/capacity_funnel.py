"""Offline capacity audit of saved comparison batches; never connects to Spread.

Outputs aggregate counters and per-week diagnostics, without note prose or driver
identities. A booking is not a payment: paid fees come only from ledger entries.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
from statistics import median


def read_json(path):
    with gzip.open(path, 'rt') if path.suffix == '.gz' else path.open() as source:
        return json.load(source)


def percentile(values, fraction):
    return sorted(values)[min(len(values) - 1, int((len(values) - 1) * fraction))] if values else None


def audit(trace, reveal, run):
    events, intents, responses, diagnostics, final_orders = {}, {}, {}, [], {}
    with gzip.open(trace, 'rt') if trace.suffix == '.gz' else trace.open() as source:
        for line in source:
            row = json.loads(line)
            if row['type'] == 'action_intent':
                intents[row['batchId']] = row
            elif row['type'] in ('advance_batch', 'act_result'):
                response = row.get('response', row)
                responses[row['batchId']] = response.get('results', [])
                for event in response.get('events', []):
                    if event['seq'] in events and events[event['seq']] != event:
                        raise ValueError('conflicting event sequence')
                    events[event['seq']] = event
            elif row['type'] == 'event':
                events[row['event']['seq']] = row['event']
            elif row['type'] == 'snapshot' and row.get('phase') == 'end':
                final_orders = {o['id']: o for o in row['snapshot']['orders']}
            else:
                diagnostics.append(row)
    posts, schedules, first_posts = {}, {}, {}
    rejected = Counter()
    for batch, intent in intents.items():
        results = responses.get(batch)
        if results is None:
            raise ValueError('unresolved action intent')
        if len(results) != len(intent['actions']):
            raise ValueError('action/result length mismatch')
        for action, result in zip(intent['actions'], results):
            if not result.get('ok'):
                rejected[action['type']] += 1
                continue
            if action['type'] == 'post':
                posts[result['id']] = {'at': intent['at'], **action}
                schedules[result['id']] = [(intent['at'], action['schedule'])]
                for stop in action['stops']:
                    first_posts.setdefault((stop['orderId'], stop['leg']), result['id'])
            elif action['type'] == 'reprice':
                schedules.setdefault(action['gigId'], []).append((intent['at'], action['schedule']))
    declines = Counter(row['reason'] for row in diagnostics if row['type'] == 'beta_decline')
    skip = Counter()
    for row in diagnostics:
        if row['type'] == 'gamma_pair_skip':
            skip.update(row['counts'])
    ordered = sorted(events.values(), key=lambda e: e['seq'])
    kinds = Counter(e['kind'] for e in ordered)
    won = {e['order']['id']: e['order'] for e in ordered if e['kind'] == 'order_won'}
    won.update({identity: order for identity, order in final_orders.items() if identity in won})
    cancelled = {e['orderId'] for e in ordered if e['kind'] == 'order_cancelled'}
    expired, booked, pair_orders, first_booked_legs = set(), set(), set(), set()
    expired_before_booking = set()
    attempts = Counter()
    hour = defaultdict(lambda: {'posted': 0, 'booked': 0, 'delays': []})
    opening_sum = booking_sum = booked_first = bookings_after_expiry = 0
    pair_booking_count = 0
    first_booking_by_leg = {}
    booking_hour = Counter()
    fee_steps = night_steps = 0
    for gig, action in posts.items():
        hour[action['at'] // 60 % 24]['posted'] += 1
        for step in action['schedule'][1:]:
            fee_steps += 1
            night_steps += step['at'] % 1440 < 420 or step['at'] % 1440 >= 1380
    for event in ordered:
        gig = event.get('gigId')
        if event['kind'] == 'gig_expired':
            expired.add(gig)
            for stop in posts.get(gig, {}).get('stops', []):
                expired_before_booking.add((stop['orderId'], stop['leg']))
        elif event['kind'] == 'gig_booked' and gig in posts:
            action = posts[gig]
            opening_sum += action['schedule'][0]['feeCents']
            booking_sum += event['feeCents']
            attempts[gig] += 1
            legs = {(s['orderId'], s['leg']) for s in action['stops']}
            booking_hour[event['at'] // 60 % 24] += 1
            for leg in legs:
                first_booking_by_leg.setdefault(leg, {'firstPosting': first_posts[leg] == gig,
                                                     'afterExpiry': leg in expired_before_booking})
            if all(first_posts[leg] == gig for leg in legs):
                booked_first += 1
                first_booked_legs.update(legs)
            if any(leg in expired_before_booking for leg in legs):
                bookings_after_expiry += 1
            if len({s['orderId'] for s in action['stops']}) > 1:
                pair_booking_count += 1
                pair_orders.update(s['orderId'] for s in action['stops'])
            if gig not in booked:
                bucket = hour[action['at'] // 60 % 24]
                bucket['booked'] += 1
                bucket['delays'].append(event['at'] - action['at'])
            booked.add(gig)
    ledger = Counter()
    failures = defaultdict(set)
    order_events = defaultdict(Counter)
    delivered = defaultdict(dict)
    paid_by_gig = Counter()
    for event in ordered:
        if event.get('orderId'):
            order_events[event['orderId']][event['kind']] += 1
        if event['kind'] == 'ledger':
            line = event['line']
            ledger[line['kind']] += line['cents']
            if line['kind'] == 'driver_fee':
                paid_by_gig[line.get('gigId')] -= line['cents']
        elif event['kind'] == 'visit_failed':
            failures[event['orderId']].add(event['reason'])
        elif event['kind'] == 'delivered':
            delivered[event['orderId']][event['leg']] = event['at']
    problems = []
    revealed_orders = {o['orderId']: o for o in reveal['reveal']['orders']}
    for identity, order in won.items():
        if identity in cancelled:
            continue
        times = delivered[identity]
        incomplete = len(times) != len(order['legs'])
        note_deadlines = [leg.get('noteDeadline') for leg in revealed_orders[identity]['legs']]
        late = not incomplete and any(at > min(order['deadline'], note_deadlines[leg] or order['deadline'])
                                      for leg, at in times.items())
        if incomplete or late:
            own = {g: p for g, p in posts.items() if any(s['orderId'] == identity for s in p['stops'])}
            problems.append(dict(orderId=identity, undelivered=incomplete, late=late,
                                 failureReasons=sorted(failures[identity]), events=dict(order_events[identity]),
                                 posts=len(own), expiries=len(set(own) & expired),
                                 bookedGigs=len(set(own) & booked),
                                 firstPickupWidth=min((s['window']['to'] - s['window']['from']
                                                      for g, p in own.items() for s in p['stops']
                                                      if s['orderId'] == identity and s['kind'] == 'pickup'
                                                      and first_posts[identity, s['leg']] == g), default=None)))
    requests = reveal['reveal']['requests']
    hours = {str(h): {'posted': b['posted'], 'booked': b['booked'],
                      'medianBookingMinutes': median(b['delays']) if b['delays'] else None,
                      'p90BookingMinutes': percentile(b['delays'], .9),
                      'bookingMinutes': b['delays'], 'bookingEventsAtHour': booking_hour[h]}
             for h, b in sorted(hour.items())}
    all_delays = [d for b in hour.values() for d in b['delays']]
    pickup_widths = [s['window']['to'] - s['window']['from'] for p in posts.values()
                     for s in p['stops'] if s['kind'] == 'pickup']
    paid_opening = sum(posts[g]['schedule'][0]['feeCents'] for g in paid_by_gig if g in posts)
    night_views = sum(e['kind'] == 'gig_viewed' and (e['at'] % 1440 < 420 or e['at'] % 1440 >= 1380)
                      for e in ordered)
    return dict(seed=run['seed'], label=run['label'], score=run['score'],
                requests=len(requests), declined=sum(declines.values()), declineReasons=dict(declines),
                quoted=sum(r['type'] == 'beta_quote' for r in diagnostics),
                allQuotesIncludingDeclines=sum(bool(r['quote']) for r in requests),
                wonEvents=len(won), cancelled=len(cancelled),
                posts=len(posts), uniqueBookedGigs=len(booked), bookingEvents=kinds['gig_booked'],
                firstPostingBookingEvents=booked_first, firstPostingBookedLegs=len(first_booked_legs),
                firstBookedLegs=len(first_booking_by_leg),
                firstBookedLegsOnFirstPosting=sum(v['firstPosting'] for v in first_booking_by_leg.values()),
                firstBookedLegsAfterExpiry=sum(v['afterExpiry'] for v in first_booking_by_leg.values()),
                bookingEventsAfterExpiry=bookings_after_expiry, expiredGigs=len(expired),
                expiredNeverBooked=len(expired - booked), pairPosts=sum(len({s['orderId'] for s in p['stops']}) > 1 for p in posts.values()),
                pairBookingEvents=pair_booking_count, pairedOrders=len(pair_orders),
                pairSkipReasons=dict(skip), medianBookingMinutes=median(all_delays),
                pickupWidthMedian=median(pickup_widths), pickupWidthUnder180=sum(w < 180 for w in pickup_widths),
                bookingFeeCents=booking_sum, bookingOpeningCents=opening_sum,
                paidDriverFeeCents=-ledger['driver_fee'], paidGigOpeningCents=paid_opening,
                feeSteps=fee_steps, nightFeeSteps=night_steps, nightViews=night_views,
                ledger=dict(ledger), events=dict(kinds), hours=hours, problems=problems,
                actionRejections=dict(rejected))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batches', type=Path, nargs='+')
    parser.add_argument('--label', default='rescue-notes')
    args = parser.parse_args()
    weeks = []
    for batch in args.batches:
        for line in (batch / 'runs.jsonl').read_text().splitlines():
            run = json.loads(line)
            if run['label'] == args.label:
                weeks.append(audit(batch / 'traces' / run['trace'],
                                   read_json(batch / 'reveals' / run['reveal']), run))
    print(json.dumps(weeks, indent=2))


if __name__ == '__main__':
    main()
