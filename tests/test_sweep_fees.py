"""Fee measurements use charges, confirmed posts, and original nominal fees."""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from compare import MetricsJournal
from dispatch import play_model
from models.delta import make_delta
from scripts.sweep_fees import FeeMetricsJournal
from scripts.sweep import play_week
from tests.test_performance import LossWorld


def post(order, fee=8000, leg=0):
    return dict(type='post', schedule=[dict(at=0, feeCents=fee)],
                stops=[dict(orderId=order, leg=leg, kind=k) for k in ('pickup', 'delivery')])


class SweepFeeTests(unittest.TestCase):
    def journal(self):
        return FeeMetricsJournal(io.StringIO(), lambda action: 8000)

    def accept(self, journal, action, gig):
        journal.record('action_result', action=action, result=dict(ok=True, id=gig))

    def charge(self, journal, gig, cents):
        journal.record('event', event=dict(kind='ledger', line=dict(kind='driver_fee',
                                                                  gigId=gig, cents=cents)))

    def test_repost_excess_uses_nominal_opening_and_paid_ledger_not_booking_offer(self):
        j = self.journal()
        self.accept(j, post('o'), 'first')
        j.record('event', event=dict(kind='gig_expired', gigId='first'))
        self.accept(j, post('o', fee=12000), 'second')
        j.record('event', event=dict(kind='gig_booked', gigId='second', feeCents=17000))
        self.assertEqual(j.metrics()['fee_escalation'], {})
        self.charge(j, 'second', -13000)
        m = j.metrics()['fee_escalation']
        self.assertEqual(m['reposted_single_above_opening_cents'], 5000)
        self.assertEqual(m['expired_reposted_single_paid_cents'], 13000)
        self.assertEqual(m['single_charges'], 1)

    def test_failed_posts_do_not_create_a_repost_and_refunds_are_not_new_charges(self):
        j = self.journal()
        j.record('action_result', action=post('o'), result=dict(ok=False, reason='bad'))
        self.accept(j, post('o'), 'g')
        self.charge(j, 'g', -7000)
        self.charge(j, 'g', 7000)
        m = j.metrics()['fee_escalation']
        self.assertEqual(m['single_paid_cents'], 7000)
        self.assertEqual(m['single_above_opening_cents'], 0)
        self.assertNotIn('reposted_single_charges', m)

    def test_pair_withdrawal_fallback_is_a_repost_but_not_an_expiry_repost(self):
        j = self.journal()
        pair = post('one')
        pair['stops'] += post('two')['stops']
        self.accept(j, pair, 'pair')
        self.charge(j, 'pair', -12000)
        self.accept(j, post('one'), 'single')
        self.charge(j, 'single', -10000)
        m = j.metrics()['fee_escalation']
        self.assertEqual(m['unmeasured_driver_fee_cents'], 12000)
        self.assertEqual(m['reposted_single_above_opening_cents'], 2000)
        self.assertNotIn('expired_reposted_single_charges', m)

    def test_advance_receipts_precede_events_and_order_legs_are_distinct(self):
        j = self.journal()
        j.record('action_intent', batchId=1, actions=[post('o')])
        j.record('advance_batch', batchId=1, response=dict(results=[dict(ok=True, id='g')],
                 events=[dict(kind='ledger', line=dict(kind='driver_fee', gigId='g', cents=-9000))]))
        self.accept(j, post('o', leg=1), 'other-leg')
        self.charge(j, 'other-leg', -9000)
        m = j.metrics()['fee_escalation']
        self.assertEqual(m['single_above_opening_cents'], 2000)
        self.assertNotIn('reposted_single_charges', m)
        self.assertEqual(j.intents, {})

    def test_read_only_measurement_preserves_delta_actions_calls_score_and_trace(self):
        outcomes = []
        for journal_type in (MetricsJournal, FeeMetricsJournal):
            stream, world = io.StringIO(), LossWorld()
            args = (stream,) if journal_type is MetricsJournal else (stream, lambda action: 8000)
            journal = journal_type(*args)
            with redirect_stdout(io.StringIO()):
                score = play_model(world, 8, journal,
                                   lambda w, l, n, j: make_delta(w, l, n, j, pairs=1), fast=True)
            outcomes.append((world.sent, world.calls, score, stream.getvalue()))
        self.assertEqual(*outcomes)

    def test_sweep_opt_in_exports_metrics_without_changing_score_or_actions(self):
        outcomes = []
        for enabled in ('0', '1'):
            world = LossWorld()
            world.id = 'offline-fee-world'
            client = Mock()
            client.create.return_value = world
            client.call.return_value = {}
            with tempfile.TemporaryDirectory() as directory:
                out = Path(directory)
                for sub in ('worlds', 'traces', 'reveals'):
                    (out / sub).mkdir()
                with patch.dict(os.environ, {'SWEEP_FEE_DIAGNOSTICS': enabled}), \
                        patch('performance.PracticeClient', return_value=client):
                    result = play_week(out, 'models.delta:make_delta', 8, 'offline',
                                       'fees', {'pairs': 1}, True)
            self.assertEqual('fee_escalation' in result, enabled == '1')
            outcomes.append((world.sent, world.calls, result['score']))
        self.assertEqual(*outcomes)
