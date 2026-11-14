"""Offline contracts for package imports, persisted names and script entry points."""
from contextlib import redirect_stdout
from copy import deepcopy
import gzip
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from capture import Journal
from compare import load_model, model_from_spec
from dispatch import JournalDesk
from models import persisted_factory_name
from recovery import CheckpointStore, model_state, restore_state
from scripts.replay_dispatch import replay
from scripts.sweep import play_week
from tests.test_dispatch_performance import SyntheticWeek, synthetic_rows
from tests.test_recovery import new_desk

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('alpha', 'beta', 'gamma', 'gamma_notes', 'gamma_pairs', 'delta',
           'delta_b1', 'delta_lanes', 'delta_option_spread', 'notes', 'gemini_notes')


class ConfigWorld(SyntheticWeek):
    def snapshot(self):
        return {**super().snapshot(), 'driverPositions': []}


class ModelPackageTests(unittest.TestCase):
    def test_old_and_new_imports_share_identity_in_either_fresh_import_order(self):
        # A separate interpreter for every model/order catches bootstrap cycles
        # hidden by unittest's collection-time legacy imports.
        code = '''
import importlib, pickle, sys
from unittest.mock import patch
import models  # registers the legacy import aliases; there are no root shim files
name, first = sys.argv[1:]
a = importlib.import_module(first)
b = importlib.import_module(name if first.startswith('models.') else 'models.' + name)
assert a is b
owned = [(key, value) for key, value in vars(a).items()
         if isinstance(value, type) and value.__module__ == 'models.' + name]
assert owned, name
for key, cls in owned:
    assert getattr(b, key) is cls
    assert pickle.loads(pickle.dumps(cls)) is cls
    assert pickle.loads(('c' + name + '\\n' + key + '\\n.').encode()) is cls
    assert pickle.loads(('cmodels.' + name + '\\n' + key + '\\n.').encode()) is cls
    with patch.object(a, key, object()) as replacement:
        assert getattr(b, key) is replacement
'''
        for name in MODULES:
            for first in (name, 'models.' + name):
                with self.subTest(name=name, first=first):
                    result = subprocess.run([sys.executable, '-c', code, name, first],
                                            cwd=ROOT, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_config_constructs_offline_and_preserves_persisted_spec(self):
        for path in sorted((ROOT / 'models').glob('*.json')):
            with self.subTest(config=path.name):
                spec = json.loads(path.read_text())
                model = load_model(path)
                desk = model.factory(ConfigWorld(), 8, 600, Journal(io.StringIO()))
                self.assertIsInstance(desk, JournalDesk)
                if ':' in spec['factory']:
                    self.assertTrue(spec['factory'].startswith('models.'))
                    self.assertEqual(model_from_spec(spec).spec, model.spec)
                    self.assertTrue(spec['factory'].startswith('models.'))
                    old = deepcopy(spec)
                    old['factory'] = old['factory'].removeprefix('models.')
                    with tempfile.TemporaryDirectory() as directory:
                        old_path = Path(directory) / path.name
                        old_path.write_text(json.dumps(old))
                        legacy = load_model(old_path)
                    self.assertEqual(model.spec, legacy.spec)
                    other = legacy.factory(ConfigWorld(), 8, 600, Journal(io.StringIO()))
                    # Some existing factories define a fresh local desk class
                    # on every invocation; their shared bases retain identity.
                    self.assertEqual(type(desk).__bases__, type(other).__bases__)
                    self.assertEqual(type(desk).__qualname__, type(other).__qualname__)
                self.assertEqual(json.loads(path.read_text()), spec)

    def test_only_relocated_factory_names_change_in_persisted_specs(self):
        for name in ('fixed', 'starter', 'compare:fixed', 'models.custom:factory',
                     'other.delta:factory', 'models.delta.child:factory'):
            with self.subTest(factory=name):
                self.assertEqual(persisted_factory_name(name), name)

    def test_all_saved_plan_factory_fields_resolve_without_rewriting(self):
        def check(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == 'factory' and isinstance(child, str) and ':' in child:
                        module, attribute = child.split(':', 1)
                        self.assertTrue(callable(getattr(importlib.import_module(module), attribute)))
                    else:
                        check(child)
            elif isinstance(value, list):
                for child in value:
                    check(child)
        for path in (ROOT / 'docs/research/plans').rglob('*.json'):
            with self.subTest(plan=path.relative_to(ROOT)):
                check(json.loads(path.read_text()))

    def test_sweep_resolves_both_factory_names_and_records_identical_actions(self):
        class Client:
            def __init__(self, **kwargs):
                pass

            def create(self, **kwargs):
                world = SyntheticWeek()
                world.id = 'offline-package-test'
                return world

            def call(self, *args):
                return {}

        intents = []
        with tempfile.TemporaryDirectory() as directory:
            for factory in ('delta:make_delta', 'models.delta:make_delta'):
                out = Path(directory) / factory.split(':')[0]
                for sub in ('worlds', 'traces', 'reveals'):
                    (out / sub).mkdir(parents=True)
                with patch('performance.PracticeClient', Client), patch('scripts.sweep.time.sleep'), redirect_stdout(io.StringIO()):
                    result = play_week(out, factory, 8, 'offline', 'test', {}, True)
                with gzip.open(out / 'traces' / result['trace'], 'rt') as stream:
                    rows = [json.loads(line) for line in stream]
                self.assertEqual(rows[0]['factory'], factory)
                intents.append([row for row in rows if row['type'] == 'action_intent'])
        self.assertEqual(*intents)

    def test_journal_replay_accepts_both_factory_names(self):
        rows = synthetic_rows('delta.json')
        results = []
        for factory in ('delta:make_delta', 'models.delta:make_delta'):
            fixture = deepcopy(rows)
            fixture[0]['factory'] = factory
            with redirect_stdout(io.StringIO()):
                result = replay(fixture)
            results.append({k: v for k, v in result.items() if k != 'seconds'})
        self.assertEqual(*results)

    def test_checkpoint_and_quote_receipts_survive_factory_spelling_change(self):
        spec = load_model(ROOT / 'models/delta.json').spec
        for written, loaded in (('delta:make_delta', 'models.delta:make_delta'),
                                ('models.delta:make_delta', 'delta:make_delta')):
            with self.subTest(written=written), tempfile.TemporaryDirectory() as directory:
                old = model_from_spec({**deepcopy(spec), 'factory': written}).spec
                new = model_from_spec({**deepcopy(spec), 'factory': loaded}).spec
                desk = new_desk()
                path = Path(directory) / 'checkpoint.json'
                store = CheckpointStore(path, 'world', old)
                try:
                    store.save(desk, 12)
                finally:
                    store.close()
                rows = [dict(type='run', worldId='world', model=old),
                        dict(type='beta_quote', requestId='r', at=600),
                        dict(type='model_quote_result', requestId='r', at=600, ok=True,
                             competitive=True, tracker='global')]
                with gzip.open(Path(directory) / 'trace-world.jsonl.gz', 'wt') as stream:
                    for row in rows:
                        stream.write(json.dumps(row) + '\n')
                resumed = CheckpointStore(path, 'world', new)
                try:
                    checkpoint = resumed.load()
                    self.assertIsNotNone(checkpoint)
                    self.assertEqual(checkpoint['lastSeq'], 12)
                    restored = new_desk()
                    restore_state(restored, checkpoint['state'])
                    self.assertEqual(model_state(restored), model_state(desk))
                    self.assertTrue(resumed.quote_receipts()['r']['ok'])
                finally:
                    resumed.close()

    def test_script_path_entry_points_offline_from_an_unrelated_directory(self):
        commands = [(['final.py', 'models/delta.json', '--help'], 0),
                    (['scripts/board.py', '--help'], 0),
                    (['compare.py', '--help'], 0),
                    (['compare.py', 'run', '--help'], 0),
                    (['compare.py', 'report', '--help'], 0),
                    (['week_report.py', '--help'], 0), (['demo.py'], 0),
                    # sweep has a positional-only CLI, no --help: reaching its
                    # existing argument error proves the script imports offline.
                    (['scripts/sweep.py'], 1)]
        env = {k: v for k, v in os.environ.items() if k not in ('SPREAD_KEY', 'PYTHONPATH')}
        with tempfile.TemporaryDirectory() as directory:
            for args, expected in commands:
                with self.subTest(script=args):
                    result = subprocess.run([sys.executable, str(ROOT / args[0]), *args[1:]],
                                            cwd=directory, env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, expected, result.stderr)
                    self.assertNotIn('ModuleNotFoundError', result.stderr)
                    self.assertNotIn('ImportError', result.stderr)
                    if args == ['scripts/sweep.py']:
                        self.assertIn('IndexError', result.stderr)
