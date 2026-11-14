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

Confirmation is in progress. No revised Gamma configuration is promoted yet.

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

The implementation passes 226 offline tests on Python 3.9 and 3.14; GitHub
checks also pass on Python 3.12. Historical Beta is unchanged.
