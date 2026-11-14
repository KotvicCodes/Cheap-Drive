# Delta research and staged testing

**Verdict:** investigate pairability and live backlog as signals for profitable
additional intake. Gamma's paired improvement is established; the proposed
35–42% targets, €650–700 immediate rescue gain and top-ten projections are not.
Keep supported Gamma fixed. This document stages research only: no strategy
implementation, model promotion, live runs or world changes.

## Evidence and objections

[Gamma's frozen confirmation](gamma-recovery-results.md#confirmation-verdict)
is the strongest evidence: 8/8 ranked, 8/8 positive against paired Beta,
+€2,030.845/week, 98.062% mean and 96.947% worst on time. Its 1/148 late long
orders includes undelivered orders. Screening was used for selection and must
remain separate. Three historical stress weeks are exposed diagnostics; their
94.273% worst on time is also relevant to risk.

An independent offline audit selected the exact completed traces named by each
`runs.jsonl` record, reconciled score and summed ledger, and excluded cancelled
orders from segment wins. Only sanitized aggregates are retained in
[the evidence summary](plans/delta/saved-evidence-summary.json).

| Claim | Assessment and consequence |
| --- | --- |
| Global target cannibalizes standard orders | Plausible mechanism with observed displacement, not an isolated causal estimate. Across 16 paired weeks, short wins rose from 18.94 to 31.69/week, standard 45–500 km wins fell from 224.81 to 208.19, and long wins added 18.25; net +14.375. Gamma and Beta differ in notes, eligible pool, fees, pairing and segment prices. Those comparisons cannot assign the −16.625 standard wins to the tracker alone. |
| A 30% target caps total intake | Incorrect as a hard-cap description. `GammaCoreDesk.learn()` raises a shared markup after competitive wins and lowers it after losses; declines do not enter that feedback. Bounds, startup, trust, mix, cancellations and market responses prevent an exact quota. The +42.25 quoted requests/week and +14.375 wins are consistent with feedback coupling, but `0.30 × extra quotes` is not a causal proof. |
| No-window abandonment is real | Supported: 28 distinct no-window orders across 16 weeks, all subsequently penalized; 29 undelivered/penalized orders total. Confirmation has 11 no-window orders and 12 undelivered orders. Events occur at 18:00/19:00. `post()` returns without a replacement or retry timer. A later external event could still cause another attempt; “permanent” is not an explicit state transition. |
| Fixing rescue immediately adds €650–700/week and on-time headroom | Not measured. All Gamma undelivered penalties average €452.67/week; those linked to no-window average €444.44, not the entire penalty row. Avoiding them still requires a feasible booking and costs driver fees, refunds and possibly failed visits. Next-day rescue normally remains late; reducing abandonment need not improve nominal on-time share. |
| 263 otherwise eligible long requests rejected | Corrected to **243 capacity refusals** in completed traces: 108 screening + 135 confirmation (15.19/week). Capacity is checked before long-option kinds and 24-hour slack, so these are not all otherwise eligible. Re-evaluate remaining guards offline before estimating addressable volume. Accepted long orders are selected by the cap; their low late rate does not establish service for marginal orders. |
| 46 stale pair-split collisions | Completed traces contain **47 errors**, 22 screening + 25 confirmation, all withdraw-phase errors. Both pair formation from waiting singles and pair splitting withdraw gigs; these logs alone do not identify every caller or prove lost margin. The current method is `_split_pair`, not `_split_stale_pairs`. Reconcile event batches and ownership before fixing. |
| High on-time share proves spare capacity | It justifies a small experiment, not an intake entitlement. Service is conditional on accepted work; added orders change local availability, windows, driver learning and future bookings. A 6.95-point confirmation gap above the 90% floor is not a measured capacity reserve. Aggregate profit/order is not marginal profit/order. |
| Juhus uses roster scaling, long routes, notes and pairs | Unverified competitor-policy guesses. Public wins/margin/service identify outcomes, not quotes, route mix, driver fees or mechanisms. Even on common ranking worlds, aggregate profit/order does not identify strategy. More wins at similar unit profit is a useful objective, not a replication recipe. |
| Gamma now beats Juhus's unit economics / projected ranks | Gamma practice seeds and Juhus ranking seeds differ. The €47.14 confirmation profit/order versus €46.74 ranking figure is not paired evidence. Multiplying old ranking totals by practice gains is an illustration with no prediction interval, not an achieved rank or safe-volume forecast. |

The earlier 38% arm, with corrected brake but without the final note/pair
combination, lost €329.89/week versus Beta on four recovery seeds and reached
90.278% worst on time. Roster-only screening also produced an unranked week
at 88.768%. These results neither prove notes/pairs would fail at higher intake
nor establish that their absence was the *only* cause. Town caps sacrificed
margin. Do not reactivate roster scaling, town caps or brakes by default.

## Reproducible baseline and seed separation

[The baseline manifest](plans/delta/gamma-baseline.json) pins merged Gamma at
`0eb4e3e`, its full commit ID, source SHA-256 hashes, factory, explicit model
settings, expanded defaults, level 8, ordinary practice, fast mode and SDK
artifact hash. It fixes notes + pairs + segments, 30% target, long cap 3,
500–700 km guarded routes, 24-hour long slack, fresh/rescue pair fees 7200/7800,
60-minute rescue flat period and second-pickup idle limit. Brake, supply scaling,
town caps and capacity valve are off. Preserve `models/gamma.json` and historical
Beta. Snapshot candidate code separately; never silently update this control.

Use `gamma-v01..v08` only for initial exposed screening. `gamma-v09..v16`
were Gamma's confirmation, are now exposed, and are excluded from Delta tuning
and qualification. Historical `gamma-h07`, `gamma-t02`, `gamma-t04` are diagnostic.
The reserved Delta blocks are:

- `delta-r1-s01..s08`: exploratory backlog/repair/cap screening.
- `delta-r1-d01..d08`: fresh development block after choosing a combination.
- `delta-r1-c01..c08`: untouched confirmation; no execution or outcome inspection
  until code, settings, candidate count and gates are frozen.

Reservation is local intent, not proof another controller has never used these
names. Check local run indexes and coordinate with the owner before release;
if a reserved name is exposed, replace the entire block and record that before
seeing candidate outcomes. Holdout seeds must never be used by speed experiments.

## Ordered arms and budgets

Every candidate compares directly with the frozen Gamma control on identical
seeds. No multi-setting jump to 35–38%, cap 5–6 or >700 km routes.

| Stage | Exact arms and purpose | Completed-world budget |
| --- | --- | ---: |
| A1/A2: segment attribution | Gamma; no segments (`short_bps=10000`, both segment opening floors 0, premium slack 0); short only (premium floor/slack 0); premium only (short discount neutral, short floor 0); higher pair opening (`pair_fee_bps=7500`, `pair_rescue_fee_bps=8000`). All other Gamma settings fixed. First four screening seeds, review, then remaining four for surviving arms. | 20 + at most 12 |
| B: modest intake | Gamma; low-backlog 31%; low-backlog 32%. Existing `capacity_valve=1`, `open_low=3`, `open_high=6`; high targets 3100/3200, mid/low targets both 3000. Above three orders without drivers, target returns to 30%. Keep Gamma segments and long cap 3 to isolate intake. Use s01–s08. | 24 |
| C: repairs separately | Gamma; note date/closing fixes only; rescue-window fallback only; pair/brake bookkeeping only. All remain 30%, cap 3. Run s01–s08 after separate opt-in Delta factories and regressions exist. No patch to supported Gamma. | 32 |
| D: capacity boundary | Gamma; selected repaired anchor; that same anchor with `long_open_cap=4` only, on s01–s08. Release only after C; retain long options, distance and slack guards. Cap 5 is a later experiment requiring its own predeclared budget. | 24 |
| E: development | Beta, Gamma and one selected Delta combination, frozen before d01–d08. May combine only individually justified changes. If the combination fails, return to exploratory work and reserve a replacement fresh development block. | 24 |
| F: confirmation | Same three factories/settings, fresh c01–c08, no tuning or arm selection from these results. Failed confirmation leaves Gamma supported. | 24 |
| Optional stress | Gamma and one finalist on the three exposed difficult weeks; diagnostic only. | 6 |

Maximum listed program: **166 completed worlds**, including optional stress;
stop early when gates reject an arm. A1 can resolve the first decision in 20
worlds. Do not execute all rows as one unattended sweep. This is a staged
research budget, not a request to occupy all slots before the final.

B is a limited settings-only probe: `orders_without_driver()` includes missing
posts but excludes competitive pending quotes and does not measure local driver
availability. The target is evaluated again when outcomes arrive. Thus the
valve is neither a hard admission cap nor a reservation system.

A stronger pairability hypothesis needs future Delta-only code and additional
arms: low-backlog 31% with no pair gate versus identical intake enabled only
when a hypothetical order has a physically feasible waiting partner. A valid
plan must include both pickup/delivery calendars, note readiness, licences,
charging, second-pickup idle, deadlines and the existing pair fee clock; it must
make no withdraw/post mutation while scoring a quote. Reserve partner capacity
across pending quotes and invalidate reservations on all outcome/change events.
Use only observable state. Require positive incremental margin after pairing
costs; “nearby partner” alone is insufficient. Freeze thresholds before testing.
This code and its run budget are **not** part of the executable staged plans.

## Repair prerequisites

Synthetic boundary inspection reproduces the rescue defect: on Tuesday at
19:01 with a 20:00 absolute pickup-window end and an 18:00 recurring close,
`visit_window(..., rescue=True)` returns `None`; after the absolute end passes,
it can return Wednesday's open interval. First search for a physically valid
on-time route; only if none exists should late rescue relax expired absolute
promises to the horizon. Preserve recurring hours, weekdays, readiness, plates,
charging and licence requirements. Never blindly remove all window limits.
Test pickup and delivery, exact inclusive close, expired note promises,
weekends, horizon exhaustion and failure to find any safe rescue. Replay affected
screening cases privately, then measure actual rescue bookings and net ledger.

For notes, cover the already documented day/date typos and negative closing
clause with bounded parsing and arrival-based dates; prevent access codes or
unrelated prose becoming times. For bookkeeping, replay booking/expiry races,
partial withdraw success, failed pair posts, cancellation and event batching.
Assert each undelivered leg has one valid owner or an explicit retry state.
Pair handlers intercept some events before `GammaCoreDesk.handle()`; ensure
brake observations see warnings and relevant terminal outcomes exactly once.
Audit unposted/undelivered orders that have no late-refund event. Existing brake
counts are not automatically a complete future-lateness estimate. Keep brake
off until tested independently; no profitable effect is assumed from a repair.

## Metrics and decision gates

For each seed retain score, exact margin/ledger reconciliation, source/settings
hashes, attempts and owned world IDs privately. Report paired net margin versus
Gamma (and Beta in E/F), all seed differences, mean, median and worst difference,
positive-week count, ranked count and worst/mean on time. An eight-seed paired
bootstrap interval can describe uncertainty but cannot replace safety gates or
be treated as a final-market guarantee.

Also report noncancelled won/delivered/late/undelivered counts; unique failed
orders and failed-visit events separately; long late/won including undelivered;
quotes, wins and profit by short/standard/long, premium, dealer, town and option;
fee/revenue, refunds, waiting and penalties; booking latency, overdue unbooked
backlog, maximum backlog, and time at each target. Reconcile segment totals to
score. Use stable boundaries `<45`, `45–500`, `>500` km and overlapping premium
as its own dimension. Track eligible pair opportunities, attempts, booked pairs,
withdraw errors, split reasons, orphan legs, no-window orders and actual rescue
outcomes. Audit long-cap refusals through the remaining guards before labeling
additional addressable orders.

Predeclare these gates; do not loosen them after observing results:

- Stop scheduling an arm at the next stage boundary for any unranked completed
  week, <93% on time, ownership/invariant failure, duplicate mutation, or new
  unexplained orphaned order. Preserve evidence and drain only its owned work.
- A1 advancement requires all four ranked, at least three positive paired
  weeks, positive mean margin, and no worsened undelivered count. Carry at most
  two settings arms forward if several pass; record selection before A2.
  Repair arms may advance for demonstrated correctness even without a profit
  gain, but cannot justify extra intake without separate economic evidence.
- Before E and at F require 8/8 ranked, worst on time ≥93%, pooled long lateness
  ≤5%, mean gain ≥€500/week versus Gamma, and ≥6/8 positive paired weeks. Require
  mean on time no more than 0.5 percentage points below paired Gamma and pooled
  undelivered share no higher than Gamma. A rescue-only arm may reduce
  abandonment without improving on-time share, but still must meet these gates
  as part of any final combined candidate. Reject profitable volume that merely
  moves cost into tail risk or uncompleted work.
- F gets one frozen candidate. Any strategy revision after an outcome invalidates
  F as confirmation and needs new seeds. Infrastructure failures may retry only
  identical code/settings/seeds; retain every attempt and failure reason.

## Local queue and execution limits

The three JSON plans under `plans/delta/` use the existing `scripts/sweep.py`
`factory/level/seeds/base/variants/fast` schema. No run commands have been executed.
The private staged queue and exact commands are under ignored
`runs/delta-research/queue.json` and `commands.txt` in the prepared checkout;
copy them privately when integrating, since cherry-pick will not carry them.
C–F have no runnable candidate plans until their prerequisites are met.

Default to one worker, at most two after coordination with speed work and the
owner. Never touch preexisting practice worlds, leaderboard/ranking worlds or
final worlds. Only new ordinary practice worlds belong to this queue. The
sweep creates with `board=False` and cleans up only its own failed attempts,
but it does **not** discover free slots, lock outputs, validate code hashes on
resume, enforce safety gates, or stop the pool when a week is unranked. It also
retries failures up to four times. Therefore release small stages manually,
use immutable source copies and fresh output directories, retain failure
records, and do not run a retry storm against a full slot pool. For bounded
risk launch a one-seed copied plan first, inspect it, then release the rest.
The 166 budget counts completed weeks; reserve at most one manually reviewed
infrastructure retry per job. Existing automatic retry behavior must be
controlled by a supervising owner or a separate runner improvement before
claiming this attempt limit is enforced.

Saved Gamma screening/confirmation median completed-week times were 265/327
seconds; these are not speed experiments or an SLA. Budget 5–15 worker-minutes
per world (13.8–41.5 worker-hours for the maximum 166-world program), plus
outages and review. With two independent free workers that is ideally
6.9–20.75 elapsed hours; actual shared rate limits and slots can be slower.
Coordinate rather than consuming practice slots needed for speed validation.

The final-clock runner is a separate operational priority. `dispatch.py` still
has no `--final` integration or validated reconnect path at this baseline.
Practice qualification cannot validate streaming, recovery, action idempotency,
clock handling or live rate limits. Nothing here registers or joins a final.

Offline validation: all three sweep plans parse and pass the actual settings
classes' validators (extracted without importing the SDK), excluded seed checks
and baseline hash checks. Saved score/ledger/segment reconciliations passed.
No simulator, SDK/network integration, final-clock validation or new strategy
performance test was run; these artifacts are proposals, not qualified Delta.
