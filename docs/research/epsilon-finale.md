# Epsilon Finale: offline build and practice plan

These mechanisms are inspired by publicly available information from people solving similar problems.
This is an independent implementation. No practice, ranking, or final worlds
were started for this build. Effects on won orders, margin, and on-time share
remain unmeasured.

`models/epsilon-finale.json` uses `models.delta:make_delta` and preserves every
Early Epsilon setting, enabling three additional mechanisms. Their flags
default to **0** in `GammaSettings`; existing Early Epsilon and Delta model
files are unchanged. Each flag can be swept independently.

## Supply and timing risk in quotes

Count unique public driver homes within 60 directed road km of the first
pickup. These homes describe geographic supply, not live positions,
availability, or driver qualifications. Missing/ambiguous homes or missing
home-to-pickup roads make supply unknown and preserve the existing quote.
An explicitly empty roster means zero supply.

For each option, estimate a lateness prior in basis points (100 bps = 1%):

```text
risk = pickup-day base
     + max(0, minimum nearby drivers - nearby drivers) * missing-driver penalty
     + floor(total route drive minutes * hourly drive penalty / 60)
     + tight-slack penalty, when slack < tight-slack threshold
```

The pickup-day base uses the last feasible pickup day, including note and
calendar constraints in Delta. Thus a next-day delivery that requires pickup
today receives the same-day base. Slack uses the existing note-aware slack
calculation. The estimate is capped at 10,000 bps. It is a tunable heuristic,
not a calibrated prediction.

Options above the maximum risk are filtered before option selection. At or
below the safe threshold, multiply the quote by 0.98 to allow slightly more
competitive bidding. Other accepted options get a premium of
`risk * supply_risk_price_bps_per_1000 / 1000` quote bps, rounded down before
the existing final cent ceiling. The global learner and its win target are
unchanged. Other enabled pricing factors still compose normally.

| Setting | Default | Meaning |
| --- | ---: | --- |
| `supply_risk` | 0 | Enable option filtering and price factors |
| `supply_risk_radius_km` | 60 | Inclusive home-to-pickup radius |
| `supply_risk_min_nearby` | 6 | Supply count with no scarcity penalty |
| `supply_risk_same_day_bps` | 600 | Base for pickup required today |
| `supply_risk_future_day_bps` | 140 | Base for pickup possible on a later day |
| `supply_risk_missing_driver_bps` | 120 | Added risk per missing nearby driver |
| `supply_risk_drive_hour_bps` | 40 | Added risk per hour of route driving |
| `supply_risk_tight_slack_minutes` | 720 | Slack below this receives a penalty |
| `supply_risk_tight_slack_bps` | 400 | Tight-slack risk addition |
| `supply_risk_max_bps` | 1800 | Highest accepted risk; equality is accepted |
| `supply_risk_safe_bps` | 300 | Highest risk receiving the safe discount |
| `supply_risk_safe_quote_bps` | 9800 | Safe quote multiplier, in bps |
| `supply_risk_price_bps_per_1000` | 1500 | Premium per 1,000 risk bps |

For example, a 180-minute route with 600 minutes of slack and zero nearby
drivers estimates 1,840 bps and is filtered by default. With six nearby
drivers it estimates 1,120 bps and gets a 16.8% price premium. A future-day
pickup on the same route with ample slack estimates 260 bps and gets the 2%
discount. `supply_risk` journal records expose estimates and nearby supply;
`beta_quote.optionFactors.supplyRiskBps` records the applied quote multiplier.

## Conditional arrival buffer

Build the original feasible stop windows first, using the existing Gamma or
Delta note, rescue, and wide-window planner. Tighten delivery ends by the
arrival allowance, respecting the order deadline, parsed note limits, and
real site closing. Walk backwards through the complete route to tighten
pickup ends for driving, charging, plates, and transfers. Calendar searches
avoid creating a latest arrival inside a closed night or weekend.

If any buffered stop loses feasibility, return the complete original route
windows. Pair planning also retries with original windows if individually
buffered singles cannot form a feasible pair. This keeps feasible work
available. Order deadlines, fee calculations, and pickup lower bounds are
unchanged. A wide window can still span several business days: the buffer
protects its chosen latest feasible delivery; it does not encode a separate
30-minute exclusion before every intermediate day's closing.

| Setting | Default | Meaning |
| --- | ---: | --- |
| `arrival_buffer` | 0 | Enable conditional stop-window tightening |
| `arrival_buffer_minutes` | 30 | Delivery arrival allowance; 0 leaves windows unchanged |

## Aged workload gate

An open order is stuck when no observed progress has occurred for at least
45 minutes. Acceptance starts the clock. Booking, gig start, pickup, and
delivery reset it; a booking/start updates every order in that gig. A
repost, failed visit, drop, or order edit is not progress. Partial deliveries
leave remaining legs in the workload. Delivered and cancelled work is
excluded. Booked orders can become stuck again if progress stops.

Count each stuck order once nationally and once locally if its next
undelivered pickup is within the radius of the candidate's pickup, using
directed road km. Same-place pickups always count. Unknown roads cannot
establish locality, but the national gate still counts the order.

Public requests have no yard identifier, so a yard is the pair
`(dealerId, next pickup placeId)`. Its pressure is stuck orders plus weighted
undecided competitive quotes from that yard. Broad backlog is orders still
needing a driver (including partly booked trade-ins) plus weighted undecided
competitive quotes. Each undecided quote has half weight by default, and a
candidate does not count itself. Declined and rejected quotes do not reserve
capacity; outcomes release pending reservations. Acceptance replaces the
pending quote with one order.

Decline new intake when **any count exceeds** its configured limit. At the
limit, intake remains eligible. The existing decline quote policy applies.
All open orders contribute to stuck pressure, while only work needing a
driver contributes to broad backlog. `stuck_work_gate` journal records expose
all four counts.

| Setting | Default | Meaning |
| --- | ---: | --- |
| `stuck_work` | 0 | Enable aged workload admission gate |
| `stuck_work_age_minutes` | 45 | Inclusive inactivity age |
| `stuck_work_radius_km` | 120 | Inclusive local pickup radius |
| `stuck_work_local_limit` | 16 | Local stuck orders |
| `stuck_work_national_limit` | 60 | National stuck orders |
| `stuck_work_yard_limit` | 20 | Yard stuck orders plus weighted pending quotes |
| `stuck_work_backlog_limit` | 120 | Orders needing drivers plus weighted pending quotes |
| `stuck_work_pending_weight_pct` | 50 | Undecided quote weight, 0–100% |

Progress timestamps and captured risk supply are checkpointed. Event-history
replay rebuilds progress without submitting past actions. For missing clock
data, use first-post time where available, otherwise the request decision
time; reposting never refreshes a known progress timestamp.

## Ready-to-run paired sweep

Plan file: `docs/research/plans/epsilon/epsilon-finale.json`.
It has five arms over the same eight seeds (40 ordinary practice weeks):

| Arm | Early Epsilon overlay |
| --- | --- |
| `early-epsilon` | Baseline; all new flags off |
| `supply-risk` | `supply_risk=1` |
| `arrival-buffer` | `arrival_buffer=1` |
| `stuck-work` | `stuck_work=1` |
| `finale-all` | All three enabled |

Hard weeks: `eps-sp-s001`, `eps-bf-s002`.
Normal weeks: `delta-f1-s01` through `delta-f1-s06`.
The JSON base is an exact copy of Early Epsilon's settings. The all-enabled
arm uses the same defaults as the Epsilon Finale model file.

Run from the repository root when practice is authorized and capacity is
available; this command was **not executed** for the build:

```bash
SWEEP_WORKERS=2 SWEEP_TEAM_WORLD_LIMIT=8 \
  /home/agent/.t3/worktrees/Cheap-Drive/t3-034ebca2-70a3ee396c687b47/.venv/bin/python \
  scripts/sweep.py runs/epsilon/finale \
  docs/research/plans/epsilon/epsilon-finale.json
```

Keep the paired seed results and compare won orders, on-time share,
undelivered share, margin, and qualification for each arm against the baseline.
Require at least 90% on time on every week, with particular attention to both
hard weeks. Inspect risk filtering, premiums/discounts, and local/yard gate
counts in traces to explain throughput changes. Do not promote solely from
an improvement in mean margin or total wins that hides a failed week.

## Offline validation

`tests/test_epsilon_finale.py` covers risk, buffer fallback (including pairs),
age/radius/count boundaries, weighted pending quotes, progress/recovery,
disabled behavior, and model/plan construction. The golden Early Epsilon
action fixture was generated from untouched base commit
`a4f7350f5c665f73b90a7a4b67e283f8b50e68f5`; flags omitted or explicitly off
must preserve its quotes, posts, learning updates, and trust changes.

Run the full offline suite and CI command checks using the supplied Python:

```bash
FINALE_PYTHON=/home/agent/.t3/worktrees/Cheap-Drive/t3-034ebca2-70a3ee396c687b47/.venv/bin/python
"$FINALE_PYTHON" -m unittest discover -s tests -v
"$FINALE_PYTHON" dispatch.py --demo --log runs/epsilon-finale-demo.jsonl
"$FINALE_PYTHON" dispatch.py --help
"$FINALE_PYTHON" compare.py run --help
"$FINALE_PYTHON" compare.py report --help
```
