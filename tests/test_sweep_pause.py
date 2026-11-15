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
