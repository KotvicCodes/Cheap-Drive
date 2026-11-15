# Epsilon P1 pair planner and rescue experiments

All policies are opt-in. `models/delta.json` and `models/epsilon.json` remain
unchanged. The base is `origin/t3/epsilon-model`; the comparison uses the
nineteen saved current-Delta weeks, not new Delta worlds.

## Settings

| Setting | Default | Enabled behavior |
| --- | ---: | --- |
| `delta_pair_latest0_windows` | 0 | Delta alias for `pair_tight_windows=1` |
| `pair_tight_windows` | 0 | Clamp four posted stop ends to backward latest(0) visit times |
| `delta_pair_stop_spare` / `pair_stop_spare` | 0 | Apply admission/timer spare to the tighter delivery-stop end |
| `pair_rescue_floor_bps` | 0 | Floor rescue opening at this fraction of the combined current solo offers |
| `pair_rescue_step_minutes` | 0 | Add an early rescue increase after this many minutes |
| `pair_rescue_step_bps` | 600 | Size of the optional step, against combined raw reference fees |
| `pair_retry_limit` | 0 | Allow different partners after failure, up to this many failures per order |
| `pair_retry_transfer_km` | 30 | Transfer bound when either order has a prior failed pair |
| `pair_cancel_cleanup` | 0 | Retire shortened pairs, prune cancelled stops, preserve survivor eligibility |
| `pair_aged_guard_minutes` | 0 | Exclude waiting singles older than this age only when their current fee reaches the guard |
| `pair_aged_guard_bps` | 10000 | Current solo fee threshold for the optional age guard |
| `pair_self_time` | 0 | Count map self-road minutes while retaining zero same-town transfer distance |
| `pair_economic_rank` | 0 | Prefer greatest combined reference less opening fee among feasible pairs |
| `pair_earliest_finish` | 0 | Prefer `(finish, transfer_km, orders)` within the same legal candidate set |
| `pair_finish_band_minutes` | 0 | Minimize transfer among candidates finishing within this many minutes of the fastest legal plan |

The numeric step/transfer/guard defaults have no effect unless their policy
is enabled. Existing `delta_pair_self_roads` is reused only in combination;
its standalone negative experiment is not replayed.

## Verified mechanisms and limits

The planner already computes backward feasibility, including calendars,
charging and plates, but originally posts the original solo stop windows.
Latest(0) bounds are captured after calendar/charging handling and before the
30-minute pre-pickup plate allowance. Admission spare, aggregate last start,
latest-safe time, timer and solo windows retain their existing behavior.
Clamping preserves each low bound; an invalid interval is rejected before
withdrawal. Checkpoint and public-gig reconstruction use the same plan.

Rescue pairs reset the fee clock and normally hold the opening for the full
60-minute split interval. The new floor uses actual current solo schedules,
not reference fees as a substitute for an aged offer. An optional early rung
can increase before the timer. Fresh pairs are unaffected. Schedules remain
monotone with unique timestamps.

Bounded re-pairing records failed unordered combinations and per-order failure
counts. It never withdraws booked or started gigs, restores singles after post
failure, and retains the existing confirmed-withdrawal requirement. Failure counts and unordered bans survive checkpoints; public history and
withdrawn gigs conservatively reconstruct missing attempts without double
counting. The window and rescue-fee arms introduce no additional recovery state.

Self-road timing and transfer-distance sorting are separate hypotheses. The
existing road flag changes both; `pair_self_time` changes only driving time.
Economic ranking uses a reference-based estimate, not a causal fee-saving
forecast. It may favor long routes and must pass the service gate.

## Evaluation protocol

Use only `scripts/sweep.py`, three workers, ordinary level-eight worlds,
complete Delta JSON base, and separate ignored output beneath
`runs/epsilon-p1/`. Screen seeds include `delta-f1-s07` and `delta-f2-s04`;
initial planner probes use `delta-f1-s06` and `delta-f1-s08` for the other two.
Extend survivors to the exact nineteen-seed union f1 s01..s11 / f2 s01..s08.
Then confirm independently on fresh seeds with retained Delta references.
Read only `summary.md` and `runs.jsonl` for empirical selection.

Promotion requires positive paired mean margin and every observed week at
least 91.5% on time in both existing and fresh cohorts. A screen result is
not promotion, and unchanged Delta itself misses the floor on f1-s07.
No ranking or final worlds are authorized. Pause launches at 03:00 UTC,
resume at 03:45, stop new worlds at 05:30, and drain all worlds by 05:50.
The final report deadline is 05:45 UTC.


## Predeclared fresh confirmation

Reserve `epsilon-margin-confirm-20261115-s01` through `s08` for independent
confirmation of a candidate selected from the nineteen old paired seeds.
Reuse the orchestrator's `runs/epsilon/margin-fresh-reference/runs.jsonl`
Delta scores when available. Do not tune against candidate outcomes on these
seeds. The earlier `epsilon-confirm-20261115-s01..s08` brake cohort is not a
new holdout for this lane.

Exact-off comparison against the frozen origin driver mixin passed 300
synthetic pair plans and 30 order/timer/receipt batches, yielding 45 identical
actions. The tests construct no network client and read no saved traces.


## Delivery-stop spare (wave two)

The original planner subtracts spare only from the stated order deadline.
An earlier note closing or private delivery slot is enforced but receives no
spare of its own. Enabled stop spare uses `min(deadline, delivery_stop_end)`
before subtracting the existing spare, in both forward admission and backward
safe-start calculation. It leaves latest(0), posted windows, fees, transfer
limits, pickup bounds and the 60-minute timer unchanged. Infeasible plans are
rejected before withdrawal. Public reconstruction uses the same policy.

After the tight-roads extension, screen the isolated stop-spare arm, its
combination with tight-roads, and that combination plus rescue85/step25.
These use the common screen seeds s07, f2-s04, s01, s05. The earlier prepared
planner-ranking/time/retry screens are deferred. Per orchestrator steering,
no further rescue-pricing worlds run without tight-roads.


## Earliest-completion priority (volume-gap steering)

Screen `pair_earliest_finish=1` on Early Epsilon: unchanged Delta settings
except the already confirmed premium admission slack of 1440 minutes. The
control is the retained nineteen premium1440 weeks, with exact configuration
matching checked. Also retain the matching Delta comparison. No new control
worlds, transfer widening, fee changes, timing repairs or target increase are
part of this first screen. Ranking alone changes from `(transfer_km, finish,
orders)` to `(finish, transfer_km, orders)`. Conflicting economic and earliest
ranking flags are rejected.

The selector must first improve paired margin and pass every service week;
then a target-4400 test may be considered independently. Total completed wins,
late share and expiry counts can be compared from runs.jsonl. A nominal finish
improvement does not demonstrate actual driver reuse. The earlier strict
read restriction excludes retrospective saved-tape exposure mining in this
lane; synthetic exact-off plans/actions establish parity instead.

This priority supersedes the queued diagnostic fresh tight-roads block, which
was cancelled before it created a world. Stop-spare combinations already in
flight are retained. Target a confirmed result by 05:45 UTC, drain all worlds
by 05:50, and retain the 03:00–03:45 launch pause.


## Volume follow-up and hard cutoff

Strict earliest completion screened at -€169.28/week versus Early Epsilon,
2/4 positive, floor 91.892%, and -2 completed orders/week. The conditional
4400 arm is not authorized by its own dispatch-first gate and was not run.
Two follow-ups retain low-transfer preference when candidates finish within
60 or 180 minutes of the fastest plan, while excluding large readiness waits.
A separate bounded-retry arm tests two attempts per order on the Early Epsilon
base. These retain target4200, fees, route limits and all admission guards.

For every new screen/extension, the plan base includes premium slack1440.
The old Delta-base results remain historical and are never pooled with a
new Early Epsilon candidate under the same label. The new hard deadlines
are no practice starts after 05:30, all worlds ended by 05:50, final report
by 05:45. The launch gate has an independent 05:30 timer. Use only fixed known
paths and shallow own-worktree reads; no recursive scans across worktrees.


## Timing-only diagnostic

The broad same-town-road policy changes both driving time and transfer ranking:
a same-town connection moves from zero to the map's positive transfer distance.
Its negative full-cohort result therefore does not isolate timing correction.
The queued `epsilon-time-screen.json` retains zero same-town transfer preference
and changes only intra-town driving minutes (`pair_self_time=1`), independently
and with latest(0) windows. It retains Early Epsilon's premium1440 guard and all
route, fee, spare and quote-target settings. This is not a repeat of the old
road-only arm. It starts only after the three-worker volume screen drains.


## Cost per car mission (02:38 UTC)

The orchestrator replaced the selector experiments with a cost-then-volume
mission and reduced this lane to two world slots. The three in-flight selector
worlds drained before their controller was stopped; both finish bands and retry2
failed the service floor on the two completed hard seeds, so no extension is
authorized. The queued timing-only screen is deferred.

First screen larger candidate pools: transfer120/150km and second-pickup idle180
minutes, leaving the physical720-minute drive cap, arrival180, spare60, fees,
last-safe-start timer, premium1440 and target4200 unchanged. These are separate
from the prior wider-reach screens on a projected-brake base. Profile `off`
prevents its90km override; `pairs=1` remains explicit.

Opt-in `SWEEP_PAIR_DIAGNOSTICS=1` adds aggregate realized pooling to runs.jsonl.
A shared gig must actually deliver at least two distinct orders. A split trial,
a dropped booking, and a shortened pair completing one car are not counted as
pooled completions. Fee/car uses net driver-fee ledger charges, including fees
on unsuccessful gigs and refunds. Diagnostic-only instrumentation introduces
no extra model actions or calls, and never reopens saved traces.

Only a profitable service-safe cost cut can be combined with target4600/5000;
opening7000/7500 must also include a wider-pair policy. Existing saved Early
Epsilon controls are reused.


## Settings-only capacity priority (02:49 UTC)

Before any chain or further implementation screen, test the orchestrator's
capacity-study levers separately at target4200,4600,5000, retaining premium1440:

- Young retry: `pair_once=0`, `pair_max_idle_minutes=120`,
  `delta_pair_max_wait_minutes=180`, `delta_pair_min_slack_minutes=480`.
- Rescue offer: `pair_fee_bps=7800`, `pair_rescue_fee_bps=8500`,
  `pair_rescue_flat_minutes=15`, `pair_split_minutes=45`.

All keys exist. Code verification qualifies the Gemini narrative: unbounded
pair_once0 does not record or exclude a previously failed combination, unlike
this branch's opt-in bounded retry policy. The15-minute hold releases an
existing ramp step; it does not manufacture a raise before the45-minute split.
The report's feasibility counts and lateness correlations do not establish a
causal margin gain. This screen uses exactly the requested existing settings
and the new read-only pooling diagnostics, with two workers and both launch
cutoffs retained.

Wider reach was drained after both hard seeds so this priority could start.
The three-car code is implemented and tested but has created no world.


## Convergence (02:57 UTC)

Only the young-retry and rescue-offer arms at target4200/4600 remain active.
The orchestrator canceled target5000 and all three-car/new-code ideas before
any chain world began. The untested chain implementation and its plan/tests
were removed from the branch; the read-only pooling instrumentation remains.
Resume uses epsilon-capacity-converge.json and reuses completed rows in the
same output directory after the03:00–03:45 pause.

After four seeds per arm, publish the complete setting diff and paired table
to the orchestrator's scratchpad/pairing-best.json. Extend only a qualifying
positive-margin arm with every week at least91.5% on time; if none qualifies,
report Early Epsilon as the fallback rather than promote an unsafe screen.


At03:00 all four converged arms had completed s07 and every arm failed the
service floor (young retry4200:90.805%, rescue4200:90.751%, young retry4600:
89.182%, rescue4600:89.153%). No5000 or chain world started. All own worlds
were drained, and the12 remaining screen worlds are gated until03:45. An
interim pairing-best.json explicitly marks the screen incomplete, selects no
experimental candidate, and retains Early Epsilon as the valid fallback.


At03:17 the orchestrator ended the ranking pause early and returned this lane
to three slots. Replaced the idle two-worker controller with three workers,
removed the pause gate, and canceled the obsolete03:45 resume timer. Existing
four scores are reused; only the12 remaining converged screen worlds run.
The05:30 hard launch cutoff remains armed.


## Revised screen-only protocol (03:18 UTC)

The orchestrator replaced the full-cohort gate with four-seed screens, early
termination of weak arms, and at most one roughly8-seed extension started by
04:45. The signal sought is at least+€500/week versus Early Epsilon, around
380+orders/week, and every observed week at least91.5% on time. Do not run
19/27-seed extensions.

All four isolated retry/rescue arms had already failed service on s07. Their
three resumed f2 worlds were canceled and ended, rather than consuming more
time on ineligible arms. No partial canceled world is a performance score.
The next and only active screen combines the supplied young-retry and rescue
offer settings at target4200/4600, on the same four predeclared seeds. It uses
three workers. No new policy code, chains, wider reach, or target5000 is active.


The combined retry/rescue screen also failed service:89.655% and89.544% on
the two hard seeds at target4200, and88.127% plus one undelivered order on
s07 at target4600. Three in-flight disqualified worlds were ended. One final
settings-only probe narrows waiting age180→120 and pickup slack480→720,
retaining pair_once0, idle120 and the original pair fees, at target4200/4600.
It uses the same four seeds and retains the early service stop.


## Deep queue overrides the screen-only protocol (03:29 UTC)

On explicit orchestrator instruction, replace all re-pairing screens with one
long three-worker sweep. Run `epsilon-finish-band180` and
`epsilon-volume-stack-tilt-win4600-finish-band180` on all19 paired seeds plus
the8 predeclared margin-confirmation seeds. The combo retains Early Epsilon
and adds short_km300,short_bps9300,long_markup_bps10500,target4600,band180.
No new policy code is involved. Reuse the two already-completed exact-setting
finish-band180 rows;52 new worlds remain. All3 superseded tighter-guard worlds
were ended before replacing their controller.

The orchestrator was informed that finish-band180's+€406.17/week on the two
hard seeds includes a90.811% on-time week, so it cannot pass the service gate.
The latest instruction nevertheless explicitly requests this diagnostic full
extension; it supersedes the prior prohibition on19/27-seed extensions and
early stopping weak arms. Do not treat it as a promoted model. All workers
remain filled from the deep queue; at05:30 the gate stops new worlds, active
worlds finish, and then the controller is stopped. Drain by05:50 and publish
the final paired report by05:45.


## Full-stack and safe-quote handoff (03:36–03:56 UTC)

The orchestrator clarified that volume-stack means the entire saved stack, not
just its four tilt fields. The earlier four-setting combo is a separate model;
it was dropped. Reused the exact guarded intake implementation from7ad565e,
with its11 tests and compatible optional facts argument. Delta defaults stay
off. The full-stack4400 queue reused three main-loop scores and filled3 slots
on remaining seeds, then sequentially failed at+€223.26/week over7 pairs,5/7
positive,worst91.022%. Its3 active worlds were ended on the stop signal.

All stored4600 full-stack evidence was also checked:5 pairs,+€774.75/week,4/5
positive,but90.144% worst,below the90.5% stop rule. Admission360 was explicitly
rejected by the orchestrator at−€17.45/week over8 stored pairs. Neither fallback
was run.

On explicit user instruction,cherry-picked P5'sa2310e2 safe-quote implementation,
resolved only its intake import and plan-location conflicts,and retained its
original human commit identity. Full suite:492 tests passing.

Current queue:safe9800-backlog10 on Early Epsilon,with no volume-stack overrides.
Settings delta_safe_quote_bps9800 and delta_safe_quote_max_backlog10. Reused P5's
three stored scores;reserved its unfinished fourth screen seed to avoid replay;
queued the15 remaining paired seeds plus15 fresh seeds with retained Early
Epsilon controls. All three workers stay fed.

Latest continuation gate:mean paired gain≥€300/week,at least half positive,and
worst≥91.0%,judged from3 weeks onward against all stored scores,including P5.
A watcher recomputes after each append and immediately closes the launch gate
on failure. Final adoption still requires worst≥91.5%;the stored safe-quote
arm's91.379% worst already misses that final bar despite passing continuation.
Stop launches05:30,drain by05:50,report by05:45.


## Centralized final handoff (04:01 UTC)

The orchestrator stopped this lane's safe9800 sweep and deleted its open worlds.
No new worlds are authorized. Final safe tally versus Early Epsilon:6 paired
weeks,+€302.58/week,3/6 positive,worst91.379%. It receives no more local runs.
The remaining local watcher and05:30 timer were stopped; all own world markers
are empty. Final suite:492 tests. See epsilon-p1-final.md for the final handoff
and epsilon-p1-results.md for complete paired tables.
