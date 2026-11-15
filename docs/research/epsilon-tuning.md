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


## Fee measurement before policy work, 00:44 UTC

Four unchanged Delta runs on the standard screen seeds exactly reproduced the
retained margin, on-time and won-order scores. Gross negative ledger charges
above the nominal unaged opening were:

| Quantity | Mean per screen week |
| --- | ---: |
| All single-gig charges above nominal opening | €4,066.27 |
| Singles after an earlier successful post, including pair fallback | €3,412.66 |
| Narrower expired-then-reposted singles | €1,420.56 |

This deliberately hard screening cohort is not an unbiased nineteen-week
estimate. Pairs/unmatched charges are excluded and tracked as unmeasured.
Positive fee refunds are not netted from these gross excess charges. The
€1,421 expired-repost figure is the closest measured counterpart to the
manager's earlier €1,240/week observation; the broader €3,413 includes pair
withdrawal/split fallback. Neither number is a counterfactual saving.

Only after this measurement, started the global fee-cap screen below. Opening
fees and escalation times stay unchanged; each candidate lowers all ramp
rungs above opening proportionately. Delta's actual default cap is 15000 bps.
The study changes driver fees, not quote prices by lane or option. Existing
fee-setting validation/unit coverage applies; no new model implementation.

| Change against current Delta | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Projected brake + fee cap 14000 | Pending (4) | — | — | — | Screen in flight |
| Projected brake + fee cap 13000 | Pending (4) | — | — | — | Screen in flight |
| Pickup-opportunity 360/2 + fee cap 14000 | Pending (4) | — | — | — | Screen in flight |
| Pickup-opportunity 360/2 + fee cap 13000 | Pending (4) | — | — | — | Screen in flight |
| Projected brake + pairable quote factor 9800 | 4 | −€553.97 | 1/4 | 89.109% | Rejected: service and margin |
| Projected brake + pairable quote factor 9500 | 4 | −€259.42 | 2/4 | 90.820% | Rejected: service and margin |

The orchestrator expects a vetted shortlist in scratchpad `top7-vetted.md`
around 01:35 UTC. Its build-ready hypotheses go ahead of remaining speculative
queue entries. The 03:00 ranking instruction stays in force.


## Vetted shortlist and schedule update, 01:12 UTC

Own allocation is six workers; P1 and P5 own three each. Vetted items 1, 2,
4 and 5 are assigned here; latest-feasible pair windows belong to P1.
Freeze moves to 04:30 UTC, rehearsal/practice cutoff to 06:15 UTC, final to
07:00 UTC. The five sequential 03:00 UTC ranking runs remain authorized.

| Change against Delta | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Premium slack threshold 1440 minutes | 19 | +€121.69 | 13/19 | 91.667% | Fresh eight-week confirmation running; not adopted |
| Projected brake + cap14000 | 4 | −€603.51 | 1/4 | 90.823% | Reject |
| Projected brake + cap13000 | 4 | −€208.19 | 1/4 | 89.562% | Reject |
| Raw-reference quote floor11000 | Pending4 | — | — | — | Screen prepared |
| Raw-reference quote floor11500 | Pending4 | — | — | — | Screen prepared |

Raw-reference floors apply after normal rounding to competitive single-leg
quotes at level4+, road distance45km+. Practical declines, low levels,
trade-ins and short routes retain their original paths. The integer-cent
ceiling uses the raw reference, with no admission or learning changes.
Default-off action replay of the complete hard s07 week matched all2277
batches and1943 actions, including clocks; explicit0 matched too. Local439
tests and1689 subtests pass. This replay establishes equivalence, not
counterfactual profit. Epsilon JSON still equals Delta.


## Readiness discount implementation

`delta_readiness_early_cut_bps` defaults0. Eligible45–500km nonpremium,
nonprivate singles have at least720 minutes until the original/parsed pickup
readiness. Manual/plates, urgent, level1, trade-in and fewer-than-three-rung
schedules are excluded. Only the first two remaining rungs fall; independent
segment floors and later cap amount/time remain. Equal adjacent fees merge.
Focused boundary/floor/exclusion/post-age checks pass; complete s07 replay
with explicit0 matches2277 batches/1943 actions. Local444 tests pass.

| Change against Delta | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Readiness early cut600bps | Pending4 | — | — | — | Prepared |
| Readiness early cut800bps | Pending4 | — | — | — | Prepared |
| Pickup-opportunity360/2 + cap14000 | 4 | −€245.43 | 1/4 | 92.199% | Reject: negative margin |
| Pickup-opportunity360/2 + cap13000 | 4 | −€285.62 | 2/4 | 89.683% | Reject: service and margin |


## Saturday phrase experiment

`delta_note_weekday_saturday=0` keeps the original parser. Enabled bare
`arkisin`/`weekdays` retains hours and allows Monday–Saturday; Sunday stays
excluded. Explicit Monday–Friday phrases remain restricted. Bounded Saturday
negatives in FI/EN/SV preserve pickup/delivery scope, including a negative
preceding a role word. All Delta parser branches receive the flag. Private
slots and explicit dates retain their constraints. Five focused tests pass;
449 local tests pass and explicit0 matches the complete s07 action tape.

| Change against Delta | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Bare weekday phrases preserve Saturday | Pending4 | — | — | — | Prepared; independent screen |


## Urgent escalation clock implementation

`delta_urgent_fee_memory=0` preserves Delta exactly. Enabled single fees use
the first actual deadline warning, remembered before pair interception and
by side-effect-free history observation. Checkpoints retain that dictionary;
receipt-free reconstruction derives it from warnings before reconciliation.
Elapsed steep rungs fold to one current step; unique future rungs retain
original times. Stronger accepted single current fees are preserved; pair
schedules and nonurgent fees remain unchanged. No final-runner edit.
Tests cover0/30/120+minutes, repeat warnings, pair split, drop/expiry, moved
private windows, checkpoint and receipt-free recovery. Local455 tests pass;
explicit0 exactly replays2277 batches/1943 actions on s07. Fee diagnostics
export urgency age/reset counts and readiness first-rung offered reductions;
paid ledger cost remains the economic measure.

| Change against Delta | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Urgent fee clock memory | Pending4 | — | — | — | Prepared; service gain must pay for increased fees |


Urgent-clock edge review: receipt-free history deliberately skips normal
observation for a booked pair warning, so its deadline branch now preserves
the clock independently. Accepted-fee evidence must also match the requested
car count, preventing a two-car trade-in offer from flooring a one-car split.
Both have regression tests;457 local tests pass. No urgent worlds have been
started with the preceding implementation.


## First confirmed adoption, 01:24 UTC

**Epsilon now changes only `premium_min_slack_minutes`600→1440.** This
requires a full day of feasible slack for premium-car quote options, allowing
more time to find experienced drivers. Factory remains `models.delta:make_delta`.
No quote floor, fee cut, parser or urgent-memory flag is adopted.

| Change / cohort | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Premium slack1440 / all existing | 19 | +€121.69 | 13/19 | 91.667% | Adopted |
| Same / independent reserved fresh | 8 | +€291.38 | 4/8 | 92.049% | Confirmed; adopted |

All27 observed candidate weeks clear91.5%; gains are means of per-seed
paired differences, not mixed-cohort averages. Existing mean margin is
€13,881.91 versus Delta€13,760.21. Fresh candidate mean is€12,511.02.
The saved paired score artifact is
`docs/research/plans/epsilon/premium1440-confirmed-results.json`.
This is a modest validated improvement, not evidence of reaching top7.

The03:00 ranking choice now points to Epsilon; it can change only if a
stronger candidate completes the same full and fresh gates. Current own
six-worker queue: raw-floor screens2, readiness/Saturday screens2,
urgent-memory screen2. P1/P5 extensions remain their owners' work; merges
await explicit orchestrator instruction. Next: test the best shortlist
combinations with confirmed premium slack, and prepare the builder combination.

Own pushes since the previous report: `5f71742` quote floor, `b6913be`
readiness fees, `982c9d6` Saturday parser, `07fdb54` urgency memory,
`67c1554` urgency recovery edges,
`e42c6eb` reproducible sweep plans. All defaults remain off for Delta.


## Wave2 note-urgency implementation

`delta_note_urgency=0` leaves schedules identical. Enabled nonurgent singles
compare a stable note-aware route against neutral note facts using the current
order legs/deadline and original request response/readiness floor. Only a
note-tightened pickup cutoff arms a steep curve atcutoff−180. Merge by maximum
with the ordinary fee schedule, fold elapsed steps into one current rung,
and retain strictly increasing future times. Actual-warning, pair and
infeasible-route rescue behavior remains unchanged. No persistent clock,
network timer or final-runner change. Reposts cannot reset this derived clock;
changed appointments/deadlines recompute the current order version's cutoff.

Six focused tests cover elapsed0/30/120+, rounding, monotonicity, pre-trigger
fees, actual warning, neutral calendars, infeasibility, current private slots,
plates, pair/trade-in exclusions. Explicit0 complete s07 replay matches all
2277 batches/1943 actions;463 local tests pass.

| Change against Delta | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Anticipated note urgency, anchored single fees | Pending4 | — | — | — | Queued after existing fee items |
| Raw-reference floor11000 | 4 | +€355.10 | 3/4 | 90.296% | Reject standalone: service |
| Raw-reference floor11500 | 4 | +€179.95 | 2/4 | 91.398% | Reject standalone: service |
| Premium1440 + floor11000 | Pending4 | — | — | — | New combination screen |
| Premium1440 + floor11500 | Pending4 | — | — | — | New combination screen |

The quote floors' combination screens are new candidates; no floor-failing
component was adopted or advanced to19 by itself. Their margin evidence
motivates testing whether the confirmed premium guard changes the service
interaction. They must independently pass the full promotion gates.


## Continued selection, 01:38 UTC

Pooled premium1440 result:27 paired weeks,+€171.97/week,17/27 positive,
worst91.667%. Already adopted in`a4cd6b3`;03:00 ranking selection is Epsilon.
The orchestrator withdrew builder merge instructions after both leads lost
margin on extension. Do not merge P1/P5. Reserve a new eight-seed package
cohort before seeing package outcomes, with both Delta and premium1440
references; additions must improve confirmed Epsilon as well as Delta.

The rejected Saturday experiment received a scope regression correction for
“No Saturday deliveries” and analogous FI/SV orderings. The earlier screen
uses the preceding parser version and remains rejected; this correction is
not adopted or claimed to inherit those scores. Defaults/off remain exact.
Local463 tests pass after this correction.

| Change against Delta | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Urgent fee-clock memory | 4 | −€1,114.73 | 0/4 | 91.057% | Reject: cost and service |
| Readiness early cut600 | 4 | −€266.59 | 2/4 | 90.191% | Reject: margin and service |

Queued after current screens: premium1440 plus readiness200/400bps or a
14500bps nonurgent cap. These are smaller, separate fee levers with existing
parameter tests; none is adopted before full paired and fresh confirmation.
A neighboring premium threshold screen is also prepared. Builder combinations
were cancelled before launch. Freeze04:30 and practice cutoff06:15 unchanged.


## Rehearsal ownership and five-slot tuning allocation, 01:48 UTC

The orchestrator assigned the entire rehearsal/kill-restart drill to a
dedicated agent. This manager will not start a rehearsal or signal any
`final.py`. Own tuning allocation is now five slots, leaving one rehearsal
slot. To release one immediately, paused launches, ended one already-rejected
floor-screen world, let its sibling finish, then resumed only the unfinished
week with one worker. Completed scores remain resume-safe.

| Change against Delta | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Readiness early cut800 | 4 | −€351.47 | 1/4 | 90.909% | Reject |
| Saturday bare-weekday parser, preceding scope version | 4 | −€2.84 | 2/4 | 90.566% | Reject; later scope correction unpromoted |
| Anticipated note urgency | 4 | +€167.25 | 2/4 | 90.836% | Reject standalone: service |
| Premium1440 + floor11000 | 4 | +€235.19 | 2/4 | 91.066% | Reject: service; only+€21.77 versus premium |
| Premium1440 + floor11500 | 4 | +€16.43 | 2/4 | 90.984% | Reject: service; −€196.98 versus premium |
| Premium1440 + readiness200 | Pending4 | — | — | — | Screen running |
| Premium1440 + readiness400 | Pending4 | — | — | — | Screen running |
| Premium1440 + nonurgent fee cap14500 | Pending4 | — | — | — | Screen running |
| Premium1440 + anticipated note urgency | Pending4 | — | — | — | Queued, incremental comparison required |

New package seeds were reserved before outcomes. Delta and confirmed premium
references run on all eight. The neighbor1200/1800 premium-threshold screen
is deferred behind testing additions to the confirmed1440 guard.


## Additional fresh week withdraws ranking qualification, 01:57 UTC

The new pre-reserved package reference cohort revealed a strict-floor miss:
`epsilon-package-confirm-20261115-s03`, premium1440, onTimeShare
**0.9149560117302052 =91.4956011730%**, margin€13,892.16,341 won,
zero undelivered, server ranked=true. This remains above the official90%
threshold, but is **below our91.5% selection gate**; rounding to91.5% would
conceal that miss. Original19+8 confirmation evidence remains accurately
recorded above. Additional observations cannot be excluded from the safety
minimum merely because adoption happened earlier.

The03:00 ranking-choice file now falls back to plain`models/delta.json`
unless another candidate completes the gates. Epsilon JSON stays1440 pending
further tuning; this preserves the previously selected specification while
ranking eligibility is withdrawn. The orchestrator was told immediately.
Rehearsal remains wholly owned by the dedicated agent.

Next settings-only screen: premium1200 and1800, with existing premium guard
unit coverage in`tests/test_gamma_segments.py`,`test_delta.py` and
`test_delta_lanes.py`. Each needs all19 old pairs and a newly reserved
independent confirmation cohort before promotion. Fees remain lower priority
after all three smaller-cut arms missed service on a hard week.


## Aggressive volume pivot, 02:09 UTC

Latest orchestrator instruction cancels remaining fee/note/service micro-items
and restores six tuning slots. New priority: **premium1440 + targets4600,
5000,5500, each with projected350 or pickup360/2/4 protection**. This is a
new combined-policy screen; prior target4600/5000 failures lacked premium1440.
All new candidates retain the strict91.5% worst-week gate, full19 old pairs
and fresh confirmation. Best report due05:45 UTC; existing04:30 freeze is
retained unless explicitly superseded. Rehearsal remains delegated.

Drained active micro-item worlds under the shared pause gate, stopped only
those sweep controllers after their worlds ended, and launched the new
24-world screen with six workers. No final process or live-final file was
touched. Cancelled unfinished rows remain resumable but are no longer queued.
Projected protection uses350/600bps late thresholds, targets3600/3000,
120-minute hold and no extra quote bump. Pickup protection uses a360-minute
horizon, soft2/hard4 risky unbooked orders and targets3000/2400. All knobs
already exist, default off; an integration test checks all six combinations'
premium option filtering, brake activation/release and checkpoint recovery.

| Change against Delta, all with premium1440 | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Projected350 + target4600 | Pending4 | — | — | — | Volume screen |
| Projected350 + target5000 | Pending4 | — | — | — | Volume screen |
| Projected350 + target5500 | Pending4 | — | — | — | Volume screen |
| Pickup360/2/4 + target4600 | Pending4 | — | — | — | Volume screen |
| Pickup360/2/4 + target5000 | Pending4 | — | — | — | Volume screen |
| Pickup360/2/4 + target5500 | Pending4 | — | — | — | Volume screen |

The latest instruction explicitly keeps03:00 ranking on **Delta+premium1440**.
The private controller therefore pins that specification, with explicit
selection metadata documenting the extra91.495601% research-floor miss.
It does not label that week as meeting91.5%. New volume candidates cannot
silently change the pinned ranking model. Five runs remain sequential,
server-checked, and must start before04:00. The controller was restarted
while still waiting so its explicit-selection handling is actually loaded.

Completed abandoned micro-items: readiness200 +€31.04/week versus Delta
(2/4positive), −€182.36 versus premium, worst90.642%; readiness400 −€138.10
(2/4positive), −€351.51 versus premium, worst90.885%; cap14500 −€210.29
(0/4positive), −€423.70 versus premium, worst91.117%. Premium+note urgency
screen was+€229.12 versus Delta(3/4), +€15.71 versus premium(2/4), floor91.667%,
but the added package-s03 regression remained91.495601%, so no extension.
Premium1800 was stopped after its first two old weeks: −€679.51,0/2positive,
floor91.304%. No component from this cancelled queue was adopted.


## Explicit ranking exception and tighter shutdown, 02:20 UTC

The orchestrator/user explicitly selected **premium1440 Epsilon for03:00**
after reviewing the extra fresh91.495601173% week: the91.5% miss is at
rounding scale; Delta's observed floor on the same combined seed set is
lower at91.117%; premium1440 remains ahead on paired margin over27+weeks.
This is a documented selection exception for that named ranking model,
not a claim that91.495601% mathematically meets91.5%. New volume candidates
still need the strict91.5% worst-week floor. The controller's explicit-model
metadata now records this authorization and reasoning.

New hard deadlines: **no new practice after05:30 UTC; every own world ended
by05:50; final report by05:45.** A quiet rehearsal then needs the machine
idle because concurrent sweep load caused11-second fsync stalls. No more
recursive filesystem scans across worktrees. Own stop guard gates launches
at05:29 (one minute early for in-flight request margin), drains and stops
own sweeps, and ends any remaining own nonranking practice by05:40. It never
touches final processes or live-final files. Existing04:30 freeze remains.

First two hard weeks show every initial volume arm below91.5%. Pickup
win4600/5000/5500 reduce orders by40.5/49.0/32.5 per week versus premium1440;
projectedwin5500 adds only5 while losing€624/week versus premium. Finish
the requested four-week screens, with no extensions for floor failures.
Next volume test keeps pickup horizon360/thresholds2&4 but relaxes the
braked targets from3000/2400 to3600/3000 or4200/3600, each with outside
target4600/5000/5500. This tests whether less drastic cuts preserve volume
while the same trouble signal still protects service. It changes existing
settings only; no fee, note or service-code micro-item is resumed.


## Early Epsilon baseline, 02:28 UTC

The user named Delta + `premium_min_slack_minutes=1440` **Early Epsilon**.
`models/epsilon-early.json` freezes that exact specification, named "Early Epsilon";
`models/epsilon.json` currently matches it. The authorized 03:00 ranking
selection is the named Early Epsilon file, with the previously documented
91.495601% rounding-level floor exception. All subsequent test-plan bases
include premium1440, and all decisions compare paired margin against Early
Epsilon using its existing 34 per-seed scores, rather than replaying Delta.
Historical Delta comparisons remain as historical evidence. Volume screens
continue at targets4600/5000/5500 with brakes; new adoption still requires
strict worst-week91.5%, at least8 paired weeks and fresh confirmation.

Initial volume screen against Early Epsilon (02:30 UTC):

| Change on Early Epsilon | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| premium1440-opportunity360-2-win4600 | 4 | €-263.99 | 1/4 | 90.663% | Reject: floor below91.5%; margin loss |
| premium1440-opportunity360-2-win5000 | 4 | €-332.84 | 2/4 | 91.420% | Reject: floor below91.5%; margin loss |
| premium1440-opportunity360-2-win5500 | 4 | €-993.08 | 0/4 | 90.268% | Reject: floor below91.5%; margin loss |
| premium1440-projected350-win4600 | 4 | €-686.44 | 1/4 | 90.331% | Reject: floor below91.5%; margin loss |
| premium1440-projected350-win5000 | 4 | €-1608.85 | 1/4 | 89.189% | Reject: floor below91.5%; margin loss |
| premium1440-projected350-win5500 | 3 | €-488.05 | 1/3 | 90.828% | Reject: floor below91.5%; margin loss |

Projected5500 has3 completed pairs; its fourth row exhausted creation
retries while other agents filled all12 team slots. It already fails the
service gate and is not extended. The remaining five arms have all4 pairs.
The six-arm milder-brake follow-up is now running, base Early Epsilon.
Local CI-equivalent suite:464 tests passed.

Reusable Early Epsilon scores are archived in
`docs/research/plans/epsilon/early-epsilon-baseline.json` (34 unique seeds).
Prepared next screen: projected350 with higher braked targets4200/3600,
and pickup protection moved from360 to720 minutes with targets4200/3600;
each crosses external target4600/5000/5500. This changes existing knobs
only and tests whether earlier protection with a smaller intake reduction
can keep both order volume and service. Eighteen composition cases now
check premium1440 bases, actual brake targets/release and checkpoint
recovery. Future fresh-reference plan contains Early Epsilon only.


## Buy service with fees, 02:39 UTC

New orchestrator priority: keep high win targets and pay for faster bookings,
instead of suppressing intake. Queued six arms on Early Epsilon: targets5000
and5500 crossed with opening8500 only, faster fee policy only, or both.
Faster policy uses existing `fee_shape=review`, `review_after_minutes=180`,
`review_fee_bps=11000`, `cap_before_last_pickup_minutes=720`, plus
`delta_urgent_fee_memory=1`. The note-aware effective latest pickup drives
the cap; it arrives12hours before that cutoff rather than3hours. The110%
review comes3hours after first post (normal review default6hours). Existing
night review handling remains enabled. Urgent memory preserves the original
warning clock across reposts/recovery; the standard urgent curve stays
150%→250% over120minutes. This policy affects ordinary unbooked gigs as
well as near-cutoff ones; it is not a new backlog-triggered fee rule.
Short/premium/long opening floors remain in effect. No intake brakes are
enabled in these arms, and no production source/default changes.
Six integration cases check target retention, actual opening/review/cap
fees and the urgent clock after checkpoint restoration. It takes priority
over the prepared earlier-brake screen as soon as the current six workers
finish; no additional workers are allocated.

| Change on Early Epsilon | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| premium1440-buyservice-opening8500-win5000 | Pending4 | — | — | — | Screen next |
| premium1440-buyservice-fasturgent-win5000 | Pending4 | — | — | — | Screen next |
| premium1440-buyservice-opening8500-fasturgent-win5000 | Pending4 | — | — | — | Screen next |
| premium1440-buyservice-opening8500-win5500 | Pending4 | — | — | — | Screen next |
| premium1440-buyservice-fasturgent-win5500 | Pending4 | — | — | — | Screen next |
| premium1440-buyservice-opening8500-fasturgent-win5500 | Pending4 | — | — | — | Screen next |

At02:44 the quota dropped to4 workers (offers builder gets2). Paused
launches, drained the six active weeks, stopped only the old sweep processes,
and resumed with4 workers. The fee batch includes the milder-brake remainder:
22 completed scores were copied unchanged with provenance; two missing
week rows are retried alongside the24 fee-grid worlds. No finished week is
replayed. Gate/controller and hard-stop guard were rechecked live.

Validation:465 unittest tests passed; pytest465 passed plus1779 subtests.
The new fee-grid commit was transplanted onto authoritative remote history
after an unintended local history rewrite. Old local state is preserved
on the unpushed `backup/rewrite-f4768bd` branch. No force push, no builder
merge, and no final runner/process/files were touched.

Added the orchestrator's zero-code capacity arm on Early Epsilon:
`capacity_valve=1`, backlog bands12/20, targets5200/4400/3000. Existing
keys are verified; five boundary cases check the actual target and its
checkpoint restoration. This arm joins the fee screen at the same4-worker
quota. At02:48 the first fee sweep process exited143 unexpectedly; registry
showed4 owned ordinary practice worlds and no sweep processes. Ended only
those orphaned worlds, then resumed the same sweep with finished rows
skipped. Ranking gate/controller and shutdown guard remained live. No
ranking or final world was ended, and no final process was touched.
