"""Replay a captured practice week offline, asserting every batch and its minute.

    python scripts/replay_dispatch.py TRACE.jsonl.gz [--profile PROFILE]

Trace contents stay local. This uses the real runner and model, with recorded
SDK returns; it is an equivalence/CPU check, not a simulator or latency test.
"""
from __future__ import annotations

import argparse
from collections import deque
from copy import deepcopy
import cProfile
import gzip
import importlib
import io
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capture import Journal
from dispatch import play_model


class ReplayJournal(Journal):
    def __init__(self, rows, output):
        super().__init__(output)
        self.expected = deque(r for r in rows if r['type'] == 'action_intent')
        self.batches = self.actions = 0

    def record(self, kind, **fields):
        if kind == 'action_intent':
            expected = self.expected.popleft()
            if {'type': kind, **fields} != expected:
                raise AssertionError(f'action batch {self.batches + 1} differs (including clock/parameters)')
            self.batches += 1
            self.actions += len(fields['actions'])
        super().record(kind, **fields)


class ReplayWorld:
    def __init__(self, rows):
        self.client = self
        self.returns = {}
        for row in rows:
            kind = row['type']
            if kind in ('snapshot', 'map', 'roster', 'reveal', 'score', 'daily_score',
                        'act_result', 'advance_batch'):
                self.returns.setdefault(kind, deque()).append(row)

    def _read(self, kind, field=None):
        # Desks mutate events/orders as in live play; never mutate the fixture.
        return deepcopy(self.returns[kind].popleft()[field or kind])

    def snapshot(self):
        return self._read('snapshot')

    def map(self):
        return self._read('map')

    def roster(self):
        return self._read('roster')

    def reveal(self):
        return self._read('reveal')

    def score(self):
        return self._read('daily_score' if self.returns.get('daily_score') else 'score', 'score')

    def act(self, actions):
        return self._read('act_result', 'results')

    def advance(self, **parameters):
        return self._read('advance_batch', 'response')


def replay(rows, output=None):
    run = next(r for r in rows if r['type'] == 'run')
    module, name = run['factory'].split(':')
    factory = getattr(importlib.import_module(module), name)
    journal = ReplayJournal(rows, output if output is not None else io.StringIO())
    world = ReplayWorld(rows)
    started = time.perf_counter()
    score = play_model(world, run['level'], journal,
                       lambda w, l, n, j: factory(w, l, n, j, **run['settings']),
                       fast=run.get('fast', False))
    elapsed = time.perf_counter() - started
    if journal.expected or any(world.returns.values()):
        raise AssertionError('replay did not consume every recorded batch/return')
    return dict(seconds=elapsed, batches=journal.batches, actions=journal.actions, score=score)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--journal', type=Path, help='also measure real gzip/durable journal writes')
    args = parser.parse_args()
    opener = gzip.open if args.trace.suffix == '.gz' else open
    with opener(args.trace, 'rt', encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream]
    profiler = cProfile.Profile() if args.profile else None
    if profiler:
        profiler.enable()
    try:
        if args.journal:
            with gzip.open(args.journal, 'wt', encoding='utf-8') as output:
                result = replay(rows, output)
        else:
            result = replay(rows)
    finally:
        if profiler:
            profiler.disable()
            profiler.dump_stats(args.profile)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
