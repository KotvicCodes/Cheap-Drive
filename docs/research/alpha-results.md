# Alpha results: why it trails the leaders

Measured on level-8 ordinary practice worlds, November 2026. Alpha is the
quote-pricing prototype described in [PROTOTYPES.md](../../PROTOTYPES.md); it
keeps the official starter's driver fees, posting and delivery execution.

## Headline

| | Margin / week | On time |
|---|---|---|
| Top level-8 practice teams (season 4) | about €16–17k | 95–97% |
| Alpha, tuned (trial 137) | about €6.2k | 91.2% worst week |
| Alpha, hand-made "proposed" set | about €1.4k | 90.8% worst week |

The automated search improved Alpha about fourfold over the hand-made
coefficients, but it still makes roughly a third of the leaders' margin with a
thin delivery buffer. Tuning quote coefficients alone will not close the gap.

## Where the money goes

Average per week over trial 137's six tuning seeds (`alpha-night-01`…`06`):

| Ledger line | € / week |
|---|---|
| Revenue | 21,382 |
| Driver fees | −14,273 (67% of revenue) |
| Late refunds | −411 |
| Failed visits | −352 |
| Waiting, release fees, undelivered | −135 |
| **Margin** | **about 6,200** |

Activity per week: 1,034 price requests, 297 won (29%), 342 gig bookings for
298 deliveries, 34 dropped gigs, 14 expired gigs, 43 deadline warnings and 11
failed visits. Failed visits were mostly cars not ready (45 over six weeks)
and missing plates (16).

## Why Alpha underperforms

1. **It wins too little work.** Alpha wins 29% of requests. Its winning quotes
   have a median of 1.37× the list price, its losing quotes 1.87×. At level 8
   the competitor prices 26–54% above list, so most losses were priced above
   the competitor. The cost floor, `max(reference fee, €/km × route)`, plus a
   margin and a scarcity allowance, often lands above the market.
2. **The scarcity term prices away scarce work instead of serving it.** The
   search pushed the scarcity allowance to the top of its range (€147.50 of a
   possible €150). Where few drivers are estimated nearby, Alpha quotes much
   higher and mostly loses. That protects on-time share, but gives up volume
   in exactly the regions the level-8 shortage affects.
3. **One price for every delivery option.** 61% of quotes charge the same price
   for all offered options. List prices and the competitor's prices differ by
   option. Alpha therefore under-charges urgent options and over-charges
   relaxed ones.
4. **Driver costs are not managed.** Fees come from the starter's schedule and
   take 67% of revenue. Alpha's cost estimate decides the quote only. It
   neither sets driver pay nor influences how quickly gigs are booked.
5. **Execution leaks margin and on-time share.** Drops, expired gigs, cars
   not ready, missing plates and late refunds cost about €760 a week. They
   also keep the worst week only about one point above the 90% minimum. These
   come from the starter's posting and recovery, which Alpha does not change.
6. **Coarse, public-only supply estimates.** Driver positions are known only
   while drivers work our gigs, and daily availability is hidden. The estimate
   of nearby drivers is therefore noisy, and reservations are internal
   guesses.

## Deeper trace analysis

From the full traces and end-of-week reveals of trial 137 (six seeds) and
the search as a whole. The reveals do not include competitor prices, driver
costs, or the timing of the outage and price war. Price comparisons below
therefore use the list price as a proxy, not the competitor's price.

- **Distance kills conversion.** Alpha wins 63.8% of requests under 100 km,
  23.6% at 100–199 km, 14.2% at 200–299 km and 5.3% at 300–399 km.
- **Price position.** Conversion is 87% at 1.1× the list price, 73% at 1.3×,
  57% at 1.4×, 29% at 1.6× and below 7% at 1.9–2.0×. About 76% of quotes are
  above 1.5× list and 33% above 2×.
- **Low estimated supply means almost no wins.** With fewer than five
  candidate drivers, Alpha won 0.3% of requests (2 of 667); with 20 or more,
  37%. The scarcity surcharge is steepest exactly there.
- **Winning more without capacity backfires.** Trial 10 won 64 more orders a
  week than trial 137, but averaged 81.4% on time and lost money. Its extra
  revenue went to driver fees and late refunds. Volume needs admission
  control tied to deliverable capacity.
- **Trust is modelled wrongly.** At level 8 each dealer accepts 1% more per
  on-time delivery, up to 25%, and a late order halves that count. Alpha's
  margin step instead reacts to quote wins and losses, regardless of whether
  the delivery was on time.
- **Deadline warnings are an early signal.** They preceded 76% of late
  orders, although only 37% of warned orders ended late.
- **Booking delay has a long tail.** The median gig books 6 minutes after
  posting, but the 90th percentile waits 13 hours. Driver fees average 1.17×
  the reference fee, with the 90th percentile at 1.5×, driven by the
  starter's escalation ladder.
- **Long routes are risky to deliver as well as to win.** About 22% of won
  300–399 km routes were late, against about 5% under 100 km; the long-route
  samples are small.

## What the tuning showed

- Six tuning seeds and 629 weeks in total. 41 of 82 fully evaluated
  candidates qualified on every seed.
- Well identified: route cost €0.50–0.57/km, fast margin feedback (5–7
  percentage points per quote), maximum margin around 37.5%.
- Barely matters: the cost per km to the first pickup.
- At the edge of the searched range: the scarcity allowance.
- The tuned coefficients were chosen on fixed seeds. The holdout check on
  eight untouched seeds is the guard against overfitting, and small
  differences between the top candidates are noise.

## Directions for Beta

- Admission control: cap expected wins by deliverable capacity, and target
  95% on time in every week.
- Price each option separately, anchored to its list price, and learn the
  competitor's level per lane and option instead of building up from a cost
  floor.
- Replace the scarcity markup with capacity-aware acceptance: win scarce
  work when a driver can actually be secured, and decline it otherwise.
- Own the driver-fee schedule: open lower where supply is good, and escalate
  earlier for urgent or scarce gigs to cut drops and expiries.
- Detect plate and readiness requirements before posting, to remove most
  failed visits.
- Track level-8 dealer trust from on-time and late deliveries, not from quote
  wins and losses.

