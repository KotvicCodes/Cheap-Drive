# Surprise live final: post-mortem, 14–15 November 2026

Audited 15 November 2026 UTC. **The principal failure was having no dispatcher waiting when a scored final-mode event started seven hours before the published final time.** Delta then recovered some business, but did not reach its usual performance over the remaining demand. A confirmed recovery bug also trained its price learner on 621 quotes that we never submitted.

Outcome: **€2,374.14 margin, €9,843.03 revenue, 89 orders, 83/89 on time (93.2584%), zero undelivered, ranked**. The public final feed placed Guardians of the Moonlight **38th of 41 ranked teams**. These are actual event results; whether organisers intended this as the official deciding final or an additional test remains unconfirmed.

## Evidence and counting conventions

Only existing local artifacts, offline model execution and GET requests were used. No practice, ranking or final world was created or advanced. No running `final.py` or `sweep.py` process was stopped, restarted or changed. No model, tuning document, credential or unrelated work was edited.

Code references below are pinned to audited source revision `e595cdd96e3aa98a96b799f4d1b027745b1cecb8`. Primary local sources:

- Checkout: `/home/agent/.t3/worktrees/Cheap-Drive/t3-cb1f1e60-3100c14e73a0d169`.
- Trace: `runs/final/20261114T231711Z-final-f361626ab97b2bcdfa5ea.jsonl.gz`; SHA-256 `7c414a76b033379fe8dd9e8245e81e352c5a169b61b68227b619c19c8b24a263`. Row numbers below mean **decompressed JSONL rows**, not compressed-file byte offsets.
- Console: `runs/final/live-2317.log`; checkpoint: `runs/final/f361626ab97b2bcdfa5ea-checkpoint.json`.
- Exact-settings practice comparison: sibling `t3-4d9ed6f5-d50ae2340a835fbb/runs/queue/out/volume-tap/weeks/cap-4200--<seed>/traces/cap-4200--<seed>.jsonl.gz`, relative to `/home/agent/.t3/worktrees/Cheap-Drive/`. All 19 completed seeds `delta-f1-s01`–`s11` and `delta-f2-s01`–`s08`; rehearsals, other settings and incomplete attempts were excluded. The suggested `t3-54bca21f-.../runs/queue/` was absent; the retained queue artifacts were found in this sibling.

Events were deduplicated by `seq`: **1,391 history events + 3,652 streamed events = 5,043**, sequences 0–5042 without gaps. Practice events come from `advance_batch.response.events`; final events come from `history_event` and `event`. Money is the sum of **ledger `line.cents`**, which reconciles exactly to every included terminal score. “Booked margin” means ledger money recorded in a time interval. “Arrival-cohort margin” means all eventual revenue, refunds and costs attributed to requests arriving in that interval, including money recorded later. Pair fees with null `orderId` are divided equally among the distinct orders in that gig; mixed-cutoff pair allocations are an approximation, and the cohort totals still reconcile exactly.

The supplied join estimate was **4,906 (Thursday 09:46)**. The actual first recorded snapshot is **4,939 (Thursday 10:19)**: trace row 2, `snapshot.now`, followed by `model_rejoin` at row 1404. The filename records trace creation at **23:17:11 UTC**. The trace does not substantiate a 23:12 process launch; do not silently treat the supplied estimate as a measured timestamp. The outer capture row has `at: 0` because it precedes the first snapshot clock assignment; use `snapshot.now` ([`capture.py:116`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/capture.py#L116)).

## 1. How much did joining late cost?

### Direct observations

| Measurement | Before minute 4,906 | At/after minute 4,906 | Total |
| --- | ---: | ---: | ---: |
| Price requests by arrival time | 683 | 353 | 1,036 |
| Competitive quote attempts | 0 | 297 | 297 |
| Deliberate decline quote attempts | 0 | 48 | 48 |
| Wins by settlement event | 0 | 89 | 89 |
| Losses by settlement event | 672 | 275 | 947 |
| Booked margin | €0.00 | €2,374.14 | €2,374.14 |

Thus **65.93% of all demand arrived before 4,906**, although only **34.36% of the 14,280-minute world** had elapsed. Demand is concentrated in the business week: daily requests were **219 Monday, 204 Tuesday, 227 Wednesday, 207 Thursday, 179 Friday**, then zero. The last request arrived at **6,839 (Friday 17:59)**. The long delivery tail is not additional selling time.

At minute 4,906, 11 of those earlier requests still had response windows open; all expired before our first snapshot. At the measured 4,939 join, **698 requests had arrived, 691 were already lost, seven were still open, and 338 more would arrive**. We quoted those seven and won four. Overall, **691 requests received no attempt**, and one additional request received a rejected attempt. In the 353-request post-4,906 cohort, eight expired during the remaining join delay; 345 were attempted. This accounts for all 1,036 requests.

At a 4,939 split, event-time wins/margin remain **0/€0 before, 89/€2,374.14 after**. Arrival-cohort wins are **4 before and 85 after**, because four still-open requests were rescued. Their eventual cohort margin was **−€2.99 before / €2,377.13 after**. Do not confuse these arrival and settlement partitions.

### Same weekday/hour span in Delta practice

All 19 comparator runs use the live trace's exact Delta settings, including `win_target_bps=4200`, extended pairing, wide windows and private-delivery rescue. They are different seeds, with established earlier orders, trust and supply interactions. Exact settings do not establish identical source revision or a controlled same-seed counterfactual.

| Span/rate | Surprise final | Practice mean |
| --- | ---: | ---: |
| Whole world margin | €2,374.14 | €13,760.21 |
| Whole world net wins | 89 | 341.89 |
| Requests arriving at/after 4,906 | 353 | 375.11 |
| Gross wins from those requests | 89 | 124.53 |
| Booked margin during [4,906, 14,280], 156.233 simulated hours | €2,374.14 | €8,654.51 |
| Booked margin per simulated hour in that span | **€15.20/h** | **€55.39/h** |
| Eventual margin from requests arriving at/after 4,906 | €2,374.14 | €5,097.98 |
| That cohort's margin divided by the same span | **€15.20/h** | **€32.63/h** |

The booked-money comparison includes practice deliveries from orders won before the cutoff, which we did not inherit. The arrival-cohort comparison removes that major accounting distortion. Practice post-cutoff booked margin ranged **€5,004.07–€12,957.35**; eventual post-cutoff cohort margin ranged **€2,620.60–€7,909.23**.

An explicit **benchmark decomposition**, not a causal measurement of this unseen seed, is:

- Practice mean full margin **€13,760.21** minus live **€2,374.14** = **€11,386.07 shortfall**.
- Practice mean eventual margin from pre-4,906 requests: **€8,662.24**, or **76.08% of that shortfall**.
- Practice mean post-4,906 cohort **€5,097.98** minus live **€2,374.14** = **€2,723.84 remaining gap**, or **23.92%**.

Using the measured 4,939 boundary gives **155.683 hours**, live **€15.25/h**, practice booked **€54.99/h** and practice new-cohort **€31.65/h**. The corresponding benchmark pre-arrival contribution is **€8,832.59 (77.57% of the full shortfall)**. Its simple post-cohort gap is **€2,553.48** when comparing against the entire live score; using the correctly split live post-cohort €2,377.13 gives **€2,550.49**, with the rescued pre-cohort −€2.99 accounting for the difference.

These estimates cannot separate missed dealer trust/goodwill, secret-seed difficulty, price learning and delivery costs. In particular, lateness may also hurt *subsequent* wins; the remaining gap is not proof that all of it came from an independent model bug.

### Per-week comparison, cutoff 4,906

“Post ledger” is booked after the cutoff; “post cohort” is eventual margin on requests arriving after it. Weekly wins are terminal score net wins, whereas cohort wins above count gross `order_won` events before cancellations.

| Practice seed | Full margin | Net wins | Post requests | Post ledger | Post cohort |
| --- | ---: | ---: | ---: | ---: | ---: |
| delta-f1-s01 | €9,711.04 | 305 | 370 | €5,004.07 | €4,014.41 |
| delta-f1-s02 | €15,218.71 | 363 | 373 | €8,635.82 | €4,320.98 |
| delta-f1-s03 | €14,376.53 | 333 | 387 | €10,523.72 | €5,922.31 |
| delta-f1-s04 | €16,230.16 | 359 | 369 | €11,557.98 | €7,344.13 |
| delta-f1-s05 | €13,499.61 | 340 | 370 | €9,270.58 | €4,453.60 |
| delta-f1-s06 | €18,366.42 | 364 | 371 | €12,957.35 | €7,008.40 |
| delta-f1-s07 | €11,462.67 | 349 | 373 | €7,800.24 | €4,574.89 |
| delta-f1-s08 | €11,575.92 | 338 | 395 | €8,712.37 | €5,325.00 |
| delta-f1-s09 | €15,608.46 | 350 | 374 | €9,655.82 | €7,145.90 |
| delta-f1-s10 | €17,344.20 | 366 | 363 | €10,021.39 | €6,898.33 |
| delta-f1-s11 | €13,098.79 | 321 | 357 | €6,564.61 | €2,648.94 |
| delta-f2-s01 | €16,020.64 | 337 | 365 | €8,848.51 | €3,891.67 |
| delta-f2-s02 | €12,712.21 | 298 | 372 | €9,377.89 | €6,690.72 |
| delta-f2-s03 | €11,161.66 | 375 | 403 | €6,333.11 | €4,648.19 |
| delta-f2-s04 | €14,206.55 | 371 | 405 | €8,342.97 | €4,652.32 |
| delta-f2-s05 | €10,967.42 | 317 | 367 | €5,266.99 | €2,869.32 |
| delta-f2-s06 | €9,894.92 | 312 | 369 | €6,533.91 | €3,922.60 |
| delta-f2-s07 | €16,115.66 | 358 | 378 | €11,909.98 | €7,909.23 |
| delta-f2-s08 | €13,872.46 | 340 | 366 | €7,118.40 | €2,620.60 |
| **Mean** | **€13,760.21** | **341.89** | **375.11** | **€8,654.51** | **€5,097.98** |

## 2. Did Delta play normally after joining?

**Its recorded actions match the model, but its learned starting state and commercial results were not normal full-week Delta performance.** Offline, with all HTTP/action methods replaced by an in-memory receipt tape, the audited model reproduced **all 493 action batches exactly**, including all quotes, pair withdrawals, posts, fee changes and the rejected quote. No live API action was used for this replay. The final reconstructed learner was **12,577.3476 bps** after decisions; the last quote used **12,214 bps**.

- **Quotes:** 345 attempts = 297 competitive + 48 deliberate declines. **344 accepted / one rejected**. Competitive win rate **89/297 = 29.966%**, or **89/296 = 30.068%** among accepted competitive quotes. Including deliberate declines gives **89/345 = 25.797%**. Comparable practice post-arrival competitive win rate was **39.519% pooled**; the configured target was 42%. Do not count the 691 pre-connection losses against live quotes.
- **Prices:** Across competitive option offers, median quote/reference-driver-fee ratio **1.3399×**, mean **1.3691×**, range **0.6098×–2.2830×**. Reference means `referenceFeeCents`, not the competitor's undisclosed quote. Median quote/list-price ratio **1.2424×**, mean **1.2396×**. For won orders, actual contract/reference ratio had median **1.3536×**, mean **1.3785×**. Learned quoted markup ranged **12,000–13,239 bps**, mean **12,322.00**; **113/297 (38.05%)** competitive quotes used the floor. **76/89 wins** were quoted at zero dealer trust. Practice post-cutoff per-seed median quote/reference ratios ranged **1.4391×–1.8890×**.
- **Declines:** **48/345 = 13.91%**: 30 “no option leaves a driver enough time”, eight trade-ins, seven routes too long, two without an eligible long-route option, one long-route capacity rejection. All were deliberate 10× list-price quotes, all accepted, and none won. Comparable practice post-cutoff decline share was **16.00%**.
- **Dispatch actions:** **122 posts, 34 withdrawals, 13 reprices**, all accepted. **86 booking events across 80 distinct gigs, 79 gig starts, nine expiries, seven drops**. Six bookings were repeat bookings; the booked pair g59 was dropped and split, accounting for the remaining distinct booked gig that never started. Final snapshot: **79 done gigs, 43 withdrawn**, zero active gigs. No visit failures, no no-shows and no order cancellations occurred. All 89 orders were delivered.
- **Pairs:** **21 pair posts**, **11 pair-booked diagnostics**, **11 splits** (ten timers, one drop). Joining midweek did not disable pairing: first pair posted at **4,974**, first timer split at **5,034**. A pair can book and later split, so these diagnostics are not disjoint terminal statuses. Pair timers run through outbox polling ([`models/gamma_pairs.py:144`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/models/gamma_pairs.py#L144), [`models/gamma_pairs.py:499`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/models/gamma_pairs.py#L499)), and `final.py` calls `send()` after events and idle ticks ([`final.py:164`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L164)).
- **Slow responses:** log line 698 records **`minute=6269 order_lost took 8.70s to answer`**; terminal stats row 6962 records **one >1s handler, max 8.700279671s**, with **zero HTTP 429s**. Request **R00861**, arriving 6,274 with `respondBy=6289`, was attempted at desk minute 6,274 and rejected as “not open” (trace row **4358**, action batch **266**). This is consistent with a backlog after the stall; the journal lacks wall-clock request/response timestamps needed to prove the exact delay or its origin. It cost one quoting opportunity, not a measured euro amount. Other 344 attempts succeeded. Handler timing excludes waiting for the next stream event and initial rejoin work ([`final.py:165`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L165), [`final.py:184`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L184)), so “one slow handler” is not a complete network-latency guarantee.

The score reconciles as **€9,843.03 revenue − €7,149.25 driver fees − €319.64 late refunds = €2,374.14**. Margin share was **24.1200%**. Six late orders caused those refunds:

| Order | Refund | Lateness stated in ledger | Event seq for refund |
| --- | ---: | ---: | ---: |
| R00850 | €36.22 | 780 minutes | 4544 |
| R00756 | €32.04 | 780 minutes | 4564 |
| R00753 | €79.78 | 3,540 minutes | 4751 |
| R00699 | €70.80 | 3,945 minutes | 4965 |
| R00698 | €70.80 | 4,111 minutes | 5001 |
| R00971 | €30.00 | 1,209 minutes | 5041 |
| **Total** | **€319.64** | **6/89 late** | |

The practice terminal on-time mean was **95.674%**, worst **91.117%**, versus live **93.258%**. Rescue was active: R00753 expired on gigs g43/g97/g103 before g113 delivered it; R00699 expired on g5/g101, R00698 on g14/g104, and R00971 on g99/g121 before later gigs completed them. All nine expiries belong to these four orders. This is observed delivery risk/cost, not evidence of a blanket live-dispatch failure.

**Inherited obligations:** none. At first snapshot: **zero orders, zero gigs, zero driver positions, €0 revenue/margin**, plus seven open requests. `model_rejoin` recorded **zero open orders/pairs, seven pending quotes**, replaying 1,391 events. There was no pre-join debt or abandoned fleet to pay for.

**Notes, rescue and clocks:** all 493 action batches matched an offline execution using original request timestamps. Notes use `arrivedAt`, not connection time ([`models/delta.py:129`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/models/delta.py#L129)); rescue uses current world minutes and site windows ([`models/delta.py:150`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/models/delta.py#L150)). No malformed-note, missing-order, pair-error or unreachable diagnostics occurred. The exception is the learner contamination below. Snapshot delivery timestamps also differ from streamed delivery event times for **five orders**; refund details and terminal score, rather than naive event-time subtraction, determine the lateness table. For example R00850's delivered event was at 6,982 but snapshot `deliveredAt` was 7,740, consistent with its 780-minute refund. This is a data-contract discrepancy, not an established client bug.

## 3. What event was this, and does it count?

Read-only SDK queries at **2026-11-15 00:20:53.601 UTC**, using the specified Python environment and sourced environment file, returned:

```json
{
  "client.final()": {
    "worldId": "f361626ab97b2bcdfa5ea",
    "startsAt": "2026-11-14T23:00:00.000Z",
    "now": 0
  },
  "worlds() matching entry": {
    "worldId": "f361626ab97b2bcdfa5ea",
    "kind": "final",
    "level": 8,
    "parent": null,
    "season": null,
    "boardRun": null,
    "ended": true
  },
  "snapshot": {"now": 14280, "endsAt": 14280},
  "score": {
    "marginCents": 237414,
    "revenueCents": 984303,
    "wonOrders": 89,
    "onTimeShare": 0.9325842696629213,
    "undeliveredShare": 0,
    "ranked": true
  }
}
```

The snapshot does **not** expose `startsAt` or level; those come from `client.final()` and `client.worlds()` respectively. `endsAt=14280` is a simulated minute, not a wall-clock timestamp. `/v1/final.now=0` is stale/inconsistent with the ended snapshot; it does not mean this event has not run. `final.py` correctly checks snapshot completion when selecting a world ([`final.py:229`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L229)), although its background clock reads `/v1/final` ([`final.py:337`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L337)).

A separate unauthenticated GET of the public [final leaderboard feed](https://spread.bahnexpress.com/v1/leaderboard), at **2026-11-15 00:25:53.748 UTC**, returned **`status: ended`, `startsAt: 2026-11-14T23:00:00.000Z`, `now: 14280`, `endsAt: 14280`**, and our exact ranked score at **rank 38**. There were **41 non-null ranks**. Its `clock.endsAtWall=1794699258000` corresponds to **2026-11-14 23:34:18 UTC**: a **34-minute 18-second** event, consistent with the advertised final duration, rather than the approximately 19-minute tests.

The published repository schedule says **15 November 08:00 Helsinki / 06:00 UTC**, with the two announced test finals on 14 November at **12:00 and 18:00 UTC** ([`README.md:32`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/README.md#L32), [`README.md:118`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/README.md#L118)). This extra event began **01:00 Helsinki**, seven hours early. It is unquestionably a **scored final-mode event represented on the current final leaderboard**, and its qualification flag counts there. The API and public feed have **no official-versus-test discriminator**; the earlier known 18:00 test used the same final endpoint/feed. Therefore we cannot certify organiser intent, permanence of this result, or jury selection from these fields. Treat it as consequential until organisers explicitly resolve the schedule discrepancy; retain standby for any subsequent final as well.

## 4. Bugs and money impact

### Confirmed: recovery learns from never-submitted quotes

[`recovery.py:205`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/recovery.py#L205) explicitly assumes normal historical quotes were accepted when receipts are absent. It calls `desk.quote()` on every historical price request ([`recovery.py:264`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/recovery.py#L264)), then processes `order_lost` feedback through `observe_feedback` ([`recovery.py:258`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/recovery.py#L258), [`models/beta.py:138`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/models/beta.py#L138)). Gamma only updates prices when a request is marked pending, but replay has just put these hypothetical competitive quotes in pending ([`models/gamma.py:514`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/models/gamma.py#L514), [`models/gamma.py:568`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/models/gamma.py#L568)).

A credential-free reconstruction of the actual initial snapshot/history, with `act()` forbidden, measured:

| Reconstruction | Initial learner | Replayed competitive losing feedback | Learner at first live quote |
| --- | ---: | ---: | ---: |
| Current code, no prior checkpoint/receipts | 15,000 bps | **621** | **12,000 bps** |
| Same history, explicitly mark every historical request as unsubmitted | 15,000 bps | **0** | **15,000 bps** |

The current replay first reached the floor at **minute 669, R00033**, long before connection. There was no real quote history to learn from. It depressed initial prices **20% relative to the intended fresh start** (or the fresh start is 25% above observed initial prices). This changes money decisions, but the lost margin is **not identifiable** without knowing which higher-price quotes would still have won. Do not assign all €2,723.84 residual gap to it. Fix by recording connection/coverage boundaries and distinguishing *unsubmitted*, *accepted*, *rejected* and *unknown* requests; only actual accepted competitive quotes should train. A receipt-free genuine old run needs an explicitly documented fallback, rather than treating all pre-connection requests as bids.

### Observed: one expired quote opportunity; latency cause unresolved

The R00861 rejection above is the only action failure. `final.py` handles events serially ([`final.py:164`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L164)); durable journal boundaries synchronously flush/fsync ([`capture.py:34`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/capture.py#L34)), and checkpoint state copying occurs inside the measured handler ([`final.py:181`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L181), [`recovery.py:105`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/recovery.py#L105)). Any of these, the action network path or host scheduling can contribute to a stall. The trace does not isolate the 8.70 seconds, so “fsync caused it” would be speculation. Add wall-clock received/sent/completed times and component timings before assigning a cause; preserve the durable receipt guarantees.

### Observed: six late deliveries, no demonstrated new live-path bug

Late refunds directly cost **€319.64**, plus any unmeasured effects on subsequent trust/wins. Late transport and rescue paid real fees too, already in €7,149.25 total driver expense. These are reproducible model decisions in the receipt-tape audit, not an unexplained live-only divergence. There were no visit failures to support blaming note parsing. One broad pickup stop ended a minute after server `lastPickupAt` (g79: 6,704 versus 6,703), and g41 actually picked up R00756 after its latest pickup; these illustrate tight-window risk, not proof that a one-minute window adjustment would have prevented the refunds. The model's post-window construction uses nominal road time with optional charging ([`models/delta.py:204`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/models/delta.py#L204)); service buffers need separate validation.

### Confirmed operational gaps, not demonstrated extra loss in this run

`main()` loads a model once, before waiting ([`final.py:318`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L318)), and returns after one event ([`final.py:365`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L365)). It neither watches model-file changes nor automatically rearms for a subsequent final. `play_until_done` retries `Unreachable`, not arbitrary fatal exceptions ([`final.py:205`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L205)). A supervisor and explicit deployment policy are required for continuous standby. These gaps explain how a process that played an earlier test could still leave us uncovered later, but this trace alone does not establish how the earlier process was managed.

## 5. Standby procedure and safe Epsilon handoff

**Top recommendation: keep exactly one supervised `final.py` waiting continuously, beginning immediately after each completed event and throughout the whole competition window; never gate connection on the published start time.** The wait loop polls every **five real seconds**, accepts an announced future or active final, ignores completed snapshots, and can attach before the first request ([`final.py:223`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L223)). A final's appearance must trigger connection automatically, even if its time is unexpected.

This is a proposed operator procedure; this audit did not launch or restart a runner:

1. Assign one runner owner and one stable host. Use the known working SDK Python, a source checkout pinned to a reviewed commit, and an immutable model release. Source the configured `.env` privately with `set -a; . <env-file>; set +a`; never echo it or enable shell tracing. Reserve resources so sweeps cannot starve the dispatcher.
2. Have a single-instance service/supervisor run the equivalent of **`<venv>/bin/python final.py <frozen-release>/models/delta.json --quiet --output <persistent-final-directory>`**, with an absolute executable/model/output path. **Do not pass `--rehearse`**. The source/import path must also be pinned: freezing only JSON does not freeze the code it names. Keep output in a durable directory across releases and restarts; `--output` is supported at [`final.py:313`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L313).
3. Configure **restart even after exit code 0**, with a short backoff and a single-instance lock. One completed final makes the current CLI exit; the replacement must return to `wait_for_final`, waiting past the old completed world. A crash requires automatic same-model rejoin. Prevent overlapping writers/dispatchers during both ordinary restarts and deployment.
4. Verify process liveness, the “No live final yet”/world-attachment log and server reachability. The waiting message is printed only once ([`final.py:239`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L239)), so log silence is not a heartbeat. Add an independent read-only health check using `/v1/final` plus the **world snapshot**, with alerts for an unfinished world without an attached runner, stalled event progress, rejoin errors, quote rejection and missing checkpoints. Clock metadata disagreement must be visible. Checks should be bounded and infrequent enough not to consume action capacity. Alerting is a proposed operator responsibility; none was sent by this audit.
5. When Epsilon is frozen, validate its configuration/imports and preserve its commit/model identity. Deploy during **idle standby with no active final**, through a controlled one-process stop/start owned by the operator, then verify the Epsilon command is waiting. A short gap during this handoff still needs monitoring because the published timetable proved unreliable. For a gap-free future handoff, add a tested model-selector reload **before a newly discovered world's desk is constructed**, with a process lock/acknowledgment; current `final.py` has no such feature. If an event has already started, keep the current frozen model through its end and activate Epsilon for the next event unless a separately validated migration is essential.
6. Archive each world ID, actual UTC start/end, run/model spec, checkpoints, traces, score and public standing. Do not stop coverage merely because an event ended or because its official/test designation is uncertain.

### What restart and model swap actually guarantee

**Same model restart:** designed to rejoin the same unfinished final. Snapshot/history are reconciled, and only current actionable work is queued ([`final.py:134`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L134), [`recovery.py:374`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/recovery.py#L374)). Checkpoints are versioned and tied to world/model, atomically replaced after fsync ([`recovery.py:87`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/recovery.py#L87), [`recovery.py:150`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/recovery.py#L150)). Durable quote receipts recover the tail, including complete JSON lines from a truncated gzip file ([`recovery.py:115`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/recovery.py#L115)). Original fee ages and safe pair reconstruction prevent a routine restart from resetting every fee ramp ([`recovery.py:435`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/recovery.py#L435), [`recovery.py:450`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/recovery.py#L450)). This is best-effort crash recovery, not an exactly-once guarantee for every unknown in-flight action. Preserve the complete output directory. The confirmed pre-connection learner bug remains relevant on a receipt-free rebuild.

**Hot swap:** **not supported**. Editing/replacing JSON or a symlink while the process waits or plays does not change its already loaded `model.spec` or factory ([`final.py:318`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L318), [`final.py:354`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/final.py#L354)).

**Restart with Epsilon during an active world:** **not a state-preserving model swap**. Checkpoint loading rejects a different model spec ([`recovery.py:90`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/recovery.py#L90)), and receipt discovery also skips every trace whose model spec differs ([`recovery.py:127`](https://github.com/KotvicCodes/Cheap-Drive/blob/e595cdd96e3aa98a96b799f4d1b027745b1cecb8/recovery.py#L127)). It then replays historical events under Epsilon and its changed settings. World obligations can be recovered structurally, but actual Delta acceptance/decline, learner, capacity and pair decisions are no longer guaranteed exact, and absent receipts expose the phantom-quote problem. A changed model name alone is sufficient to change identity. Do not claim “restart safely switches models” without migration support that carries real historical receipts independently of pricing policy and validates compatible state.

### Verification performed

- Gzip integrity/readability and unique event-sequence coverage; final ledger reconciles **237,414 cents**, and all 19 practice ledgers reconcile to their terminal scores.
- Exact live settings checked against the practice run headers; one standard complete run per seed, no rehearsals or incomplete attempts.
- In-memory replay reproduced **493/493 live action batches**, using recorded server results, without network mutations.
- Initial-snapshot replay independently reproduced **621 phantom losses**, **12,000-bps** reconstructed markup, and **15,000 bps** when historical quotes were explicitly marked unsubmitted.
- Existing credential-free runner/recovery checks passed: **39 tests**, via the specified virtualenv Python and `-m unittest tests.test_recovery tests.test_final`. No new product tests or live rehearsals were created for this documentation task.

All monetary figures above are simulated euros. This report commits only aggregate findings and code references; it does not publish the private trace, checkpoint, raw request data or API key.
