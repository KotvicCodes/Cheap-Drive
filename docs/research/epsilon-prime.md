# Epsilon Prime

The selected model is `models/epsilon-prime.json`, named **Epsilon Prime**. Its settings exactly match the recorded `medium-breaker-24h95` candidate: the complete Epsilon Medium stack plus `epsilon_breaker=1`, `epsilon_breaker_on_time_bps=9500`, `epsilon_breaker_window_minutes=1440`, `epsilon_breaker_risk_orders=0`, and `epsilon_breaker_restore_pairing=0`. The minimum sample remains 20 resolved orders.

The breaker latches for the rest of the week when trailing 24-hour realized service falls below 95%. It restores target 4200, short tilt 45 km / 9200 bps, long markup 10000, and turns off new trade intake, relaxed slack, and the corridor-cap override. It preserves Medium pairing and previously accepted trade routing; existing gigs and bookings are not changed. The existing Medium model remains default-off.

## Provenance

The implementation pin is `d02ca9b148763223f8480199bd172e845183f138` (`d02ca9b`). The strategy, recovery, and final-runner Python sources are unchanged in the final model packaging commit. The named `medium-breaker-24h95` stress runs used this implementation. The earlier backfill result on `eps-bf-s002` came from `7a0fc57` under the same 24-hour policy; the explicit zero leading-risk and pairing-restoration controls preserve that behavior in d02ca9b.

The latch-rebuild fix `e07ac2065888fcb14c64d6fa70882f1a86c863d5` (`e07ac20`) is an ancestor of d02ca9b. Both checkpoint restoration and full-history replay preserve the active latch, trigger time, per-order outcomes, and their first resolution times. Checkpoint restoration reapplies the conservative effective settings. History replay rebuilds the signal without submitting historical actions.

## Final-mode validation

All **538 offline tests pass** with `python -m unittest discover -s tests`. `tests/test_epsilon_prime.py` verifies the exact model settings and exercises `final.play_live` using an in-memory stream with:

- no checkpoint, rebuilding the latch from full history;
- a checkpoint before the trigger, rebuilding from the history tail;
- a checkpoint after the trigger, restoring the latch and effective settings.

Each recovery case sends only the new live quote, retains the 24-hour outcome state, and preserves the selected Medium pairing behavior. These tests create no API worlds.

Run the final with `python final.py models/epsilon-prime.json --quiet`. Reuse the same model file and output directory after a restart; the default checkpoint/receipt directory is `runs/final/`. No rehearsal or live final was started during this handoff.

## Paired evidence

The orchestrator’s final selection covers 13 paired weeks: **+€523/week**, **+24.8 orders/week**, **10/13 positive margins**, and **90.1% worst service**. The revised service rule is strictly above 90.0% in every week. The local seven-seed screen below is a smaller cohort: the 95% arm was positive in all seven, averaged +€752.99/week, and retained 101.4% of plain Medium’s paired margin gain across the six non-bf-s002 weeks.

### 24-hour medium-breaker94

| Seed | Margin Δ vs Early | Orders (Early) | On time (Early) |
|---|---:|---:|---:|
| eps-bf-s002 | €-137.14 | 324 (303) | 89.20% (92.41%) |
| delta-f1-s07 | €+552.26 | 363 (348) | 93.11% (91.67%) |
| delta-f2-s04 | €+849.66 | 386 (372) | 91.19% (91.67%) |
| eps-bf-s001 | €+766.90 | 344 (298) | 99.71% (98.99%) |
| eps-bf-s003 | €+476.93 | 389 (359) | 96.92% (96.66%) |
| eps-bf-s004 | €+680.89 | 380 (345) | 97.63% (95.65%) |
| eps-bf-s005 | €+847.68 | 396 (358) | 98.23% (98.32%) |

### 24-hour medium-breaker95

| Seed | Margin Δ vs Early | Orders (Early) | On time (Early) |
|---|---:|---:|---:|
| eps-bf-s002 | €+622.45 | 323 (303) | 90.09% (92.41%) |
| delta-f1-s07 | €+552.26 | 363 (348) | 93.11% (91.67%) |
| delta-f2-s04 | €+1,160.42 | 383 (372) | 92.43% (91.67%) |
| eps-bf-s001 | €+766.90 | 344 (298) | 99.71% (98.99%) |
| eps-bf-s003 | €+359.79 | 382 (359) | 97.12% (96.66%) |
| eps-bf-s004 | €+961.42 | 370 (345) | 97.84% (95.65%) |
| eps-bf-s005 | €+847.68 | 396 (358) | 98.23% (98.32%) |

### Additional stress results

| Arm | Seed | Margin Δ vs Early | Orders | On time |
|---|---|---:|---:|---:|
| medium-breaker-leading-pair94 | eps-sp-s001 | €-356.36 | 366 | 89.34% |
| medium-breaker-24h95 | eps-sp-s001 | €+918.65 | 372 | 91.40% |
| medium-breaker-leading-pair94 | eps-sv-s001 | €+1,007.99 | 354 | 96.89% |
| medium-breaker-24h95 | eps-sv-s001 | €+1,122.70 | 367 | 96.46% |

Leading-pair94 was rejected after its sp-s001 failure. The orchestrator then stopped further local world creation and took over the candidate backfill; queued work was disabled, and all already-started worlds finished naturally. No worlds were deleted, ended manually, or left in flight. The local sv-s002 priority jobs and the 93/97 threshold jobs were not launched after that instruction.

Raw local results are retained under `runs/epsilon/medium-breaker-24h/` and `runs/epsilon/medium-breaker-priority/`; screening plans are committed under `docs/research/plans/epsilon/`.
