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

- Price each option separately, anchored to its list price, and learn the
  competitor's level per lane and option instead of building up from a cost
  floor.
- Replace the scarcity markup with capacity-aware acceptance: win scarce
  work when a driver can actually be secured, and decline it otherwise.
- Own the driver-fee schedule: open lower where supply is good, and escalate
  earlier for urgent or scarce gigs to cut drops and expiries.
- Detect plate and readiness requirements before posting, to remove most
  failed visits.
- Keep the delivery buffer at 93% or more in every week, not only on average.

A deeper analysis of the traces and end-of-week reveals is in progress and
may refine these numbers.
