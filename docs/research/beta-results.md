# Beta results

Measured on level-8 ordinary practice worlds on 14 November 2026: 192 weeks in
six sweeps, on eight seeds (`beta-01` … `beta-08`). Beta is described in
[PROTOTYPES.md](../../PROTOTYPES.md). Alpha's results are in
[alpha-results.md](alpha-results.md).

## Headline

| | Margin / week | Weeks ranked | On time, worst / mean | Orders / week |
|---|---|---|---|---|
| Alpha, tuned (its six tuning seeds) | about €6,200 | 6 of 6 | 91.2% / 95.0% | 297 |
| **Beta** (eight seeds) | **€10,786** | **8 of 8** | **93.9% / 96.2%** | 246 |
| Leading teams, ranking round 5 | about €14–15k | 5 of 5 | 92–99% | 350–450 |

Beta's weeks range from €8,694 to €17,209. Seeds `beta-05` … `beta-08` were not
used for any choice before the route limit; they are the weaker half (€8.7–9.3k
each), so expect about €9–11k on an unseen week, not the best seeds' figures.
Alpha and Beta were measured on different seeds; the comparison is of levels,
not a paired test.

Per order, Beta earns about €44 against Alpha's €21: revenue €111, driver fees
€65 (59% of revenue, Alpha 67%), refunds and failed visits under €2.

## What changed, in the order it was found

Each row adds one idea to the row above. Margins are means over the seeds
played at that step, so rows are not all on the same seeds.

| Step | Seeds | Margin / week | Ranked | On time, worst |
|---|---|---|---|---|
| List price × 1.35, starter fees | 2 | −€28 | 0 of 2 | 76.7% |
| Markup 1.5; decline tight options and trade-ins | 3 | €8,433 | 2 of 3 | 89.5% |
| Fee rises over the order's own time, not over 5 hours | 3 | €9,945 | 3 of 3 | 90.0% |
| Fee opens at 0.8 × typical fee | 3 | €11,963 | 3 of 3 | 90.5% |
| Markup follows the market to a 30% win share | 3 | €14,879 | 3 of 3 | 92.5% |
| The same, on four more seeds | 8 | about €11,650 | 7 of 8 | 86.4% |
| Decline routes over 500 km | 8 | €10,786 | 8 of 8 | 93.9% |

## Why each step helped

1. **Anchor on the list price.** Away from the shortest routes the typical
   driver fee is about equal to the list price (0.98–1.00 × over 50 km, 0.68 ×
   under 50 km), and the competitor sits 26–54% above list. Alpha's cost floor
   plus margin plus scarcity landed above the competitor on most long lanes: it
   won 64% of requests under 100 km and 5% at 300–400 km. A plain multiple of
   each option's list price wins on every distance.
2. **Winning alone loses money.** At 1.35 × list with starter fees Beta won 356
   orders a week, paid drivers well above the typical fee (1.24 × at a 1.45
   markup) and delivered 82% on time. The fee leak had two parts. A next-day car posted in the afternoon
   climbed to 1.5 × that evening, although most drivers book only the next day.
   And the share of gigs booked at the opening fee fell from 82% on Monday to
   55% on Friday, while views per gig rose from 12 to 34: drivers had learned
   to wait for our raises.
3. **Spread the rise over the order's own time.** With the cap arriving at the
   deadline warning, driver fees fell from 74% to 69% of revenue at the same
   prices.
4. **Open below the typical fee.** At 0.8 ×, 56% of gigs still booked at the
   opening fee and driver fees fell to 61% of revenue. At 0.6 × too few gigs
   booked in time; 0.7 × and 0.9 × were within noise of 0.8 ×.
5. **Let the markup find the market.** With a fixed 1.5 a cheap world gave 124
   orders and a dear one 335. Stepping the markup on each win and loss took the
   cheap world from €5,901 to €8,394 and removed the one unranked week.
6. **Long routes cause half the late orders.** Over the eight seeds, routes
   over 600 km were late 22% of the time and earned −€1 an order; 500–600 km,
   17%; under 500 km, 2.5–4.7%. One held-out week (`beta-08`) fell to 86.4% on
   time through them. The limit costs about €850 a week on average and makes
   every week rank.

## Tried and not kept

- A cap on orders waiting for a driver: at the final settings it never bound
  (identical weeks with and without it).
- A separate, lower markup for short routes: +€120 a week, inside the noise.
- Declining premium cars and private addresses: fewer orders, no gain in
  on-time share.
- Opening at the typical fee or 1.2 ×; a fee that never rises.
- A 10-hour or 5-hour minimum for the driver in place of 8.

Higher-margin settings that also ranked on all eight seeds, with a thinner
on-time buffer: a 600 km limit (€12,187, worst week 92.9%) and a 34% win share
(€11,476, worst week 93.4%).

## Ranking round 5, level 8

Played with `models/beta.json` on 14 November. These are the public ranking
worlds, the same for every team.

| Run | Margin | On time | Orders |
|---|---|---|---|
| 1 | €7,872 | 97.0% | 234 |
| 2 | €12,396 | 98.7% | 232 |
| 3 | €9,653 | 98.2% | 221 |
| 4 | €12,804 | 96.9% | 258 |
| 5 | €7,816 | 95.5% | 244 |
| **Total** | **€50,541** | all five ranked | 1,189 |

That placed 41st of the 65 teams ranked in the round when it closed, level with
the organisers' own "House best" (€50,660). The round's leaders totalled
€77–79k and the tenth-placed team about €71k: the final's top ten needs roughly
40% more margin than Beta makes.

## Ranking round 6, level 8

Played with unchanged `models/beta.json` on 14 November ("Saturday 12:00").

| Run | Margin | On time | Orders |
|---|---|---|---|
| 1 | €12,273 | 96.9% | 255 |
| 2 | €13,501 | 96.1% | 257 |
| 3 | €9,191 | 98.3% | 236 |
| 4 | €12,596 | 99.2% | 244 |
| 5 | €11,968 | 96.6% | 263 |
| **Total** | **€59,529** | all five ranked | 1,255 |

That placed 45th of the 58 teams ranked in the round when it closed (House best
€77,560; tenth place about €91k; leaders €99–110k).

## Limits

- Eight seeds, and the settings were chosen on them. Differences under about
  €1,000 between variants are noise.
- Beta wins about 250 orders a week where the leaders win 350–450. Its on-time
  share (96%) leaves room to take more work; how to do that without the late
  long routes is open.
- Orders that reach the deadline warning without a driver are still rescued by
  the starter's steep fees, at about 2 × the typical fee, and most arrive late.
- Notes about ready times on a later day ("valmis huomenna klo 11.30") are
  still read by the starter's reader, which misses the day. They cause most
  remaining failed visits.
- Trade-ins and routes over 500 km are declined outright, not priced.
- No final mode yet: Beta has only been played on practice clocks.

## Reproduce

```bash
python scripts/sweep.py runs/beta/check plan.json
```

with `plan.json`:

```json
{"factory": "beta:make_beta", "level": 8,
 "seeds": ["beta-01", "beta-02", "beta-03", "beta-04", "beta-05", "beta-06", "beta-07", "beta-08"],
 "variants": {"beta": {"win_target_bps": 3000, "opening_fee_bps": 8000, "max_km": 500}}}
```

Practice worlds are deterministic: `beta-01` gives €8,694 and `beta-08` €8,743,
with or without `"fast": true`.
