"""An operator pause drains active weeks and gates every new creation."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.sweep import play_week, wait_for_launch


class SweepPauseTests(unittest.TestCase):
    def test_unconfigured_gate_never_waits(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch('scripts.sweep.time.sleep', side_effect=AssertionError('wait')):
            wait_for_launch()

    def test_absent_flag_runs_and_present_flag_waits_until_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            flag = Path(directory) / 'PAUSE'
            with patch.dict(os.environ, {'SWEEP_PAUSE_FILE': str(flag)}):
                with patch('scripts.sweep.time.sleep', side_effect=AssertionError('wait')):
                    wait_for_launch()
                flag.touch()
                with patch('scripts.sweep.time.sleep', side_effect=lambda _: flag.unlink()) as sleep:
                    wait_for_launch()
                sleep.assert_called_once_with(1)

    def test_pause_can_hold_for_multiple_checks(self):
        with patch.dict(os.environ, {'SWEEP_PAUSE_FILE': '/unused/flag'}), \
                patch('scripts.sweep.Path.exists', side_effect=[True, True, False]), \
                patch('scripts.sweep.time.sleep') as sleep:
            wait_for_launch()
            self.assertEqual(sleep.call_count, 2)

    def test_worker_waits_before_creation_but_finishes_if_paused_during_week(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            for name in ('worlds', 'traces', 'reveals'):
                (out / name).mkdir()
            flag = out / 'PAUSE'
            flag.touch()
            world = Mock(id='offline-world')
            client = Mock()
            client.call.return_value = {}

            def create(**kwargs):
                self.assertFalse(flag.exists())
                self.assertFalse(kwargs['board'])
                return world

            def finish(*args, **kwargs):
                flag.touch()  # operator pauses new launches while this week runs
                return {'marginCents': 12345}

            def sleep(seconds):
                if seconds == 1:
                    client.create.assert_not_called()
                    flag.unlink()

            client.create.side_effect = create
            with patch.dict(os.environ, {'SWEEP_PAUSE_FILE': str(flag)}), \
                    patch('performance.PracticeClient', return_value=client), \
                    patch('dispatch.play_model', side_effect=finish), \
                    patch('scripts.sweep.time.sleep', side_effect=sleep):
                result = play_week(out, 'models.delta:make_delta', 8, 'offline', 'gate', {}, True)
            self.assertEqual(result['score']['marginCents'], 12345)
            self.assertTrue(flag.exists())
            client.create.assert_called_once()
            world.delete.assert_not_called()

    def test_utc_blackout_blocks_then_resumes_and_cutoff_refuses_launch(self):
        from datetime import datetime, timezone
        env = {'SWEEP_LAUNCH_BLACKOUT_UTC': '03:00-03:30', 'SWEEP_LAUNCH_CUTOFF_UTC': '05:30'}
        with patch.dict(os.environ, env, clear=True), patch('scripts.sweep.datetime') as clock, \
                patch('scripts.sweep.time.sleep') as sleep:
            clock.now.side_effect = [datetime(2026, 11, 15, 3, 0, tzinfo=timezone.utc),
                                     datetime(2026, 11, 15, 3, 30, tzinfo=timezone.utc)]
            wait_for_launch()
            sleep.assert_called_once_with(1)
            clock.now.side_effect = None
            clock.now.return_value = datetime(2026, 11, 15, 5, 30, tzinfo=timezone.utc)
            with self.assertRaisesRegex(RuntimeError, 'cutoff'):
                wait_for_launch()

    def test_shared_capacity_gate_checks_worlds_before_launch(self):
        from scripts.sweep import wait_for_capacity
        client = Mock()
        client.worlds.side_effect = [[dict(ended=False)] * 12, [dict(ended=False)] * 10]
        with patch.dict(os.environ, {'SWEEP_ACTIVE_WORLD_LIMIT': '12'}, clear=True), \
                patch('scripts.sweep.time.sleep') as sleep:
            wait_for_capacity(client)
        self.assertEqual(client.worlds.call_count, 2)
        sleep.assert_called_once_with(5)
