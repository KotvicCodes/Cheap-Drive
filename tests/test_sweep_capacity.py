"""Shared world capacity is checked before launch, not during a running week."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.sweep import LaunchWindowClosed, planned_jobs, wait_for_launch, wait_for_team_capacity, world_launch_slot


class SweepCapacityTests(unittest.TestCase):
    def test_explicit_job_order_reuses_finished_weeks_and_rejects_invalid_work(self):
        plan={'variants':{'admission':{},'segmented':{}},'seeds':['paired','fresh'],
              'jobs':[{'label':'admission','seed':'paired'},{'label':'admission','seed':'fresh'},
                      {'label':'segmented','seed':'paired'},{'label':'segmented','seed':'fresh'}]}
        self.assertEqual(planned_jobs(plan,{('admission','paired')}),
                         [('admission','fresh'),('segmented','paired'),('segmented','fresh')])
        plan['jobs'].append({'label':'admission','seed':'paired'})
        with self.assertRaises(ValueError):planned_jobs(plan,set())
        plan['jobs']=[{'label':'unknown','seed':'paired'}]
        with self.assertRaises(ValueError):planned_jobs(plan,set())

    def test_disabled_screen_arm_never_checks_capacity_or_creates_a_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            disabled=Path(tmp)/'disabled.json'
            disabled.write_text('["weak"]')
            client=Mock()
            with patch.dict(os.environ, {'SWEEP_DISABLED_LABELS_FILE':str(disabled)},clear=True):
                with self.assertRaisesRegex(LaunchWindowClosed,'arm disabled'):
                    with world_launch_slot(client,'weak'):self.fail('weak arm launched')
                with world_launch_slot(client,'survivor'):pass
            client.worlds.assert_not_called()

    def test_lane_wait_counts_only_its_unfinished_worlds_across_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane=Path(tmp)
            for name in ('a','b'):
                (lane/name/'worlds').mkdir(parents=True)
            (lane/'a/worlds/own').write_text('candidate--seed')
            (lane/'b/worlds/ended').write_text('candidate--previous')
            client=Mock()
            client.worlds.side_effect=[
                [{'worldId':'own','ended':False},{'worldId':'ended','ended':True},
                 {'worldId':'another-lane','ended':False}],
                [{'worldId':'own','ended':True},{'worldId':'another-lane','ended':False}]]
            with patch.dict(os.environ, {'SWEEP_LANE_WORLD_LIMIT':'1','SWEEP_LANE_ROOT':tmp,
                                        'SWEEP_TEAM_WORLD_LIMIT':'0','SWEEP_PAUSE_FILE':''},clear=True), \
                    patch('scripts.sweep.time.sleep') as sleep:
                with world_launch_slot(client):
                    (lane/'b/worlds/new').write_text('new--seed')
            sleep.assert_called_once_with(3)
            self.assertEqual(client.worlds.call_count,2)
            self.assertTrue((lane/'b/worlds/new').exists())

    def test_lane_default_is_off_and_missing_root_fails_closed(self):
        client=Mock()
        with patch.dict(os.environ, {}, clear=True):
            with world_launch_slot(client):pass
        client.worlds.assert_not_called()
        with patch.dict(os.environ, {'SWEEP_LANE_WORLD_LIMIT':'3'},clear=True):
            with self.assertRaises(ValueError):
                with world_launch_slot(client):self.fail('invalid gate permitted creation')

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
