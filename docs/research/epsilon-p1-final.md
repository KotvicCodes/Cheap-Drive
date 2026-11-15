# Epsilon P1 final handoff

No candidate from this lane qualifies for the required 91.5% worst-week service floor. The orchestrator centralized all practice work at 04:01 UTC. This checkout has zero open-world markers, no sweep controller, no score watcher, and no cutoff timer; it will start no new worlds.

The final candidate studied was Early Epsilon plus:

```json
{"delta_safe_quote_bps": 9800, "delta_safe_quote_max_backlog": 10}
```

Early Epsilon already includes `premium_min_slack_minutes: 1440`. No production model JSON was changed. The safe-quote arm is a research result, not a deployment recommendation.

## Paired results against Early Epsilon

| Arm | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| Earliest completion | 4 | −€169.28 | 2/4 | 91.892% | Negative margin |
| Finish band 180 min | 7 | +€95.99 | 4/7 | 90.811% | Service failure |
| Transfer 120 km / idle 180 min | 2 | +€93.47 | 1/2 | 91.691% | Weak screen; superseded |
| Young re-pairing, target 4200 | 1 | −€486.61 | 0/1 | 90.805% | Stopped early |
| Rescue fee 8500, target 4200 | 1 | −€1,622.78 | 0/1 | 90.751% | Stopped early |
| Young re-pairing + rescue, target 4200 | 2 | −€1,109.17 | 1/2 | 89.544% | Stopped early |
| Four-field tilt + finish band 180 | 4 | −€487.94 | 1/4 | 95.750% | Negative margin |
| Full volume stack + tilt, target 4400 | 7 | +€223.26 | 5/7 | 91.022% | Sequential mean gate failed |
| Full volume stack + tilt, target 4600 | 5 | +€774.75 | 4/5 | 90.144% | Sequential service gate failed |
| Safe quote 9800 / backlog 10 | 6 | +€302.58 | 3/6 | 91.379% | Centralized; below final service floor |

The last three rows combine matching stored scores from the loop manager/P5 with this lane's completed scores. Duplicated copied scores are counted once. Canceled worlds and capacity-start errors are excluded. No fresh confirmation completed. The four-field tilt experiment omitted the rest of the volume stack; it is explicitly separate from the subsequent full-stack experiment.

The original tight-roads policy completed 19 paired weeks against **Delta**, at −€51.58/week, 11/19 positive, and 91.714% worst on time. Its initial screen gain did not survive extension. Its reference is different from the table above.

The complete tables, including latest-feasible windows, delivery-stop spare, rescue floors/steps, bounded retries, age guards, economic selection, completion bands, and rejected target-4600 combinations, are in [epsilon-p1-results.md](epsilon-p1-results.md). Plans are retained under `docs/research/plans/epsilon-p1/`.

## Realized cost and pooling

| Arm | Instrumented weeks | Cars delivered in shared gigs | Net driver fee/car | Difference vs matched Early Epsilon |
| --- | ---: | ---: | ---: | ---: |
| Finish band 180 | 5 | 27.41% | €67.53 | +€0.51 |
| Four-field tilt + band | 4 | 31.22% | €63.00 | −€4.87 |
| Full stack + tilt 4400 | 3 | 31.79% | €63.04 | −€5.59 |
| Safe quote 9800 / backlog 10 | 3 | 27.92% | €67.68 | −€0.94 |

Pooling requires at least two distinct orders actually delivered by the same gig. Fees use net ledger charges, including refunds and unsuccessful gigs. Stored external scores did not retain these diagnostics, so these figures use only the instrumented subset. Fee reductions in the volume arms did not establish a qualifying margin/service result.

## Implementation and validation

All P1 planner/rescue policies default off. Tests cover latest(0) stop bounds, delivery-stop spare, plates and charging, offer floors and steps, failed withdrawals, cancellation, split fallbacks, retry recovery, ranking, and validation. Read-only pooling instrumentation is opt-in with `SWEEP_PAIR_DIAGNOSTICS=1` and preserves actions/calls/scores. The three-car prototype was removed without starting a chain world.

To run the shared full-stack/safe-quote handoff, reused the existing guarded intake implementation from `origin/t3/epsilon-model` and cherry-picked P5's `a2310e2` safe-quote implementation. Its default-off boundaries remain intact. The final full offline suite passed **492 tests**. No ranking/final world or final runner was started or changed.

Next: retain the centrally selected safe baseline unless a candidate passes the final 91.5% floor. Re-pairing and rescue-fee changes have no promotion evidence here. All further queue ownership belongs to the loop manager/backfiller.
