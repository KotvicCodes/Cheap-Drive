"""An operator pause drains active weeks and gates every new creation."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.sweep import wait_for_launch


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
