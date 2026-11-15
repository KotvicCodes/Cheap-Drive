# Final runner recovery, 14 November 2026

The live command remains `python final.py models/delta.json`. Model settings,
pricing formulas and `dispatch.play_model` are unchanged. Verification for this
change was entirely offline; no worlds were created, advanced or deleted, and
no team key was used.

## What tonight's trace actually shows

Source: `20261114T174535Z-final-fbba6be07b1ee0c2e25e7.jsonl.gz`, with the
`test-final-2000.log` console log supplied for this task. These private files
are not included in this commit.

- The last price request arrived at minute **6837**. There were **1,030**
  requests in total: **872** competitive quotes and **158** deliberate declines.
- Three quote actions were rejected as already closed: `R01014` at minute
  **6775**, `R01015` at **6783**, and `R01017` at **6784**. Treating those
  requests as accepted losing quotes would incorrectly lower the learner.
- Several event handlers took 1–2 seconds, including minutes **6871–6873**.
  The last consumed event was sequence **17842**, minute **7075**. A read timeout
  and DNS failure preceded the rebuild at **7849**, with **18,342** history
  events. The **499** events since the last consumed sequence contained **zero
  price requests**.
- The rejoin snapshot had **zero open requests**, **8 open gigs**, **16 booked
  gigs**, **10 working gigs**, and **zero active two-order gigs**. Order statuses
  were 218 delivered, 17 booked, 12 waiting, 9 moving and 4 cancelled.
- After rejoin there were **1,171** streamed events: 976 gig views, 76 ledger
  entries, 38 deliveries, 29 pickups, 28 gig starts, 14 bookings, 7 expiries,
  2 drops and 1 deadline warning. There were **zero price requests, quotes,
  declines, wins or losses**. Thus there is no post-rejoin markup or decline
  reason to report. The unchanged 256 net wins does not establish a quoting
  failure in this particular run.
- The runner made **11 single-order posts**: four immediately at rejoin for
  waiting work without gigs, then seven after expiries. It made **one reprice**
  at minute **10857**, in response to a deadline warning, and **zero withdrawals**.
  It did not proactively reprice the eight restored open gigs at rejoin.
- The last quoted markup was **16,675 bps**. Replaying all feedback with the
  recorded action receipts reconstructs **16,180.99041248096 bps** after all
  decisions. It reproduces **all 1,030 quote/decline pricing decisions exactly**.
  History alone cannot identify the three rejected quotes and instead gives
  15,891.47663692692 bps; this is why retaining local receipts matters.

The reproduced restart defects are real even though the live trace does not
exercise a post-rejoin request or a restored active pair.

## Recovery behavior

`GammaDesk.rejoin` now uses `recovery.py` for Gamma, Gamma notes/pairs and Delta.
Replay uses the ordinary quote, learner and feedback bookkeeping hooks, suppresses
pair timers and discards historical actions. It never calls the live event
handler or submits past actions. Snapshot reconciliation then:

1. Rebuilds requests, learner markup, scoped trackers/day starts, dealer/trust
   mappings, warnings, driver progress and fee ages. It reads history after the
   snapshot and stops at that snapshot minute; same-minute settlement,
   cancellation, delivery and gig transitions override stale snapshot fields.
2. Reconstructs pair metadata at each pair's original posting time and checks
   the actual stops and audience. Original split timers survive. If that cannot
   be done safely, it withdraws the unbooked pair and posts its members singly.
   A failed/racing withdrawal keeps the links and a protective pair record;
   it never posts duplicate singles before confirmation. Booked/working pairs
   retain partner rescue on later cancellations, drops and expiry.
3. Reprices urgent unbooked singles. Urgent pairs go through the pair split
   handler first, avoiding a two-car reprice based on one order's fee.
4. Quotes every still-open, unexpired request through normal pricing, even if
   replay already knows its ID. Quotes precede pair withdrawal round trips.
   A request straddling its deadline retains any earlier pending feedback.
5. Repairs missing legs and failed-visit restrictions without resetting the
   original posting age or duplicating an existing/currently queued post.

A JSON checkpoint is queued every five real seconds after successful action
handling, plus immediately after rejoin. A coalescing background writer fsyncs
and atomically replaces `runs/final/<world-id>-checkpoint.json`. It includes
model books, original supply inputs, pair plans, exclusion/progress sets and
learner state. World ID, model spec, version, sequence and basic state validity
must match before it is used. Bad or unavailable checkpoints fall back to replay.

Durable trace quote receipts recover the checkpoint tail and failed quotes;
the reader also understands the previous runner's `beta_quote`/`beta_decline`
and `action_intent`/`act_result` records. Complete JSON lines from a gzip file
without its final footer remain usable after SIGKILL. Historical trace logging
uses one durable flush for the batch instead of an fsync per old event.

The final CLI now flushes each input, intent and returned receipt through
Python/gzip to the operating system before handling or proceeding, while a
coalescing background worker performs journal `fsync` at most about four times
per second. A blocked storage sync cannot hold up the quote consumer. Complete
records remain recoverable after process SIGKILL, including when the worker's
first sync has not returned; there is no queue of unwritten receipt records.
Storage-sync errors are raised at the next journal boundary, and clean shutdown
waits for the last sync. Practice journals retain synchronous fsync.

This preserves process-crash recovery, not identical power-loss durability:
a host/power failure can lose the unsynced journal tail while storage is stalled.
The checkpoint writer already runs separately. A kernel-flushed write can still
block under severe storage pressure, so the final also needs a quiet host and
free disk space; background fsync is not a guarantee against every I/O stall.

Clock and daily score reads run in separate daemon workers, each with its own
HTTP client in the CLI. The consumer only reads the cached minute and completed
reports. A 429 retry, DNS failure or 20-second read timeout cannot hold up its
quotes. Only terminal score/snapshot reads remain synchronous. Daily scores are
observations taken after their requested day boundary; they are not atomic
midnight measurements.

## What remains approximate without local state

Keep `runs/final/` with the process when restarting. Server events do not expose
quote acceptance/rejection, our timer/withdrawal decisions, rejected pair posts,
original public supply inputs, or the exact wall-clock minute at which a delayed
event was handled. Checkpoints and trace receipts preserve the available local
evidence. If both are missing, replay assumes the normal historical quote was
accepted; a lost request alone cannot prove that. Historical capacity-dependent
admission/targets can also be approximate when a gig's old stops were changed.

For missing fee-age evidence, the order's win time is the conservative floor,
so recovery never starts a fresh cheap ramp. Former visible pairs are excluded
from re-pairing when their exact split cause is unknown. An unreconstructable
open pair is split, while an unreconstructable booked pair retains a protective
record and is resolved on its next actionable event. Some reconstructed pair
diagnostic fields (such as whether a waiting single was withdrawn) need not
match without a checkpoint; snapshot schedules and safe split timing are what
control recovery. No model parameters are changed to compensate for uncertainty.

## Offline verification

The full suite passes: **337 tests**, including **32 added tests** (baseline
305). Added coverage includes open requests and expired
pending feedback, scoped learners/day starts/trust, side-effect-free replay,
restored pair timers/cancellation/drop/expiry, failed withdrawal races, urgent
single and pair fees, original fee age, failed-visit restrictions, checkpoints,
truncated gzip receipts, same-minute snapshot races, and blocked background
reads. The synthetic half-week test compares a continuous Delta desk with a
fresh desk rebuilt from public snapshot/history, then applies more feedback.

Additionally, all three saved `rescue-notes--delta-f1-s01/s02/s03` practice traces
were fed through an in-memory SDK response tape. **All 5,704 action batches were
reproduced exactly** (1,864 + 1,920 + 1,920). Fresh desks rebuilt at minutes
5043, 5051 and 5040 matched markup, trackers/day starts, pending quotes, open
orders, gig links, first-posted times, dealer/trust mappings, driver progress
and active pair timing. No private fixture or reveal was committed.

Run the suite with the SDK environment supplied for this task:

```sh
/home/agent/.t3/worktrees/Cheap-Drive/t3-a14884b2-9968a1fe51ca69bf/.venv/bin/python -m unittest discover -s tests
```

## Operator rehearsal: deliberate kill and restart

This is a future network rehearsal for an operator, not part of the offline
verification above. Activate the SDK virtualenv and use the normal configured
credentials. From this worktree:

```sh
python final.py models/delta.json --rehearse recovery-drill --quiet &
runner_pid=$!
```

After there are won orders and a checkpoint, note the printed world ID and kill
the runner (a formed pair makes a stronger drill):

```sh
kill -KILL "$runner_pid"
python final.py models/delta.json --rehearse recovery-drill --quiet
```

The same seed/model resumes the unfinished world using a local rehearsal
manifest, restarts its pacer from the saved server minute, and creates a new
trace. Confirm the same world ID and a `model_rejoin` record with the restored
markup/checkpoint sequence; check that open requests receive quotes and pairs
retain or safely split their partners. Completed/deleted rehearsals start fresh.
Use a new seed for a separate rehearsal. Practice pauses while its pacer is
stopped, so this tests process recovery rather than a final continuing to move
while the whole process is dead. Preserve the rehearsal world for inspection;
this runner does not delete it.
