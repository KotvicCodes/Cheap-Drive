# Faster official practice runs

Measured and implemented on 14 November 2026. These changes use the official
simulator and preserve its eight unfinished-world slots and shared team rate
limit.

## Changes

- `compare.py run --workers 8` uses separate worker processes, SDK connections
  and worlds. It caps the initial pool at the number of free team slots. On a
  failure, it stops scheduling new worlds and drains active work; Ctrl-C asks
  active workers to stop between SDK calls. Existing worlds are never removed
  unless `--delete-on-error` was explicitly requested for this invocation.
- `--fast` coalesces declared bookkeeping wakes without discarding events. The
  starter, fixed strategy and Alpha explicitly opt in. In particular, a lost
  Alpha quote updates margin feedback and reservations but queues no action.
  The update can arrive with the next decision event, before that decision is
  handled. Intermediate handler clock values are reconstructed: an earlier
  `gig_started` event can re-estimate reservations using `desk.now`, so simply
  processing the whole larger batch at its final minute would be incorrect.
- Fast mode omits daily score requests and the final roster/reveal. Final
  score, end snapshot, all action intents/results and event batches remain
  durably journaled. Full capture is still the default.
- `PracticeClient` wraps the pinned SDK transport to request and decode gzip,
  collect timings, and cache copies of the public map. SDK validation, retries
  and rate-limit waits remain in effect. World state is not cached. Alpha
  reuses initial reads already captured by `play_model` instead of fetching
  snapshot, roster and map again during construction.
- `--resume` reuses completed weeks only when code revision, project Python
  hashes, settings, server and clock configuration match. Failed runs get new
  trace names; previous attempts and world IDs remain inspectable. An output
  file lock prevents competing controllers. This is suite resumption, not
  resumption of an interrupted world or replay of unknown-outcome mutations.
- The GitHub practice workflow requests up to eight free slots with full
  captures, rather than executing every week sequentially.

## Evidence

The earlier Alpha search recorded 659 completed weeks with a median duration
of 272 seconds, using eight workers. Adding workers to that existing search
cannot shorten its individual weeks. The ordinary `compare.py` CLI previously
had only sequential execution.

In the six saved weeks for tuned Alpha trial 137, there were 1,661–1,968
distinct event minutes that matched the old wake policy. Of those, 288–416 per
week (15–25%) contained only events removed from the fast wake list. This is a
trace-based estimate of avoidable stopping points, **not** an end-to-end speed
measurement. Multiple SDK calls, same-minute responses and the remaining
network/CPU work affect actual duration.

The official server returned the same public map as 54,171 uncompressed bytes
or 7,669 gzip bytes. Alternating read-only requests on a completed level-8
world returned a 100-event page as 35,324 or 3,700 wire bytes. Across four
samples per encoding, median event-read durations were 129 ms uncompressed and
146 ms with gzip. Tiny score reads were about 80 and 83 ms and were not
compressed. Thus gzip clearly reduced bytes but did **not** establish a
latency improvement in that small, variable sample. `--no-compression` allows
the tradeoff to be checked on the actual runner host.

At that observation the practice bucket allowed 196 requests per second.
Eight processes issuing one sequential call each over an approximately 80 ms
path would still be below that allowance. This is evidence for investigating
round-trip latency, not proof of where all world runtime goes: large batches,
server work, local computation, changing rate limits and other clients matter.
While a test final runs, the official allowance falls to 20 requests per
second and can become the limiting factor.

The server reported all eight slots occupied by the ongoing Beta sweep during
verification. No additional worlds were created and none of that sweep's
worlds or processes were modified. A full paired official-week speed and score
comparison remains to be run when slots are free; no measured whole-week
speedup is claimed.

## Verification and use

The offline suite exercises compressed responses and errors, SDK 429 retry,
unchanged request validation, copied map caching, identical Alpha actions and
handler clocks under coalescing, conservative custom subclasses, process-pool
pairing, interruption, failure checkpoints and resumable traces. These tests
verify integration behavior, not simulator performance.

```bash
python -m unittest discover -s tests -v
python compare.py run --model-a models/alpha.json --model-b models/starter.json \
  --levels 8 --seeds screen-1 screen-2 --workers 8 --fast \
  --output runs/quick-screen
# Repeat the exact command with --resume after an interruption.
python performance.py --samples 8
```

Use the public benchmark from candidate runner locations before paying for a
server. Keep the same strategy, seeds and engine conditions when measuring
actual weeks. Compare action contents and world minutes as well as final
scores when validating fast mode. A normal full-capture run provides reveals
and daily checkpoints for finalists and diagnosis.

Sources: [official API and limits](https://spread.bahnexpress.com/kit/API.md),
[official handbook](https://spread.bahnexpress.com/kit/HANDBOOK.md), the pinned
Python SDK, and local saved Alpha timing/event data. Raw traces and generated
benchmark data remain under ignored directories.
