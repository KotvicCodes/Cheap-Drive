"""Durable application-boundary capture, without HTTP headers or credentials."""
from __future__ import annotations

import io
import json
import os
import re
import threading
import time
from contextlib import contextmanager
from functools import lru_cache
from typing import TextIO

SECRET_KEY = re.compile(r'^(authorization|proxy.authorization|.*api.?key|spread.?key|access.?token|refresh.?token|password|secret)$', re.I)
SECRET_TEXT = re.compile(r'(?i)(?:bearer\s+\S+|(?:authorization|spread_key|api[_-]?key)\s*[=:]\s*[^\s,}\]]+)')

# API field names repeat throughout a week. Cache only key classification;
# values (including note text and credentials) are always inspected afresh.
_secret_key = lru_cache(maxsize=1024)(SECRET_KEY.fullmatch)


def clean(value):
    if isinstance(value, dict):
        return {k: '[credential removed]' if _secret_key(k) else clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return SECRET_TEXT.sub('[credential removed]', value) if isinstance(value, str) else value


class Journal:
    def __init__(self, output: TextIO, *, fsync=None):
        self.output = output
        self.fsync = fsync if fsync is not None else os.fsync
        self._batch_depth = 0
        self._dirty = False

    def record(self, kind: str, **fields: object) -> None:
        self.output.write(json.dumps(clean({'type': kind, **fields}), ensure_ascii=False, allow_nan=False) + '\n')
        self._dirty = True
        # Inputs are flushed before handling; intents before the SDK call;
        # complete returns before their bookkeeping. Only adjacent diagnostics
        # may share a flush inside an explicit batch.
        if not self._batch_depth or kind in ('event', 'action_intent', 'act_result', 'advance_batch',
                                            'model_quote_result'):
            self._flush()

    def _flush(self):
        self.output.flush()
        try:
            self.fsync(self.output.fileno())
        except (io.UnsupportedOperation, AttributeError):
            pass  # In-memory fixtures have no durable file descriptor.
        self._dirty = False

    @contextmanager
    def batch(self):
        """Group diagnostics, retaining flushed SDK boundaries even when nested."""
        self._batch_depth += 1
        try:
            yield
        finally:
            self._batch_depth -= 1
            if not self._batch_depth and self._dirty:
                self._flush()

    def record_history(self, events) -> None:
        """One durable flush for an already read replay, not one fsync per old event."""
        for event in events:
            self.output.write(json.dumps(clean({'type': 'history_event', 'event': event}),
                                         ensure_ascii=False, allow_nan=False) + '\n')
        self._flush()


class BackgroundFsync:
    """Keep flush-before-action ordering without waiting for storage on the consumer.

    Journal still flushes complete records through Python/gzip to the kernel at
    each boundary, preserving them across process SIGKILL. This worker coalesces
    fsync requests on a duplicate descriptor. A host/power failure can lose the
    unsynced tail; process-crash recovery does not depend on fsync completing.
    """
    def __init__(self, fd, *, interval=0.25):
        self.fd = os.dup(fd)
        self.interval = interval
        self.wake = threading.Event()
        self.stopping = False
        self.error = None
        self.count = 0
        self.max_seconds = 0.0
        self.worker = threading.Thread(target=self._run, daemon=True, name="final-journal-fsync")
        self.worker.start()

    def request(self, fd):
        if self.error is not None:
            raise self.error
        self.wake.set()

    def _run(self):
        while True:
            self.wake.wait()
            time.sleep(self.interval)
            self.wake.clear()
            started = time.monotonic()
            try:
                os.fsync(self.fd)
            except OSError as error:
                self.error = error
                return
            self.count += 1
            self.max_seconds = max(self.max_seconds, time.monotonic() - started)
            if self.stopping and not self.wake.is_set():
                return

    def stats(self):
        return dict(completed=self.count, max_seconds=self.max_seconds)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stopping = True
        self.wake.set()
        self.worker.join()  # only at shutdown, when no more quote windows remain
        os.close(self.fd)
        if self.error is not None:
            raise self.error


class CapturedWorld:
    """Persist intent before each SDK call and its whole return before desk handling.

    No automatic retry: an intent without a return has an unknown server outcome.
    Splitting here prevents the SDK's 50-action batching from hiding earlier returns.
    """
    def __init__(self, world, journal):
        self.world, self.journal = world, journal
        self.now, self.serial = 0, 0

    def _intent(self, method, actions, **parameters):
        self.serial += 1
        batch = self.serial
        self.journal.record('action_intent', batchId=batch, at=self.now, method=method,
                            actions=actions, parameters=parameters)
        return batch

    def act(self, actions):
        results = []
        for start in range(0, len(actions), 50):
            part = actions[start:start + 50]
            batch = self._intent('act', part)
            response = self.world.act(part)
            self.journal.record('act_result', batchId=batch, at=self.now, results=response)
            results.extend(response)
        return results

    def advance(self, *, actions, **parameters):
        early = actions[:-50]
        results = self.act(early)
        last = actions[-50:]
        batch = self._intent('advance', last, **parameters)
        response = self.world.advance(actions=last, **parameters)
        self.journal.record('advance_batch', batchId=batch, at=self.now, response=response)
        self.now = response['now']
        return {**response, 'results': results + response.get('results', [])}

    def capture(self, kind, getter, phase=None):
        value = getter()
        return self._save_capture(kind, value, phase)

    def _save_capture(self, kind, value, phase):
        self.journal.record(kind, phase=phase, at=self.now, **{kind: value})
        if kind == 'snapshot':
            self.now = value['now']
        return value

    def optional(self, kind, getter, phase=None):
        try:
            value = getter()
        except (Exception, KeyboardInterrupt) as error:
            if isinstance(error, KeyboardInterrupt):
                raise
            # Exception messages can contain URLs, headers or credentials.
            self.journal.record('capability_unavailable', capability=kind, phase=phase)
            return None
        # Persistence failure must stop the run, even for optional SDK capabilities.
        return self._save_capture(kind, value, phase)
