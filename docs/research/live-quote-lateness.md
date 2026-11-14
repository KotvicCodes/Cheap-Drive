# Live quote lateness investigation, 14 November 2026

The fix changes the **rehearsal clock**, not the live-final action path or any
model decision. Keep model-aware recovery, the five-second checkpoints, quote
receipts and separate clock/score connections. All runs in this investigation
are ordinary level-8 practice worlds, using `models/delta.json` unchanged.

## Saved traces first

The source traces are in the operator's other checkout under
`runs/final/20261114T...jsonl.gz`; private trace data is not committed here.
Quotes below count every SDK quote action, including deliberately uncompetitive
quotes logged as `beta_decline`. Counting only `beta_quote` while counting all
rejections overstates the failure share.

| runner / trace stamp | quote actions | rejected as closed | competitive quotes | competitive rejections |
|---|---:|---:|---:|---:|
| old rehearsal, 164752 | 1,033 | 5 | 883 | 4 |
| old real test final, 174535 | 1,030 | 3 | 872 | 3 |
| recovery rehearsal, 191523 | 850 | 136 | 760 | 126 |
| recovery restart, 192543 | 190 | 9 | 152 | 8 |
| recovery rehearsal, 214405 | 851 | 214 | 737 | 193 |
| recovery restart, 215425 | 190 | 51 | 160 | 40 |

The earlier loaded recovery rehearsal still used the **30% target** model.
Therefore the later 42% target and extended pairing do not explain the
regression by themselves. Peak action-call density was comparable: 25 calls
per 15 world minutes in the old rehearsal versus 22 in the later recovery
rehearsal; 95th percentiles were 16 and 15 respectively. Almost every batch
contained one action, in both runners.

All 214 pre-kill rejections in the later drill had `action_intent.at` equal to
`price_request.event.at`, with `respondBy` exactly 15 minutes later. After
restart 48/51 also had zero recorded lag; the other three were rejoin quotes
with recorded lags 11, 5 and 4 minutes. For example, R00064 arrived at 664,
was due at 679, and the rejected action was recorded at 664. R00850 arrived
at 5372, was due at 5387, and its initial rejoin quote was recorded at 5383.

This is **not a real send timestamp**: `CapturedWorld.now` inherits `desk.now`,
and the desk advances from consumed event timestamps. A backed-up stream
therefore makes an already-late send look instantaneous in the old trace.
There are no wall timestamps or pacer advances in those saved files, so they
cannot distinguish transport queuing from atomic practice advances alone.

## Instrumented reproduction and mechanism

A short, unfixed recovery-runner rehearsal on fresh seed
`lateness-control-20261114`, pace 9, produced **42/423 late quote actions
(9.93%)** in 302 seconds. It lost 35 of its first 219 requests during Monday.
The probe recorded monotonic wall time, actual pacer minute, every advance,
request consumption, action intent/result, checkpoint copy duration and slow
journal writes, without changing the model.

The consumer fell **47 world minutes behind**; an answer completed as much
as **50 world minutes after arrival**. Around the first rejection, HTTP calls
in both the advance and action connections rose from roughly 80 ms to
400–500 ms. R00089 arrived at 799, was due at 814, was consumed and sent while
the pacer reported 813, and was rejected with the world at 817. Its own
request handler and HTTP answer occupied about half a second. The consumer
was answering earlier requests and performing synchronous gig actions while
the pacer continued advancing the clock. It was not holding an answered quote
for a later batch.

The pacer formerly computed `target = start + elapsed * rate` and advanced
atomically to that target. A slow HTTP call accumulated clock debt; the next
advance repaid it in one jump. The measured maximum jump was **25 minutes**,
longer than an entire 15-minute response window. Such an advance can create
and expire a request before *any* client has an opportunity to answer it.
Smaller jumps also deliver bursts to a consumer already blocked on action
HTTP calls. This catch-up behavior amplifies intermittent transport/service
stalls into a stream backlog. The pacer is byte-for-byte the same in the old
and recovery versions: these observations do not implicate the recovery
commit as the origin of the problem.

The initiating HTTP latency is variable; the old control did not experience
the same stalls on its first Monday. We cannot assign the server/network
portion of that latency from client traces. The measured and fixed local
mechanism is unbounded clock catch-up, rather than a claimed server defect.

Other candidates:

- **Rate buckets:** SDK `_buckets` and `_bucket_of` are instance dictionaries,
  not shared globals. The new clients cannot double-charge the action
  client's local bucket. Saved completed runs reported zero 429s. On the
  later restarted drill, API time exceeded transport time by only **98 ms
  total across 292 calls**, ruling out substantial SDK bucket sleeps there.
- **Checkpoint and journal:** the instrumented reproduction's largest
  synchronous checkpoint copy was **6.1 ms**; no journal write exceeded
  **50 ms**. Copying and encoding the saved 1.1 MB checkpoint locally took
  about 24 ms on average, 33 ms maximum. The checkpoint's fsync already runs
  in its writer thread. These are not multi-second request delays.
- **Stream threads / polling:** events are yielded directly from the SDK's
  WebSocket generator into the desk; there is no event queue worker between
  them. `idle=1` is a timeout only when no buffered/socket data is available,
  not a one-second sleep per event. Clock/score workers do not consume events.
- **Desk clock:** it can lag the server while the socket is backed up; that
  explains misleading `at` values. Changing it to wall time would change
  model/pair decisions and was deliberately not done.
- **Model search / batching:** the unfixed quote's largest own answer time
  was 1.415 s; the backlog reached over five seconds at pace 9. The old-model
  loaded drill also failed. No pricing, admission, search or batching rule
  was changed to compensate.

## Fix and real-final implications

The pacer now advances **one world minute per API call**. Its next scheduled
tick is bounded by the completion of the previous call, so missed wall-clock
ticks cannot turn into a multi-minute atomic catch-up. Fast calls retain the
requested pace. Slow transport reduces achieved rehearsal speed instead of
skipping opportunities to answer. The command's pace is therefore a target,
not a guarantee when the advance endpoint cannot sustain it.

There is **no Pacer in the real final**, so the clock artefact does not affect
that path. Ordinary synchronous HTTP/network stalls can still back up either
runner, as they could before recovery. The shorter final response throughput
budget, at about 4.7 rather than 9 minutes/second, provides more time; this
investigation does not promise that arbitrary outages cannot lose a quote.
There is no evidence here that removing the recovery features would make the
real final safer.

## Acceptance rehearsal

Per the revised instruction, no full-week proof is claimed. Two ten-minute
fixed runs at requested pace 9 run in parallel, with an old `e41c7e2:final.py`
control using the **same seed and current model**. The second fixed process is
SIGKILLed after five minutes and restarted with the identical command. The
probe only observes boundary timings. Each fixed run has its own trace and
manifest directory to prevent the same seed from sharing a world.

All runs used seed `lateness-control-20261114`. The fixed runs overlapped for
all ten minutes; the old control started about three minutes earlier and
stopped at its own ten-minute mark. All three used the same current Delta
model. A diagnostic wrapper loaded the old runner from `git show
 e41c7e2:final.py`, or imported the candidate, then observed public boundary
timings. It changed no model methods, requests, actions or SDK rate limits.

| run | requests seen | quote attempts | returned results | late (share of results) | slowest quote answer | net won orders |
|---|---:|---:|---:|---:|---:|---:|
| old control, 10 min | 851 | 851 | 851 | 7 (0.82%) | 0.875 s | 289 |
| fixed A, 10 min | 709 | 709 | 709 | 0 (0%) | 0.210 s | 241 |
| fixed B, total 10 min | 723 | 723 | 722 | 0 (0%) | 0.640 s | 242 |
| B before SIGKILL, 5 min | 416 | 416 | 416 | 0 (0%) | 0.640 s | 129 |
| B after restart, 5 min | 307 | 307 | 306 | 0 (0%) | 0.281 s | +113 |

Quote attempts count durable `action_intent` records. One B quote was in flight
at the planned stop and has no return record: its result is **unknown**, not
counted as an accepted quote. Its request arrived at 5156, deadline 5171, while
the stopped practice world reached 5157. All other attempts have receipts.
Shares use the returned-result denominator. Quotes include deliberate declines.
Net won orders match the server score; the post-restart figure is the increment
since the restart snapshot. Gross wins were 293/243/245 for old/A/B, with
4/2/3 cancellations respectively.

“Slowest quote answer” measures monotonic time from consuming the request to
receiving its quote result, including model handling and HTTP, excluding time
already spent in the WebSocket backlog. Maximum observed arrival-to-result
**world-clock** lags were 17 minutes old, 10 A, 11 B before restart and 8 B
after restart. Pacer minutes update when an advance response returns, so these
world-clock measurements have approximately one-tick uncertainty in the fixed
runner. They are not exact server acceptance timestamps.

Achieved speeds were **9.00 / 8.53 / 8.61** world minutes per second for
old/A/B against target 9. The candidate slowed about 4–5% under API stalls.
At stop the server snapshots were at minutes 5402 / 5108 / 5157. Thus the order
counts are partial-week observations at different world minutes, **not** a
claim of better or worse full-week score. Maximum fixed pacer step was one
minute throughout both runs. The control's maximum was 17 minutes.

B resumed **world w60798583c20c76d63801** at minute **2596**. Its `model_rejoin`
reported checkpoint sequence **2853**, **18** replayed events, markup
**12831.025430056101 bps**, **129** recovered noncancelled orders and **five**
pairs. The model was not reset to its initial 15000 bps. The restart command
and environment were identical, including the per-run trace/manifest root.

Private evidence is under this checkout's `runs/lateness/`: probe timing JSONL,
console logs, summary JSON, server snapshots/scores and per-run gzip traces.
The old trace is under `runs/final/20261114T222327Z-...`. Fixed traces are under
`runs/lateness/fixed-a/runs/final/` and `fixed-b/runs/final/`. The operator's
requested `runs/delta-final/late-quotes-interim.md` in the parent checkout was
updated during the test and at completion.

All **four worlds created by this investigation** (unfixed diagnostic, old
control and two fixed runs) were stopped and deleted. No other world was
deleted; no ranking run or live final was started or changed. Maximum
concurrent unfinished worlds owned by this investigation was three.

Acceptance passes on the observed receipts: both fixed runs, including each
restart segment, are at or below the old control's late-quote share. The
in-flight final attempt remains explicitly unconfirmed. Per the revised
instruction there was no full-week rehearsal or ordinary-practice score run.

Use this fix with recovery retained for the final; rolling back to e41c7e2
would remove recovery without addressing the pacer, which that version also
contains. The real-final action code is unchanged by this fix.

## Tests

`python -m unittest discover -s tests`: **371 passed**, baseline 367. Four new
tests cover a request born inside an advance after a three-second HTTP stall,
requested pacing with fast transport, no catch-up budget with slow transport,
and invalid paces rejected before accessing a world.
