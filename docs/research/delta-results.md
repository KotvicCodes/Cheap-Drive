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
