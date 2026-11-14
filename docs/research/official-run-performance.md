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
that verification. No additional worlds were created and none of that sweep's
worlds or processes were modified. The selected Gamma follow-up below adds
paired full/fast weeks when slots later became free; neither investigation
establishes a whole-week speedup.

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

## Selected Gamma follow-up: speed without changing margin

Measured on 14 November 2026, using source revision
`0eb4e3efc7b49c17a29aa05e9249e7ab45db710d`, Python 3.12.12 and the pinned SDK.
The selected `models/gamma.json` and all dispatcher/model source files were
unchanged. This is an execution and reporting audit, not a new prototype or
parameter selection.

### Full capture versus fast practice

Four new level-8 **ordinary practice** worlds ran the selected Gamma on two
shared seeds. The initial read-only capacity check found two unfinished worlds
(one final, one practice). Four new worlds left two slots spare even when
counting the final conservatively. All four completed naturally. No existing
world was advanced, stopped, deleted or otherwise changed, and no ranking or
final world was created. The final capacity query confirmed all four owned
worlds ended and two other worlds remained unfinished.

| Seed | Full margin | Fast margin | Orders | On time | Exact actions / events |
| --- | ---: | ---: | ---: | ---: | ---: |
| `gamma-speed-01` | €7,635.40 | €7,635.40 | 210 | 97.619% | 1,394 / 10,967 |
| `gamma-speed-02` | €6,818.57 | €6,818.57 | 240 | 97.500% | 1,526 / 14,746 |

Both modes ranked on both seeds. The offline audit compared **every action and
its submission minute/method, every action result, the complete ordered event
stream (including ledger), final score, and final snapshot**. Everything
matched exactly after removing only the snapshot's world ID. These are exact
observations on two deterministic practice weeks, not a guarantee for every
seed, custom desk, server revision or final clock.

The selected factory enables pairs, whose concrete desk explicitly declares
an empty `passive_wake_events`. Consequently `--fast` does **not** coalesce
Gamma's pair wakes: full/fast each made 1,752 advances on seed 01 and 1,849 on
seed 02. Fast omitted nine daily score reads, one end roster and one reveal,
saving eleven calls per week (about 0.6% of SDK calls). It retained initial
supply inputs, the end snapshot and all events/actions. Do not enable inherited
coalescing for this desk: its outbox access polls pair timers and can queue
withdrawals or fallback posts.

Observed full/fast durations were 223.308/210.579 seconds on seed 01 and
224.358/389.925 seconds on seed 02. These concurrent, single-pair timing
observations **do not establish a whole-week speedup**. The first fast run
was profiled; three other profiling attempts stopped before any world read
because Python's profiler conflicted across threads. Those same three newly
created worlds were then played without profiling, with no earlier action
intent to retry. Their initial failed setup duration is excluded from the
reported completed attempt. Raw attempts remain in private artifacts.

SDK calls accounted for 97–98% of completed-attempt wall time, with zero 429
responses in all four runs. On the profiled seed-01 fast run, SSL reads took
201.2 seconds, all API calls 203.9 seconds, and the journal 5.15 seconds out of
210.58 seconds total. The journal's 5,040 `fsync` calls took 4.00 seconds.
These nested timings must not be added together. Removing durability or
changing model admission/fees would address little of the measured runtime
while changing a useful guarantee or the policy, so neither was changed.

A separate credential-free alternating public-map benchmark (eight samples per
encoding on one warmed connection) measured median 111.65 ms identity versus
109.80 ms gzip, and 54,171 versus 7,669 wire bytes. Compression reduces transfer
size; this small latency difference is not evidence of a stable speed gain.

### Offline report improvement

Profiling a saved 7,879,926-byte, 3,554-record journal found 421,821 JSON decodes:
the credential pre-scan decoded every ordinary object key separately, and
credential traversal repeatedly revisited nested objects while their parents
were decoded. `week_report.py` now checks plain printable keys directly and
reuses the fact that JSON's object hook has already validated child objects.
Escaped/control-character keys still use JSON validation. Strings and arrays,
including values overwritten by duplicate keys, still undergo credential
checks. Original bytes, diagnostics and report contents are retained.

The final benchmark alternates old/new analysis order over five repetitions,
reading each fixture's bytes once. It compares the entire returned model and
rendered HTML for exact equality. The old module is loaded from the source
revision above; `VERSION` and renderer assets are identical. Results and
fixture hashes are retained privately; no raw notes or reveals are published.

| Journal | Bytes | Before (s) | After (s) | Reduction |
| --- | ---: | ---: | ---: | ---: |
| Historical journal (3,554 records) | 7,879,926 | 1.525 | 1.134 | 25.6% |
| Historical journal (17,909 records) | 3,196,052 | 0.725 | 0.554 | 23.5% |
| Gamma seed 01, fast | 4,321,009 | 0.860 | 0.603 | 29.9% |
| Gamma seed 01, full | 5,944,302 | 1.162 | 0.829 | 28.7% |
| Gamma seed 02, fast | 4,951,692 | 1.152 | 0.919 | 20.2% |
| Gamma seed 02, full | 6,860,344 | 1.514 | 1.062 | 29.8% |

The dispatcher and comparison runner are unchanged, so this report improvement
cannot affect dispatch decisions or economic outcomes. It speeds report
construction; it does not speed simulator weeks or reduce HTML size/browser
rendering cost. The compare path already uses separate worker SDK connections;
more workers improve suite throughput only while slots and team rate limits
permit, and a capacity observation is not a reservation against another chat.

Verification: 229 offline tests passed, including added escaped-credential,
nested-array, duplicate-value and malformed-key cases. A deterministic
504-input differential check against the original parser matched outputs or
exception types on nested, escaped, duplicate and malformed sources. Every
measured saved trace produced the identical analysis model and identical HTML.

Private reproduction/handoff artifacts in this checkout:

- `runs/sources-baseline/`: baseline Python/model copies and SHA-256 manifest.
- `runs/speed_probe.py`, `runs/recover_probe.py`: live probe and recovery
  scripts; these require the authorized private credential source. Use only
  ordinary practice worlds, query slots before creation and leave spare
  capacity. The original probe's per-thread profiler limitation is documented
  above; do not repeat concurrent profiler starts.
- `runs/speed-baseline/`: all four complete JSONL journals, timing/score records,
  original failed setup attempts, profile and exact-equivalence digests.
- `runs/audit_equivalence.py`: rerun with
  `.venv/bin/python runs/audit_equivalence.py` (offline).
- `runs/report_bench.py`, `runs/week_report_before.py`,
  `runs/report-benchmark.json`: alternating five-repeat old/new benchmark;
  rerun with `.venv/bin/python runs/report_bench.py` after practice work drains.
- `runs/public-transport-benchmark.json`: reproduce with
  `.venv/bin/python performance.py --samples 8`.

For further practice acceleration, benchmark the same frozen model near the
simulator host and compare complete action/event streams again. Preserve pair
wakes, durable intents/results, SDK validation and official retries. Final
clocks require their own integration and validation.
