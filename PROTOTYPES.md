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
privately. The existing tracked `AI overview.md` remains public project
documentation; it is separate from the local story.

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

## Gamma (experimental)

Gamma is Beta plus guarded long routes. Beta refuses every route over 500 km;
Gamma admits some of the valuable longer work without reopening it all. The
other pricing and dispatch experiments remain in the code, off by default.

### The rule

Quote routes over 500 km and up to 700 km only when all three hold:

- The option is `next_day` or `within_3_days`, never `same_day`.
- The driver has at least 24 hours from the dealer's decision to the last
  feasible pickup.
- Fewer than three of our long orders are still without a driver.

Long gigs open at 1.0 × the typical fee instead of 0.8 ×. Beta's fee ramp and
rescue still apply. This is the admission and opening-fee half of roadmap step 4;
it sends no direct offers.

### Settings and what stays Beta's

[models/gamma.json](models/gamma.json) uses factory `gamma:make_gamma` and
`win_target_bps=3000`, `opening_fee_bps=8000`, `max_km=500`, `long_max_km=700`.
Defaults supply `long_options="next_day,within_3_days"`,
`long_min_slack_minutes=1440`, `long_open_cap=3`, `long_opening_fee_bps=10000`.
With `long_max_km=500` (the effective dataclass default), Gamma reproduces Beta
to the cent; eight live paired seeds confirmed identical scores and ledgers.
Omitting it follows `max_km`, including sweep overrides.

The global markup, 30% win target, dealer trust charge, eight-hour minimum on
shorter routes, trade-in refusal, notes, posting and rescue stay Beta's. Tables,
trust building and guard, capacity valve, option/distance pricing, on-time brake,
stale-gig fee review and two-car pairs are documented experiments, not enabled
in this model. Review and pairs use `gamma_pairs:make_gamma_pairs` when tested.

### Evaluation

On eight shared tuning seeds Gamma gained €1,232/week (+10.93%) over Beta,
positive on all eight, with all weeks ranked. Its worst on-time share was
92.975%, below the roadmap's 93% safety target. This is a modest step, not a
route to the top ten. The held-out check, rejected variants and reproduction
plan are in [docs/research/gamma-results.md](docs/research/gamma-results.md).
The completed held-out check ranked only seven of eight weeks: the worst was
89.956% on time. Neither tested brake repaired it. Beta remains the ranking
model until a revised candidate passes qualification.
