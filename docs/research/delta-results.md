# Delta investigation

Development began on 14 November 2026. Gamma remains the supported qualified
baseline. The new `delta:make_delta` factory exposes separate experiments;
there is no selected or qualified Delta model configuration yet.

## Correctness experiments

Both switches default to zero, preserving Gamma's selected note/pair behavior:

- `delta_note_fixes=1`: correct only the observed whole-word spellings
  `huoomenna`, `Friay` and `aikaisiintaan`, and interpret the standalone Finnish
  clause “Klo … jälkeen ei enää luovutuksia” as a pickup closing time. Arrival
  anchoring and independent pickup/delivery clauses remain in effect.
- `delta_rescue_windows=1`: search within original absolute promises first.
  If no open dealer interval remains, search the rescue horizon while retaining
  readiness and recurring business hours. Private booked slots are not extended.
  Admission, quote learning, driver fees and pair settings remain unchanged.

Synthetic regressions cover date anchoring, negation, codes/prose, inclusive
closing, weekday/weekend calendars, readiness, private slots, plates, charging,
route timing and neutral pairing. All 242 offline tests pass on Python 3.12.
Negated typo asides are left uncorrected so they cannot override an affirmative
weekday elsewhere in the clause.
An offline posting-window reconstruction on the 17 unique no-window orders
from Gamma's exposed screening traces found no Gamma route and a Delta route
in every case, with calendar/private-slot checks passing. This reconstructs
windows with a conservative retry time, not complete dispatch state, bookings
or economic outcomes.

## Initial official practice pilot

All arms used level 8 and exposed seed `gamma-v01`, frozen Gamma source from
`0eb4e3e`, the pinned SDK, Python 3.12.12 and fast practice. Candidate source
hashes and sanitized results are in [the pilot record](plans/delta/pilot-results.json).
No parameter was selected from this single seed.

| Arm | Margin | On time | Won | Undelivered |
| --- | ---: | ---: | ---: | ---: |
| Gamma | €18,066.72 | 99.245% | 265 | 1 |
| No segments | €17,478.73 | 99.240% | 263 | 1 |
| Short only | €17,664.43 | 99.242% | 264 | 2 |
| Premium only | €17,569.38 | 98.127% | 267 | 3 |
| Higher pair opening, 7500/8000 bps | €17,991.29 | 99.245% | 265 | 1 |
| Rescue only | €17,960.15 | 98.868% | 265 | 0 |

All arms ranked. None beat Gamma's margin on this seed. Rescue eliminated the
one undelivered order, but lost €106.57 overall and reduced on-time share;
delivering formerly abandoned work is not automatically profitable or safer.
The four-seed A1 screen is now complete; see the stage verdict below.
The larger rescue screen and note-correction economic tests remain pending.

Neutral Delta exactly matched frozen Gamma across 1,521 actions, their world
minutes, action results, all 16,658 ordered events (including ledger), final
score and end snapshot after excluding world ID. This is an observed one-seed
parity check alongside neutral offline regressions, not universal qualification.

Three initial attempts encountered `Unreachable` and were discarded. Their
traces were retained and the same frozen code/settings/seed were rerun in fresh
practice worlds. Only this experiment's verified ordinary-practice failures
were removed; no preexisting, leaderboard or final world was modified. All
completed scores reconcile to their captured ledgers. Immutable source copies,
owned-world records, every attempt and raw traces/reveals remain private.

Use the [staged testing plan](delta-testing-plan.md) for promotion gates, fresh
seed separation and the remaining intake, repair and capacity hypotheses.
Practice results do not validate final-clock integration.

## Four-seed A1 attribution verdict

All 20 planned worlds completed and ranked on `gamma-v01..v04`; all were at
least 93% on time. Eight infrastructure-failed attempts (three on v01, five on
v04) were retained and rerun once with identical frozen source/settings/seed.
Only the owned, verified failed ordinary-practice worlds were removed. A retry
launcher also failed before SDK import/world creation and was corrected; it did
not consume a simulator attempt. Completed scores reconcile to full ledgers.
Sanitized scores and every paired margin delta are in
[the A1 results](plans/delta/segments-a1-results.json).

| Arm | Mean margin vs Gamma/week | Positive weeks | Total undelivered | Worst on time | A2 decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Gamma | €0 | — | 15 | 94.574% | Control |
| No segments | +€168.78 | 3/4 | 13 | 95.000% | Advance |
| Short only | −€114.19 | 1/4 | 18 | 94.355% | Stop |
| Premium only | +€234.37 | 3/4 | 14 | 94.672% | Advance |
| Higher pair opening | −€24.47 | 1/4 | 18 | 94.615% | Stop |

Selection used the declared four-seed A1 gates: all ranked, at least three
positive weeks, positive mean margin and no greater total undelivered count.
There were exactly two passing arms, so neither needed discretionary ranking.
Their gains remain exploratory and below the final €500/week requirement.
No settings were promoted and Gamma remains supported.

A2 completed Gamma, no-segments and premium-only on `gamma-v05..v08`, with
unchanged baseline source and settings. Its pruned plan was hashed and selection
recorded before launch. All 12 worlds completed without failures or pending
jobs; scores, ledgers and service counts reconcile. The four-seed A2 subset
had pooled long lateness above 5% for Gamma (3/58), no-segments (4/58) and
premium-only (4/60); retain this warning even though eight-seed pools pass.

## Eight-seed segment outcome and current tests

The complete exposed screening block gives the following paired results;
[sanitized aggregates and gates](plans/delta/segments-results.json) retain all
weekly margin deltas and source provenance.

| Arm | Mean margin vs Gamma/week | Positive weeks | Worst on time | Total undelivered | Long late/won |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gamma | €0 | — | 94.574% | 17 | 6/144 |
| No segments | +€318.02 | 7/8 | 95.000% | 15 | 6/148 |
| Premium only | +€408.14 | 7/8 | 94.672% | 16 | 7/154 |

Both simplifications improved mean margin and mean on time, with fewer total
undelivered orders. Neither reaches the declared €500/week gain, so neither
advances as a selected Delta. The evidence points toward reconsidering short
controls rather than higher pair openings; it does not isolate discount versus
short opening-fee effects. Keep those controls independent of learner/lane tests.

B modest intake completed 14 worlds before its scheduling guard stopped all
three arms; remaining seeds were not launched. Preliminary completed results
include a strong isolated 31% week, but not a robust gain. Gamma and both intake
arms fell below the 93% scheduling guard on `delta-r1-s03` (all still ranked),
so future scheduling stopped for those arms and already owned work drained.
Gamma's failure on that same seed means this does not identify extra intake as
the cause. These outcomes also warn against assuming old Gamma confirmation
safety generalizes to a new block. Do not select or extend intake from the early
profit spike.

At the user's request to occupy all eight practice slots, execution now
counts practice/ranking worlds separately from finals, as the official API
specifies, leaves no deliberate spare, and overlaps independent `trust=50` and
`fee_shape=review` screens with B. Frozen Gamma controls on the same seeds are
reused only with matching source/settings provenance. Existing B is not
interrupted; a supplemental controller imports only its never-created jobs
after it drains, honors blocked arms, and never replays owned worlds. This
changes scheduling, not economic/service gates. No preexisting, leaderboard or
final world is modified. Learner and lane arms remain isolated; their code and
release prerequisites still apply.

The [Gemini note prototype](gemini-notes.md) adds an offline extraction contract,
validated cached-response adapter and three-arm semantic benchmark. No inference,
latency, note-accuracy gain or margin gain has been measured; dispatch never
imports it. The active simulator tests continue independently of this research.

## B1 learning pilot and release

The default-off `delta_b1` switch now implements feedback exclusion, exclusion
plus skipped-fastest 9200 bps pricing, and a separate skipped-fastest tracker.
An independent code/lifecycle review found no substantive issue. The combined
offline suite passes 271 tests. Gamma/configs remain unchanged; enabled B1
rejects combinations with intake, tables, other tracker scopes, review fees or
Delta note/rescue repairs. Its [technical contract](delta-b1-implementation-contract.md)
records the hook ordering and lifecycle assumptions.

All four `delta-r1-s01` pilot worlds completed ranked and ≥93% on time, with
live menu, exact-price and learner-update audits passing and terminal pending
state empty. Neutral Delta exactly matched all **5,347 chronological operational
rows** of the retained frozen-Gamma control, after removing world IDs: actions,
timing, receipts, events, ledger, score and initial/end snapshots. See the
[sanitized pilot record](plans/delta/b1-pilot-results.json). This is one seed's
identity/economic pilot, not a selected gain or universal parity proof.

The remaining candidate screen drained 14 additional worlds from the exact same
reviewed source, settings and controller. All three arms missed 93% on time
on s03, so subsequent scheduling stopped and owned work drained. Retain partial
means as exploratory only; no learner arm advances. Candidate
service/integrity stops remain in force and there is no automatic confirmation.
The trust/review supplemental screen drained 15 worlds and stopped both
candidate arms by its service guard; it did not select a model.

Four frozen-Gamma s05–s08 references were never created because the original B
controller incorrectly applied a candidate scheduling guard to the reference.
The separate immutable reference-only completion finished all four missing
weeks with unchanged Gamma source/settings and reconciled ledgers. This
completes paired measurements regardless of the fixed control's service score;
it does not restart any unsafe candidate or change a promotion threshold.
Preserve the earlier bad Gamma week in every report. All eight Gamma references now exist. Stopped learner arms have fewer than
eight candidate weeks, so partial paired gains cannot establish eight-seed uplift.

## B2 lane and independent repair pilots

The five directional-lane arms are implemented behind `delta_lanes`, default
`off`, with exact 9100 inbound and 10400/10600 outbound factors, frozen five-hub
and remote-destination cohorts, the explicit short-hop clamp, per-quote
diagnostics and invalid-combination checks. Gamma retains admission, learning,
fees and one final cent ceiling. The [technical contract](delta-b2-implementation-contract.md)
and [frozen plan](plans/delta/b2-lanes.json) specify boundaries and composition.
All 288 combined offline tests pass, including 17 lane-specific checks.

A six-world s01 pilot (neutral plus five treatments) and two independent
note-only/rescue-only pilots completed naturally. Neutral matched all 5,347
retained Gamma operational rows exactly. Source/SDK provenance, actual menus,
exact factors and rounding, full ledgers, terminal ownership and service were
reviewed. All eight runs passed the bounded service check.

Three lane treatments passed the bounded integrity review: outbound 10400 and
both inbound/outbound combinations. Inbound-only 9100 and outbound-only 10600
each exposed an inherited frozen-Gamma rescue path extending a private delivery
window beyond its original bounds. Those trajectories cannot pass integrity
review. The combined 9100/10600 treatment lost margin on this seed despite
passing the bounded checks. No arm is selected or qualified from this pilot.

Notes-only matched Gamma's operational rows exactly on s01. Rescue-only had no
no-window gaps or undelivered orders on this seed, unlike the earlier
`gamma-v01` pilot; its economic effect remains seed-dependent. C bookkeeping
is still unimplemented. No lane or repair arm advanced to remaining seeds.

At the user's stopping instruction, all eight owned worlds had completed and
both controllers had exited; zero active/draining worlds or follow-up launches
remained. Other chats' worlds were untouched. Private review artifacts retain
the complete prices, deltas, objections and controller/source hashes.

## B4 conditional pricing prepared offline

The default-off `delta_option_spread="dual_10400_9800"` experiment is implemented
and reviewed. Only final competitive menus containing both same-day and
next-day receive the respective 10400/9800 bps factors before one final cent
ceiling. Lone menus and third options retain Gamma prices. Invalid experimental
combinations are rejected; admission, learner and driver behavior are inherited.
See the [implementation contract](delta-b4-implementation-contract.md).

All 301 offline tests pass on the integration checkout's Python 3.12, including
13 B4 checks for real option gating, exact rounding, neutral action/event parity,
pair timers and lifecycle handling. No B4 live worlds were launched. A separately
frozen executable snapshot and live review remain necessary; the inherited
private-window limitation remains open. All new launches are held at the user's
requested stopping point. Offline readiness establishes no service or economic
qualification, and no Delta model has been selected.

## Selection before the evening test final (14 November, 16:40–17:45 UTC)

Delta and the live final runner (`final.py`) were merged into one branch; the
combined offline suite passes (305 tests). Four unattended level-8 practice
batches then tested the remaining candidates against existing frozen-Gamma
references on the same seeds. All 29 candidate weeks ranked.

| Candidate (change from Gamma) | Seeds | Mean margin vs Gamma/week | Positive / equal / negative weeks | Verdict |
| --- | --- | ---: | --- | --- |
| Premium only (no short controls) + note fixes | `delta-r1-s01..s08` | −€364 | 2 / 0 / 6 | Rejected |
| Lanes, inbound 9100 / outbound 10400 | `delta-r1-s02..s08` | −€92 | 3 / 0 / 4 | Rejected |
| Rescue windows + note fixes | `delta-r1-s02..s08` | +€118 | 4 / 2 / 1 | Selected |
| Rescue windows + note fixes | `gamma-v02..v08` | +€633 | 5 / 2 / 0 | Selected |

Premium only had gained €408/week on the `gamma-v` block it was screened on.
On the `delta-r1` block, which played no part in choosing it, it lost €364/week,
lowered on time in six weeks and left the hardest week at 90.5%. Over all 16
weeks the two blocks cancel; the short-route controls stay as in Gamma.

The lane arm's +€2,748 on `delta-r1-s01` did not repeat: the other seven
weeks average −€92. With s01 the eight-week mean is +€263 on 4 positive weeks,
which is within the week-to-week noise seen in every arm on that seed.

Rescue windows with note fixes is the only candidate that held on both blocks.
Including the two earlier rescue-only pilots (`delta-r1-s01` +€1,320,
`gamma-v01` −€107), the 16 paired weeks average **+€405/week**: 10 positive,
4 identical to Gamma, 2 negative (−€107 and −€186). On time moved by at most
0.4 points down (five weeks) and 0.8 up; the worst week was 91.1% against
Gamma's 91.4% on the same seed. The gain is concentrated: three weeks
(+€2,750, +€1,320, +€1,054) carry 79% of it, as expected for a repair that only
acts when an order has no postable window. Fourteen of these weeks were known
seeds; the two blocks were not used to tune any parameter, since the repair
has none.

[models/delta.json](../../models/delta.json) is therefore Gamma's settings with
`delta_note_fixes=1` and `delta_rescue_windows=1`. The €500/week gate in the
testing plan is not met; Delta is selected as a correctness repair with a
positive measured mean, not as a qualified uplift.
