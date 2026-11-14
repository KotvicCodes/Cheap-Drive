# Gamma recovery experiments

Level-8 ordinary practice, 14 November 2026. These runs follow the original
guarded-700 candidate's failed held-out check. See [the original results](gamma-results.md)
for that failure and the completed round-6 Beta leaderboard runs.

## Screening

Every gain below is the mean margin difference against unchanged Beta on the
same seeds. Means include every completed week. The first screening block is
`gamma-v01` through `gamma-v04`; the strongest candidate continued through
`gamma-v08`. These seeds selected the candidate and cannot confirm it.

| Arm | Weeks | Gain / week | Positive | Ranked | Worst on time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Guarded 700 km, 48-hour long slack | 4 | +€770.64 | 3 | 4/4 | 93.651% |
| Guarded 700 km + segment controls | 4 | +€798.69 | 3 | 4/4 | 91.698% |
| Segment controls + 48-hour long slack | 4 | +€539.91 | 3 | 4/4 | 92.885% |
| Guarded 700 km + 38% target + corrected brake | 4 | −€329.89 | 2 | 4/4 | 90.278% |
| Notes + guarded 700 km | 4 | +€184.59 | 3 | 4/4 | 92.405% |
| Notes + segments | 4 | +€643.78 | 3 | 4/4 | 94.961% |
| Notes + segments + 48-hour long slack | 4 | +€586.86 | 3 | 4/4 | 94.841% |
| Notes + corrected pairs + segments, initial screen | 4 | +€1,846.53 | 3 | 4/4 | 94.574% |
| Notes + corrected pairs + segments, complete screen | 8 | +€1,585.95 | 6 | 8/8 | 94.574% |

The complete candidate screen earned €13,372.28/week versus Beta's €11,786.33.
Its mean weekly on-time share was 97.544%, versus 96.507% for Beta. The eight
weeks contained nine failed visits; these fixes do not eliminate every failure.

On the common first four seeds:

- Adding corrected pairs to notes + segments added **€1,202.75/week**.
- Adding segment controls to notes + guarded 700 km added **€459.19/week**.
- Adding notes to the segment arm reduced failed visits from **22 to 1** and
  raised worst-week on time from **91.698% to 94.961%**, while reducing mean
  margin by **€154.91/week**.

These are comparisons between policy combinations. They do not isolate the
profit effect of each repaired line: the old buggy pair and brake implementations
were not replayed on these new seeds. A functional regression fix need not make
the entire policy profitable; the corrected brake arm still trailed Beta.

## Known difficult weeks

These are diagnostics on previously exposed seeds, not fresh confirmation.
The selected pair candidate ranked on all three, with 94.273% worst on time.

| Seed | Beta margin | Candidate margin | Difference | Candidate on time |
| --- | ---: | ---: | ---: | ---: |
| `gamma-h07` | €8,656.79 | €8,297.48 | −€359.31 | 94.273% |
| `gamma-t02` | €10,704.72 | €13,554.91 | +€2,850.19 | 96.283% |
| `gamma-t04` | €10,245.77 | €10,052.80 | −€192.97 | 96.154% |

The pooled long-route service audit counts won, noncancelled orders above
500 km, including undelivered orders as late. Ledger late refunds capture
tighter note promises as well as nominal deadlines. Its totals reconcile to
each week's score: **6/144 (4.17%)** long orders were late in screening and
**2/52 (3.85%)** in these stress tests.

Supply scaling alone ranked 3/3 stress weeks but lost €546.75/week against
Beta. Adding town caps, pending reservations and the sparse-town opening floor
lost €1,712.68/week. Adding notes and segments to those controls lost
€870.05/week; adding corrected pairs as well lost €778.42/week. All four arms
ranked 3/3. Town caps improved service but sacrificed margin on this sample;
the proposed universal €1,800–2,400 profit gain is not established.

The completed four-seed supply screen (`gamma-v01` … `gamma-v04`) also argues
against selecting those controls:

| Supply arm | Gain / week versus Beta | Ranked | Worst on time |
| --- | ---: | ---: | ---: |
| Scaling only | +€561.31 | 3/4 | 88.768% |
| Scaling + town caps and sparse-town floor | −€757.66 | 4/4 | 90.769% |
| Above + notes and segments | −€753.12 | 4/4 | 92.188% |
| Above + corrected pairs | +€179.79 | 4/4 | 94.819% |

The same four seeds with notes + pairs + segments and supply controls disabled
gained €1,846.53/week. These supply diagnostics did not alter the frozen selection.

## Frozen confirmation plan

Selection was frozen at 13:58 UTC, before any candidate result on `gamma-v09`
through `gamma-v16`. The cached unchanged-Beta baseline uses those exact seeds.
Remaining supply screening is diagnostic and cannot change the selected arm.
Source copies and SHA-256 manifests are retained privately with every job.

Factory: `gamma_notes:make_gamma_notes_pairs`.

```json
{
  "max_km": 500,
  "long_max_km": 700,
  "win_target_bps": 3000,
  "opening_fee_bps": 8000,
  "pairs": 1,
  "short_fee_km": 45,
  "short_opening_fee_bps": 11000,
  "short_km": 45,
  "short_bps": 9200,
  "premium_opening_fee_bps": 10500,
  "premium_min_slack_minutes": 600
}
```

Brake and supply controls stay disabled. Pair defaults are fresh opening 7200
bps, waiting-car rescue opening 7800 bps with a new 60-minute flat period, and
at most 60 minutes of idle wait at the second pickup. Other guarded-route and
fee defaults remain unchanged.

Acceptance requires all eight fresh weeks ranked, worst on time at least 93%,
mean paired gain at least €500/week, at least six positive paired weeks, and
pooled long-route lateness at most 5%. A repeat of one screening seed must also
reproduce its score and ledger using the final code with supply controls off.
No settings may be changed using these confirmation outcomes. A failed gate
leaves Beta as the ranking model.

## Confirmation verdict

**Passed all frozen gates.** `models/gamma.json` now selects the note/pair/segment
configuration above; brakes and supply controls stay disabled.

| Model | Margin / week | Ranked | Worst / mean on time | Orders / week |
| --- | ---: | ---: | ---: | ---: |
| Beta | €10,047.87 | 8/8 | 93.671% / 95.692% | 241.625 |
| Gamma | €12,078.71 | 8/8 | 96.947% / 98.062% | 256.250 |

Mean paired gain is **€2,030.845/week (+20.21%)**, positive on **8/8** seeds.
Long-route lateness is **1/148 (0.676%)**, including one undelivered long order.
Across all routes, 40/2,050 orders were late, including 12 undelivered orders.
The final-code repeat matched score, ledger, events, visit failures and rejections.

| Seed | Beta margin | Gamma margin | Gain | Gamma on time |
| --- | ---: | ---: | ---: | ---: |
| `gamma-v09` | €10,982.60 | €13,013.17 | +€2,030.57 | 97.119% |
| `gamma-v10` | €7,809.27 | €10,349.11 | +€2,539.84 | 97.692% |
| `gamma-v11` | €13,243.86 | €14,130.65 | +€886.79 | 98.162% |
| `gamma-v12` | €10,822.78 | €13,453.38 | +€2,630.60 | 97.398% |
| `gamma-v13` | €6,896.33 | €8,546.16 | +€1,649.83 | 99.190% |
| `gamma-v14` | €11,067.42 | €13,495.76 | +€2,428.34 | 98.795% |
| `gamma-v15` | €10,979.91 | €12,842.54 | +€1,862.63 | 96.947% |
| `gamma-v16` | €8,580.77 | €10,798.93 | +€2,218.16 | 99.194% |

A practice-server restart returned HTTP 502 and interrupted active worlds.
Incomplete attempts were discarded and rerun on the same seeds with unchanged
code and settings; no candidate was retuned. Confirmation had 22 failed-visit
events across 11 unique orders, so the remaining parser limitations still matter.
Further settings experiments were parked before launch for [Delta](delta-handoff.md).

## Limits and verification

The note parser has bounded Finnish/Swedish/English vocabulary. A remaining
screening failure involved a misspelled weekday; finding a readiness clock does
not mean the complete date was understood. An offline fact-coverage audit cannot
establish that every failed visit will be prevented.

Practice weeks are deterministic for shared seeds. Eight fresh confirmation
weeks can reject this candidate but cannot guarantee performance on every
market or final clocks. The runner maintains up to eight unfinished practice
worlds and refills slots as jobs finish. Running jobs use immutable source
copies; raw traces, reveals, job records and credentials remain git-ignored.

The implementation passes 226 offline tests on Python 3.9 and 3.14. GitHub CI
covers Python 3.9, 3.12 and 3.14. Historical Beta is unchanged.

To reproduce a paired comparison with the selected configuration, load practice
credentials and run from the repository root:

```bash
python compare.py run --model-a models/beta.json --model-b models/gamma.json \
  --levels 8 --seeds gamma-v09 gamma-v10 gamma-v11 gamma-v12 \
    gamma-v13 gamma-v14 gamma-v15 gamma-v16 \
  --workers 8 --fast --output runs/gamma/reproduce-confirmation
```

Those seeds are now exposed. Delta must reserve new seeds for its own confirmation.
