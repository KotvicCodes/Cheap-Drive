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
