# Epsilon tuning log

Epsilon starts as an exact copy of Delta's settings ([models/epsilon.json](../../models/epsilon.json))
and is tuned on paired practice weeks against Delta. Goal: enough margin per week to reach the
top 7 on the official board while every week stays above 90% on time.

| Step | Change | Paired weeks | Margin vs Delta / week | Positive weeks | Worst on time | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 0 | Delta settings, unchanged | 19 | €0 (reference) | — | 91.12% | Current baseline; below the promotion floor |

## Protocol and schedule

Work started 14 November 2026 at 23:00 UTC. All tuning uses level-8 ordinary
practice worlds through `scripts/sweep.py`, with at least two shared slots
reserved. Checkpoint 1: 00:45 UTC; freeze: 03:30 UTC; practice stops by
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
| Earlier projected brake: 350/600 bps | Pending (4 planned) | — | — | — | Screen in flight |
| Earlier projected brake: 450/650 bps | Pending (4 planned) | — | — | — | Screen in flight |
| 350/600 brake with immediate 3%/6% markup bumps | Pending (4 planned) | — | — | — | Screen in flight |
| 350/600 brake with targets 3000/2600 | Pending (4 planned) | — | — | — | Screen in flight |
| Remaining pickup-opportunity brake, 360 min horizon | Pending | — | — | — | Implemented; offline validation |

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
