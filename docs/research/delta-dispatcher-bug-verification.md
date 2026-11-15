# Dispatcher hypothesis verification

Verified against the public official [Rules](https://spread.bahnexpress.com/kit/RULES.md),
[Handbook](https://spread.bahnexpress.com/kit/HANDBOOK.md) and pinned installed
`spread` starter/types on 2026-11-14. No game clients, team keys or live worlds
were used. Each repair is an independent integer `0`/`1` argument of
`delta:make_delta`, default `0`; `models/delta.json` is unchanged.

## Private-delivery rescue: confirmed

Rules, Gigs:

> At a private pickup it must also end inside the slot. At other stops it may
> end after the order's window, so a late car can still be collected and delivered.

The Handbook repeats: "Except at a private pickup, that window may end after
the order's window, so a late car can still go." The rule distinguishes
pickup from delivery; a private delivery's booked slot is not an absolute
upper bound on an explicit posted window. The starter's `stops_for` uses
the **order deadline** for its delivery base, and `without_windows` permits
late deliveries by dropping expired explicit windows.

Rules, Handling cars 5: a private delivery is due 30 minutes after the booked
hour ends. Delivering during that grace period remains on time. Later delivery
incurs the ordinary late refunds in Your account: 10%, 25%, 50% or the whole
price according to lateness. Extending a posted window changes neither the
deadline nor these penalties; the rules specify no separate fine for extending
a private delivery window.

`delta_private_delivery_rescue=1` allows the existing rescue intersection to
relax a private **delivery** end when the strict window is infeasible. It
prefers the original slot, then delivery by the real deadline, before the
existing late rescue horizon. Private pickups never extend. Readiness,
recurring note hours, note weekdays and site calendars still apply. Absolute
note promises can relax only through the existing rescue policy. Orders,
original windows and deadlines are not mutated.

The earlier private-delivery integrity finding in `delta-results.md` and the
B4 contract interpreted the booked delivery end too strictly. The official
rule explicitly permits the extension. Saved Gamma controls also show **13
such postings across five orders accepted by the server**, including extensions
past the order deadline. This is direct recorded acceptance, not a new probe.

In the eleven saved Delta (`rescue-notes`) weeks, all **three**
`gamma_note_no_window` diagnostics concern private deliveries. Rechecking
their saved order, note facts and clock with `Retry()` reproduces no route;
changing only this switch yields a route in all three. These are distinct
orders. Diagnostics do not retain retry flags, so this is a bounded window
recheck rather than full counterfactual simulation.

## Unconditional single-day stop windows: confirmed

Rules, Gigs: a stop without an explicit window uses the order's window and
deadline, cut to stated site hours; drivers plan visits when the stated hours
show the site open. There is no requirement to restrict all stops to their
first feasible day. The SDK starter's `stops_for` says:

> A stop has its own window only when the note or the retry makes it narrower.
> Without one, the world plans the pickup in the order's window and the delivery
> by the deadline.

`GammaNotesMixin._post_windows` calls `visit_window`, which returns only one
day's intersection, for every stop. Both Delta's existing rescue path and its
ordinary path consequently turn multi-day order windows into first-day posts
even with no restrictive note. Beta inherits the starter's posting behavior.

`delta_wide_windows=1` posts the widest representable span starting at the
first feasible visit. Stated opening hours can create overnight/weekend gaps
inside that span because the server enforces them. Note-only recurring
restrictions cannot: the span ends before any stated-open minute forbidden
by parsed note hours or weekdays. A single API interval cannot represent those
holes. The code retains readiness, release times, retry floors, plates,
charging time, sequential-leg repositioning, place ends, private slots and
order/note deadlines. Already impossible promises retain the prior rescue
policy; this switch does not itself relax their absolute ends. The independent
private-delivery switch still controls the repaired private rescue path.

The eleven Delta weeks contain **2,684 widenable pickup postings**, representing
**1,577 distinct legs**. Of those postings, **2,280** belong to `next_day`
orders (**1,395 distinct orders**). There are 1,549 captured `gig_expired`
events; **556** occur one minute after the posted end of a pickup that can
be widened under strict order/place/note bounds. Those are associated events,
not a claim that the new policy would prevent all 556 expirations. Other
windows, booking decisions and future driver availability remain relevant.

The counts compare each saved posted pickup floor with the widest strict
pickup/delivery bounds using that posting's charging flag and map duration.
They do not attribute economic outcomes. No saved Beta cohort was supplied,
so the claim of *more expirations than Beta* is unverified. An offline pair
fixture confirms that the narrow windows can reject a pair which the wider
windows make feasible; the number of newly feasible real pairs is unmeasured.

## EV charging: confirmed

Rules, Handling cars 3:

> An electric car below 30% charge on a route over 200 km needs a charging stop.
> Without one, the car arrives 90 minutes late, and the fine is €100.

Rules, Gigs specifies `withCharging` plans a **40-minute** stop. The Handbook's
driver cost description includes charging among the extras in a driver's
private cost; it specifies no fixed charging surcharge. Omitting required
charging is a delivery delay/fine, rather than a posting rejection according
to the documented behavior. No live missing-charge experiment was performed.

Both Gamma's `_needs_charging` and the official starter check low battery
without the distance threshold. `delta_ev_rule=1` retains that battery check
and additionally requires the leg's pickup-to-delivery **map road km > 200**.
At exactly 200 km it does not charge. It changes posting flags, forward timing,
latest pickup/slack and pair feasibility through the existing method hook.
Long low-charge routes still include the 40 minutes.

The eleven Delta weeks contain **127 unnecessary charging pickup postings**
across **54 distinct legs**, among 182 low-charge EV pickup postings. Repeated
posts of a leg are counted separately as postings; this is not a count of
127 charging stops actually performed or fees paid.

## Validation and hand-off

`tests/test_delta_dispatch.py` adds neutral-off byte parity for each switch,
strict integer validation, all 32 combinations of the five note/rescue/new
switches, boundary distance/charge checks, booked slots and grace, recurring
hours and weekdays, deadlines, readiness/release, opening calendars, charging,
plates, sequential repositioning and pairing coverage. Existing Gamma/Delta
neutral-parity tests remain intact.

Full offline command:

```sh
.venv/bin/python -m unittest discover -s tests
```

All **328 tests pass**, including 23 new dispatcher tests. The first EV,
private-delivery and wide-window deliveries passed the full suite at 310,
316 and 325 tests respectively before their separate commits and pushes.

Raw traces/reveals were read only from `runs/delta-final/{b5,b6,b8}` in the
measurement worktree, seeds `delta-f1-s01` through `s11`. Action intents were
matched to saved batch results, and events deduplicated by sequence. The
private local `runs/dispatcher-bug-audit/` contains the public rule snapshots,
offline counting script and detailed count output; raw run details are not
committed. Profits, causally avoided expirations and effects on real pairing
remain for the measurement queue.

Branch: `t3/verify-dispatcher-bugs` (the supplied worktree's existing branch).
Repair commits, pushed before queueing:

- EV: `621d01afeab7e46384712a986553eea29a7d0282`.
- Private delivery: `293e9302c1ede4a271b0611a14ab50aa3e6d3963`.
- Wide windows: `58ebe840239450841852700fa5a8d0ee53e5108d`.

Priority-8 queue files were atomically written to the measurement worktree's
`runs/queue/pending/` immediately after their pushes:
`dispatcher-ev-rule.json`, `dispatcher-private-delivery.json`,
`dispatcher-wide-windows.json`, and `dispatcher-all-fixes.json`. Each single
variant enables only its own new switch on the exact settings object from
`models/delta.json`; the combined variant enables all three. No PR was opened.
