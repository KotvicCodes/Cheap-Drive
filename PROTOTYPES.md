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
