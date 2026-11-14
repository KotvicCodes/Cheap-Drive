# Gamma results

Measured on level-8 ordinary practice worlds on 14 November 2026. Tuning uses
eight seeds (`gamma-t01` … `gamma-t08`). Gamma is Beta plus **guarded long
routes**; see [PROTOTYPES.md](../../PROTOTYPES.md). The earlier
[roadmap](gamma-roadmap.md) records proposals, not measured gains.

## Headline: eight tuning seeds

| Model | Margin / week | Weeks ranked | On time, worst / mean | Orders / week |
|---|---|---|---|---|
| Beta | €11,268.68 | 8 of 8 | 92.692% / 96.35% | 244.25 |
| Gamma | €12,500.43 | 8 of 8 | 92.975% / 95.51% | 259.38 |

Gamma gains **€1,231.75/week (+10.93%)**, positive on **8 of 8** paired seeds.
All means include every completed week, including unranked weeks. Orders are
`score.wonOrders`; on-time means are means of weekly shares, not pooled orders.
Beta here is t1's `beta`; t2's `baseline` reproduced its score and ledger to the
cent on all eight seeds. Earlier Beta results used different seeds.

## Held-out confirmation: fresh seeds

<!-- H1 -->
7 of 16 planned h1 weeks have finished; 9 are missing.
These seeds (`gamma-h01` … `gamma-h08`) were not used to choose the settings.
Model means use all available weeks; paired gains use only matched seeds.

| Model | Seeds played | Margin / week | Weeks ranked | On time, worst / mean | Orders / week |
|---|---|---|---|---|---|
| Beta | 4 of 8 | €9,326.83 | 4 of 4 | 95.122% / 95.74% | 224.25 |
| Gamma | 3 of 8 | €10,711.97 | 3 of 3 | 94.017% / 94.94% | 242.67 |

Paired gain: €830.06/week; 3 of 3 matched seeds positive.
This is not a completed held-out check; the available rows are provisional.
<!-- /H1 -->

## What was kept, and why

Beta refuses every route over 500 km. Gamma quotes routes over 500 km and up to
700 km only for `next_day` or `within_3_days`, with at least 24 hours from the
dealer's decision to the last feasible pickup and fewer than three of our long
orders still without a driver. Long gigs open at 1.0 × typical fee, rather than
0.8 ×. The global markup, trust charge, shorter-route fee ramp, trade-in refusal
and starter rescue stay Beta's.

This admits valuable work while limiting its tightest deadlines and backlog.
The guarded 600 km trial gained €930/week on 7 of 8 seeds; guarded 700 km gained
€1,232 on all eight. That was the only change kept. It is the first half of
roadmap step 4; direct offers were not run. A public log of another team reported
poor offer acceptance and no useful margin gain; that outside evidence stopped
step 3. It is a self-report, not our own experiment.

`models/gamma.json` uses `gamma:make_gamma`, with Beta's `win_target_bps=3000`,
`opening_fee_bps=8000`, `max_km=500`, plus `long_max_km=700`. Defaults supply
`long_options="next_day,within_3_days"`, `long_min_slack_minutes=1440`,
`long_open_cap=3`, `long_opening_fee_bps=10000`. At `long_max_km=500`, the
effective dataclass default, Gamma reproduces Beta; omission follows `max_km`.

## Tried and not kept

Each gain is the mean difference against **Beta on the same seeds**, not the
full eight-seed Beta mean when a variant is incomplete. “Positive” counts seeds
with strictly higher margin. Each row is a separate variant, not an ablation of
the final Gamma model. Worst on time and orders/week describe that variant.

| Variant | Seeds | Gain / week | Positive | Worst on time | Ranked | Orders / week | What it showed |
|---|---|---|---|---|---|---|---|
| Plain 600 km, 30% | 8/8 | +€1,117 | 8/8 | 92.57% | 8/8 | 259.2 | More margin, with less service buffer. |
| Plain 600 km, 34% | 8/8 | +€1,440 | 7/8 | 89.55% | 7/8 | 288.1 | More work lost qualification on one week. |
| Plain 600 km, 38% | 8/8 | +€2,115 | 7/8 | 89.80% | 7/8 | 317.5 | More orders still lost qualification. |
| Plain 700 km, 34% | 8/8 | +€1,931 | 7/8 | 86.23% | 7/8 | 297.5 | The longer limit had the worst late tail. |
| Guarded 600 km | 8/8 | +€930 | 7/8 | 92.88% | 8/8 | 254.9 | Positive, but 700 km added more margin. |
| Dealer/place tables, 100% | 8/8 | −€705 | 1/8 | 93.55% | 8/8 | 240.0 | The fixed factors reduced margin. |
| Trust build + guard | 8/8 | −€398 | 2/8 | 93.66% | 8/8 | 248.2 | Discounting early work did not pay back. |
| No trust charge | 8/8 | +€288 | 6/8 | 94.34% | 8/8 | 257.6 | The small gain did not justify changing Beta. |
| Same-day quotes +8% | 8/8 | −€577 | 1/8 | 94.05% | 8/8 | 240.0 | Better service cost margin. |
| Separate distance-band markups | 8/8 | −€357 | 3/8 | 91.74% | 8/8 | 254.2 | More orders did not improve margin. |
| Capacity valve | 8/8 | −€343 | 2/8 | 95.38% | 8/8 | 227.8 | Fewer orders improved service but lost margin. |
| Guarded 700 km, 38%, brake | 6/8 | +€627 | 4/6 | 92.36% | 6/6 | 279.8 | The partial gain trailed the kept rule. |
| Guarded 700 km, 42%, brake | 6/8 | −€91 | 3/6 | 91.67% | 6/6 | 281.7 | Higher volume did not pay. |
| Plain 600 km, 38%, brake | 7/8 | +€1,525 | 5/7 | 92.86% | 7/7 | 288.4 | Promising, but incomplete and below 93% worst. |
| Guarded 700 km, 38%, early brake | 6/8 | −€21 | 3/6 | 92.95% | 6/6 | 263.7 | Earlier braking erased the gain. |
| Stale-gig fee review | 6/8 | −€300 | 1/6 | 93.46% | 6/6 | 242.3 | The alternative fee shape lost margin. |
| Two-car pairs | 5/8 | +€89 | 2/5 | 93.46% | 5/5 | 239.6 | The partial gain was small. |
| Review + pairs | 5/8 | +€188 | 3/5 | 94.25% | 5/5 | 240.0 | The combination added little. |
| Longs + 38% + brake + review + pairs | 5/8 | +€640 | 3/5 | 90.91% | 5/5 | 280.0 | Combining changes left a thin service buffer. |

The plain-limit failures were all on `gamma-t04`: 600 km/34% reached **89.55%**,
600 km/38% **89.80%**, and 700 km/34% **86.23%**. Extra margin does not compensate
for a week below the 90% ranking requirement. No plain 700 km/38% arm was run.

The t3 sweep was **stopped early at 45 of 64 weeks** when the server slowed during
a test final. At write-up the saved file contains 46 completed weeks, one more
than the stop count. Most variants have 5–6 of 8 seeds; plain 600 km/38%/brake has 7.
These are incomplete comparisons, not eight-seed results. The brake adjusts
quotes when service worsens; review changes the fee of a stale unbooked gig;
pairs combine two orders into one gig. None is enabled in the Gamma model.
The tables, trust build and guard, capacity valve, option/distance adjustments
and brake remain opt-in in `gamma.py`; review and pairs remain opt-in in
`gamma_pairs.py`. No offers implementation was tested or included.

## Limits

- Eight tuning seeds, with settings chosen on them. The fresh held-out check
  above is needed before claiming the gain generalises.
- Gamma's worst tuning week is **92.975%**, slightly below the roadmap's 93%
  target. Rounding it to 93.0% does not make it pass. Aggregate weeks do not
  establish the roadmap's separate long-band lateness target either.
- The extra margin comes with a lower mean on-time share: 95.51% versus 96.35%.
  All eight weeks rank, but this is not a guarantee on new weeks or final clocks.
- Tenth place in ranking round 6 averaged about **€17.7k/week and 450 orders**;
  Gamma makes about **€12.5k and 260** on practice seeds. Those are different
  worlds. Gamma is a modest step, about **+11% margin over Beta**, not a route
  to the top ten.
- Neither this report nor the tuning sweeps establish final-mode readiness.

## Reproduce

With the official kit installed and practice credentials loaded, run:

```bash
python scripts/sweep.py runs/gamma/check plan.json
```

Use this `plan.json` for the paired tuning comparison:

```json
{"factory": "gamma:make_gamma", "level": 8,
 "seeds": ["gamma-t01", "gamma-t02", "gamma-t03", "gamma-t04",
           "gamma-t05", "gamma-t06", "gamma-t07", "gamma-t08"],
 "base": {"win_target_bps": 3000, "opening_fee_bps": 8000, "max_km": 500},
 "variants": {"beta": {}, "long700g": {"long_max_km": 700}},
 "fast": true}
```

For held-out confirmation use `gamma-h01` … `gamma-h08` and output directory
`runs/gamma/h1`. The original plans are kept privately under
`runs/gamma/plans/{t1,t2,t3,h1}.json`; t1 uses `beta:make_beta`, t2 and h1 use
`gamma:make_gamma`, and t3 uses `gamma_pairs:make_gamma_pairs`.
Each completed week is in `runs/gamma/<sweep>/runs.jsonl`; raw files stay ignored.
Compare `score.marginCents` against the matching seed's Beta row before averaging.
The sweep makes practice-server calls; it was not run for this documentation.
Offline checks are `python -m unittest discover -s tests` and the demo/help
commands in `.github/workflows/checks.yml`.
