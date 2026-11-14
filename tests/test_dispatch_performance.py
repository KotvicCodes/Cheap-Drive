"""Decision and persistence contracts for the dispatcher performance changes."""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import itertools
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from capture import CapturedWorld, Journal, clean
from compare import load_model
from dispatch import play_model
from final import play_live
from scripts.replay_dispatch import replay
from tests.test_gamma_pairs import PairWorld, order_for
from tests.test_recovery import request

ROOT = Path(__file__).resolve().parents[1]


class SyntheticWeek(PairWorld):
    """Fixed public inputs/receipts, no market logic or private trace data."""
    def __init__(self):
        super().__init__()
        self.client, self.seq = self, -1
        self.initial_roster[0]['homePlaceId'] = 'a'
        one, two, three = request(), request('two', 'b', 'c', at=601), request('three', at=900)
        one['note'] = {'text': 'Ready for pickup today 10:00'}
        self.pending = [
            dict(at=600, kind='price_request', request=one),
            dict(at=601, kind='price_request', request=two),
            dict(at=620, kind='order_won', order=order_for(one)),
            dict(at=625, kind='order_won', order=order_for(two)),
            dict(at=900, kind='price_request', request=three),
            dict(at=915, kind='order_lost', requestId='three'),
            dict(at=1000, kind='deadline_close', orderId='one', lastPickupAt=5820),
            dict(at=1100, kind='order_cancelled', orderId='one', gigs=[]),
        ]

    def map(self):
        return deepcopy(self.initial_map)

    def roster(self):
        return deepcopy(self.initial_roster)

    def snapshot(self):
        return dict(worldId='synthetic', now=self.now, endsAt=1200, orders=[], gigs=[], openRequests=[])

    def score(self):
        return dict(marginCents=0, wonOrders=2, onTimeShare=0, ranked=False)

    def advance(self, *, actions=(), until=(), max=1200):
        results = self.act(actions)
        self.now = min(max, next((e['at'] for e in self.pending if e['kind'] in until), max))
        events = []
        while self.pending and self.pending[0]['at'] <= self.now:
            self.seq += 1
            events.append(dict(seq=self.seq, **self.pending.pop(0)))
        return dict(now=self.now, events=events, results=results)


def synthetic_rows(model_name):
    model = load_model(ROOT / 'models' / model_name)
    stream, world = io.StringIO(), SyntheticWeek()
    journal = Journal(stream)
    journal.record('run', level=8, factory=model.spec['factory'], settings=model.spec['settings'], fast=True)
    with redirect_stdout(io.StringIO()):
        play_model(world, 8, journal, model.factory, fast=True)
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def synthetic_live_rows(model_name):
    class Reads:
        latest = 600

        def request_score(self, *args):
            pass

        def drain(self, journal):
            pass

    class LiveWeek(SyntheticWeek):
        def events(self, **kwargs):
            return []

        def stream(self, **kwargs):
            seq = 0
            for at in (600, 601, 620, 625, 805, 900, 915, 1000, 1100, 1200):
                self.now = reads.latest = at
                if self.pending and self.pending[0]['at'] == at:
                    yield dict(seq=seq, **self.pending.pop(0))
                    seq += 1
                else:
                    yield None

    model = load_model(ROOT / 'models' / model_name)
    stream, reads, world = io.StringIO(), Reads(), LiveWeek()
    journal = Journal(stream)
    with redirect_stdout(io.StringIO()):
        play_live(world, 8, journal, model.factory, clock=lambda: world.now, reads=reads)
    return [json.loads(line) for line in stream.getvalue().splitlines()]


class DispatcherEquivalenceTests(unittest.TestCase):
    def test_live_quotes_and_timer_sends_match_the_unmodified_runner(self):
        expected = {
            'delta.json': '9467e7006a2f586b879eb89cae275f79bd301437e93979ad88f8219fe448c6ec',
            'delta-early.json': '62ed8bcab6e32111f1483ecee552ee3d60c30ec943a3efacfde92eb88ef85350',
        }
        for model, digest in expected.items():
            with self.subTest(model=model):
                rows = synthetic_live_rows(model)
                intents = [r for r in rows if r['type'] == 'action_intent']
                encoded = json.dumps(intents, sort_keys=True, separators=(',', ':')).encode()
                self.assertEqual(hashlib.sha256(encoded).hexdigest(), digest)

    def test_frozen_synthetic_batches_replay_with_exact_actions_and_minutes(self):
        # Digests from unmodified 51a1c80, including empty batches, timer stops,
        # synchronous withdrawals, post/reprice schedules and advance parameters.
        expected = {
            'delta.json': '44baf25b379fe5d89565e9e66f79e31440ea1fdf83f51d31d443ac6fc03d3ef3',
            'delta-early.json': '24a3e2bef3868ff0e1bc85a888ac0930147f973441985950ef260972ad195551',
        }
        for model, digest in expected.items():
            with self.subTest(model=model):
                rows = synthetic_rows(model)
                intents = [r for r in rows if r['type'] == 'action_intent']
                encoded = json.dumps(intents, sort_keys=True, separators=(',', ':')).encode()
                self.assertEqual(hashlib.sha256(encoded).hexdigest(), digest)
                before = deepcopy(rows)
                result = replay(rows)
                self.assertEqual(result['batches'], len(intents))
                self.assertEqual(result['actions'], sum(len(r['actions']) for r in intents))
                self.assertEqual(rows, before)

    def test_replay_detects_a_changed_minute_or_price(self):
        for change in ('minute', 'price'):
            rows = synthetic_rows('delta.json')
            intent = next(r for r in rows if r['type'] == 'action_intent' and r['actions'])
            if change == 'minute':
                intent['at'] += 1
            else:
                intent['actions'][0]['prices']['same_day'] += 1
            with self.subTest(change=change), self.assertRaisesRegex(AssertionError, 'action batch'):
                replay(rows)

    def test_admission_reads_follow_partial_bookings_and_deliveries(self):
        from tests.test_recovery import new_desk
        desk = new_desk()
        for index, (status, delivered, booked) in enumerate(itertools.product(
                ('waiting', 'moving', 'cancelled', 'delivered'),
                ((None, None), (10, None), (None, 10), (10, 20)),
                ((), (0,), (1,), (0, 1)))):
            identity = str(index)
            desk.orders[identity] = dict(status=status, legs=[{}, {}], deliveredAt=list(delivered))
            desk.leg_gigs[identity] = {leg: f'{identity}-{leg}' for leg in (0, 1)}
            desk.booked.update(f'{identity}-{leg}' for leg in booked)
        expected = {identity for identity, order in desk.orders.items()
                    if order['status'] not in ('cancelled', 'delivered')
                    and any(at is None and f'{identity}-{leg}' not in desk.booked
                            for leg, at in enumerate(order['deliveredAt']))}
        self.assertEqual(desk.orders_without_driver(), expected)
        desk.booked.clear()
        self.assertGreater(len(desk.orders_without_driver()), len(expected))

    def test_quote_local_reads_are_cleared_even_after_an_exception(self):
        from tests.test_recovery import new_desk
        desk = new_desk()
        with patch.object(desk, 'price_option', side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError):
                desk.quote(request())
        self.assertFalse(hasattr(desk, '_quote_open_orders'))
        order = order_for(request('new'))
        desk.orders['new'] = order
        self.assertEqual(desk.orders_without_driver(), {'new'})
        order['deliveredAt'][0] = 700
        self.assertEqual(desk.orders_without_driver(), set())


class JournalBoundaryTests(unittest.TestCase):
    def test_batch_preserves_bytes_and_flushes_before_each_sdk_boundary(self):
        class Output(io.StringIO):
            def __init__(self):
                super().__init__()
                self.durable = ''
                self.flushes = 0

            def flush(self):
                self.durable = self.getvalue()
                self.flushes += 1

        output, calls = Output(), []

        class World:
            def act(self, actions):
                rows = [json.loads(line) for line in output.durable.splitlines()]
                self_outer.assertEqual(rows[-1]['type'], 'action_intent')
                self_outer.assertEqual(rows[-2]['type'], 'beta_quote')
                calls.append(actions)
                return [dict(ok=True)]

        self_outer = self
        journal = Journal(output)
        world = CapturedWorld(World(), journal)
        with journal.batch():
            journal.record('event', event={'kind': 'price_request'})
            self.assertEqual(output.durable, output.getvalue())
            with journal.batch():
                journal.record('beta_quote', prices={'same_day': 100})
                world.act([dict(type='quote', requestId='synthetic', prices={'same_day': 100})])
                self.assertEqual(json.loads(output.durable.splitlines()[-1])['type'], 'act_result')
                journal.record('model_quote_result', requestId='synthetic', ok=True)
                self.assertEqual(json.loads(output.durable.splitlines()[-1])['type'], 'model_quote_result')
        self.assertEqual(output.flushes, 4)
        self.assertEqual(len(calls), 1)
        plain = io.StringIO()
        original = Journal(plain)
        for row in map(json.loads, output.getvalue().splitlines()):
            original.record(row.pop('type'), **row)
        self.assertEqual(output.getvalue(), plain.getvalue())

    def test_failed_durable_intent_prevents_http_and_exception_exit_flushes_diagnostics(self):
        stream = io.StringIO()
        journal = Journal(stream)
        world = CapturedWorld(unittest.mock.Mock(), journal)
        with self.assertRaises(OSError), patch.object(journal, '_flush', side_effect=OSError('fixture')):
            with journal.batch():
                journal.record('beta_quote', at=1)
                world.act([dict(type='quote')])
        world.world.act.assert_not_called()
        with patch.object(journal, '_flush') as flush:
            with self.assertRaises(RuntimeError):
                with journal.batch():
                    journal.record('diagnostic')
                    raise RuntimeError('fixture')
            flush.assert_called_once()

    def test_cached_key_classification_keeps_nested_redaction_after_eviction(self):
        for index in range(1100):
            clean({f'public-{index}': 'value'})
        data = dict(Authorization='sensitive', payload=[{'API_KEY': 'sensitive'},
                    {'note': 'Bearer sensitive'}, {'public': 'value'}])
        self.assertEqual(clean(data), dict(Authorization='[credential removed]',
                         payload=[{'API_KEY': '[credential removed]'},
                                  {'note': '[credential removed]'}, {'public': 'value'}]))
        self.assertIn('sensitive', data['Authorization'])


if __name__ == '__main__':
    unittest.main()
