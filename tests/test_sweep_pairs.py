"""Pooling diagnostics count actual deliveries and net paid fees, offline."""
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from compare import MetricsJournal
from scripts.sweep import play_week
from scripts.sweep_fees import FeeMetricsJournal
from scripts.sweep_pairs import PairMetricsMixin
from tests.test_performance import LossWorld


class PairMetricsJournal(PairMetricsMixin, MetricsJournal):
    pass


def delivery(gig, order, leg=0):
    return dict(kind='delivered', gigId=gig, orderId=order, leg=leg)


def charge(gig, cents):
    return dict(kind='ledger', line=dict(kind='driver_fee', gigId=gig, cents=cents))


class SweepPairTests(unittest.TestCase):
    def test_only_realized_shared_deliveries_count_as_pooling(self):
        j = PairMetricsJournal(io.StringIO())
        for kind in ('gamma_pair', 'gamma_pair_booked', 'gamma_pair_split'):
            j.record(kind)
        # A failed trial and a shortened pair are two single deliveries.
        for event in (delivery('fallback', 'one'), delivery('shortened', 'two'),
                      delivery('shared', 'three'), delivery('shared', 'four')):
            j.record('event', event=event)
        m = j.metrics()['pairing']
        self.assertEqual(m['delivered_cars'], 4)
        self.assertEqual(m['pooled_delivered_cars'], 2)
        self.assertEqual(m['pooled_delivery_share'], .5)
        self.assertEqual(m['pooled_completed_gigs'], 1)
        self.assertEqual(m['pair_posts'], 1)
        self.assertEqual(m['pair_bookings'], 1)
        self.assertEqual(m['pair_splits'], 1)

    def test_cost_uses_net_charges_including_failed_gigs_and_refunds(self):
        j = PairMetricsJournal(io.StringIO())
        j.record('advance_batch', response=dict(results=[], events=[
            delivery('shared', 'one'), delivery('shared', 'two'),
            charge('shared', -12000), charge('shared', 2000),
            charge('failed', -3000), charge('failed', 3000),
            delivery('solo', 'three'), charge('solo', -8000)]))
        m = j.metrics()['pairing']
        self.assertEqual(m['net_driver_fee_cents'], 18000)
        self.assertEqual(m['driver_fee_per_car_cents'], 6000)
        self.assertEqual(m['pooled_driver_fee_per_car_cents'], 5000)
        self.assertEqual(j.metrics()['ledger']['driver_fee'], -18000)

    def test_one_order_with_two_legs_is_not_multi_order_pooling(self):
        j = PairMetricsJournal(io.StringIO())
        for event in (delivery('tradein', 'one', 0), delivery('tradein', 'one', 1)):
            j.record('event', event=event)
        self.assertEqual(j.metrics()['pairing']['delivered_cars'], 2)
        self.assertEqual(j.metrics()['pairing']['pooled_delivered_cars'], 0)
        self.assertIsNone(PairMetricsJournal(io.StringIO()).metrics()['pairing']['driver_fee_per_car_cents'])

    def test_fee_and_pool_measurements_compose_without_extra_records(self):
        class Both(PairMetricsMixin, FeeMetricsJournal):
            pass
        stream = io.StringIO()
        j = Both(stream, lambda action: 8000)
        j.record('event', event=delivery('g', 'o'))
        self.assertIn('pairing', j.metrics())
        self.assertIn('fee_escalation', j.metrics())
        self.assertEqual(len(stream.getvalue().splitlines()), 1)

    def test_sweep_opt_in_is_read_only_and_preserves_actions_and_score(self):
        outcomes = []
        for enabled in ('0', '1'):
            world, client = LossWorld(), Mock()
            world.id = 'offline-pooling-world'
            client.create.return_value, client.call.return_value = world, {}
            with tempfile.TemporaryDirectory() as directory:
                out = Path(directory)
                for sub in ('worlds', 'traces', 'reveals'):
                    (out / sub).mkdir()
                with patch.dict(os.environ, {'SWEEP_PAIR_DIAGNOSTICS': enabled,
                                             'SWEEP_FEE_DIAGNOSTICS': '0'}), \
                        patch('performance.PracticeClient', return_value=client):
                    result = play_week(out, 'models.delta:make_delta', 8, 'offline',
                                       'pooling', {'pairs': 1}, True)
            self.assertEqual('pairing' in result, enabled == '1')
            outcomes.append((world.sent, world.calls, result['score']))
        self.assertEqual(*outcomes)
