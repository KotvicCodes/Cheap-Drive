# Challenge constraints

Durable rules and integration requirements from the public-document review of
13 November 2026 and subsequent research notes, consolidated for Delta groundwork.
These are constraints and requirements, not new experiment results. For current strategy behavior and
measured evidence, see [prototype conventions](../PROTOTYPES.md) and the
[Delta handoff](research/delta-handoff.md). Event dates, run limits, setup and
commands live in the [operational reference](reference.md).

## Objective and evaluation

- The final is one secret level-8 week. Teams get separate copies of the same
  requests, drivers and random events; they do not share cars or drivers.
- Rank by gross margin: revenue minus driver fees, refunds, penalties, fines,
  waiting and release costs. Win at least one order and deliver at least 90%
  of won, noncancelled orders on time. Both cars of a two-car order must arrive
  by their deadlines. The top ten ranked teams reach the jury, which judges
  elegance, clarity, creativity and robustness rather than margin.
- Practice is deterministic for the same seed, level, actions and action times.
  Compare policies on shared seeds, then freeze code/settings before fresh
  confirmation. Count qualifying weeks and inspect every week's on-time share;
  averages can hide an unranked week. Low levels isolate bugs; level 8 selects
  strategy. Gamma's acceptance evidence is in its [recovery report](research/gamma-recovery-results.md).
- Save code revision, settings, scores, ledger costs, booking delay, drops,
  failed visits and rejection reasons. Reveals expose constraints for work we
  won, not competitor prices, private driver costs or hidden facts for lost work.
  Forks compare decisions at one state; they do not replace independent weeks.
  Keep raw traces, reveals and reports private under ignored `runs/`.

## Prices, supply and driver fees

- Levels 7–8 have only 26–40% of an average week's drivers; level 8 redistributes
  them unevenly between towns. List prices and reference fees still describe a
  normal week. The roster exposes homes, licence, rating, completed gigs and
  drops, not private schedules or public-transport costs. A view signals app
  activity, not confirmed availability or route suitability. Driver IDs change
  between worlds, so learning about a driver stays within that week.
- The level-8 competitor starts 26–54% above list before lane, day and request
  effects. Every week includes an outage, driver flu, bulk order and price war;
  the war cuts its usual prices by 20% from 08:00 to 18:00 that day. Wins and
  losses are noisy evidence; the competitor's prices remain hidden.
- Quotes must arrive strictly before `respondBy`. At levels 4–8 a losing quote
  costs no goodwill, while silence does. At levels 1–3 every quote wins at the
  first option's list price, so declining requires silence. A deliberately high
  quote is not an API rejection and could still win.
- At level 8 each on-time delivery increases what that dealer accepts by 1%,
  capped at 25 orders; a late order halves the count, rounded down. This does
  not guarantee a win or make unprofitable early work worthwhile.
- Most gig views arrive early. Repricing sends no new notification; drivers
  learn to wait for routine raises. Reposting preserves order age and fee history.
  Direct offers last ten world minutes, at most three open per gig and three
  per driver per day; nobody reads them 23:00–07:00. An expired offer may be unread.
  Offers remain unimplemented; see [historical Gamma evidence](research/gamma-results.md#what-was-kept-and-why)
  for why that proposal was not tested.

## Constraints and recovery

- Finnish, Swedish and English notes can change readiness, payment release,
  pickup/delivery hours, promises, plates, gearbox and summer-tyre requirements.
  Resolve relative days from request arrival. Named weekdays mean 2–6 days
  after arrival; word hours follow the dispatch vocabulary. Corrections,
  negations and typos require clause scope. The bounded parser has [known gaps](research/delta-handoff.md#remaining-note-cases).
- Premium cars need rating 4.8 or higher and at least 50 completed gigs; manual
  cars need a compatible licence. Plates add 30 minutes; charging adds 40.
  Electric cars below 30% charge on routes over 200 km need charging; omitting it
  adds 90 minutes of lateness and a €100 fine. Premium-driver violations cost €150.
- Private deliveries have booked slots and a deadline 30 minutes after the
  booked hour ends; missed private pickup slots do not simply extend. Dealer
  sites have restricted Saturday hours and close Sunday. `deadline_close`
  arrives three hours before `lastPickupAt`; leave time for booking and travel.
  After a missed window, `lastPickupAt` can describe the first collectable minute
  instead of an on-time pickup deadline.
- Multi-car gigs move cars sequentially, with at most 12 road-driving hours
  from first pickup to last delivery, including repositioning. Plates/charging
  affect feasibility but not that driving cap; single-car gigs have no such cap.
  For trade-ins, the old pickup immediately following the new delivery shares
  that visit's protection. Separated legs must meet the private slot; split a
  trade-in exceeding the combined driving cap.
- Track legs and gigs through drops, no-shows, failed visits, expiry, forecasts,
  changed orders and cancellations. Cancelling one paired order can withdraw
  the other car's gig, requiring reposting. Destination changes apply even to
  booked/started gigs and can add driver cost. Undelivered work earns no revenue
  and incurs twice its price as a penalty; rescue needs incremental-cost and
  qualification analysis, not just the original expected profit.

## Final integration requirements

No repository runner implements final mode yet. Practice qualification alone
does not validate Alpha, Beta or Gamma on final clocks.

- Practice pauses until `advance`; final time moves independently. During normal
  weekday daytime, a fifteen-world-minute quote window is only 4.5 real seconds;
  other periods compress differently. Prioritize quotes/recovery over diagnostics
  and budget for bursts. Keep policy separate from transport.
- Use the official client's rate limiting and reconnect support. Final limits
  are 20 actions and 50 reads per second with token buckets. Batches contain at
  most 50 actions, charged individually in final mode.
- Consume WebSocket events, resume from the last sequence and deduplicate
  replays. Rebuild state from snapshots/history after restart. Reconcile gigs
  and orders before retrying uncertain writes; a lost response is not proof of
  failure or idempotency. HTTP 200 can contain `{ok: false, reason}` per action.
- Preserve recovery for unreachable servers and 502/503/504 responses. The final
  continues if the process stops; drivers work but unanswered requests are lost.
  Validate reconnects and process restart in a test final. Use a stable host and
  connection, preferably near Stockholm; keep `SPREAD_KEY` outside Git.

## Official sources

This consolidation does not re-fetch or re-verify the published rules. Recheck
them before event operations; the rules take precedence over explanatory pages.

- [Rules](https://spread.bahnexpress.com/kit/RULES.md)
- [Handbook](https://spread.bahnexpress.com/kit/HANDBOOK.md)
- [API reference](https://spread.bahnexpress.com/kit/API.md) and [OpenAPI schema](https://spread.bahnexpress.com/openapi.json)
- [How it works](https://spread.bahnexpress.com/how) and [judging/submission](https://spread.bahnexpress.com/judging)
- [Documentation index](https://spread.bahnexpress.com/llms.txt) and [official kit](https://spread.bahnexpress.com/kit/)
