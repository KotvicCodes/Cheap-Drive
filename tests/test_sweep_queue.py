"""Shared-arm assignments avoid replaying weeks owned by peer workers."""
import unittest

from scripts.sweep import queued_jobs


class SweepQueueTests(unittest.TestCase):
    def test_default_order_and_resume_preserve_the_existing_grid(self):
        plan = {'seeds': ['hard', 'normal'], 'variants': {'control': {}, 'arm': {}}}
        self.assertEqual(queued_jobs(plan, {('arm', 'hard')}),
                         [('control', 'hard'), ('control', 'normal'), ('arm', 'normal')])

    def test_peer_owned_arm_and_disjoint_seeds_leave_control_coverage_intact(self):
        plan = {'seeds': ['hard', 'normal', 'fresh'],
                'variants': {'control': {}, 'local': {}, 'peer': {}},
                'variant_seeds': {'local': ['hard', 'fresh'], 'peer': []}}
        self.assertEqual(queued_jobs(plan, set()),
                         [('control', 'hard'), ('local', 'hard'),
                          ('control', 'normal'), ('control', 'fresh'), ('local', 'fresh')])

    def test_mistyped_assignments_fail_instead_of_silently_omitting_weeks(self):
        for assignments in ({'missing': ['hard']}, {'arm': ['typo']}):
            with self.subTest(assignments=assignments), self.assertRaises(ValueError):
                queued_jobs({'seeds': ['hard'], 'variants': {'arm': {}},
                             'variant_seeds': assignments}, set())


class SequentialGateTests(unittest.TestCase):
    def row(self, label, seed, margin, on_time=.95):
        return {'label': label, 'seed': seed,
                'score': {'marginCents': margin, 'onTimeShare': on_time}}

    def plan(self):
        return {'variants': {'control': {}, 'arm': {}},
                'sequential_gate': {'control': 'control', 'min_pairs': 3,
                                    'min_gain_cents': 30000, 'min_on_time': .91}}

    def test_only_current_paired_rows_reach_gate_and_margin_threshold_is_inclusive(self):
        from scripts.sweep import gate_failures
        rows = [self.row('arm', str(i), 130000) for i in range(3)]
        self.assertEqual(gate_failures(self.plan(), rows), {})
        rows += [self.row('control', str(i), 100000) for i in range(3)]
        self.assertEqual(gate_failures(self.plan(), rows), {})
        rows[-1]['score']['marginCents'] += 1
        self.assertIn('arm', gate_failures(self.plan(), rows))

    def test_floor_includes_unpaired_completed_candidate_week(self):
        from scripts.sweep import gate_failures
        rows = [self.row(label, str(i), margin) for i in range(3)
                for label, margin in [('control', 100000), ('arm', 140000)]]
        rows.append(self.row('arm', 'unpaired', 140000, .909))
        self.assertIn('arm', gate_failures(self.plan(), rows))
        plan = self.plan()
        plan['sequential_gate']['overrides'] = {'arm': {'min_on_time': .90}}
        self.assertEqual(gate_failures(plan, rows), {})

    def test_cap_and_disabled_arm_never_consume_extra_worker(self):
        from scripts.sweep import next_job
        jobs = [('arm', 'a'), ('control', 'a')]
        plan = {'variant_workers': {'arm': 2}}
        self.assertEqual(next_job(jobs, [('arm', 'x'), ('arm', 'y')], plan, set()), ('control', 'a'))
        self.assertIsNone(next_job(jobs, [], plan, {'arm'}))


class StartedWorldTests(unittest.TestCase):
    def test_transport_failure_rejoins_same_world_and_never_creates_or_deletes(self):
        from unittest.mock import Mock, patch
        from scripts.sweep import finish_started_week
        world, captured, desk, journal = Mock(), Mock(), Mock(), Mock()
        world.id = 'practice-world'
        captured.initial_snapshot = {'now': 500, 'endsAt': 10080}
        factory = Mock(return_value=desk)
        def play(w, level, j, make, fast):
            self.assertIs(w, world)
            make(captured, level, 500, j)
            if play.calls == 0:
                play.calls += 1
                raise ConnectionError('transient')
            return {'ranked': True}
        play.calls = 0
        with patch('dispatch.play_model', side_effect=play), \
                patch('final.full_history', return_value=[{'seq': 1}]) as history, \
                patch('scripts.sweep.time.sleep'):
            self.assertEqual(finish_started_week(world, 8, journal, factory, fast=True), {'ranked': True})
        desk.rejoin.assert_called_once_with(captured.initial_snapshot, [{'seq': 1}])
        world.delete.assert_not_called()
        world.client.create.assert_not_called()
        history.assert_called_once_with(world, through=500)

    def test_repeated_setup_failures_preserve_the_created_world_until_it_finishes(self):
        import gzip
        from pathlib import Path
        import tempfile
        from unittest.mock import Mock, patch
        from scripts.sweep import play_week
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            for name in ('worlds', 'traces', 'reveals'):
                (out / name).mkdir()
            world, client = Mock(id='same-started-world'), Mock()
            client.create.return_value = world
            client.call.return_value = {}
            real_open = gzip.open
            failures = [0]
            def flaky_open(*args, **kwargs):
                if failures[0] < 5:
                    failures[0] += 1
                    raise OSError('temporary trace failure')
                return real_open(*args, **kwargs)
            with patch('performance.PracticeClient', return_value=client), \
                    patch('scripts.sweep.gzip.open', side_effect=flaky_open), \
                    patch('scripts.sweep.finish_started_week', return_value={'marginCents': 1}) as finish, \
                    patch('scripts.sweep.time.sleep'):
                result = play_week(out, 'models.delta:make_delta', 8, 'seed', 'arm', {}, True)
            self.assertEqual(result['score']['marginCents'], 1)
            self.assertEqual(result['attempts'], 6)
            client.create.assert_called_once()
            world.delete.assert_not_called()
            self.assertTrue(finish.call_args.kwargs['resumed'])
            self.assertFalse((out / 'worlds' / world.id).exists())
