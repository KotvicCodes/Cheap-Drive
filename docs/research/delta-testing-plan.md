# Delta research and staged testing

**Verdict:** investigate pairability and live backlog as signals for profitable
additional intake. Gamma's paired improvement is established; the proposed
35–42% targets, €650–700 immediate rescue gain and top-ten projections are not.
Keep supported Gamma fixed. This document defines the staged research gates;
[investigation results](delta-results.md) track execution and experimental
Delta code. No model has been promoted. A1 and A2 completed; eight-seed
no-segments and premium-only gains remain
below the final margin threshold. B intake drained after the service guard;
independent trust/review screening has drained. The reviewed B1 learner
pilot passed, then the larger learner screen stopped on its service guard.
B2 lanes and independent note/rescue pilots are now running. Two additional diagnostic worlds on exposed
`gamma-v01` checked neutral-factory parity and rescue.
These add two completed worlds to the program budget below, without changing
its selection or confirmation gates.

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

- `delta-r1-s01..s08`: exploratory backlog, quote/fee hypotheses, repair and cap screening.
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
| B1: fastest-option learner | Gamma; exclude skipped-fastest quotes from learning; exclusion + 0.92× skipped-fastest prices; separate skipped-fastest tracker. s01–s08, independent of A/B winners. | 32 |
| B2: lane asymmetry | Gamma; inbound 0.91×; outbound 1.04×; outbound 1.06×; inbound + outbound 1.04×; inbound + outbound 1.06×. s01–s08; learner unchanged. | 48 |
| B3: reference-fee anchor | Gamma; 0.4·reference + 0.6·(0.96·minimum list price) on routes ≥45 km. s01–s08, only after booking-latency audit and fee-path review. | 16 |
| B4: two-option menu spread | Gamma; same-day 1.04× and next-day 0.98× only when both are actually quoted. s01–s08. | 16 |
| B5: smaller independent controls | Gamma; `trust_bps_per_order=50`; `fee_shape="review"`. s01–s08, separate arms. | 24 |
| Optional B6: learner × lane interaction | Gamma; one preselected passing learner arm; one preselected passing lane arm; both. s01–s08. Only after separate B1/B2 success; freeze choice before combining. | 32 |
| B7: private-pickup admission | Gamma; private slack 240 minutes, initial-roster `near30≥5`, opening floor 10000 bps for newly admitted work only. Single-leg original no-time declines, all other guards retained; offline route/window audit first. s01–s08. | 16 |
| C: repairs separately | Gamma; note date/closing fixes only; rescue-window fallback only; pair/brake bookkeeping only. All remain 30%, cap 3. Run s01–s08 after separate opt-in Delta factories and regressions exist. No patch to supported Gamma. | 32 |
| D: capacity boundary | Gamma; selected repaired anchor; that same anchor with `long_open_cap=4` only, on s01–s08. Release only after C; retain long options, distance and slack guards. Cap 5 is a later experiment requiring its own predeclared budget. | 24 |
| E: development | Beta, Gamma and one selected Delta combination, frozen before d01–d08. May combine only individually justified changes. If the combination fails, return to exploratory work and reserve a replacement fresh development block. | 24 |
| F: confirmation | Same three factories/settings, fresh c01–c08, no tuning or arm selection from these results. Failed confirmation leaves Gamma supported. | 24 |
| Optional stress | Gamma and one finalist on the three exposed difficult weeks; diagnostic only. | 6 |

Maximum listed program: **350 completed worlds**, including optional stress and
the conditional interaction screen; **352 including the two completed parity/rescue
diagnostics**. The additions reserve 152 independent-screen worlds plus 32
conditional interaction worlds; stop early when gates reject an arm. A1 can resolve the first decision in 20
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

## Quote and fee hypotheses after A/B

B1–B5 retain this research priority after A/B; independent existing-settings
B5 was released early under the user's later all-slots instruction. Conditional
B6 follows B5, then B7 before C. They do not interrupt A1 or change any A/B arm, source,
seed or gate. Every stage uses frozen Gamma on `delta-r1-s01..s08`, with a
same-stage control and unchanged global intake target, segments, cap and repairs;
B7 alone isolates the specified private-pickup admission exception. Screen
learner and lane effects separately before any combination. Their full specs and
release prerequisites are in [the non-executable stage manifest](plans/delta/quote-fee-stages.json).
Do not feed that manifest to `sweep.py`: B3/B4/B6/B7 still need Delta-only code
and validated executable plans. B2 now has [isolated lane code and a frozen plan](plans/delta/b2-lanes.json),
with remaining seeds gated on its neutral/parity pilot review. B1 now has a [reviewed executable plan](plans/delta/b1-fastest-learning.json),
with a completed neutral/parity pilot and default-off implementation. Existing B5 settings need no strategy
implementation and now run independently during B.

[The saved-week audit](delta-quote-fee-leads.md) supports the mechanisms, not a
measured gain. Completed-trace selection changes the supplied counts: full menus
win 32.4% of 669.9 quotes/week versus 21.3% of 204.1 skipped-fastest quotes/week.
Three lexicographically last traces were incomplete retries. Segment economics
also omit €893.50/week of gig-only driver fees and include subsequently cancelled
wins. Reconcile costs and cancellation denominators before quoting net segment
margins or releasing the fee experiment. All 16 completed scores reconcile to
full ledgers; their trace/reveal world identities match.

- **B1:** classify using original `request.options[0]` and the actually submitted
  competitive price keys, after all eligibility guards. Exclusion changes only
  feedback, not outcome/trust/ownership handling: clean pending and tracker state
  on win, loss, cancellation, failed quote and terminal paths exactly as required
  by the original lifecycle. Do not learn from declines or rejected submissions.
  The 0.92 factor affects only skipped-fastest quotes. The split arm uses global
  and skipped-fastest trackers at Gamma's initial markup, bounds, target and
  per-outcome step; no simultaneous learning-rate adjustment. Log cohort-specific
  quote/outcome/update counts and markup paths to expose slower adaptation.
- **B2:** inbound means origin outside exactly `{vantaa, helsinki, espoo,
  hyvinkaa, porvoo}`, destination inside that set, route ≥60 km. Outbound means
  destination in `{savonlinna, kajaani, kotka, ylivieska, kokkola, seinajoki,
  mikkeli, rovaniemi, vaasa, lappeenranta, kouvola, pori}`, route ≥100 km;
  no additional origin restriction. Freeze both definitions. The supplied
  retrospective script also excluded tampere/lempaala/raisio as inbound origins;
  report that cohort separately rather than changing the arm silently. Factors
  apply to eligible quoted options, compose with unchanged Gamma factors before
  one final cent ceiling, and never relax dispatch guards. Explicitly clamp the
  new lane offset to ≥0 below 60 km (equivalently
  a new lane multiplier ≥1); this does not neutralize Gamma's existing short
  factor or change the independent A attribution screen. Measure hub arrivals,
  available pair partners, booked pairs
  and total ledger, not just accepted-order margins.
- **B3:** first audit opening-to-booking latency for reference/minimum-list
  ratios >1.04 against lower groups, stratified by distance, place, readiness,
  pair/single status and escalated fee. Report booked-within-5/15/60-minute shares,
  unbooked/cancelled censoring and sample sizes. Quick bookings support, but do
  not prove, overpayment. Account for all gig-only/shared fees and avoid assigning
  a paired gig's full fee twice. A noisy reference may still encode real driver
  difficulty. Before release, freeze anchor application to singles, pairs,
  urgent/rescue and multi-car prorating; changing `fees_for()` alone misses the
  direct paired-fee path. Retain schedule clocks, openings, caps and rounding;
  prove neutral parity, finite positive monotone schedules and allocation totals.
- **B4:** determine the dual menu after gating, then apply 1.04/0.98 before the
  final price ceiling. Same-day-only and next-day-only submissions remain Gamma.
  Do not use unconditional `same_day_bps`/`next_day_bps` settings for this arm.
  Record actual option menus, choice shares, fees, refunds and service; historical
  same-day versus next-day outcomes do not establish causal customer switching.
- **B5:** halve trust pricing from 100 to 50 bps per order, not to zero. The old
  t2 “notrust” gain was for zero on a different stack, not evidence for 50 here.
  Test review fee shape independently with all opening fees unchanged; audit both
  pair and single schedules. No combined trust/review arm is preauthorized by
  this plan.
- **B6:** choose at most one learner and one lane arm that separately meet the
  existing pre-E gates below; freeze the selection and four arms before running.
  Report interaction as `combined − learner − lane + Gamma` per seed, alongside
  direct combined-versus-Gamma net margin and all safety metrics. Reusing s01–s08
  makes this exploratory; development and untouched confirmation remain required.
- **B7:** a separate private-pickup admission screen, not a global slack cut.
  Replay original no-time declines first. Require a single-leg pickup with
  `hours: null`, known initial-roster `near30≥5`, and at least 240 minutes of
  note-aware slack from decision/readiness. Freeze the proposed threshold before
  live release after inspecting offline coverage; if it changes, version the
  spec before any outcomes. `near30` counts homes within 30 km, not available,
  appropriately licensed drivers. Require an observable feasible route within
  the original three-hour private slot and delivery promise. Missing supply or
  infeasible readiness/licence/charging/route rejects relaxation. Preserve every
  other long, premium, option, trust and capacity guard; already eligible work
  keeps Gamma behavior. Newly admitted private work gets an opening floor of
  10000 bps, respecting any higher segment floor. Preserve fee clocks and caps,
  and never extend the private window or add the rescue repair to this arm.
  Report newly eligible/quoted/won counts, route/list-price mix, booking latency,
  failed visits, refunds, undelivered share and full incremental ledger. Stop for
  the existing service gates; additionally require paired mean on time no lower
  than Gamma and newly admitted private orders ≥93% on time. Report the new
  cohort denominator and uncertainty separately. This is timing-risk volume,
  not free margin. The other declined groups
  (ordinary same-day-only, >700 km, trade-ins, unsupported long options) stay out
  of scope; long capacity remains solely stage D.

Apply the existing safety stops and pre-E eligibility gates to these stages;
retain ≥€500/week, ≥6/8 positive, service and undelivered gates without relaxing
them after outcomes. Each stage ends with review before the next release. Stop
an unsafe arm's future scheduling and preserve/drain owned work. No historical
confirmation seed becomes a Delta holdout, and none of these observations is a
measured improvement or qualification.

## Gemini note-extraction research

[The separate Gemini prototype](gemini-notes.md) defines an offline prompt,
strict response contract, cached-response validator and three-arm semantic
benchmark (Gamma parser, deterministic Delta fixes, selective assisted facts).
It is not imported by dispatch and adds no provider dependency or live call.
Offline fixtures and independent adjudication come first, then measured shadow
latency/cost with unchanged actions, then a separately frozen practice plan if
justified. Existing main-plan promotion gates remain authoritative. No paid
inference, measured parsing gain, latency claim or extra simulator budget is
included here. Keep this research supplied independently of practice slots.

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
- Apply the scheduling guard to candidate strategies. Fixed baseline references
  must complete the declared seed block for paired measurement even when the
  reference itself misses 93%; report those failures without qualifying it.
  This corrects the initial B controller applying the guard to Gamma, which
  left four comparisons missing. No unsafe candidate is restarted and no
  candidate selection, service or economic threshold changes. Complete only
  never-created reference jobs with unchanged frozen code/settings.
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

The three original executable JSON plans under `plans/delta/` use the existing
`scripts/sweep.py`
`factory/level/seeds/base/variants/fast` schema. A1/A2 are complete. B and the
existing-settings B5 screens have been released; other quote/fee arms remain
staged. Neutral/rescue diagnostics use separate copied plans.
The integration checkout retains the private staged queue and exact commands
under ignored `runs/delta-research/queue.json` and `commands.txt`. These local
artifacts are not part of Git; use the tracked plans and this document when
preparing another checkout.
C's bookkeeping arm and D–F still need implementation or selection prerequisites.
The note/rescue switches are experimental and are not qualified settings.

The initial plan used one or two workers, then five with a spare. The user
subsequently authorized all eight practice slots and overlapping independent
concrete experiments. B5 was therefore released during B despite its original
priority position after B4; this scheduling override leaves every arm, setting,
seed and gate unchanged. Reuse B Gamma controls only with exact provenance.
The official API caps unfinished **practice** worlds at eight, including ranking
runs; finals do not consume those slots. The supplemental runner checks that
practice/ranking count before creation and leaves no deliberate spare. Existing
controllers drain naturally; owned worlds are never restarted for extra speed.
Never touch preexisting practice worlds, leaderboard/ranking worlds or
final worlds. Only new ordinary practice worlds belong to this queue. The
sweep creates with `board=False` and cleans up only its own failed attempts,
but it does **not** discover free slots, lock outputs, validate code hashes on
resume, enforce safety gates, or stop the pool when a week is unranked. It also
retries failures up to four times. Therefore release small stages manually,
use immutable source copies and fresh output directories, retain failure
records, and do not run a retry storm against a full slot pool. For bounded
risk launch a one-seed copied plan first, inspect it, then release the rest.
The 350 planned-world budget (352 with completed diagnostics) counts completed
weeks; reserve at most one manually reviewed
infrastructure retry per job. Existing automatic retry behavior must be
controlled by a supervising owner or a separate runner improvement before
claiming this attempt limit is enforced.

Saved Gamma screening/confirmation median completed-week times were 265/327
seconds; these are not speed experiments or an SLA. Budget 5–15 worker-minutes
per world (29.2–87.5 worker-hours for the maximum 350-world planned program), plus
outages and review. With two independent free workers that is ideally
14.6–43.75 elapsed hours; actual shared rate limits and slots can be slower.
Coordinate rather than consuming practice slots needed for speed validation.

The final-clock runner is a separate operational priority. `dispatch.py` still
has no `--final` integration or validated reconnect path at this baseline.
Practice qualification cannot validate streaming, recovery, action idempotency,
clock handling or live rate limits. Nothing here registers or joins a final.

Offline validation: all three sweep plans parse and pass the actual settings
classes' validators, excluded seed checks and 35 baseline hash checks. Integration
also validated all 13 settings arms through the installed SDK-backed factory's
settings splitter. Saved score/ledger/segment reconciliations passed. Those
initial checks did not run simulator weeks. Live A1 and pilot execution
is recorded separately in the investigation results. The new B1–B7 manifest is
a staged specification, not a validated executable sweep. B5 uses validated existing settings; B1 passed its implementation/pilot review.
B2 code/settings pass offline checks and its live pilot is running.
New B3/B4/B6/B7 hooks remain gated.
The separate Gemini offline prototype is not a live arm. No final-clock
validation has run; no Delta is qualified.
