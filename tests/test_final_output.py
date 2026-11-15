"""Isolated rehearsal output must keep both manifest and checkpoint on restart."""
from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import final


class FinalOutputTests(unittest.TestCase):
    def test_custom_output_rejoins_same_world_and_leaves_default_directory_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / 'isolated-rehearsal'
            world = Mock(id='offline-rehearsal')
            world.snapshot.return_value = {'now': 100, 'endsAt': 1000}
            client = Mock()
            client.create.return_value = client.world.return_value = world
            client.timing.return_value = {}
            score = dict(marginCents=12000, onTimeShare=1, wonOrders=3, ranked=True)
            model = Path(final.ROOT) / 'models/epsilon.json'
            args = [str(model), '--rehearse', 'offline-seed', '--quiet', '--output', str(out)]
            with patch.object(final, 'ROOT', root), \
                    patch.dict(os.environ, {'SPREAD_KEY': 'offline-fixture'}), \
                    patch('performance.PracticeClient', return_value=client), \
                    patch.object(final, 'Pacer', return_value=Mock(error=None)), \
                    patch.object(final, 'play_until_done', return_value=(score, {})), \
                    patch.object(final, 'report'), \
                    patch.object(final, 'datetime') as dates, \
                    patch('recovery.CheckpointStore') as checkpoints, \
                    redirect_stdout(io.StringIO()):
                # Two starts in the same second need separate gzip files: a
                # killed member cannot safely be extended by a new process.
                dates.now.side_effect = [datetime(2026, 11, 15, 5, 0, 0, microsecond=n,
                                                 tzinfo=timezone.utc) for n in (1, 2)]
                self.assertEqual(final.main(args), 0)
                self.assertEqual(final.main(args), 0)
            client.create.assert_called_once_with(level=8, seed='offline-seed')
            client.world.assert_any_call(world.id)
            self.assertEqual(len(list(out.glob('rehearsal-*.json'))), 1)
            self.assertEqual(len(list(out.glob('*.jsonl.gz'))), 2)
            self.assertEqual([call.args[0] for call in checkpoints.call_args_list],
                             [out / 'offline-rehearsal-checkpoint.json'] * 2)
            self.assertFalse((root / 'runs' / 'final').exists())
