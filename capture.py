"""Durable application-boundary capture, without HTTP headers or credentials."""
from __future__ import annotations

import io
import json
import os
import re
from typing import TextIO

SECRET_KEY = re.compile(r'^(authorization|proxy.authorization|.*api.?key|spread.?key|access.?token|refresh.?token|password|secret)$', re.I)
SECRET_TEXT = re.compile(r'(?i)(?:bearer\s+\S+|(?:authorization|spread_key|api[_-]?key)\s*[=:]\s*[^\s,}\]]+)')


def clean(value):
    if isinstance(value, dict):
        return {k: '[credential removed]' if SECRET_KEY.fullmatch(k) else clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return SECRET_TEXT.sub('[credential removed]', value) if isinstance(value, str) else value


class Journal:
    def __init__(self, output: TextIO):
        self.output = output

    def record(self, kind: str, **fields: object) -> None:
        self.output.write(json.dumps(clean({'type': kind, **fields}), ensure_ascii=False, allow_nan=False) + '\n')
        self.output.flush()
        try:
            os.fsync(self.output.fileno())
        except (io.UnsupportedOperation, AttributeError):
            pass  # In-memory fixtures have no durable file descriptor.

    def record_history(self, events) -> None:
        """One durable flush for an already read replay, not one fsync per old event."""
        for event in events:
            self.output.write(json.dumps(clean({'type': 'history_event', 'event': event}),
                                         ensure_ascii=False, allow_nan=False) + '\n')
        self.output.flush()
        try:
            os.fsync(self.output.fileno())
        except (io.UnsupportedOperation, AttributeError):
            pass


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
