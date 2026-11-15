"""Offline live-runner fault injection. No sockets or real Spread worlds.

The transport tape retains the SDK's validation, 429 retry and action buckets.
SIGKILL is sent only to subprocesses created by this module, backed by a local
JSON fake server. Known distributed-write/storage limits are asserted explicitly
and reported as failures of the stronger operational requirement in the audit.
"""
from collections import Counter, deque
from contextlib import contextmanager
from copy import deepcopy
import errno
import gzip
import io
import json
import math
import multiprocessing
import os
from pathlib import Path
import random
import signal
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from capture import BackgroundFsync, Journal
from compare import load_model
import final
from performance import PracticeClient
from recovery import CheckpointStore
from spread import SpreadError
from spread.client import World as SDKWorld, Unreachable
from spread.stream import QUIET_LIMIT, websocket as sdk_websocket
from tests.test_epsilon_prime import CandidateLiveWorld
from tests.test_gamma import request
from tests.test_gamma_pairs import order_for

ROOT = Path(__file__).resolve().parents[1]
MODEL = load_model(ROOT / 'models/epsilon-prime.json')


class Clock:
    def __init__(self):
        self.seconds = 0.

    def monotonic(self):
        return self.seconds

    perf_counter = monotonic

    def sleep(self, seconds):
        self.seconds += seconds


class Reads:
    latest = 0

    def drain(self, journal):
        pass

    def request_score(self, *args):
        pass

    def close(self):
        pass


class UpgradeSocket:
    """A complete fake HTTP upgrade, followed by a silent black hole."""
    def __init__(self, status=101):
        self.head = f'HTTP/1.1 {status} Offline\r\nContent-Length: 0\r\n\r\n'.encode()
        self.timeout, self.timeouts, self.closed = None, [], False

    def sendall(self, payload):
        pass

    def settimeout(self, seconds):
        self.timeout = seconds

    def recv(self, size):
        if self.head:
            head, self.head = self.head, b''
            return head
        self.timeouts.append(self.timeout)
        raise socket.timeout('injected silent black hole')

    def close(self):
        self.closed = True


class Transport(PracticeClient):
    def __init__(self, world):
        super().__init__(url='https://offline.invalid', key='offline-fixture')
        self.world = world
        self.faults = deque()
        self.latency = .04
        self.tokens, self.at = 20., 0.
        self.calls = 0

    def _send(self, method, path, payload, headers):
        if method != 'POST' or not path.endswith('/actions'):
            raise AssertionError(f'unexpected offline route: {method} {path}')
        self.calls += 1
        if self.faults:
            fault = self.faults.popleft()
            if isinstance(fault, BaseException):
                raise fault
            if fault == 'sdk_timeout':
                clock = self.world.clock
                class TimedOutConnection:
                    def request(self, *args):
                        clock.sleep(20)
                        raise TimeoutError('injected 20-second socket timeout')
                    def close(self):
                        pass
                # Exercise the SDK's real timeout -> Unreachable conversion,
                # with a fake HTTP connection and no socket creation.
                with patch('spread.client.http.client.HTTPSConnection', return_value=TimedOutConnection()):
                    return super()._send(method, path, payload, headers)
            return fault, {'Retry-After': '100'}, b'{"error":"injected fault"}'
        self.world.clock.sleep(self.latency)
        now = self.world.clock.seconds
        self.tokens = min(20., self.tokens + (now - self.at) * 20)
        self.at = now
        actions = json.loads(payload)
        if self.tokens + 1e-6 < len(actions):
            return 429, {'Retry-After': '50'}, b'{"error":"injected bucket limit"}'
        self.tokens -= len(actions)
        fraction = self.tokens - int(self.tokens)
        reset = math.ceil((1 - fraction) * 50) if fraction > 1e-6 else 0
        answer = {'RateLimit-Policy': 'final-actions', 'RateLimit-Limit': '20',
                  'RateLimit-Remaining': str(int(self.tokens)), 'RateLimit-Reset': str(reset)}
        return 200, answer, json.dumps(self.world.apply(actions)).encode()

    def map(self):
        return self.world.map()


class FaultWorld(CandidateLiveWorld):
    """Actual Epsilon Prime, historical breaker trip, then a timed request burst."""
    id = 'offline-fault-final'

    def __init__(self, count=64, *, initial_open=False, persisted=None, hook=None):
        super().__init__()
        self.clock = Clock()
        self.client = Transport(self)
        self.count, self.initial_open = count, initial_open
        self.attempts, self.accepted, self.gigs = [], {}, {}
        self.disconnect_at = None
        self.reject = set()
        self.started = initial_open
        self.persisted, self.hook = persisted, hook or (lambda *args: None)
        self.requests = []
        for n in range(count):
            req = request(f'burst-{n}')
            req.update(arrivedAt=1310, respondBy=1325)
            for option in req['options']:
                option['deadline'] += 3000
            self.requests.append(req)
        if initial_open:
            self.publish()
        if persisted and persisted.exists():
            data = json.loads(persisted.read_text())
            for key in ('history', 'orders', 'attempts', 'accepted', 'gigs', 'started', 'now'):
                setattr(self, key, data[key])

    def save_server(self):
        if self.persisted:
            data = {key: getattr(self, key) for key in
                    ('history', 'orders', 'attempts', 'accepted', 'gigs', 'started', 'now')}
            temporary = self.persisted.with_suffix('.tmp')
            temporary.write_text(json.dumps(data))
            os.replace(temporary, self.persisted)

    def publish(self):
        if not self.started:
            self.clock.seconds = 0.
        self.started = True
        self.now = 1310
        if not any(e['kind'] == 'price_request' and e['request']['id'].startswith('burst-')
                   for e in self.history):
            for req in self.requests:
                self.emit(1310, 'price_request', request=req)
        self.save_server()

    def server_now(self):
        return max(self.now, 1310 + self.clock.seconds * 5) if self.started else self.now

    def snapshot(self):
        return dict(worldId=self.id, now=int(self.server_now()), endsAt=1370,
                    orders=deepcopy(self.orders), gigs=deepcopy(list(self.gigs.values())),
                    openRequests=deepcopy(self.requests) if self.started and self.server_now() < 1325 else [])

    def stream(self, after=-1, idle=None):
        self.publish()
        for event in deepcopy(self.history):
            if event['seq'] <= after:
                continue
            if self.disconnect_at == event['seq']:
                self.disconnect_at = None
                raise Unreachable(0, 'injected mid-burst disconnect')
            yield event
        self.now = 1370
        yield dict(seq=len(self.history), at=1370, kind='forecast', text='offline end')

    def act(self, actions):
        return SDKWorld(self.client, self.id).act(actions)

    def apply(self, actions):
        results = []
        for action in actions:
            self.hook('before_server_commit', action)
            self.attempts.append(dict(at=self.server_now(), action=deepcopy(action)))
            identity = action.get('requestId')
            if action['type'] == 'quote':
                if identity in self.accepted:
                    result = dict(ok=False, reason='Request already quoted')
                elif identity in self.reject:
                    result = dict(ok=False, reason='Injected per-action rejection')
                elif self.server_now() >= next(r['respondBy'] for r in self.requests if r['id'] == identity):
                    result = dict(ok=False, reason='Request expired')
                else:
                    self.accepted[identity] = deepcopy(action)
                    result = dict(ok=True, id=identity)
            elif action['type'] == 'post':
                identity = f'fake-gig-{len(self.gigs)}'
                self.gigs[identity] = dict(id=identity, postedAt=int(self.server_now()), status='open',
                                          **{k: deepcopy(action[k]) for k in ('stops', 'audience', 'schedule')})
                result = dict(ok=True, id=identity)
            else:
                raise AssertionError(f'unexpected offline action: {action}')
            results.append(result)
            self.actions.append(deepcopy(action))
            self.save_server()
            self.hook('after_server_commit', action)
        return results


@contextmanager
def trace(directory, world, *, name='run', hook=None):
    class HookJournal(Journal):
        def record(self, kind, **fields):
            super().record(kind, **fields)
            if hook:
                hook(kind, fields)
    path = Path(directory) / f'{name}-{world.id}.jsonl.gz'
    with gzip.open(path, 'wt', encoding='utf-8') as stream:
        journal = HookJournal(stream, fsync=lambda fd: None)
        journal.record('run', worldId=world.id, model=MODEL.spec)
        store = CheckpointStore(Path(directory) / f'{world.id}-checkpoint.json', world.id, MODEL.spec)
        try:
            yield journal, store
        finally:
            store.close()


def run(world, journal, store, *, retry=False, retry_seconds=0):
    desks = []
    def factory(w, level, now, j):
        desk = MODEL.factory(w, level, now, j)
        desks.append(desk)
        return desk
    with patch('spread.client.time', world.clock), patch.object(final, 'time', world.clock):
        if retry:
            with patch.object(final, 'BackgroundReads', return_value=Reads()):
                final.play_until_done(world, 8, journal, factory, lambda: int(world.server_now()),
                                      retry_seconds=retry_seconds, checkpoint=store)
        else:
            final.play_live(world, 8, journal, factory, clock=lambda: int(world.server_now()),
                            reads=Reads(), checkpoint=store)
    return desks


class TwoWaveWorld(FaultWorld):
    """A fresh request after an outage, while the expired one stays in history."""
    def __init__(self):
        super().__init__(1)

    def snapshot(self):
        return {**super().snapshot(), 'endsAt': 2000}

    def stream(self, after=-1, idle=None):
        if not self.started:
            self.publish()
        for event in deepcopy(self.history):
            if event['seq'] > after:
                yield event
        req = deepcopy(self.requests[0])
        req.update(id='after-outage', arrivedAt=1450, respondBy=1465)
        self.requests.append(req)
        self.now, self.clock.seconds = 1450, 28.
        self.emit(1450, 'price_request', request=req)
        yield deepcopy(self.history[-1])
        self.now = 2000
        yield dict(seq=len(self.history), at=2000, kind='forecast', text='offline end')


def crash_child(arguments):
    # The parent kills only this newly created fake child, after a pipe handshake.
    def hook(kind, fields):
        if kind == cut:
            identity = fields.get('requestId')
            if kind in ('action_intent',):
                identity = fields['actions'][0].get('requestId')
            elif kind == 'act_result':
                identity = world.attempts[-1]['action'].get('requestId')
            if identity == target:
                ready.send((kind, identity))
                ready.recv()
    directory, cut, target, ready = arguments
    world = FaultWorld(12, persisted=directory / 'fake-server.json', hook=hook)
    if not world.persisted.exists():
        req = request('outstanding-obligation')
        req.update(arrivedAt=1301, respondBy=1316)
        req['options'][0]['deadline'] = 5000
        order = order_for(req, deadline=5000)
        world.emit(1301, 'price_request', request=req)
        world.emit(1302, 'order_won', order=order)
        world.orders.append(order)
        world.now = 1305
        world.save_server()
    with trace(directory, world, name='killed', hook=hook) as (journal, store):
        run(world, journal, store)


class FaultInjectionTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(socket.socket, 'connect', side_effect=AssertionError('offline test attempted a socket'))
        guard.start()
        self.addCleanup(guard.stop)

    def test_64_requests_in_one_minute_before_every_respond_by(self):
        world = FaultWorld()
        with tempfile.TemporaryDirectory() as directory, trace(directory, world) as (journal, store):
            desks = run(world, journal, store)
        self.assertEqual(len(world.accepted), 64)
        self.assertEqual(len(world.attempts), 64)
        self.assertTrue(all(a['at'] < 1325 for a in world.attempts))
        self.assertAlmostEqual(max(a['at'] for a in world.attempts), 1322.8)
        self.assertTrue(desks[-1].epsilon_breaker_active)
        self.assertEqual(desks[-1].epsilon_breaker_at, 1296)

    def test_disconnect_mid_burst_rebuilds_without_duplicate_quotes(self):
        world = FaultWorld(12)
        world.disconnect_at = 65
        with tempfile.TemporaryDirectory() as directory, trace(directory, world) as (journal, store):
            desks = run(world, journal, store, retry=True)
        self.assertEqual(len(desks), 2)
        self.assertEqual(len(world.attempts), 12)
        self.assertEqual(len(world.accepted), 12)
        self.assertTrue(all(d.epsilon_breaker_active for d in desks))

    def test_sdk_stream_disconnect_resumes_cursor_and_deduplicates_replayed_event(self):
        world = FaultWorld(12)
        cursors = []
        def websocket(url, path, key, idle):
            cursors.append(path)
            events = deepcopy(world.history[60:])
            if len(cursors) == 1:
                yield from events[:5]
                raise ConnectionResetError('injected websocket disconnect')
            yield from events[4:]  # deliberate cursor-boundary replay
            world.now = 1370
            yield dict(seq=len(world.history), at=1370, kind='forecast', text='offline end')
        def stream(after=-1, idle=None):
            world.publish()
            return SDKWorld(world.client, world.id).stream(after=after, idle=idle)
        world.stream = stream
        with tempfile.TemporaryDirectory() as directory, trace(directory, world) as (journal, store):
            with patch('spread.client.websocket', websocket):
                desks = run(world, journal, store)
        self.assertEqual(len(desks), 1)
        self.assertEqual(len(world.attempts), 12)
        self.assertEqual(len(world.accepted), 12)
        self.assertTrue(cursors[0].endswith('after=59'))
        self.assertTrue(cursors[1].endswith('after=64'))
        self.assertTrue(all(a['at'] < 1325 for a in world.attempts))

    def test_sdk_blackholed_stream_keeps_yielding_idle_past_quiet_limit(self):
        # Known requirement failure: idle timeouts are not a liveness timeout.
        # Reproduce without sleeping or opening a real socket. Operations must
        # detect stalled event consumption; the runner cannot infer it from None.
        sock = UpgradeSocket()
        with patch('spread.stream.socket.create_connection', return_value=sock):
            stream = sdk_websocket('http://offline.invalid', '/stream', 'offline', idle=1.)
            try:
                for _ in range(QUIET_LIMIT + 5):
                    self.assertIsNone(next(stream))
                self.assertEqual(sock.timeouts, [1.] * (QUIET_LIMIT + 5))
                self.assertFalse(sock.closed)
            finally:
                stream.close()
            self.assertTrue(sock.closed)

    def test_non_101_websocket_upgrades_rebuild_instead_of_exiting(self):
        for status in (409, 429, 500):
            with self.subTest(status=status):
                world = FaultWorld(4)
                world.client.url = 'http://offline.invalid'
                original, opens = world.stream, []
                def stream(after=-1, idle=None):
                    opens.append(after)
                    if len(opens) == 1:
                        return SDKWorld(world.client, world.id).stream(after=after, idle=idle)
                    return original(after=after, idle=idle)
                world.stream = stream
                sock = UpgradeSocket(status)
                with tempfile.TemporaryDirectory() as directory, trace(directory, world) as (journal, store):
                    with patch('spread.stream.socket.create_connection', return_value=sock):
                        desks = run(world, journal, store, retry=True)
                self.assertEqual(len(desks), 2)
                self.assertEqual(len(world.accepted), 4)
                self.assertTrue(sock.closed)

    def test_sdk_429_retries_and_quotes_once(self):
        world = FaultWorld(12)
        world.client.faults.append(429)
        with tempfile.TemporaryDirectory() as directory, trace(directory, world) as (journal, store):
            run(world, journal, store)
        self.assertEqual(len(world.attempts), 12)
        self.assertEqual(len(world.accepted), 12)
        self.assertEqual(world.client.calls, 13)

    def test_transient_http_errors_rebuild(self):
        for error in (409, 500, 501, 502, 503, 504, 507, Unreachable(0, 'injected socket timeout')):
            with self.subTest(error=error):
                world = FaultWorld(4)
                world.client.faults.append(error)
                with tempfile.TemporaryDirectory() as directory, trace(directory, world) as (journal, store):
                    desks = run(world, journal, store, retry=True)
                self.assertEqual(len(world.accepted), 4)
                self.assertEqual(len(world.attempts), 4)
                self.assertEqual(len(desks), 2)

    def test_auth_and_input_http_errors_remain_fatal(self):
        for status in (400, 401, 403, 404, 422):
            with self.subTest(status=status):
                world = FaultWorld(4)
                world.client.faults.append(status)
                with tempfile.TemporaryDirectory() as directory, trace(directory, world) as (journal, store):
                    with self.assertRaises(SpreadError) as raised:
                        run(world, journal, store, retry=True)
                self.assertEqual(raised.exception.status, status)
                self.assertEqual(world.client.calls, 1)

    def test_real_sdk_20_second_timeout_recovers_fresh_requests_without_quoting_expired_one(self):
        world = TwoWaveWorld()
        world.client.faults.append('sdk_timeout')
        with tempfile.TemporaryDirectory() as directory, trace(directory, world) as (journal, store):
            desks = run(world, journal, store, retry=True, retry_seconds=3)
        self.assertEqual(len(desks), 2)
        self.assertEqual(set(world.accepted), {'after-outage'})
        self.assertEqual([a['action']['requestId'] for a in world.attempts], ['after-outage'])
        self.assertTrue(desks[-1].epsilon_breaker_active)

    def test_default_three_second_recovery_can_exhaust_the_original_quote_window(self):
        world = TwoWaveWorld()
        world.client.faults.append(500)
        with tempfile.TemporaryDirectory() as directory, trace(directory, world) as (journal, store):
            desks = run(world, journal, store, retry=True, retry_seconds=3)
        self.assertEqual(len(desks), 2)
        self.assertEqual(set(world.accepted), {'after-outage'})
        self.assertEqual([a['action']['requestId'] for a in world.attempts], ['after-outage'])

    def test_sustained_sdk_429_exceeds_deadline_then_stream_quotes_fresh_requests(self):
        world = TwoWaveWorld()
        world.client.faults.extend([429] * 100)
        with tempfile.TemporaryDirectory() as directory, trace(directory, world) as (journal, store):
            desks = run(world, journal, store)
        self.assertEqual(len(desks), 1)  # SDK, rather than runner, owns these retries.
        self.assertEqual(set(world.accepted), {'after-outage'})
        old = next(a for a in world.attempts if a['action']['requestId'] == 'burst-0')
        self.assertGreater(old['at'], 1325)
        self.assertEqual(world.client.calls, 102)

    def test_wait_for_final_recovers_transient_http_errors(self):
        for error in (SpreadError(500, 'fault'), SpreadError(429, 'fault'),
                      SpreadError(409, 'fault'), Unreachable(0, 'timeout')):
            with self.subTest(error=error):
                world = FaultWorld(4)
                client = unittest.mock.Mock()
                client.final.side_effect = [error, dict(worldId=world.id)]
                client.world.return_value = world
                with patch.object(final, 'time', world.clock):
                    self.assertIs(final.wait_for_final(client)[0], world)
                self.assertEqual(client.final.call_count, 2)
                self.assertEqual(world.clock.seconds, 5)

    def test_one_rejected_action_in_batch_keeps_other_quotes_and_receipts(self):
        world = FaultWorld(4, initial_open=True)
        world.reject.add('burst-1')
        with tempfile.TemporaryDirectory() as directory, trace(directory, world) as (journal, store):
            desks = run(world, journal, store)
            receipts = store.quote_receipts()
        self.assertEqual(len(world.accepted), 3)
        self.assertEqual(len(world.attempts), 4)
        self.assertFalse(receipts['burst-1']['ok'])
        self.assertNotIn('burst-1', desks[-1].pending)
        self.assertTrue(all(receipts[f'burst-{i}']['ok'] for i in (0, 2, 3)))

    def test_truncated_checkpoint_and_journal_footer_recover(self):
        for corrupt in ('{"version":', 'not json', '[]'):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as directory:
                world = FaultWorld(4)
                with trace(directory, world) as (journal, store):
                    run(world, journal, store)
                path = Path(directory) / f'run-{world.id}.jsonl.gz'
                path.write_bytes(path.read_bytes()[:-8])
                world.now = 1311
                with trace(directory, world, name='restart') as (journal, store):
                    store.path.write_text(corrupt)
                    self.assertIsNone(store.load())
                    self.assertEqual(len(store.quote_receipts()), 4)
                    desks = run(world, journal, store)
                self.assertEqual(len(world.attempts), 4)
                self.assertTrue(desks[-1].epsilon_breaker_active)

    def test_corrupt_deflate_journal_is_ignored_for_history_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            world = FaultWorld(4)
            path = Path(directory) / f'corrupt-{world.id}.jsonl.gz'
            # Valid gzip header followed by an impossible DEFLATE block type.
            path.write_bytes(b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03\x07')
            with trace(directory, world) as (journal, store):
                self.assertEqual(store.quote_receipts(), {})
                desks = run(world, journal, store)
            self.assertEqual(len(world.accepted), 4)
            self.assertTrue(desks[-1].epsilon_breaker_active)

    def test_waiting_process_finds_new_final_and_midway_process_rebuilds(self):
        for midway in (False, True):
            with self.subTest(midway=midway):
                world = FaultWorld(4, initial_open=midway)
                joined_world = world
                class Client:
                    final = unittest.mock.Mock(side_effect=([] if midway else [SpreadError(404, 'not scheduled')])
                                                + [dict(worldId=joined_world.id, startsAt='offline')])
                    def world(self, identity):
                        return joined_world
                with patch.object(final, 'time', world.clock):
                    joined, info = final.wait_for_final(Client())
                self.assertIs(joined, world)
                with tempfile.TemporaryDirectory() as directory, trace(directory, world) as (journal, store):
                    desks = run(world, journal, store)
                self.assertEqual(len(world.accepted), 4)
                self.assertTrue(desks[-1].epsilon_breaker_active)

    def test_enospc_stops_before_unjournaled_action_then_recovers_when_space_returns(self):
        class FullDisk(io.StringIO):
            def write(self, text):
                if '"type": "action_intent"' in text:
                    raise OSError(errno.ENOSPC, 'injected journal disk full')
                return super().write(text)
        world = FaultWorld(4)
        with tempfile.TemporaryDirectory() as directory:
            store = CheckpointStore(Path(directory) / 'checkpoint.json', world.id, MODEL.spec)
            try:
                with self.assertRaises(OSError) as raised:
                    run(world, Journal(FullDisk()), store)
                self.assertEqual(raised.exception.errno, errno.ENOSPC)
                self.assertEqual(world.attempts, [])
            finally:
                store.close()
            with trace(directory, world, name='space-restored') as (journal, store):
                desks = run(world, journal, store)
            self.assertEqual(len(world.accepted), 4)
            self.assertTrue(desks[-1].epsilon_breaker_active)

    @unittest.skipUnless(hasattr(signal, 'SIGKILL'), 'requires SIGKILL')
    def test_seeded_sigkill_restart_boundaries_preserve_obligations_and_breaker(self):
        # Randomized target requests, with deterministic seeds for reproduction.
        # A committed action without a receipt has an unknowable outcome. This
        # test documents that one duplicate attempt, rather than claiming exactly once.
        context = multiprocessing.get_context('spawn')
        observed = Counter()
        for cut in ('action_intent', 'before_server_commit', 'after_server_commit',
                    'act_result', 'model_quote_result'):
            for number in random.Random(20261115).sample(range(12), 3):
                with self.subTest(cut=cut, request=number), tempfile.TemporaryDirectory() as tmp:
                    directory = Path(tmp)
                    parent, child = context.Pipe()
                    process = context.Process(target=crash_child,
                                              args=((directory, cut, f'burst-{number}', child),))
                    process.start()
                    child.close()
                    try:
                        self.assertTrue(parent.poll(5), f'child did not reach {cut}')
                        self.assertEqual(parent.recv(), (cut, f'burst-{number}'))
                        process.kill()
                        process.join(2)
                        self.assertEqual(process.exitcode, -signal.SIGKILL)
                        world = FaultWorld(12, persisted=directory / 'fake-server.json')
                        with trace(directory, world, name='restart') as (journal, store):
                            desks = run(world, journal, store)
                        attempts = Counter(a['action']['requestId'] for a in world.attempts
                                           if a['action']['type'] == 'quote')
                        duplicates = sum(count - 1 for count in attempts.values())
                        observed[cut] += duplicates
                        self.assertEqual(len(world.accepted), 12)
                        self.assertEqual(duplicates, int(cut == 'after_server_commit'))
                        desk = desks[-1]
                        self.assertTrue(desk.epsilon_breaker_active)
                        self.assertEqual(desk.epsilon_breaker_at, 1296)
                        self.assertIn('outstanding-obligation', desk.orders)
                        self.assertTrue(desk.leg_gigs.get('outstanding-obligation'))
                        self.assertTrue(all(a['at'] < 1325 for a in world.attempts
                                            if a['action']['type'] == 'quote'))
                    finally:
                        if process.is_alive():
                            process.kill()
                            process.join(2)
                        parent.close()
                        process.close()
        self.assertEqual(observed['after_server_commit'], 3)

    def test_ten_second_fsync_does_not_delay_64_quotes(self):
        entered = threading.Event()
        def slow_fsync(fd):
            entered.set()
            time.sleep(10)
        world = FaultWorld()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / f'slow-{world.id}.jsonl.gz'
            # Patch only capture's os facade; checkpoint and fake server I/O
            # keep normal semantics, and the real 10-second delay stays in fsync.
            class SlowOS:
                dup, close = staticmethod(os.dup), staticmethod(os.close)
                fsync = staticmethod(slow_fsync)
            with gzip.open(path, 'wt') as stream, patch('capture.os', SlowOS):
                with BackgroundFsync(stream.fileno(), interval=0) as sync:
                    journal = Journal(stream, fsync=sync.request)
                    journal.record('run', worldId=world.id, model=MODEL.spec)
                    self.assertTrue(entered.wait(2))
                    store = CheckpointStore(Path(directory) / 'checkpoint.json', world.id, MODEL.spec)
                    try:
                        started = time.monotonic()
                        run(world, journal, store)
                        elapsed = time.monotonic() - started
                        self.assertLess(elapsed, 1.)
                        self.assertEqual(len(world.accepted), 64)
                        self.assertTrue(all(a['at'] < 1325 for a in world.attempts))
                    finally:
                        store.close()
                self.assertGreaterEqual(sync.max_seconds, 10.)


if __name__ == '__main__':
    unittest.main()
