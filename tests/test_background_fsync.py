"""The final consumer must not wait for fsync or lose process-crash receipts."""
import gzip
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from capture import BackgroundFsync, CapturedWorld, Journal
from recovery import CheckpointStore


class BackgroundFsyncTests(unittest.TestCase):
    def test_blocked_fsync_does_not_block_api_or_receipt_recovery(self):
        entered, release = threading.Event(), threading.Event()
        def blocked(fd):
            entered.set()
            if not release.wait(5):
                raise OSError('fixture gate timed out')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '20261115-final-world.jsonl.gz'
            with gzip.open(path, 'wt') as stream, patch('capture.os.fsync', blocked):
                sync = BackgroundFsync(stream.fileno(), interval=0)
                try:
                    journal = Journal(stream, fsync=sync.request)
                    journal.record('run', worldId='world', model={'name': 'Delta'})
                    self.assertTrue(entered.wait(2))
                    class World:
                        def act(inner, actions):
                            self.assertFalse(release.is_set())
                            return [dict(ok=True, id='r')]
                    world = CapturedWorld(World(), journal)
                    start = time.monotonic()
                    world.act([dict(type='quote', requestId='r', prices={'same_day': 100})])
                    journal.record('model_quote_result', requestId='r', at=600,
                                   ok=True, competitive=True, tracker='global')
                    journal.record_history([dict(seq=0, at=600, kind='price_request')])
                    self.assertLess(time.monotonic() - start, .5)
                    store = CheckpointStore(Path(directory) / 'world-checkpoint.json', 'world', {'name': 'Delta'})
                    try:
                        self.assertTrue(store.quote_receipts()['r']['ok'])
                    finally:
                        store.close()
                finally:
                    release.set()
                    sync.__exit__(None, None, None)
                self.assertGreaterEqual(sync.count, 2)  # requests during fsync are not dropped

    def test_background_storage_failure_is_raised_before_next_boundary(self):
        with tempfile.TemporaryFile() as stream, patch('capture.os.fsync', side_effect=OSError('fixture I/O failure')):
            sync = BackgroundFsync(stream.fileno(), interval=0)
            sync.request(stream.fileno())
            sync.worker.join(2)
            self.assertFalse(sync.worker.is_alive())
            with self.assertRaisesRegex(OSError, 'fixture I/O failure'):
                sync.request(stream.fileno())
            with self.assertRaisesRegex(OSError, 'fixture I/O failure'):
                sync.__exit__(None, None, None)
            with self.assertRaises(OSError):
                os.fstat(sync.fd)

    @unittest.skipUnless(hasattr(signal, 'SIGKILL'), 'requires process SIGKILL')
    def test_sigkill_during_blocked_fsync_keeps_complete_quote_receipt(self):
        # The child is killed before its first fsync returns. Recovery must read
        # its complete kernel-flushed gzip records without a footer or checkpoint.
        script = '''
import gzip, threading, sys
from pathlib import Path
from capture import BackgroundFsync, Journal
root=Path(sys.argv[1]); entered=threading.Event()
def blocked(fd):
    entered.set()
    threading.Event().wait()
import capture
capture.os.fsync=blocked
with gzip.open(root/'20261115-final-world.jsonl.gz','wt') as stream:
    sync=BackgroundFsync(stream.fileno(),interval=0)
    journal=Journal(stream,fsync=sync.request)
    journal.record('run',worldId='world',model={'name':'Delta'})
    assert entered.wait(2)
    journal.record('action_intent',batchId=1,at=600,actions=[{'type':'quote','requestId':'r'}])
    journal.record('act_result',batchId=1,at=600,results=[{'ok':True,'id':'r'}])
    journal.record('model_quote_result',requestId='r',at=600,ok=True,competitive=True,tracker='global')
    (root/'ready').write_text('complete receipt flushed')
    threading.Event().wait()
'''
        with tempfile.TemporaryDirectory() as directory:
            child = subprocess.Popen([sys.executable, '-c', script, directory], cwd=Path(__file__).resolve().parents[1],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 5
                while not (Path(directory) / 'ready').exists() and child.poll() is None and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue((Path(directory) / 'ready').exists())
                child.kill()
                child.wait(timeout=2)
                self.assertEqual(child.returncode, -signal.SIGKILL)
                store = CheckpointStore(Path(directory) / 'world-checkpoint.json', 'world', {'name': 'Delta'})
                try:
                    self.assertEqual(store.quote_receipts(), {'r': dict(at=600, ok=True, competitive=True, tracker='global')})
                finally:
                    store.close()
            finally:
                if child.poll() is None:
                    child.kill(); child.wait(timeout=2)
                child.stderr.close()


if __name__ == '__main__':
    unittest.main()
