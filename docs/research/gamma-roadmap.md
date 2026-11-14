# Gamma roadmap (proposal, no code yet)

14 November 2026. Outcome: see [gamma-results.md](gamma-results.md); steps 1, 2
and 5 lost money when tested, step 3 was not run after outside evidence on direct
offers, the first half of step 4 (guarded long routes) was kept.

Written 14 November 2026 from Beta's saved weeks, the Alpha archive, the official
rules and three trace studies done that day. It is a plan for the next prototype,
**Gamma**, for someone else to implement one step at a time. Nothing here has been
played. Every euro figure marked "estimate" is an expectation to test, not a result.

Sources: [beta-results.md](beta-results.md), [alpha-results.md](alpha-results.md),
[PROTOTYPES.md](../../PROTOTYPES.md), the rules and handbook at
<https://spread.bahnexpress.com/kit/>, and the local, git-ignored reports under
`runs/gamma/research/` (`luna-lanes-dealers.md`, `luna-drivers.md`,
`luna-volume.md`, plus the probe scripts that produced the numbers quoted below).

## Where Beta stands

| | Margin / week | Orders / week | On time |
|---|---|---|---|
| Beta, eight practice seeds | €10,786 | 246 | 96.2% (worst 93.9%) |
| Beta, ranking round 5 (five weeks) | €10,108 | 238 | 95.5–98.7% |
| Tenth place, round 5 | about €14,200 | | |
| Leaders, round 5 | €15,400–15,800 | 350–450 | 92–99% |

The gap to the top ten is about €4,000 a week.

## What the studies changed

1. **Lower prices do not buy margin.** Steering to a 34% or 38% win share instead
   of 30% added 27 or 52 orders a week and €690 or €803 of margin, both inside the
   noise (eight seeds). Volume has to come from work that is worth more or costs
   less, not from a lower markup.
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

## The two ideas, answered

**Randomness in pricing.** Not as proposed, yes as an experiment tool.

- Random timing or size of fee raises does not help. The rules say each driver
  keeps a running mean of "booked fee ÷ first fee I saw" and of the minutes the
  gig stayed open. A shuffled schedule with the same average teaches the same
  belief. What lowers the belief is fewer public raises: keep the public fee flat
  and send the extra money privately (step 3).
- Random jitter on quotes to learn the market inside a week does not work either:
  about 4,600 randomised quotes are needed to estimate the slope of the win curve
  roughly, and a week has about 840 competitive quotes. Per dealer or per distance
  band it is hopeless.
- Where randomness earns its place: assigning gigs at random to an old and a new
  fee policy inside the same week (step 3). That gives a paired comparison on
  identical conditions, which is also the evidence the jury asks for.

**Understanding dealers and drivers over time.** Yes, and it is most of this plan:
steps 1 and 2 for dealers, steps 3 and 4 for drivers.

## Ground rules for every step

- Gamma is a subclass of `BetaDesk` in `gamma.py`, with `models/gamma.json` and
  `tests/test_gamma.py`. Every new behaviour sits behind a setting that defaults
  to off. **With all settings off, Gamma must reproduce Beta to the cent**
  (`beta-01` gives €8,694, `beta-08` €8,743). Make that the first test.
- One step per pull request, in the order below. PR title format:
  `Gamma model γ: <what it does>`. Follow [PROTOTYPES.md](../../PROTOTYPES.md):
  discuss before code, publish only with approval.
- Any random choice uses a generator seeded from the world id and the order id,
  so a week replays identically.
- Journal everything a later analysis needs (listed per step). Luna could not
  answer several questions because the traces lacked the fields.
- Evaluate with `scripts/sweep.py`, eight worlds at once, on `beta-01 … beta-08`
  for choosing settings and on eight fresh seeds `gamma-h01 … gamma-h08` that are
  played only once per step, for the verdict. Worlds are deterministic, so compare
  each variant with Beta **on the same seed** and report the per-seed differences.
- Keep a step when, on the held-out seeds: every week is ranked, the worst week is
  at least 93% on time, and the mean paired gain is at least €500 with at least 6
  of 8 seeds positive. Otherwise leave the setting off and write down why.

## Step 1. Price what is known before the week starts

Beta uses one markup for every dealer and lane. Multiply it by two fixed tables
learned from 675,490 old quotes.

```text
quote(option) = list price × world markup × place factor × dealer factor × (1 + 0.01 × trust)
```

- `world markup` is Beta's tracker, unchanged: it still steps on every win and
  loss to a 30% share, so the tables only redistribute where we are dear and cheap.
- Place factor: the lane's value if listed, otherwise the delivery town's,
  otherwise 1.00. Dealer factor: listed value or 1.00. Clamp the product of the
  two to 0.88–1.15.
- Starting values (measured effect, pulled part of the way to 1.00 where the
  spread between seeds was large). Place ids are the map's lowercase ids; check
  them against the map on start-up and fail loudly on an unknown id.

| Dealer | Factor | | Delivery town | Factor | | Lane | Factor |
|---|---|---|---|---|---|---|---|
| D01 | 1.04 | | lappeenranta | 1.10 | | espoo → vantaa | 0.90 |
| D03 | 0.97 | | mikkeli | 1.08 | | helsinki → vantaa | 0.90 |
| D08 | 0.91 | | lahti | 1.05 | | helsinki → espoo | 0.91 |
| D10 | 0.95 | | ylivieska | 1.05 | | hyvinkaa → tampere | 1.10 |
| D19 | 0.94 | | rauma | 1.05 | | hyvinkaa → raisio | 1.10 |
| | | | kouvola, salo, pori | 1.04 | | vantaa → pori | 1.08 |
| | | | vantaa | 0.95 | | | |

- Settings: `dealer_table` on/off, `place_table` on/off, `table_strength`
  (0, 50, 100: how much of each factor's distance from 1.00 to apply).
- Journal per quote: both factors, the world markup, the lane.
- Sweep: off / dealers only / places only / both, at strength 50 and 100.
- Estimate: €500–1,000 a week. Risk: the tables came from Alpha, which sent one
  price for all options; the lane effects are noisy (spread 4–22% between seeds).

## Step 2. Treat trust with the big dealers as an asset

Only for dealers that send at least 60 requests a week in every world: D01, D02,
D03, D04 (a fixed list; ids persist).

**Build it early.** While such a dealer's trust count is below 25, quote its safe
options at a discount so the count fills on Monday and Tuesday instead of by
Thursday. Safe means: route up to 200 km and at least 12 hours from the dealer's
decision to the last pickup.

- Setting `trust_build_bps`: 0, 500, 1000 (discount on the quote).
- Why it should pay: D01 gives about 80 orders and €8,800 of revenue a week. Each
  point of trust is 1% on everything it buys afterwards. Reaching 25 a day and a
  half sooner is worth roughly €600 a week on D01 (estimate), against about €200
  of discount on the first 25 orders.

**Protect it.** A late order to D01 at a count of 20–25 costs the refund (about
€12) plus roughly 10% on its next 15–20 orders, about €180 (estimate). Beta treats
it like any other order.

- Setting `trust_guard`: for a big dealer whose count is 10 or more, do not quote
  options with under 12 hours for a driver (Beta's general limit is 8).
- In the deadline rescue, serve big-dealer orders first.
- Journal per quote: the dealer's count, whether the discount or the guard
  applied. Journal every change of a count with its cause.
- Sweep: build 0/500/1000 × guard off/on.
- Estimate: €500–1,000 a week together. Risk: discounted wins also move the world
  markup up; leave that alone at first, it self-corrects to the 30% share.

## Step 3. Stop raising in public; pay the extra in private

Beta opens at 0.8 × the typical fee and raises in 8 public steps to 1.5 ×. About
half the gigs book at once at 0.8 ×; the rest wait, and every public raise teaches
the drivers who viewed the gig. Replace the ramp, not the low opening.

```text
public fee:   0.8 × typical, flat, until 6 hours before the deadline warning;
              then 1.2 ×; 1.5 × at the warning (two raises instead of seven)
private:      after 60 minutes without a booking, direct offers in rounds
              round 1 at 1.0 × typical, later rounds at 1.2 ×
```

- Offer limits from the rules: an offer lasts 10 world minutes; at most 3 open
  per gig; at most 3 per driver per day; nobody reads them 23:00–07:00. Start a
  new round when the last one has expired. Read the offer action and its result
  events in the kit's API reference and the pinned client before coding.
- Whom to offer to, in this order, skipping drivers who lack the licence or the
  premium rating the gig needs, who hold one of our gigs overlapping it, or who
  have had 3 offers today:
  1. a driver finishing one of our gigs within 30 km of the pickup in the next
     3 hours;
  2. a driver whose home is within 30 km of the **delivery** place and who viewed
     any of our gigs today (a view shows they are using the app today);
  3. a driver who viewed this gig and did not book it;
  4. a driver who booked from us earlier this week, home within 30 km of the
     pickup or the delivery.
- Keep a per-driver record for the week: home, licence, rating, roster drops,
  last view minute, gigs booked and at what fee ÷ typical fee, gigs dropped,
  offers sent/read/taken/declined today, where and when their current gig of ours
  ends.
- **Measure before trusting it.** We have no data on offers at all. First run:
  assign each order at random (seeded by order id) to the offer policy or to
  Beta's ramp, half each, in the same weeks. Compare per arm: fee ÷ typical fee,
  minutes to book, drops, share reaching the warning, late share, and for offers
  the read and take-up rate per candidate kind and per fee. Second run: whole
  weeks on one policy each, to see whether the Monday-to-Friday fall in gigs
  booked at the opening fee (63% → 43% under Beta) flattens.
- Settings: `offers` off/on/random-half, `offer_after_minutes` (30, 60, 120),
  `offer_fee_bps` per round, `public_raise_hours_before_warning` (6).
- Estimate: up to €1,000 a week. The ceiling is the €1,160 that waiters are paid
  above the fee they first saw. Unknowns: whether a booking through an offer
  teaches the gig's viewers like a public raise does; how many offers are read.

## Step 4. Take long routes that a delivery-end driver can do

Depends on step 3's offers working. Beta refuses every route over 500 km; that is
110 requests and €18,800 of list price a week, and these orders earn two to five
times the average.

- Quote routes of 500–700 km only when all hold: the option is `next_day` or
  `within_3_days` (never `same_day`: 35% late on long routes); at least 24 hours
  from the dealer's decision to the last pickup; fewer than 3 long orders of ours
  are still without a driver.
- Post them at 1.0 × the typical fee, not 0.8 ×, and send round-1 offers at once
  to drivers living within 30 km of the delivery place, without the 60-minute
  wait. Long gigs cost a driver the trip home; a driver who lives there has none.
- Settings: `long_max_km` (500 = off, 600, 700), `long_open_cap` (3),
  `long_opening_fee_bps` (10000).
- Journal per long order: candidates found, offers sent and taken, hours to book.
- Keep only if the long band itself is at most 5% late on the held-out seeds.
- Estimate: €1,400 a week is what 500–600 km gave with no special handling and
  10% late; up to about €3,000 if 600–700 km can be delivered too. This is the
  largest single item and the least certain.

## Step 5. Let the win share follow free capacity (only if steps 1–4 hold)

The best live sign of trouble is the number of won orders still without a driver:
2.2% late with none, 4.5% with 3–5, 6.7% with 6–10, 11.3% with 11 or more.

- Win target 34% while that number is 5 or less, 30% at 6–10, 26% above 10.
- On its own this is worth nothing measurable (finding 1). It becomes useful when
  the earlier steps make each order worth more, and as a brake when they add load.

## Not in this plan, and why

| Idea | Why not now |
|---|---|
| Random fee timing; random quote jitter to learn the market | See "The two ideas, answered". |
| A lower markup or higher win target alone | +27 to +52 orders, margin unchanged within noise. |
| All routes up to 600 km with no other change | That band was 10.2% late; no safe sub-group was large enough. |
| Options with under 8 hours for a driver | 11–18% late in every band; 4- and 5-hour limits fell below 90% on their worst seed. |
| Trade-ins | About 7 orders a week at €36 each, 33% late in Alpha, cause unknown. Needs the note reader first. |
| A better note reader | Beta has 2.9 failed visits a week costing €96. Worth doing before trade-ins, not for its own sake. |
| Detecting the price war or the outage | The simple alert fired in 307 of 659 weeks; without labels it cannot be validated. Beta's markup shows no visible damage from chasing a war day. |
| Reacting to the competitor's morning move per dealer | No effect visible: our win rate is 29–32% whatever our share with that dealer was the day before. |
| Remembering drivers across weeks | Driver ids are new in every world. |
| Capping wins from the bulk order's yard | Beta already wins 75 of 275 such requests with 2 late. |

## What it could add up to

| Step | Estimate, € / week | Confidence |
|---|---|---|
| 1. Dealer and place tables | 500–1,000 | medium: stable effects, small |
| 2. Trust built early and guarded | 500–1,000 | medium: the rule is exact, the sizes are estimates |
| 3. Flat public fee and private offers | 0–1,000 | low: never tested |
| 4. Long routes through delivery-end drivers | 1,400–3,000 | low: needs step 3 |
| 5. Win share follows capacity | 0–700 | low |

If most of it holds, Gamma lands near €13,000–15,000 a week, the level of round
5's top ten. The estimates are not independent and will not simply add.

## The final comes first

At the time of writing there is no final-mode runner: Beta has only played
practice clocks. The final is on Sunday 15 November at 08:00 Helsinki, with test
finals on Saturday at 14:00 and 20:00. A runner that plays Beta on the live clock
is worth more than any step above, because without it there is no score at all.
No Gamma step should go into the final unless it has passed its held-out seeds
and a test final.
