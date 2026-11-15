# Epsilon tuning log

Epsilon starts as an exact copy of Delta's settings ([models/epsilon.json](../../models/epsilon.json))
and is tuned on paired practice weeks against Delta. Goal: enough margin per week to reach the
top 7 on the official board while every week stays above 90% on time.

| Step | Change | Paired weeks | Margin vs Delta / week | Positive weeks | Worst on time | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 0 | Delta settings, unchanged | 19 | €0 (reference) | — | 91.12% | Current baseline; below the promotion floor |

## Protocol and schedule

Work started 14 November 2026 at 23:00 UTC. All tuning uses level-8 ordinary
practice worlds through `scripts/sweep.py`, with the orchestrator controlling shared-slot capacity. Since the live final
ended, the current allocation is twelve practice workers with no reserve. Checkpoint 1: 00:45 UTC; freeze: 03:30 UTC; practice stops by
05:15 UTC. Never launch board or live final runs. Adopt only after at least
eight paired weeks, all 19 existing f1/f2 weeks and independent fresh
confirmation, with no observed week below 91.5% on time. Prioritise service
headroom before increasing intake.

The reference is **current Delta**, target 4200 with wide windows, private
rescue and extended pairing, not Early Delta at target 3000. Nineteen exact
per-seed references were recovered from the prior queue's `volume-tap`
`runs.jsonl` in sibling worktree `t3-4d9ed6f5-d50ae2340a835fbb` and retained
under ignored `runs/epsilon/delta-baseline.jsonl`. Earlier experiments use the
same code path and settings; no repeated baseline worlds are needed.

## Recovered completed experiments

These rows were recomputed from the prior queue's per-seed scores at 23:02 UTC.
They complete the manager's formerly unfinished queue. The old screen used
s07 plus s01/s05/s10; the new screens include both s07 and f2-s04.

| Change against current Delta | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Projected lateness 600/750 bps, target 3600/3000 | 19 | +€13.95 | 1/19 | 90.94% | Rejected: service floor |
| Projected lateness 500/750 bps, target 3600/3000 | 4 | −€131.44 | 0/4 | 90.33% | Rejected: service and margin |
| Return unbooked pairs to singles after 30 min | 4 | −€250.36 | 1/4 | 91.14% | Rejected: service and margin |
| Return unbooked pairs to singles after 45 min | 11 | −€202.17 | 3/11 | 91.14% | Rejected: service and margin |
| Backlog >25 lowers win target to 3000 | 19 | −€189.81 | 5/19 | 91.25% | Rejected: service and margin |

## Active hypotheses

All new controls default off. Epsilon's selected settings remain identical to
Delta until a complete confirmation passes.

| Change against current Delta | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Earlier projected brake: 350/600 bps | 4 | +€35.64 | 2/4 | 91.72% | Survived screen; remaining 15 paired weeks in flight |
| Earlier projected brake: 450/650 bps | 4 | −€1.50 | 1/4 | 90.81% | Rejected: service floor |
| 350/600 brake with immediate 3%/6% markup bumps | 4 | +€143.97 | 2/4 | 90.65% | Rejected: service floor |
| 350/600 brake with targets 3000/2600 | 4 | −€106.72 | 1/4 | 90.97% | Rejected: service and margin |
| Remaining pickup-opportunity brake, 360 min horizon | 4 | +€50.40 | 2/4 | 92.31% | Not advanced: 2/4-order version has better screen margin and floor |

The pickup-opportunity brake counts only orders still needing a driver and
uses the existing note-aware backward route planner to find their latest
feasible start, including closing times, charging and plate collection.
Three/six orders within six hours of losing that opportunity cap the learner
target at 3000/2400. This needs no additional historical state and therefore
survives the existing final-runner checkpoint/replay path. It changes only
the target; it preserves admission and fee formulas.

Prepared next, behind `delta_pair_same_audience=0`: when enabled, compare the
exact audiences of the two proposed single gigs and reject mismatches before
any withdrawal. Matching pairs retain the existing union, calendar checks,
fees and fallback. Four unit tests cover neutral parity, accepted plans,
manual/experienced mismatches and strict integer validation. No worlds yet.

Prepared a separate default-off note repair, `delta_english_pickup_close=1`:
standalone English “No pickups after 17:00” / “No collections after 17:00”
becomes a pickup closing constraint, rather than ready-after 17:00. It works
independently of Delta's earlier typo corrections. Four unit tests cover the
specific bug, combined readiness, bounded matching and strict validation. A
paired screen is required before selecting it.

Prepared pairing-aware quote discounts, default `delta_pair_quote_bps=0`:
an enabled factor such as 9800 applies only if the ordinary pair planner finds
a feasible route with an existing unbooked waiting gig. Prediction suppresses
outbox-driven pair timers and never posts, withdraws or reserves the partner.
Actual order admission, learner and final cent rounding remain inherited.
This can prefer cheaper-to-serve requests but does not guarantee a future pair;
multiple undecided requests may compete for the same partner. Five unit tests
cover feasibility, booking exclusion, audience compatibility, no mutation,
neutral behavior, rounding and validation. No practice results yet.

Fresh confirmation seeds were reserved before outcomes:
`epsilon-confirm-20261115-s01..s08`. They have not been played by this loop.

## Operator control, 23:18 UTC

The orchestrator confirmed a 12-world practice limit. Worker allocation was
raised to ten and `client.worlds()` confirmed ten ordinary practice worlds
(no active ranking world, plus the existing final). The orchestrator then
reported a live final and prohibited all new practice creation until its
snapshot reaches `now >= endsAt`. The existing sweep processes were suspended
with SIGSTOP to guarantee that their already-queued jobs could not refill
slots; current worlds and completed results remain intact. No `final.py`
process or `runs/final/` file was touched.

After that final, the updated instruction is twelve total practice workers,
no reserve, until the orchestrator requests a ranking stop. New sweeps support
`SWEEP_PAUSE_FILE`: touching the configured flag blocks creation and retry at
world boundaries while current weeks finish; removing it resumes the queue.
The pre-existing suspended processes were started before that flag existed
and will be resumed only after the final ends. Re-running their original
`sweep.py` commands reuses completed weekly scores.


## Read-only trace findings received at 23:26 UTC

`epsilon-patterns.md` confirms 19 current-Delta weeks at €13,760.21/week,
95.67% mean on time and 91.12% worst. Weekly driver fees (€23,686.96) and
late refunds (€563.72) match the retained `runs.jsonl` ledgers. Booked pairs
paid €28,282 less than their typical scheduled fees in total, €1,489/week;
this is a measured pooling benefit, not a counterfactual margin forecast.
The helper did not measure the remaining above-opening spend on reposts,
so fee escalation work remains deferred until that specific quantity is known.

Premium orders have 53/330 late deliveries (16.1%) and low allocated margin
(€17.71/order, with joint-gig fees allocated approximately). Prepared a
**service-only** screen at premium slack 1440/2880 minutes, using the existing
admission setting and its unit coverage; no segment pricing changes. All four
screen seeds include s07 and f2-s04. This is a queued hypothesis, not a selected
repair. The helper's lane/segment price recommendations are excluded under
the manager's instructions. No fresh worlds were created during the live-final
pause.

The lower-trust idea scout arrived at 23:30 UTC. One finding was independently
verified against both code and the unauthenticated public map: all 30 self
roads have 12 km / 25 minutes, while pair planning returns 0 / 0 for identical
place IDs. Added opt-in `delta_pair_self_roads=1`, default 0, to use real map
self roads where present. Synthetic maps without self roads retain the old
fallback. Four tests cover drive accounting, rejection above 720 minutes,
missing fixture roads and strict validation. This is a separate hypothesis;
its service/margin effect remains unmeasured. The scout's “strictly positive”
causal claims are not accepted without paired practice confirmation.

Prepared a second independent safety hypothesis from verified code:
`delta_wide_pickup_buffer_minutes=20/30` trims only the final pickup tail to
leave driving-time tolerance before the delivery closing/deadline. Default 0
preserves Delta. If the cushion would remove all feasible pickup time, retain
the original legal window; never widen a private slot. Three tests cover
pickup-only trimming, unchanged fee/delivery schedules, tight private-window
fallback and validation. Screen it separately from the same-town road repair.

Also queued two settings-only route-safety screens from the scout: move the
existing long-route guard boundary to 400/420 km, increase its shared open cap
to six, and use 1080/1200-minute slack. The existing code confirms these are
admission/driver-fee guards, not lane pricing. The extra cap avoids conflating
a wider guarded band with the old three-order bottleneck. Neither change is
adopted or assumed beneficial.

Live final completion was confirmed by snapshot (`14280 >= 14280`) at 23:34 UTC.
The ten suspended practice workers resumed and two dispatch-safety workers
started. `client.worlds()` confirmed **12 ordinary practice, zero ranking,
zero active final worlds** at 23:35 UTC. The orchestrator's current policy is
12 total workers and no reserve until a ranking-stop instruction arrives.

A second note repair was verified offline from the scout's exact example:
“Perillä liike kiinni klo 16.30 jälkeen” currently becomes delivery **opens**
at 16:30. Opt-in `delta_finnish_close_fixes=1` removes the conflicting “after”
cue only from the bounded `kiinni [klo] HH:MM jälkeen` construction, retaining
its pickup/delivery scope as a **closing** constraint. Default 0 preserves the
old parse. Five tests cover delivery and pickup scope, independent operation,
separate readiness, bounded/invalid text and validation.

| Additional hypothesis | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Pickup-opportunity brake, 180 min horizon | 4 | −€31.65 | 1/4 | 92.13% | Not advanced: weaker screen margin and floor |
| Pickup-opportunity brake, 360 min horizon, thresholds 2/4 | 4 | +€78.34 | 3/4 | 92.81% | Survived screen; remaining 15 paired weeks in flight |
| Pickup-opportunity brake, 720 min horizon | 4 | −€416.89 | 1/4 | 92.14% | Rejected: screen cost and weaker floor |
| Require matching pair driver audiences | 4 | +€7.59 | 1/4 | 90.63% | Rejected: service floor |
| English negative pickup-closing repair | 4 | €0.00 | 0/4 | 91.12% | No effect in screen; not selected |
| Wide pickup cushion 20 min | 4 | −€57.82 | 2/4 | 90.52% | Rejected: service floor |
| Wide pickup cushion 30 min | 4 | −€25.59 | 2/4 | 91.14% | Rejected: service floor |
| Count map self roads in pair planning | 4 | +€158.53 | 3/4 | 91.71% | Survived screen; remaining 15 paired weeks in flight |
| Pairable waiting-order quote factor 9800 bps | Pending (4 planned) | — | — | — | Queued |
| Pairable waiting-order quote factor 9500 bps | Pending (4 planned) | — | — | — | Queued |
| Premium service slack 1440 min | Pending (4 planned) | — | — | — | Screen in flight |
| Premium service slack 2880 min | Pending (4 planned) | — | — | — | Screen in flight |
| Guard routes above 420 km, cap 6, slack 1200 | Pending (4 planned) | — | — | — | Screen in flight |
| Guard routes above 400 km, cap 6, slack 1080 | Pending (4 planned) | — | — | — | Screen in flight |
| Finnish closed-after note repair | Pending (4 planned) | — | — | — | Screen in flight |

Prepared selective rescue-pair guards, independently default off:
`delta_pair_max_wait_minutes=240` leaves aged waiting singles on their existing
gig instead of resetting them into a one-hour pair trial;
`delta_pair_min_slack_minutes=600` protects waiting singles whose latest legal
pickup opportunity is near. Fresh/unposted orders retain ordinary eligibility.
The existing planner, fees and confirmed withdrawal behavior stay inherited.
Four unit tests cover inclusive boundaries, note deadlines, booked exclusion,
neutral behavior and strict validation.

| Additional hypothesis | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Rescue-pair waiting age ≤240 min | 4 | +€118.60 | 2/4 | 91.26% | Rejected: service floor |
| Rescue-pair remaining pickup slack ≥600 min | 4 | −€193.66 | 1/4 | 89.70% | Rejected: unranked week |


At 23:50 UTC the completed pickup-opportunity screens selected the 360-minute,
2/4-order variant for full-cohort extension; this is selection for further
measurement, not promotion. The other opportunity variants were not extended
because the selected screen arm had both higher mean margin and a higher
observed floor. Eight previously reserved fresh Delta references started on
one worker; fresh reference outcomes will not be used to tune candidate settings.
The candidate itself must still pass its complete 19-week comparison and
fresh paired confirmation.


At 00:01 UTC the same-town road repair completed its four-week screen and
advanced to the remaining fifteen paired weeks. Both pickup cushions and both
selective rescue-pair guards failed the service floor and are rejected as
standalone candidates. Every active sweep now uses the shared launch-pause
flag; pre-gate controllers have all finished.

The stronger pickup-opportunity brake retained its floor over ten paired weeks
but cost €228/week at that intermediate point. A separate screen tests milder
3600/3000 target caps (rather than 3000/2400); the normal/global win target
remains 4200. This is service-policy refinement before volume expansion.

| Additional hypothesis | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Pickup opportunity 360 min, thresholds 2/4, targets 3600/3000 | Pending (4 planned) | — | — | — | Screen in flight |
| Pickup opportunity 360 min, thresholds 3/6, targets 3600/3000 | Pending (4 planned) | — | — | — | Screen in flight |
| Pickup opportunity 180 min, thresholds 2/4, targets 3600/3000 | Pending (4 planned) | — | — | — | Screen in flight |


## Full-cohort service result, 00:11 UTC

The pickup-opportunity brake with a 360-minute horizon, thresholds 2/4 and
3000/2400 target caps completed all nineteen existing paired weeks. It raises
the observed floor by 1.69 percentage points while sacrificing 25.6 wins/week.
Its safety is promising, but the €328/week cost requires comparison against the
cheaper projected brake. Eight pre-reserved fresh paired weeks are now in flight;
no Epsilon setting is adopted before confirmation.

| Change against current Delta | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Pickup opportunity 360 min, thresholds 2/4, caps 3000/2400 | 19 | −€328.42 | 6/19 | 92.806% | Full cohort safe; fresh confirmation in flight |

A protected-volume screen is prepared at global targets 4600 and 5000 with
each of the two brakes independently retained. It will use the same four
screen weeks, not fresh confirmation outcomes. This tests whether congestion
protection can recover the margin surrendered by the stronger brake. Existing
unit coverage exercises these settings; there is no new code path. Plans are
retained under `docs/research/plans/epsilon/` for reproducibility. The shared
pause file remains the drain-and-resume mechanism for ranking slot requests.
CI at head `5626f4c` passed Python 3.9, 3.12 and 3.14.


Prepared opt-in sweep-only fee instrumentation (`SWEEP_FEE_DIAGNOSTICS=1`).
It joins successful post receipts with actual negative `driver_fee` ledger
charges and nominal opening fees computed from the unchanged model. It reports
all single charges, singles posted after an earlier successful post (including
pair fallback), and the narrower expired-then-reposted subset separately.
Paired gigs and unmatched charges are explicitly unmeasured; booking offers
are not treated as paid ledger cost. These are gross charges above opening,
not counterfactual savings or net spend after later positive refunds.
This measurement does not modify model actions or write additional trace rows.
Six tests cover ledger versus offers, failed posts, pair fallback, separate
legs, receipt-before-event ordering and complete sweep opt-in parity.
All 431 tests and the CI demo/CLI commands pass locally. A four-week unchanged
Delta measurement batch is prepared before any fee-policy hypothesis.


## Ranking and selection update, 00:19 UTC

The orchestrator briefly authorized five sequential 01:00 UTC ranking runs,
then explicitly revoked that authorization before any run started. The timed
practice launch gate was cancelled; the queue continues at twelve workers.
Do not start board runs without a new instruction. Selection now explicitly
requires positive paired mean margin as well as the existing service and fresh
confirmation gates. Negative-margin brake arms remain reference hypotheses,
not adopted Epsilon settings. Margin/volume experiments take priority.

The projected 350/600 brake completed nineteen pairs at −€44.09/week, 3/19
positive, floor 91.718%; its pre-reserved fresh confirmation is in flight.
The stronger pickup brake remains −€328.42/week on the nineteen-week cohort.
These are distinct existing and fresh cohorts; partial combined averages do
not replace the independent fresh result.

Prepared `final.py --output DIR` so the required post-freeze rehearsal can
use ignored `runs/epsilon/rehearsal/` without touching the live runner's
`runs/final/`. The default output path and existing runner behavior stay the
same. An offline restart test checks that the custom manifest rejoins the
same world and that both checkpoint calls use the custom directory.

Repository decision-API audit: `docs/research/gemini-notes.md`,
`models/gemini_notes.py` and `scripts/benchmark_gemini_notes.py` implement only
an offline cached note-extraction contract. The doc describes a possible
Google GenerateContent transport; no live inference client, credential lookup
or model-factory integration exists. `docs/research/delta-next-steps.md`
parks live LLM notes pending independent evidence. No implemented decision
API or live LLM dispatch path was found.


## Margin queue and complete confirmations, 00:30 UTC

| Change against current Delta | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Projected brake 350/600, existing cohort | 19 | −€44.09 | 3/19 | 91.718% | No margin promotion; fresh comparison completing |
| Pickup opportunity 360 min, 2/4, fresh cohort | 8 | −€537.13 | 2/8 | 92.963% | Rejected standalone: fresh margin cost |
| Premium minimum slack 1440 min | 4 | +€213.41 | 3/4 | 91.667% | Survived screen; extend to remaining fifteen |
| Premium minimum slack 2880 min | 4 | −€489.67 | 1/4 | 90.385% | Rejected: service and margin |
| Opportunity 360 min, 2/4, mild targets 3600/3000 | 4 | −€293.42 | 1/4 | 90.278% | Rejected: service and margin |
| Opportunity 360 min, 3/6, mild targets 3600/3000 | 4 | −€299.20 | 1/4 | 92.053% | Rejected: margin |
| Opportunity 180 min, 2/4, mild targets 3600/3000 | 4 | −€231.12 | 1/4 | 91.716% | Rejected: margin |
| Rescue pair opening hold 0 min (recovered exact Delta setting arm) | 4 | €0.00 | 0/4 | 91.117% | Rejected: no effect; do not replay |
| Rescue pair opening hold 30 min (recovered exact Delta setting arm) | 4 | €0.00 | 0/4 | 91.117% | Rejected: no effect; do not replay |
| Projected brake + normal win target 4600 | Pending (4) | — | — | — | Screen in flight |
| Projected brake + normal win target 5000 | Pending (4) | — | — | — | Screen in flight |
| Pickup-opportunity 360/2 brake + normal win target 4600 | Pending (4) | — | — | — | Screen in flight |
| Pickup-opportunity 360/2 brake + normal win target 5000 | Pending (4) | — | — | — | Screen in flight |
| Projected brake + pairable-request factor 9800 | Pending (4) | — | — | — | Screen in flight |
| Projected brake + pairable-request factor 9500 | Pending (4) | — | — | — | Screen in flight |
| Projected brake + pair reach 120 km / 720 min | Pending (4) | — | — | — | Prepared |
| Projected brake + pair reach 150 km / 720 min | Pending (4) | — | — | — | Prepared |
| Projected brake + long open cap 6 | Pending (4) | — | — | — | Prepared |
| Projected brake + long open cap 10 | Pending (4) | — | — | — | Prepared |
| Projected brake + initial-roster high target 4600 | Pending (4) | — | — | — | Prepared |
| Projected brake + initial-roster mid/high targets 4600/5000 | Pending (4) | — | — | — | Prepared |
| Projected brake + initial-roster mid/high targets 5000/5500 | Pending (4) | — | — | — | Prepared |

Wider pair reach uses existing explicit driver settings with profile `off`,
which disables the profile override rather than pairing. `pairs=1` and the
720-minute drive maximum are explicit; all other pairing controls retain
Delta's settings. A new contract test verifies the extra route, deadline
rejection and twelve-hour cap. The larger long-order caps retain the 500/700 km
boundaries, original slack and driver opening fees; they increase admission,
not lane prices. The roster-volume screen retains existing 710/810 thresholds,
uses low target 4200 and preserves all long distance limits at 700 km. This
is an initial-supply volume hypothesis, not a real-time driver-location model.
All 433 tests pass locally.

Latest orchestrator authorization is **five sequential level-8 ranking runs at
03:00 UTC**, with run five started before 04:00. The practice gate is scheduled
for 03:00; resume twelve workers after the results are recorded and reported.
At 00:20 the server still reported round 10 with all five team runs already
played. Recheck the new active round and remaining sequence before creation;
never spend an extra run in an already-completed round. Use confirmed positive
Epsilon only, otherwise plain Delta. The post-freeze rehearsal may kill/restart
only its own newly started PID and must use isolated output, run with no live
final active, and finish before 05:15.


## Checkpoint 1, 00:41 UTC

Best **selected** candidate remains plain Delta; `models/epsilon.json` has no
settings difference. No positive-margin change has completed both all nineteen
paired weeks and independent fresh confirmation. The premium admission guard
is the live positive survivor, not a promoted model.

| Candidate / cohort | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Delta reference | 19 | €0.00 | — | 91.117% | Selected fallback |
| Projected 350/600 brake, existing | 19 | −€44.09 | 3/19 | 91.718% | Reject standalone: negative mean |
| Projected 350/600 brake, fresh | 8 | −€18.15 | 1/8 | 94.158% | Confirms no margin gain |
| Pickup-opportunity 360/2 brake, existing | 19 | −€328.42 | 6/19 | 92.806% | Reject standalone: negative mean |
| Pickup-opportunity 360/2 brake, fresh | 8 | −€537.13 | 2/8 | 92.963% | Confirms margin cost |
| Same-town pair roads | 19 | −€47.04 | 11/19 | 91.714% | Reject standalone: negative mean |
| Premium minimum slack 1440 min | 8 | +€250.29 | 6/8 | 91.667% | Extension in flight; fresh confirmation still required |

Twelve workers remain allocated; `client.worlds()` confirmed twelve unfinished
ordinary practice worlds at 00:36. In flight: premium extension, protected
volume and pair discounts, broader pair reach/long capacity, roster-based
volume, and the unchanged Delta fee measurement. Both uniform higher-target
arms and both pair discounts already failed the service gate and will not
advance. Fresh margin-confirmation seeds are reserved separately from the
completed brake confirmation cohort.

New implementation-manager pushes since resuming the loop: `faa5e63`,
`8fcd5b7`, `e595cdd`, `0c7301e`; earlier Epsilon work is `c144242` through
`5626f4c`. Shared-checkout documentation commits `124033d` and `03da2ae` were
created by the orchestrator, preserved unchanged and not claimed as loop work.
Local 433 tests pass; Python 3.9/3.12/3.14 CI passed at `0c7301e`.
Decision-API pointers remain `docs/research/gemini-notes.md`,
`models/gemini_notes.py`, `scripts/benchmark_gemini_notes.py`, now explicitly
parked as future work. There is no live decision-API integration.
