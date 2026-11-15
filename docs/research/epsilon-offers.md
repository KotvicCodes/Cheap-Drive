# Epsilon direct offers

Direct offers are a real, documented capacity lever. This implementation is an
opt-in experiment; Delta and Early Epsilon retain `epsilon_offers: 0` by default.

Verified 2026-11-15 against the official [API](https://spread.bahnexpress.com/kit/API.md),
[rules](https://spread.bahnexpress.com/kit/RULES.md),
[handbook](https://spread.bahnexpress.com/kit/HANDBOOK.md), OpenAPI contract and
installed Python SDK (`spread.types.OfferAction` / `OfferAnsweredEvent`).

- Action: `{type: "offer", gigId, driverId, feeCents}`; positive integer cents.
- A direct offer reaches a driver outside the first pickup's **30 km straight-line
  home notification radius**. Road distance is not that radius.
- It stays open for 10 world minutes. A yes books at the offered fee. No separate
  sending charge is documented; the booked driver's fee is the economic cost.
- Maximum three sends per driver per world day and three open offers per gig.
  Drivers read none from 23:00–07:00. This policy stops sending at 22:50.
- Direct offers unlock at level 3, remain available at level 8, and are allowed
  in ranking runs and the final. Ranking restricts fork/reveal, not offers; the
  final restricts advance/fork/delete, not offers. This experiment creates only
  ordinary seeded practice worlds (`board=False`).
- Practice: one token per HTTP request, including batches/advances carrying
  offers. Shared practice allowance is dynamic, at most 1,000 requests/sec/team,
  and 20 during a final/test final. Final: **one token per action**, 20/sec with
  a 50-token burst; reads use a separate 50/sec bucket. Maximum batch: 50 actions.

## Settings and dispatch policy

All settings are accepted by `models.delta:make_delta`.

| Setting | Default | Meaning |
|---|---:|---|
| `epsilon_offers` | 0 | Enable with integer 1 |
| `offer_after_minutes` | 120 | Unbooked age that triggers offers |
| `offer_before_pickup_minutes` | 360 | Also trigger when this close to latest pickup |
| `offer_interval_minutes` | 30 | Dispatch scan cadence, range 10–180 |
| `offer_max_eta_minutes` | 240 | Maximum estimated pickup ETA from now, range 1–480 |
| `offer_fee_bps` | 10000 | Offer as a share of current app fee, range 1–15000 |

The scan considers at most eight at-risk gigs, earliest pickup first. It excludes
booked, expired, detached and pending-withdrawal gigs. It filters manual licence
and premium experience requirements, pickup slack, all posted stop windows,
stated site hours and delivery deadlines. It only targets homes outside the
notification circle. It prefers drivers finishing our work, then drivers whose
home is near the delivery, then earlier pickup arrival and fewer past drops.

Public transport times and driver workdays are hidden. Positioning ETA is an
estimate: 1.5 × published road minutes + 30 minutes, plus 10 minutes to read the
offer; same-place transfers take no positioning time. Recent observed locations
are retained for at most 180 minutes on the same world day. Working gigs use
remaining posted stops to estimate availability. The server is the final judge
of a driver's actual route and workday.

The policy sends at most three offers per tick, reserves quota when queuing
(including failed actions), holds open-offer reservations for 11 minutes, and
never retries a driver/gig combination on the same day. It uses cached public
map/roster, action receipts and observed events. It adds no network reads and no
offer scan inside a quote handler; a tick with a queued quote defers offers until
the following world minute. Practice timers use the existing pair-timer clock
hook, including when pairing is disabled. The live runner already drains the
same outbox on events and idle ticks.

Restart limitation: snapshots/history omit outgoing offers, so after rejoin this
policy conservatively suppresses offers for the rest of the current world day
rather than risk exceeding an unknown quota. Ordinary posting and quoting
continue. This experiment does not alter the final runner or any live process.

## Validation and screen

The full offline suite and CI command-interface/demo smoke checks pass locally.
An offline tick using the public 30-place map and a 936-driver roster took about
0.9 ms, and initialization about 8.7 ms on this host; this is not a live latency
guarantee. Quote-isolation tests forbid offer scans and network actions during
both direct quote calls and price-request handling.

The screen plan is `plans/epsilon/offers-screen.json`: Early Epsilon (Delta JSON
plus `premium_min_slack_minutes: 1440`) with offers ON at win targets 4200, 5000
and 5500, on the four requested seeds. Paired baseline scores and their exact
source paths are frozen in `plans/epsilon/offers-paired-baseline.json`.

Invocation (team key loaded separately without printing):

```bash
SWEEP_WORKERS=2 SWEEP_ACTIVE_WORLD_LIMIT=12 \
SWEEP_LAUNCH_BLACKOUT_UTC=03:00-03:30 SWEEP_LAUNCH_CUTOFF_UTC=05:30 \
python scripts/sweep.py runs/epsilon-offers/screen \
  docs/research/plans/epsilon/offers-screen.json
```

Only `runs.jsonl` and `summary.md` are used to assess results. Offer send/rejection
and accepted/declined/expired counts are included in `runs.jsonl`.
