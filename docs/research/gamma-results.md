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
The complete confirmation used eight fresh seeds (`gamma-h01` … `gamma-h08`),
which were not used to choose the guarded 700 km settings. This candidate
**failed qualification**: `gamma-h07` finished below the 90% requirement.

| Model | Seeds played | Margin / week | Weeks ranked | On time, worst / mean | Orders / week |
|---|---|---|---|---|---|
| Beta | 8 of 8 | €9,552.34 | 8 of 8 | 91.705% / 95.27% | 228.75 |
| Guarded 700 km candidate | 8 of 8 | €10,382.78 | 7 of 8 | 89.956% / 94.35% | 246.50 |

Paired gain: €830.44/week; 7 of 8 seeds positive.
The failed week scored 89.956% on time, versus Beta’s 91.705%. Rounding
the candidate to 90.0% hides the failure; the server returned `ranked=false`.

Follow-up checks on that same failed seed also failed with the default brake
(88.889%) and earlier warning thresholds (88.177%). Beta with the brake ranked
at 91.089%, but earned less than unchanged Beta. These targeted follow-ups
are diagnostic tests, not fresh held-out confirmation. Round 6 therefore uses
unchanged Beta. The guarded 700 km model must not be promoted on this evidence.
<!-- /H1 -->

## Recovery work and ranking round 6

Unchanged Beta completed all five round-6 ranking runs before 15:00 Helsinki:
€12,272.77 / €13,500.54 / €9,191.30 / €12,595.82 / €11,968.19, totalling
**€59,528.62**. All five ranked, with on-time shares from 96.109% to 99.180%.
The public board showed rank 45 at 13:00 UTC; the position can change as others finish.

The recovery branch fixes markup bumps on brake de-escalation and limits the
long-route block to hard brake. Pair schedules now open fresh pairs at 0.72 of
summed reference fees, or waiting-car rescue pairs at 0.78 with a new 60-minute
flat opening. Pair feasibility rejects idle waits above 60 minutes at the second
pickup. The brake and pair regressions have offline coverage; their earlier live
results above used the old code and do not establish gains from these fixes.

Optional segment controls can set opening floors of 1.10 for routes below 45 km
and 1.05 for premium cars, a 10-hour premium slack floor, and an 8% short-route
quote discount. These are neutral by default and remain under live evaluation.
The short and premium segments overlap; their late-order shares cannot be added.

At this checkpoint, 226 offline tests pass on Python 3.9 and 3.14. Fresh Beta
baselines and four candidate arms are running on `gamma-v01` … `gamma-v08`.
`gamma-v09` … `gamma-v16` are reserved for confirmation after settings are
chosen. Note parsing and its integration are implemented in `notes.py` and `gamma_notes.py`;
five note-aware arms have joined the live queue. The saved-source snapshots keep
running experiments independent of later edits.
No revised candidate has been qualified or promoted yet.

## Note corrections under live evaluation

`gamma_notes:make_gamma_notes` applies parsed readiness, release times, real
pickup/delivery hours and explicit delivery promises to quote slack, stop
windows and fee escalation. `gamma_notes:make_gamma_notes_pairs` combines the
same constraints with the pair policy. Historical Beta remains unchanged.

Dates anchor to request arrival; pickup and delivery clauses have independent
scope. Expired gigs move to a valid later business-day window rather than
removing closing hours. Fee caps follow the last physically feasible pickup.
The offline audit (`python scripts/audit_notes.py <trace> ...`) finds a relevant
constraint for all 39 unique failed-visit orders in the original tuning traces:
27 readiness/release, 11 closed-site, and one manual-licence case. Those traces
also confirm 17 of 93 late-refund orders arrived before the nominal order
deadline, consistent with tighter promises and windows. Parsing coverage does
not prove that every failed visit or late refund is preventable.

The reader uses a bounded Finnish/Swedish/English vocabulary. It does not
translate arbitrary prose or parse every date spelling. Bare word hours one
through seven use the dispatch vocabulary's afternoon convention unless AM/PM
is explicit. After a missed promise, already-won orders can receive physically
valid late rescue windows. No feasible window within the 14-day rescue horizon
is journaled explicitly instead of submitting an invalid stop.

## Roster supply controls under live evaluation

Optional `supply_scale=1` reads the initial captured roster and selects normal
win targets of 29% / 35% / 38% at roster sizes below 710 / below 810 / at least
810. The proposed long-route ceilings are 550 / 700 / 700 km; these only tighten
an explicitly enabled long-route corridor. Hard-brake targets take priority.

`town_caps=1` limits competitive daily intake from a pickup town using
`max(2, floor(0.25 * near30[pickup] + 0.05 * near30[delivery]))`. Supply counts
public driver homes within 30 road km, not current availability. Enable
`town_reserve_pending=1` to count undecided competitive quotes as reservations;
a won-only counter can admit an entire bulk batch before its first outcome.
A separate optional 1.10 opening floor applies when pickup supply is at most four.
Missing or incomplete home/road data disables the affected estimate; roster
reads are never repeated. These controls are neutral by default.

The historical audit does not establish the proposed profit or qualification
gains. All 24 audited Beta baseline weeks ranked, including four with fewer than
700 drivers; sparse pickups accounted for 41 of 228 distinct late-refund orders.
A large roster alone does not establish a profitable market. Live experiments
therefore separate supply scaling from town caps and test both the three known
weak weeks and the new screening seeds before fresh confirmation.

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
roadmap step 4; direct offers were not run.

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
