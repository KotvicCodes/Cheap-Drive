# Gamma results

Measured on level-8 ordinary practice worlds on 14 November 2026. Tuning uses
eight seeds (`gamma-t01` … `gamma-t08`). The original candidate was Beta plus
**guarded long routes**; see [PROTOTYPES.md](../../PROTOTYPES.md). The
[pre-Gamma research context](#pre-gamma-research-context) preserves the trace
evidence that motivated its experiments.

The selected Gamma now uses the qualified note/pair/segment configuration in
[recovery results](gamma-recovery-results.md). The tuning and first held-out
sections below describe the original guarded-route candidate.

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
are diagnostic tests, not fresh held-out confirmation. Round 6 therefore used
unchanged Beta. This original guarded-700 configuration failed qualification;
the separate recovery report evaluates its replacement.

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
quote discount. These are neutral by default in code and enabled in the selected
Gamma configuration after fresh confirmation.
The short and premium segments overlap; their late-order shares cannot be added.

At this checkpoint, 226 offline tests pass on Python 3.9 and 3.14. The revised
note/pair/segment candidate completed eight screening weeks and three known
difficult weeks, all ranked. Its screening gain is €1,585.95/week over paired
Beta, with 94.574% worst on time. Settings were frozen before starting fresh
confirmation on `gamma-v09` … `gamma-v16`. See the
[recovery experiment report](gamma-recovery-results.md) for policy comparisons,
the exact candidate and acceptance gates. Saved-source snapshots keep running
experiments independent of later edits. The candidate subsequently passed all
eight fresh weeks, gaining €2,030.845/week, with 96.947% worst on time;
`models/gamma.json` now selects that note/pair/segment configuration.

## Note corrections

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

## Roster supply controls

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
separated supply scaling from town caps on the three known weak weeks and new
screening seeds. Neither policy was selected; see the recovery report's results.

## What was kept, and why

Beta refuses every route over 500 km. Gamma quotes routes over 500 km and up to
700 km only for `next_day` or `within_3_days`, with at least 24 hours from the
dealer's decision to the last feasible pickup and fewer than three of our long
orders still without a driver. Long gigs open at 1.0 × typical fee, rather than
0.8 ×. The global markup, trust charge, shorter-route fee ramp, trade-in refusal
and starter rescue stay Beta's.

This admits valuable work while limiting its tightest deadlines and backlog.
The guarded 600 km trial gained €930/week on 7 of 8 seeds; guarded 700 km gained
€1,232 on all eight. That was the only change kept in the original candidate.
Only guarded route admission was implemented from the original long-route
proposal; direct offers were not run. A public log of another team reported
poor offer acceptance and no useful margin gain; that outside evidence stopped
the offer proposal. It is a self-report, not our own experiment.

The original guarded-route candidate used `gamma:make_gamma`, with Beta's `win_target_bps=3000`,
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
pairs combine two orders into one gig. None was enabled in the original
guarded-route model. The selected replacement enables corrected pairs alongside
note and segment controls; the tables, trust build and guard, capacity valve,
brake and stale-gig review remain disabled. Their code remains available for
reproducing these experiments. No offers implementation was tested or included.

## Limits

- Eight tuning seeds, with settings chosen on them. The fresh held-out check
  above is needed before claiming the gain generalises.
- Gamma's worst tuning week is **92.975%**, slightly below the original plan's 93%
  target. Rounding it to 93.0% does not make it pass. Aggregate weeks do not
  establish the original plan's separate long-band lateness target either.
- The extra margin comes with a lower mean on-time share: 95.51% versus 96.35%.
  All eight weeks rank, but this is not a guarantee on new weeks or final clocks.
- Tenth place in ranking round 6 averaged about **€17.7k/week and 450 orders**;
  Gamma makes about **€12.5k and 260** on practice seeds. Those are different
  worlds. Gamma is a modest step, about **+11% margin over Beta**, not a route
  to the top ten.
- Neither this report nor the tuning sweeps establish final-mode readiness.

## Pre-Gamma research context

Historical trace studies from 14 November 2026 motivated the original Gamma
experiments. Their observations are separate from the tuning and confirmation
results above. Sources were Beta's saved weeks, the Alpha archive and private
reports under `runs/gamma/research/` (`luna-lanes-dealers.md`, `luna-drivers.md`,
`luna-volume.md` and their probe scripts). Fixed-table estimates used 675,490 old
quotes. The observations below do not establish gains for Delta or the selected
Gamma configuration.

1. **Higher targets alone did not establish a margin gain.** Steering to a 34% or 38% win share instead
   of 30% added 27 or 52 orders a week and €690 or €803 of margin, both inside the
   noise (eight seeds). This supports testing intake against expected value and
   capacity rather than assuming a lower markup will improve profit.
2. **The refused work is the largest untouched pool.** Beta refuses about 190 of
   1,034 requests a week: 110 over 500 km (€18,800 of list price), 21 trade-ins,
   about 62 with under 8 hours for a driver. Allowing 500–600 km added €1,401 a
   week, with that band 10.2% late. In the Alpha archive 500–599 km orders earned
   €98 each and 400–499 km €52, against €19 for the average order.
3. **Dealers are the same in every world, and few.** D01 sends 29.5% of all
   requests (302 a week), D02 12.1%, D03 8.0%; the top five send 61%. D01 accepts
   about 5% more than the world's level, D08 about 11% less.
4. **Trust arrives late and leaks.** Beta's trust count with D01 averages 0 on
   Monday, 7 on Tuesday, 15 on Wednesday, 20 on Thursday; it reaches 25 on
   Wednesday or Thursday, and in one week of eight never. D01 also takes 3.1 late
   orders a week, and each halves its count.
5. **Lanes carry a moderate, repeatable part of the price.** After removing each
   world's level, delivery-town effects correlate 0.46 between halves of the seeds
   and the busiest lanes 0.57. Deliveries to outlying towns bear 5–15% more;
   short hops inside the capital area 10–14% less.
6. **Waiting costs about €1,160 a week at most** (€637–1,692 over eight weeks):
   26% of bookings went to a driver who had seen the gig at a lower fee. A flat fee
   at the typical fee is not the fix: the one flat variant played paid 1.08 × the
   typical fee, Beta's ramp 0.96 ×.
7. **Drivers who live at the delivery end book most.** Of 2,208 bookings, 570 went
   to a driver whose home town is the delivery town and 304 to one whose home is
   the pickup town. The app only notifies drivers living within 30 km of the
   pickup. Direct offers are the one tool that reaches the delivery end, and we
   have never sent one.
8. **Driver ids are new in every world.** Any knowledge of drivers must be built
   inside the week. About 800 drivers view our gigs, 120–170 book, and two thirds
   of bookings come from drivers who booked from us earlier that week.

Random fee timing would still teach drivers the same running averages of
booked fee / first observed fee and waiting time. Random quote jitter was also
unsupported: about 4,600 randomized quotes were estimated necessary for a rough
win-curve slope, versus about 840 competitive quotes in a week, fewer per dealer
or lane. Random policy assignment within a week was proposed for comparing fee
policies, but was not run.

Other diagnostic evidence available when the original plan was written:

| Idea | Historical observation |
|---|---|
| A lower markup or higher win target alone | +27 to +52 orders, margin unchanged within noise. |
| All routes up to 600 km with no other change | That band was 10.2% late; no safe sub-group was large enough. |
| Options with under 8 hours for a driver | 11–18% late in every band; 4- and 5-hour limits fell below 90% on their worst seed. |
| Trade-ins | About 7 orders a week at €36 each, 33% late in Alpha, cause unknown. |
| A better note reader | Beta had 2.9 failed visits a week costing €96; the later recovery report measures the note-aware candidate. |
| Detecting the price war or the outage | The simple alert fired in 307 of 659 weeks; without labels it cannot be validated. Beta's markup shows no visible damage from chasing a war day. |
| Reacting to the competitor's morning move per dealer | No effect visible: our win rate is 29–32% whatever our share with that dealer was the day before. |
| Remembering drivers across weeks | Driver ids are new in every world. |
| Capping wins from the bulk order's yard | Beta already wins 75 of 275 such requests with 2 late. |

The original plan proposed accepting a change only with every held-out week
ranked, at least 93% worst on time, mean paired gain of at least €500 and at least
6/8 positive seeds; long-band lateness had a separate 5% ceiling. Those were
proposal gates, not official rules. The original guarded-route candidate missed
the 93% tuning buffer and later failed a held-out week; the selected replacement
has its own frozen gates and results in the [recovery report](gamma-recovery-results.md).

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
