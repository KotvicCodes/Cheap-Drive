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
No ranking or final worlds are authorized. Stop launching at 03:00 UTC,
resume at 03:45, and drain all worlds by 06:15. Latest report deadline 04:15.


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
by 06:15, and retain the 03:00–03:45 launch pause. If confirmation is still
running at the earlier 04:15 report checkpoint, report its partial state.


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
are no practice starts after05:30, all worlds ended by05:50, final report
by05:45. The launch gate has an independent05:30 timer. Use only fixed known
paths and shallow own-worktree reads; no recursive scans across worktrees.
