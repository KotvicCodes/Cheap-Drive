# Prototype conventions

## Names

Use one Greek letter for each successive prototype, starting with **Alpha**:

Alpha → Beta → Gamma → Delta → Epsilon → Zeta → Eta → Theta → Iota → Kappa → Lambda → Mu → Nu → Xi → Omicron → Pi → Rho → Sigma → Tau → Upsilon → Phi → Chi → Psi → Omega.

Use the title-case name in reports and lowercase filenames, such as
`models/alpha.json`. The existing fixed-price model and official starter are
pre-Alpha baselines; preserve their identities for comparison. Parameter tuning
within a prototype does not automatically need a new Greek letter. Introduce
the next name when we agree on a new strategy experiment.

## Discussion and publication

Discuss the strategy with the user before writing prototype code. Keep work
local until the user explicitly approves publishing the PR. Put each
prototype's code, model configuration, tests and technical documentation in its
PR; changes go through PR review rather than directly to `main`. Approval to
publish a PR does not authorize merging it.

Keep the evolving story, brainstorming history, personal reasoning and lessons
in `prototype-story/STORY.md`. The directory `/prototype-story/` is gitignored.
Append to the story as prototypes evolve so earlier decisions and results
remain intact. Do not include this journal in a commit, PR description,
issue, Actions artifact or other publication. Technical specifications needed
to review the implementation belong in the PR, with the user's approval.

Git ignores do not remove tracked history, prevent force-adding files or back
up local files. The story stays in this checkout unless separately backed up
privately. Public challenge constraints live in [docs/challenge.md](docs/challenge.md),
operational instructions in [docs/reference.md](docs/reference.md), and measured
prototype evidence in `docs/research/`; these are separate from the local story.

## Alpha

Alpha prices each request from its route, the estimated nearby driver supply
and a per-dealer margin that reacts to quote wins and losses.

For each feasible delivery option, Alpha quotes in euros:

```text
C = max(reference fee, distance coefficient × route km)
    + pickup coefficient × km to the first pickup
Q = C + max(minimum margin, dealer margin × C)
    + scarcity coefficient / (nearby candidate drivers + 1)
```

The proposed starting coefficients are €0.45/km for the route, €0.30/km to
pickup, €40 scarcity, 25% initial dealer margin and €20 minimum margin.
Feedback increases a dealer's margin by 3 percentage points after a quote win
and decreases it by 3 points after a loss, bounded between 15% and 60%.
Rejected actions and deliberately uncompetitive declines do not train it.
Prices are rounded upward once to whole cents. The reference fee covers the
whole request, including both trade-in legs.

`models/alpha-proposed.json` preserves those starting values. The initial
comparison uses `models/alpha-conservative.json`: €0.70/km, €0.50/km, €80
scarcity and 35% initial margin, with the same feedback bounds and step.
`models/alpha.json` holds the tuned configuration: €0.53/km route, €0.59/km
pickup, €147.50 scarcity, 14% initial margin within 1–37.5%, a 7-point
feedback step, €5 minimum margin and a 60 km nearby radius. It was selected
by an automated level-8 search on six shared practice seeds; see Evaluation.

### Public inputs and limits

- Road distances and driving minutes come from the official map. Route
  distance includes repositioning between consecutive cars.
- Candidate drivers meet the public premium-rating/experience requirements,
  are not held by one of our gigs or reserved by another pending quote, and
  pass an estimated time-window check for the option. Reserve one candidate
  per quote until it loses, is rejected, is cancelled, or receives a booking.
  These reservations are internal estimates; they do not book real drivers.
- Use a driver's visible or last observed position for up to two world hours;
  otherwise use the public home town. The nearby radius is 50 road km.
  Private daily schedules, other companies' work and public-transport costs
  are hidden. Counts therefore estimate supply, not confirmed availability.
- Window checks allow 30 world minutes after the response deadline for
  posting/booking, account for public opening hours and the starter's limited
  note parser, and include its charging delay. Hidden constraints, manual
  gearboxes and notes the parser misses can still invalidate a delivery.
- Alpha evaluates every offered option, but declines combined multi-car
  routes over the 12-hour driving cap rather than planning split capacity.
  When no candidate appears feasible, it sends a deliberately uncompetitive
  quote to avoid silence's goodwill cost. Even that quote could theoretically
  win; it is not an API-level rejection.
- Driver fees, posting, recovery and delivery execution use the official
  starter. A cost estimate neither sets driver pay nor guarantees profit.
  Escalation, incidents and scarcity can cost more than the estimate.
- Levels 1–3 retain starter quotes without competitive-price learning.

### Evaluation

Use the existing `compare.py` from PR #1. Initial tuning compares both sets at
level 8 on `alpha-tune-01` and `alpha-tune-02`. Keep
`alpha-validation-01` separate from tuning. All are ordinary practice worlds,
not ranking or final runs. Execute sequentially and do not disturb another
process's worlds; the team shares a limit of eight unfinished worlds.

Rank candidates by qualified weeks first, then mean gross margin across all
sampled weeks. Do not recommend either if neither qualifies. Inspect won
orders, late/undelivered work and action failures alongside the ranking: fewer
orders can make qualification easier. A few seeds are a pilot experiment,
not proof of generalization. Save configuration, code hashes, traces and raw
scores under ignored `runs/`, and append the private interpretation to the
local story.

The selected configuration came from an automated search (Optuna TPE) over
the nine settings, playing each candidate on the same six level-8 practice
seeds. Per week, loss = −margin + 1000·max(0, 92 − on-time %)²; a week that
misses the delivery minimum scores 20,000 plus the shortfall, whatever its
margin. A candidate's loss is the mean over seeds plus half the standard
deviation. Candidates clearly worse than the median after two seeds stopped
early. Selection on fixed seeds can overfit; separate holdout seeds are the
check, and small differences between top candidates are noise.

Measured results and the reasons Alpha trails the leading teams are in
[docs/research/alpha-results.md](docs/research/alpha-results.md).

## Beta

Beta changes two things Alpha left alone or got wrong: how the quote is
anchored, and who owns the driver fee. It has three tuned parameters
(`models/beta.json`).

### Quote: list price times a markup that follows the market and dealer trust

```text
quote(option) = option's list price x markup x (1 + 0.01 x dealer's on-time orders, at most 25)
after a win:   markup x (1 + 0.02 x (1 - win share))
after a loss:  markup x (1 - 0.02 x win share)
```

- Each option is priced from its own list price, so the dealer still chooses
  by speed. Alpha built a price up from a cost floor and sent the same price
  for every option; that priced long lanes out of the market.
- The steps cancel when the share of won quotes equals `win_target_bps`
  (30%), so the markup settles where this week's competitor gives that share.
  It starts at 1.5 and stays within 1.2-2.0. A world's competitor level
  (26-54% above list), its day factors and the price-war day are never
  observed; wins and losses are.
- The trust term is the level-8 rule itself: a dealer accepts 1% more per
  order delivered to it on time, up to 25, and a late order halves the count.
  Beta counts it from its own ledger: a revenue line adds one, a late refund
  takes that back and halves.

### Driver fee: open low, pay for time only when time is short

```text
fee(t) rises in 8 even steps from opening_fee x typical fee at posting
       to 1.5 x typical fee at the deadline warning (3 hours before the last pickup)
```

The starter opens at the typical fee and adds 10% every hour whatever the
deadline. A next-day car then climbs to 1.5x on the evening before, while most
drivers cannot yet book that day, and drivers learn that our fees rise. Beta
opens at `opening_fee_bps` (80%) and spreads the same rise over the time the
order really has. After the deadline warning the starter's steep rescue fees
still apply. Steps are never closer than an hour.

### What Beta declines

A decline is a quote at ten times the list price: it costs no goodwill, and it
does not teach the markup.

- Routes longer than `max_km` (500 km).
- Options that leave a driver less than 8 hours between the dealer's decision
  and the last pickup that still meets the deadline (by road minutes, stated
  closing times and the car's ready time). Other options of the same request
  are still quoted.
- Trade-ins (two cars).

### Also

- Notes: a car without plates is posted `withPlates`, a manual gearbox with a
  manual-licence audience. Other notes stay with the starter's reader.
- Levels 1-3 keep starter quotes.
- Posting, retries, expiry and deadline rescue are the starter's.
- `passive_wake_events` is declared, so fast practice (`--fast`) can deliver a
  lost quote with the next decision event; the markup step still happens
  before that decision.

### Evaluation

`scripts/sweep.py` plays a grid of settings on shared seeds, eight worlds at a
time, and keeps every trace and reveal under ignored `runs/`. `scripts/board.py`
plays ranking runs. Results, the rejected variants and the limits are in
[docs/research/beta-results.md](docs/research/beta-results.md).

## Gamma

The selected [models/gamma.json](models/gamma.json) uses
`gamma_notes:make_gamma_notes_pairs`. It combines guarded long routes,
note-aware dispatch, short/premium segment controls and corrected two-car pairs.

### Admission and fees

The global win target remains 30%. Routes above 500 km and up to 700 km require
`next_day` or `within_3_days`, at least 24 hours of true pickup slack, and fewer
than three long orders waiting for drivers. Long singles open at 1.0 × reference
fees. Other normal singles open at 0.8 ×, with a 1.10 floor below 45 km and a
1.05 floor for premium cars. Routes below 45 km receive an 8% quote discount;
premium options require at least ten hours of slack. Floors combine by maximum.

The note-aware factory uses arrival-anchored readiness, release times, promises
and independent pickup/delivery hours when quoting and posting. Expired windows
roll to a valid business day instead of deleting closing hours. Fee ramps use
the last feasible pickup. Plate, charging and manual-licence requirements survive
reposting and pair planning. The bounded parser still misses some notes.

Pairs combine two eligible single-leg orders. Fresh pairs open at 0.72 × summed
reference fees; waiting-car rescue pairs open at 0.78 × with a new 60-minute flat
period. Their fee clock starts at pair creation, while fallback singles retain
their original age. Pair planning rejects more than 60 minutes of idle wait
at the second pickup; 60 minutes is accepted. Transfer distance, total drive,
service needs, audiences and visit windows retain their feasibility checks.

### Optional experiments

Brake, roster scaling, town caps, tables, trust-building, capacity controls and
stale-gig fee review remain disabled in the selected model. Neutral defaults
preserve historical core behavior: `gamma:make_gamma` with no long corridor
reproduces Beta. That core parity does not apply to the selected note/pair factory.
The corrected brake arm and the proposed supply policies did not justify promotion.

### Evaluation

The selected model ranked all eight screening weeks and all three known weak
weeks, then passed a separate frozen eight-seed confirmation: **8/8 ranked,
8/8 positive, +€2,030.845/week**, with 96.947% worst on time. Long-route lateness
was 1/148 (0.68%). A repeat using final code reproduced score, ledger, events,
visit failures and rejections exactly. See [recovery results](docs/research/gamma-recovery-results.md)
for every paired week and the limits; the failed original guarded-700 candidate
is documented in [historical Gamma results](docs/research/gamma-results.md).

These are ordinary-practice results. Final clocks still require their own runner
and validation. Further experiments are reserved for [Delta](docs/research/delta-handoff.md).

## Delta

Delta started with repository cleanup and documentation consolidation, then
screened pricing, intake, learner and lane experiments against frozen Gamma.
None of those held on fresh weeks.

**Early Delta** ([models/delta-early.json](models/delta-early.json)) is Gamma's
settings plus two repairs in `delta:make_delta`: bounded note corrections and
rescue-window handling for orders Gamma could not repost. On eleven unseen
practice weeks it beat Gamma 11/11 by €682/week; over 27 paired weeks +€518/week.

**Delta** ([models/delta.json](models/delta.json)) changes what the model
optimises: orders delivered per driver rather than margin per order. A capacity
audit found a third of posted gigs expiring unbooked, and the board showed the
top ten winning 400–500 orders a week at about our unit margin while we won 250.
Delta adds three verified dispatch fixes (`delta_wide_windows`,
`delta_private_delivery_rescue`; the EV rule fix exists but is off), wider
pairing (`delta_pairing="extended"`) and a 42% win target. Against Early Delta on
19 paired weeks: +€1,664/week, 17 weeks ahead, 342 orders a week instead of 257,
expired gigs down from about 140 to 25 a week, no unranked week; on time
averages 95.7% against 96.9% and the weakest week was 91.1%. `final.py` plays
either model on the live final clock. See the
[investigation results](docs/research/delta-results.md),
[next steps](docs/research/delta-next-steps.md) and
[testing plan](docs/research/delta-testing-plan.md).
