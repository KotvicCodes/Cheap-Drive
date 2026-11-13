# AI overview: Cheap-Drive and the Spread challenge

Reviewed on 13 November 2026. This document records observations from the official documentation and my recommendations for Cheap-Drive. Recommendations are hypotheses to test, not measured results from our system. No authenticated practice worlds or ranking runs were played for this review.

## Current project decisions

- **Language: Python.** Use the official Python kit and keep the strategy easy to inspect and change. Revisit the implementation language only if there is a demonstrated reason later.
- **Compute time is not a current optimization target.** Prioritize a working prototype, correctness and strategy experiments. We explicitly accept slow or computationally expensive approaches for now; runtime and compute-cost optimization will be addressed later.
- **First baseline: constant prices on both sides.** Quote a configurable fixed euro amount per order for every offered delivery option, and pay a configurable fixed driver fee per car. This establishes the request-to-delivery flow before adding smarter bidding.

## What we should focus on

**Build a selective, reliable dispatcher that earns good margin from work it can actually deliver.** At the final's difficulty, winning more orders can make the result worse: scarce drivers become overloaded, deliveries become late, and the team can lose its ranking altogether.

My recommended order of work is:

1. Establish a working starter and repeatable evaluation on several weeks.
2. Add capacity-aware order selection and profitable quotes, while protecting the on-time threshold.
3. Make delivery constraints, dealer notes and recovery events reliable.
4. Improve opening driver fees and targeted direct offers.
5. Add simple combinations of cars, adaptive pricing and dealer-trust strategies when experiments justify them.

The final's live-clock requirements are documented below for later work. They do not change our current decision to defer compute-time optimization while building and testing the prototype.

## What winning means

The challenge has two distinct stages. [Rules: The game](https://spread.bahnexpress.com/kit/RULES.md#the-game) and [judging](https://spread.bahnexpress.com/judging) define them:

- **Reach the jury:** finish the final among the ten ranked teams with the highest gross margin. A team must win at least one order and deliver at least 90% of its won orders on time. An order with two cars is on time only when both arrive by their deadlines; cancelled orders do not count.
- **Win with the jury:** the top ten are judged on elegance, clarity, creativity and robustness. Once a team reaches this stage, its margin no longer counts in the jury's decision.

The score is the sum of the account: dealer revenue minus driver fees, refunds, penalties, fines, waiting and release costs. Revenue alone, number of orders won and percentage margin are not the ranking objective.

**Implication:** pursue strong margin with a reliability buffer, and keep evidence explaining why each major idea works. I would initially target roughly 95–97% on-time performance on validation weeks; that is a proposed engineering buffer, not an official requirement or a guarantee for the final.

## Why level 8 changes the strategy

The final is one secret level 8 week. Each team gets its own copy of the same requests, drivers and random events; teams do not share a pool of cars or drivers. [Rules: Practice and the final](https://spread.bahnexpress.com/kit/RULES.md#practice-and-the-final)

- Levels 7 and 8 have only 26–40% of the drivers of an average normal week. Level 8 also redistributes drivers unevenly between towns, so some towns lose nearly all of them.
- List prices and `referenceFeeCents` remain those of a normal week. The typical fee is a reference, not a reliable shortage-clearing fee or the cheapest possible driver cost.
- The level 8 competitor's overall price level is 26–54% above list price, before the other lane, day and request effects. Quoting list price therefore wins too much work.
- Every week includes a regional competitor outage, a driver flu, a bulk order and a price war. On the price-war day, the competitor quotes 20% below its usual prices everywhere from 08:00 to 18:00.
- Dealer trust rewards repeated reliable delivery, and a late order destroys a substantial part of that accumulated advantage.

The handbook's starter example on seed `spread-1` loses €72,612.51 at level 8 and delivers only 45.5% of orders on time. Those are the organisers' published figures, not our benchmark. The useful lesson is that the starter provides plumbing, not a competitive policy. [Handbook: The first 15 minutes](https://spread.bahnexpress.com/kit/HANDBOOK.md#the-first-15-minutes)

## Priority 1: choose orders before committing capacity

The biggest early improvement is likely to be deciding which work to win. A cheap driver for one request might be the only feasible driver for another. Accepting an order therefore consumes both money and a scarce delivery opportunity. [Handbook: Dealers compare prices](https://spread.bahnexpress.com/kit/HANDBOOK.md#dealers-compare-prices)

For each request and offered delivery option, estimate:

- A realistic driver fee, including travel to pickup, the destination, timing, special requirements and shortage conditions.
- Feasibility with slack for viewing, booking, reaching pickup, charging or plates, weather and delivery opening hours.
- Compatible driver supply near the route and the commitments we have already won.
- The chance of winning at a candidate price and the likely refunds or other costs if execution goes wrong.
- How much accepting this work reduces our ability to fulfil other orders.

A useful conceptual objective is:

```text
expected contribution(price, option)
  = P(win | price, option, recent market)
    × (price − expected fulfilment cost − expected incident costs
       − opportunity cost of scarce capacity)
```

This is a proposed model, not a simulator formula. Apply a separate feasibility/risk gate; positive expected contribution alone does not protect the 90% requirement. When quoting several options, the dealer chooses among them, so optimize the menu together rather than adding independent win probabilities.

Start with understandable rules: avoid infeasible windows, account for existing backlog, prefer routes towards driver homes or our drivers' upcoming destinations, and charge more for scarce capacity. Track outstanding quotes as possible future commitments too: several simultaneous wins can overload us before we have posted their gigs.

At levels 4–8, decline unattractive work with a deliberately uncompetitive quote. A losing quote costs no goodwill; silence does. At levels 1–3, every quote wins at the first option's list price, so decline by not quoting. Quotes must arrive strictly before `respondBy`. [Rules: Price requests](https://spread.bahnexpress.com/kit/RULES.md#price-requests)

## Priority 2: make constraints and recovery dependable

A delivery failure costs more than its immediate fee: it can also cause a refund, damage dealer trust and threaten qualification. Build a structured interpretation of each order before posting a gig. [Rules: Notes and changes of plan](https://spread.bahnexpress.com/kit/RULES.md#notes-and-changes-of-plan)

Important details to implement correctly:

- Notes in Finnish, Swedish and English can change readiness, payment release, pickup hours, delivery hours, deadlines, plates, gearbox requirements and summer-tyre restrictions. Notes can include corrections, negations, typos and multiple facts.
- Resolve relative days from the request's arrival day. A named weekday means 2–6 days after arrival; an hour written in words means a working hour. The starter's keyword-and-clock reader is deliberately incomplete.
- Premium cars need drivers rated at least 4.8 with at least 50 completed gigs. Manual cars need a compatible licence. Plates add 30 minutes; required charging adds 40 minutes.
- An electric car below 30% charge on a route over 200 km needs charging. Omitting it adds 90 minutes of lateness and a €100 fine. A premium-driver violation costs €150.
- Private deliveries have booked slots and a deadline 30 minutes after the booked hour ends. Private pickup slots do not simply extend when missed. Dealer sites have restricted Saturday hours and are closed Sunday.
- `lastPickupAt` is more useful than the nominal deadline for deciding urgency. The `deadline_close` event comes three hours before it; drivers still need time to see the gig and travel to pickup. React before that warning where possible. Re-evaluate after changes: when an on-time pickup is already impossible, `lastPickupAt` can represent the first collectable minute instead.

Maintain each leg's status and its current gig. Handle drops, no-shows, failed visits, expired gigs, forecasts, changed orders and cancellations explicitly. A cancelled order can withdraw a gig containing another order's car; those remaining cars must be posted again. A changed destination is applied by the world even to a booked or started gig, and may add driver cost.

Once we have won an order, avoiding delivery is very expensive: an undelivered order earns no revenue and incurs a penalty of twice its price. Rescue decisions should compare incremental costs, late refunds and qualification risk; simply capping every rescue fee at the original expected profit can make losses worse. [Rules: Your account](https://spread.bahnexpress.com/kit/RULES.md#your-account)

**Where AI may help:** multilingual notes are a natural candidate for language-model assistance. Start with a fast structured parser, log uncertain cases and evaluate against practice reveals. If an LLM is added, validate its output and use a bounded, conservative fallback. Avoid making every live quote depend on a slow remote model call. This is an implementation recommendation; the challenge does not require an LLM.

## Priority 3: pay enough early, and use the right drivers

The cheapest opening fee is not necessarily the cheapest completed delivery. Most gig views arrive in the first few minutes, repricing sends no new notification, and drivers learn to wait when our fees routinely rise. Reposting does not reset an order's age or erase its fee history. [Handbook: Drivers learn your fees](https://spread.bahnexpress.com/kit/HANDBOOK.md#drivers-learn-your-fees)

Test a realistic opening fee with limited, purposeful escalation against the starter's automatic hourly increases. Adjust for route, timing, requirements, current backlog and observed booking delays. Fees that only just cover a driver's cost can also produce more drops, so booking rate alone is an incomplete measure.

Direct offers are particularly interesting for drivers finishing one of our gigs near the next pickup. Their home, known work position and scheduled completion can make them cheaper than a driver starting from elsewhere. An offer can reach a driver whom a home-based notification would miss, and a driver who reads it accepts if it pays sufficiently rather than waiting for a possible app increase. [Rules: Direct offers](https://spread.bahnexpress.com/kit/RULES.md#direct-offers)

Use these limits carefully: an offer lasts ten world minutes, each driver gets at most three offers per day, and a gig can have at most three open offers. No driver reads an offer between 23:00 and 07:00. An expired offer may have gone unread; a view is evidence of app activity, not proof of availability, route suitability or willingness to accept.

The roster gives home town, licence, rating, completed gigs and drops. It does not reveal today's working schedule. Public transport costs are also unpublished. Treat both availability and fulfilment cost as estimates that improve from bookings, views and drops, rather than facts known from the map.

## Priority 4: combine cars when the savings justify the risk

One driver can move several cars sequentially in a gig. This is not a truck collecting multiple cars simultaneously. The gig fixes the stop order and can include at most 12 hours of road driving between the first pickup and last delivery, including repositioning between cars. Plates and charging time do not count towards that driving cap, but do affect feasibility. A single-car gig has no such cap. [Rules: Gigs](https://spread.bahnexpress.com/kit/RULES.md#gigs)

Start with feasible pairs: return routes, nearby consecutive pickups, and work that brings a driver home. Compare the total proposed fee, time windows, extra travel and failure exposure with posting separately. Keep a limit on how long we delay an urgent individual order while searching for a partner.

Trade-ins have an important special rule: put the old car's pickup immediately after the new car's delivery to collect it during the same visit. Separating those legs loses that protection; the old car alone must fit the private pickup slot. Split a trade-in when its combined road driving exceeds 12 hours.

A simple greedy pairing method is a good first experiment. Large optimization machinery should follow evidence that it improves margin without weakening reliability or slowing live decisions.

## Priority 5: adapt prices and protect dealer trust

The competitor is hidden, varies by lane and day, and responds to our wins. A price table learned once will become stale. At level 8, a sudden broad fall in win rate may be the temporary price war; matching every cut could win work that is no longer profitable. A regional outage can create profitable opportunities, but does not create more drivers. [Handbook: Dealers compare prices](https://spread.bahnexpress.com/kit/HANDBOOK.md#dealers-compare-prices)

Begin with a small set of price multipliers and update from wins and losses, pooling evidence across similar routes where individual lanes are sparse. Include time, dealer and current capacity. Treat outcomes as noisy evidence, not exact competitor prices: dealer preferences, speed options and trust also affect acceptance. Keep learning rates and complexity small enough to explain and validate.

Dealer trust creates an additional reason to favour reliable work. At level 8, each on-time order increases the prices that dealer accepts by 1%, up to 25 orders and 25%. A late order halves its count, rounded down. The competitor still matters. [Rules: Practice and the final](https://spread.bahnexpress.com/kit/RULES.md#practice-and-the-final)

**Hypothesis worth testing:** serving a recurring dealer reliably early in the week may enable higher-margin work later. Track trust per dealer, test modest price adjustments as it grows, and protect it from risky commitments. Do not assume trust guarantees a win or makes a loss-making early order worthwhile; the competitor may also lower prices when we win most of that dealer's requests.

## Later runtime work: transferring practice success to the final

Use the official Python client initially. Both official language kits provide practice and final modes; the clients already handle rate-limit headers and stream reconnection. Our first prototype targets ordinary practice only. Keep strategy decisions separate from the transport so we can later reuse the policy in final mode. The following are final-integration requirements, not current compute-time optimization goals. [API reference](https://spread.bahnexpress.com/kit/API.md) and [OpenAPI contract](https://spread.bahnexpress.com/openapi.json)

- Practice time pauses until `advance`. The final clock moves independently. During ordinary weekday daytime, fifteen world minutes are only **4.5 real seconds** to answer a quote. Other portions of the week are compressed differently.
- Prioritize time-sensitive quotes and recovery actions over optional learning, analysis and diagnostics. Budget for bursts such as a bulk order; a slow operation in the event handler can delay later requests.
- Final limits are **20 actions per second** and **50 reads per second**, with token buckets. A batch contains at most 50 actions, but final actions are charged individually, not one token per HTTP batch.
- Consume the WebSocket stream, resume using the last event sequence and deduplicate replayed events. Practice `advance` responses can repeat events after a server restart too.
- Reconstruct state from snapshot and event history on restart. Reconcile gigs and orders before retrying uncertain writes; do not assume a lost response means the action failed or that writes are automatically idempotent.
- Inspect each action result: a valid HTTP 200 can contain `{ ok: false, reason }`. A successful request does not imply every action succeeded.
- Retain the kit's recovery path for unreachable servers and 502/503/504 responses. If our process stops, the week continues; existing drivers work, but unanswered requests go to the competitor.

Deploy the final process on a stable machine with a good connection, ideally near the server in Stockholm as the organisers suggest. Keep `SPREAD_KEY` outside the public repository. Registration, cloud deployment and running worlds are separate tasks; this review does not perform them.

## How we should measure progress

Build an evaluation runner before tuning many parameters. Practice worlds are deterministic for the same seed, level, actions and action times. Compare versions on the same 10–20 seeds, then validate on a separate seed set that was not used for tuning. Use low levels to isolate bugs, but make level 8 the main selection criterion. [Handbook: Practice tools](https://spread.bahnexpress.com/kit/HANDBOOK.md#practice-tools)

For each run record the code revision and settings, margin, on-time share, ranked status, won orders, undelivered orders and major costs. Also record booking delay, drops, failed visits and rejection reasons by route and request type. Report how many validation worlds qualify as well as average margin: an attractive average can hide weeks below 90%.

Run these experiments in sequence, enabling one major idea at a time:

1. Starter versus capacity-aware selection and price floors.
2. The same selection policy with improved notes and constraint handling.
3. Automatic escalation versus calibrated opening fees and targeted offers.
4. Separate gigs versus feasible pairs.
5. Static prices versus online updates, then trust-aware adjustments.

Use reveals to inspect true constraints and mistakes on orders we won. They never disclose competitor prices or drivers' private costs, and do not give hidden facts about cars we did not win. Forks are useful for comparing decisions from the same moment, but do not replace testing across independent weeks. There are at most eight unfinished practice worlds per team; forks consume slots, and all systems on one team key share its practice rate limit.

Ranking rounds contain five secret weeks at each level. All five must individually meet the delivery minimum; a good aggregate on-time share cannot rescue one failed week. Runs cannot be forked or revealed, and deleting an unfinished ranking run still makes it count after it finishes unattended. Use ordinary practice for tuning and ranking rounds for external comparison with the house teams and other teams. The rounds do not count towards the final. [API: Practice rankings](https://spread.bahnexpress.com/kit/API.md#practice-rankings)

Exercise the live runtime in a test final, including reconnects and a process restart. Save paired experiment results for the jury: the idea, why we tried it, and its effect with and without it on the same weeks.

## Event deadlines and submission

The published schedule is for Junction 2026, 13–15 November. Times below are Helsinki time; on these dates Helsinki is UTC+2. Recheck the [judging page](https://spread.bahnexpress.com/judging) and Junction's schedule before relying on them.

- Preliminary Junction submission: Friday 13 November, 23:59 (21:59 UTC).
- Test finals: Saturday 14 November, 14:00 and 20:00 (12:00 and 18:00 UTC). These begin from Thursday in the simulated week and last about 19 minutes.
- Final registration closes and the final is set: Sunday 15 November, 07:30 (05:30 UTC).
- Start the dispatcher before the final begins at 08:00 (06:00 UTC); let it run through the end, roughly 34 minutes later.
- Final Junction submission: Sunday 15 November, 10:00 (08:00 UTC). Include the submission hash from the team page, a code link and a presentation, ideally 5–10 slides or a short video.

For the presentation, concentrate on a few explainable decisions and paired evidence. Show final and best ranking-round results, failures and limits. The stated jury criteria favour a small, well-supported system over complexity we cannot explain.

## Sources and limits of this review

I read the following public material, including the linked Markdown documentation and the TypeScript starter's decision and recovery logic:

- [How it works](https://spread.bahnexpress.com/how)
- [Judging and submission requirements](https://spread.bahnexpress.com/judging)
- [Leaderboard page](https://spread.bahnexpress.com/leaderboard) — explains live and practice rankings; this document makes no claim about current team standings.
- [Documentation index: llms.txt](https://spread.bahnexpress.com/llms.txt)
- [HANDBOOK.md](https://spread.bahnexpress.com/kit/HANDBOOK.md)
- [RULES.md](https://spread.bahnexpress.com/kit/RULES.md) — authoritative when explanatory pages differ.
- [API.md](https://spread.bahnexpress.com/kit/API.md)
- [OpenAPI schema](https://spread.bahnexpress.com/openapi.json)
- [Official kit directory](https://spread.bahnexpress.com/kit/) and [TypeScript kit](https://spread.bahnexpress.com/kit/spread-typescript.tar.gz)

The proposed priorities, reliability buffer, cost model, fee policy and learning methods remain untested. Their value should be decided by repeatable level 8 experiments and live-runtime checks, not by this analysis alone.
