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
route timing and neutral pairing. All 241 offline tests pass on Python 3.12.
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
The remaining three segment screening seeds are running before the A1 verdict.
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
