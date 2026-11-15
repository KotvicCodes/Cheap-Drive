"""Shared world capacity is checked before launch, not during a running week."""
import os
import unittest
from unittest.mock import Mock, patch

from scripts.sweep import LaunchWindowClosed, wait_for_launch, wait_for_team_capacity


class SweepCapacityTests(unittest.TestCase):
    def test_cutoff_is_rechecked_during_pause_and_capacity_wait(self):
        with patch.dict(os.environ, {'SWEEP_PAUSE_FILE':'/unused'}), \
                patch('scripts.sweep.Path.exists',return_value=True), \
                patch('scripts.sweep.time.sleep') as sleep, \
                patch('scripts.sweep.check_launch_cutoff',side_effect=[None,LaunchWindowClosed]):
            with self.assertRaises(LaunchWindowClosed):
                wait_for_launch()
        sleep.assert_called_once_with(1)
        client=Mock()
        client.worlds.return_value=[{'ended':False}]*12
        with patch.dict(os.environ, {'SWEEP_TEAM_WORLD_LIMIT':'12'}), \
                patch('scripts.sweep.wait_for_launch',side_effect=[None,LaunchWindowClosed]), \
                patch('scripts.sweep.time.sleep'):
            with self.assertRaises(LaunchWindowClosed):
                wait_for_team_capacity(client)
        client.worlds.assert_called_once()

    def test_cutoff_expires_while_paused(self):
        with patch.dict(os.environ, {'SWEEP_START_BEFORE_UTC':'2000-01-01T05:30:00+00:00',
                                    'SWEEP_PAUSE_FILE':'/unused'}), \
                patch('scripts.sweep.time.sleep') as sleep:
            with self.assertRaises(LaunchWindowClosed):
                wait_for_launch()
        sleep.assert_not_called()

    def test_future_cutoff_allows_launch_and_timezone_is_required(self):
        with patch.dict(os.environ, {'SWEEP_START_BEFORE_UTC':'2100-01-01T05:30:00+00:00',
                                    'SWEEP_PAUSE_FILE':''}):
            wait_for_launch()
        with patch.dict(os.environ, {'SWEEP_START_BEFORE_UTC':'2100-01-01T05:30:00'}):
            with self.assertRaises(ValueError):
                wait_for_launch()

    def test_disabled_gate_does_not_fetch(self):
        client = Mock()
        with patch.dict(os.environ, {}, clear=True):
            wait_for_team_capacity(client)
        client.worlds.assert_not_called()

    def test_full_team_waits_and_rechecks_until_a_world_ends(self):
        client = Mock()
        client.worlds.side_effect = [[{'ended':False}]*12,
                                    [{'ended':False}]*12,
                                    [{'ended':False}]*11+[{'ended':True}]*20]
        with patch.dict(os.environ, {'SWEEP_TEAM_WORLD_LIMIT':'12'}), \
                patch('scripts.sweep.wait_for_launch') as pause, \
                patch('scripts.sweep.time.sleep') as sleep:
            wait_for_team_capacity(client)
        self.assertEqual(client.worlds.call_count,3)
        self.assertEqual(pause.call_count,3)
        self.assertEqual(sleep.call_args_list, [((3,),),((3,),)])

    def test_above_cap_waits_and_invalid_data_cannot_authorize_launch(self):
        client = Mock()
        client.worlds.side_effect = [[{'ended':False}]*13, [{'ended':True}]]
        with patch.dict(os.environ, {'SWEEP_TEAM_WORLD_LIMIT':'12'}), \
                patch('scripts.sweep.wait_for_launch'), \
                patch('scripts.sweep.time.sleep') as sleep:
            wait_for_team_capacity(client)
        sleep.assert_called_once_with(3)
        client.worlds.return_value = [{}]
        client.worlds.side_effect = None
        with patch.dict(os.environ, {'SWEEP_TEAM_WORLD_LIMIT':'12'}), self.assertRaises(KeyError):
            wait_for_team_capacity(client)
