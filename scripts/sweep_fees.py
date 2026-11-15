"""Read-only fee diagnostics for unattended sweeps, separate from model policy."""
from collections import Counter

from compare import MetricsJournal


class FeeMetricsJournal(MetricsJournal):
    """Join successful posts and ledger charges without reading saved traces.

    ``opening_fee`` returns the nominal opening cents for a single-order post,
    before its aged escalation schedule. Pair fees are deliberately excluded.
    Repost means a second successful post for the same order/leg; expiry reposts
    are also counted separately from pair withdrawals and split fallbacks.
    """

    def __init__(self, output, opening_fee):
        super().__init__(output)
        self.opening_fee = opening_fee
        self.intents = {}
        self.posts = {}
        self.posted_members = set()
        self.expired_members = set()
        self.fees = Counter()
        self.interventions = Counter()

    def successful_posts(self, actions, results):
        for action, result in zip(actions, results):
            if action['type'] != 'post' or not result['ok']:
                continue
            gig = result['id']
            if gig in self.posts:
                continue
            members = frozenset((s['orderId'], s['leg']) for s in action['stops'])
            single = len(members) == 1
            nominal = self.opening_fee(action) if single else None
            self.posts[gig] = dict(
                members=members, opening=nominal,
                repost=bool(members & self.posted_members),
                expired_repost=bool(members & self.expired_members))
            self.posted_members.update(members)

    def event_fees(self, event):
        post = self.posts.get(event.get('gigId'))
        if event['kind'] == 'gig_expired' and post:
            self.expired_members.update(post['members'])
        if event['kind'] != 'ledger':
            return
        line = event['line']
        if line['kind'] != 'driver_fee' or line['cents'] >= 0:
            return
        post = self.posts.get(line.get('gigId'))
        if post is None or post['opening'] is None:
            self.fees['unmeasured_driver_fee_cents'] -= line['cents']
            return
        paid = -line['cents']
        excess = max(0, paid - post['opening'])
        for label, included in (('single', True), ('reposted_single', post['repost']),
                                ('expired_reposted_single', post['expired_repost'])):
            if included:
                self.fees[label + '_charges'] += 1
                self.fees[label + '_paid_cents'] += paid
                self.fees[label + '_above_opening_cents'] += excess

    def record(self, kind, **fields):
        super().record(kind, **fields)
        if kind == 'delta_reference_quote_floor':
            self.interventions['reference_floor_options'] += 1
            self.interventions['reference_floor_bindings'] += fields['binding']
            self.interventions['reference_floor_lift_cents'] += fields['finalCents'] - fields['baseCents']
            ratio = fields['finalCents'] * 10000 // max(1, fields['referenceFeeCents'])
            self.interventions['quote_reference_ratio_bps_' + str(ratio // 1000 * 1000)] += 1
        elif kind == 'beta_quote':
            self.interventions['quote_markup_bps_' + str(fields['markupBps'] // 1000 * 1000)] += 1
        events = []
        if kind == 'action_intent':
            self.intents[fields['batchId']] = fields['actions']
        elif kind in ('act_result', 'advance_batch'):
            response = fields['response'] if kind == 'advance_batch' else fields
            self.successful_posts(self.intents.pop(fields['batchId'], []), response['results'])
            events = response.get('events', [])
        elif kind == 'action_result':
            self.successful_posts([fields['action']], [fields['result']])
        elif kind == 'event':
            events = [fields['event']]
        for event in events:
            self.event_fees(event)

    def metrics(self):
        return {**super().metrics(), 'fee_escalation': dict(self.fees),
                'interventions': dict(self.interventions)}
