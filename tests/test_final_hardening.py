"""Offline final-runner fault cases; no real clients, worlds or run data."""
from copy import deepcopy
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest

from capture import Journal
from final import LiveWorld
from recovery import CheckpointStore, model_state
from tests.test_recovery import new_desk, paired, request, snapshot


PRIME = json.loads((Path(__file__).resolve().parents[1] /
                    'models/epsilon-prime.json').read_text())['settings']


def prime_pair():
    return paired(**{key: value for key, value in PRIME.items() if key != 'pairs'})


class LiveQuotePriorityTests(unittest.TestCase):
    def test_ready_quote_precedes_due_pair_withdrawal_and_fallback_posts(self):
        desk, _, _ = prime_pair()
        world = desk.world
        desk.world = LiveWorld(world, desk.journal)
        desk.now = world.now = 685  # pair's split timer is due
        desk.handle(dict(seq=4, at=685, kind='price_request', request=request('open', at=685)))
        start = len(world.actions)
        desk.send()
        actions = world.actions[start:]
        self.assertEqual(actions[0]['type'], 'quote')
        self.assertEqual(actions[0]['requestId'], 'open')
        self.assertEqual([a['type'] for a in actions[1:]], ['withdraw', 'post', 'post'])
        self.assertTrue(desk.recovery_quotes['open']['ok'])
        self.assertEqual(desk._busy, 0)

    def test_ready_quote_precedes_an_already_queued_post(self):
        desk, _, _ = prime_pair()
        world = desk.world
        desk.world = LiveWorld(world, desk.journal)
        # A rejoin can queue both work types, with a post ahead of a quote.
        desk._outbox.append(deepcopy(next(iter(desk.posts.values()))))
        desk.handle(dict(seq=4, at=625, kind='price_request', request=request('open', at=625)))
        start = len(world.actions)
        desk.send()
        self.assertEqual([a['type'] for a in world.actions[start:]], ['quote', 'post'])

    def test_burst_rejection_keeps_other_quotes_and_post_result_bookkeeping(self):
        desk, _, _ = prime_pair()
        world = desk.world
        desk.world = LiveWorld(world, desk.journal)
        post = deepcopy(next(iter(desk.posts.values())))
        desk._outbox.append(post)
        for index in range(55):
            desk.handle(dict(seq=4 + index, at=625, kind='price_request',
                             request=request(f'burst-{index}', at=625)))
        original = world.act
        calls = []

        def reject_first_quote(actions):
            calls.append(deepcopy(actions))
            results = original(actions)
            if actions[0].get('requestId') == 'burst-0':
                results[0] = dict(ok=False, reason='Request is not open')
            return results

        world.act = reject_first_quote
        desk.send()
        self.assertEqual([len(actions) for actions in calls], [50, 5, 1])
        self.assertTrue(all(a['type'] == 'quote' for actions in calls[:2] for a in actions))
        self.assertEqual(calls[-1], [post])
        self.assertFalse(desk.recovery_quotes['burst-0']['ok'])
        self.assertNotIn('burst-0', desk.pending)
        self.assertTrue(all(desk.recovery_quotes[f'burst-{i}']['ok'] for i in range(1, 55)))
        self.assertTrue(any(action is post for action in desk.posts.values()))


class CorruptRecoveryTests(unittest.TestCase):
    def test_invalid_checkpoint_cannot_leave_the_breaker_policy_applied(self):
        settings = dict(pairs=1, epsilon_breaker=1, epsilon_breaker_risk_orders=0,
                        win_target_bps=4400, delta_corridor_open_cap=5,
                        delta_relaxed_slack_minutes=300)
        desk = new_desk(**settings)
        state = model_state(desk)
        state.update(epsilon_breaker_active=True, epsilon_breaker_at=500, markup='corrupt')
        desk.world.recovery_checkpoint = dict(worldId=desk.world.id, lastSeq=-1, state=state)
        expected = new_desk(**settings)
        desk.rejoin(snapshot(desk), [])
        self.assertFalse(desk.epsilon_breaker_active)
        self.assertEqual(desk.settings, expected.settings)
        self.assertEqual(desk.intake_settings, expected.intake_settings)
        self.assertEqual(desk.driver_settings, expected.driver_settings)
        self.assertEqual(desk.delta_pair_max_wait_minutes, expected.delta_pair_max_wait_minutes)

    def test_corrupt_gzip_deflate_does_not_prevent_reading_other_trace_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # A legal gzip header followed by an invalid DEFLATE block (BTYPE=3).
            (root / '001-final-world.jsonl.gz').write_bytes(bytes.fromhex('1f8b08000000000002ff07'))
            with gzip.open(root / '002-final-world.jsonl.gz', 'wt') as stream:
                stream.write(json.dumps(dict(type='run', worldId='world', model={'name': 'Delta'})) + '\n')
                stream.write(json.dumps(dict(type='model_quote_result', requestId='r', at=600,
                                             ok=True, competitive=True, tracker='global')) + '\n')
            store = CheckpointStore(root / 'world-checkpoint.json', 'world', {'name': 'Delta'})
            try:
                self.assertEqual(store.quote_receipts(),
                                 {'r': dict(at=600, ok=True, competitive=True, tracker='global')})
            finally:
                store.close()

    def test_nonobject_trace_row_does_not_block_later_trace_receipts(self):
        for malformed in (None, [], 1):
            with self.subTest(malformed=malformed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for name, rows in (
                    ('001', [dict(type='run', worldId='world', model={}), malformed]),
                    ('002', [dict(type='run', worldId='world', model={}),
                             dict(type='model_quote_result', requestId='r', at=600,
                                  ok=True, competitive=True, tracker='global')]),
                ):
                    with gzip.open(root / f'{name}-final-world.jsonl.gz', 'wt') as stream:
                        stream.writelines(json.dumps(row) + '\n' for row in rows)
                store = CheckpointStore(root / 'world-checkpoint.json', 'world', {})
                try:
                    self.assertIn('r', store.quote_receipts())
                finally:
                    store.close()
