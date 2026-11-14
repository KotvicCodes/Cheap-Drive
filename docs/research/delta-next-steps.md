# Delta next steps: protect service at the higher intake

Research audit, 14 November 2026; live-results recheck at **20:40:13 UTC**.
**Keep the capacity candidate near
`win_target_bps=4200`; test small changes to its dispatch timing before another
volume increase.** Nothing here promotes a new production model. Part A is the
tonight list; Part B is explicitly parked. Gemini's unmeasured euro estimates
are not used as forecasts.

## Evidence and candidate

All code references in this report refer to frozen commit
[`589daf7ad8b17d6c2402bb45f7cab7856cd777b9`](https://github.com/KotvicCodes/Cheap-Drive/commit/589daf7ad8b17d6c2402bb45f7cab7856cd777b9),
unless labelled current worktree. In particular, `delta.py:234–241` replaces
explicit pair transfer/driving settings with the selected profile: an
`extended` experiment still means **90 km / 720 driving minutes**, regardless
of a simultaneous `pair_transfer_km` override. Other pair controls remain
independent. The official SDK is a client/starter, not the simulator source;
it cannot establish hidden distribution parameters.

The base for every proposed run is the **settings object** in
[models/delta.json](../../models/delta.json), plus exactly:

```json
{
  "delta_wide_windows": 1,
  "delta_private_delivery_rescue": 1,
  "delta_pairing": "extended",
  "win_target_bps": 4200
}
```

`delta_ev_rule` remains at its default zero. Gamma, the selected Delta JSON and
the final runner were not changed. The research worktree is actually on
`t3/54bca21f`, forked from the integration branch; the integration worktree
remains separate.

I read the live `runs/queue/RESULTS.md` at the start and again before handoff.
The fixed f1 comparison below was independently recomputed from scores and
sequence-deduplicated saved events, rather than copied from the Gemini report.
Each row has eleven **paired** `delta-f1-s01..s11` weeks against selected Delta
(`rescue-notes`), including the difficult s07. Fresh f2 results must be reported
separately; the live table also has mixed-cohort totals.

| Policy | Mean won/week | Measured mean margin difference/week | Positive weeks | Mean expiry events/week | s07 on time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Selected Delta, target 3000 | 258.636 | Reference | — | 140.818 | 93.676% |
| Capacity switches, target 3000 | 260.182 | +EUR 284.25 | 9/11 | 14.273 | 91.700% |
| Capacity switches, target 3600 | 303.091 | +EUR 1,213.00 | 10/11 | 18.545 | 91.447% |
| Capacity switches, target 4200 | 344.364 | +EUR 1,863.53 | 10/11 | 24.545 | 91.117% |
| Capacity switches, target 4600 | 370.455 | +EUR 1,676.29 | 10/11 | 35.818 | 90.155% |
| Capacity switches, target 5000 | 397.000 | +EUR 1,529.48 | 9/11 | 43.091 | **88.998%: unranked** |
| Capacity switches, target 5500 | 427.000 | +EUR 1,665.55 | 8/11 | 48.455 | **88.864%: unranked** |

The candidate gains **943 noncancelled wins / 11 = 85.727 orders/week** and
EUR 20,498.84 total on this block. On s07 it instead loses EUR 552.51 against
selected Delta: 349 wins, 318 on time, 31 late and none undelivered. Only
**three additional late orders** fit above the legal 90% boundary at that fixed
denominator; four would disqualify it. The capacity switches at target 3000
already lose **1.976 percentage points** on s07, before extra intake. Returning
to 3600 alone is not an adequate service repair.

The final recheck also has complete **fresh f2 confirmation**: cap-4200 is
7/8 positive, **+EUR 1,389.22/week**, +83.625 wins/week, worst on time
**91.644% on f2-s04**, all eight ranked. Cap-3600 is 8/8 positive,
+EUR 1,119.91/week, +43 wins/week, worst **91.793% on f2-s04**. I recomputed
these differences from each arm's and `fresh-Delta`'s per-week `runs.jsonl`
scores; the live combined cap-4200 result is +EUR 1,663.82/week over 19 pairs,
17 positive. Fresh confirmation supports the volume gain but leaves the
service-headroom question open.

### What the hard-week trace actually says

For `cap-4200--delta-f1-s07`, I joined accepted post actions to receipts by
`batchId`, then expiry/booking/delivery events by gig, with final noncancelled
orders and revealed note deadlines determining lateness. The 31 late orders
reconcile to the score; counts below overlap and are not causal savings:

- **28/31** late orders had an expired gig; **24/31** had belonged to a pair
  that split; **7/31** had a drop. There were **zero failed visits** that week.
- **124** pair posts, **122** classified as rescue, **46** pair booking events,
  and **88** split events: 76 timer, 10 drop, two window. Booking and split
  events can concern the same gig; neither is a disjoint order count.
- None of the 31 late orders was ultimately delivered in a pair; three had
  previously been in a booked pair. Thus a larger safety margin for booked
  pair routes is less directly supported than reducing unbooked pair churn.
- Only **6/46** pair bookings arrived after minute 30 of that pair's posting,
  and **2/46** after minute 45. Across all eleven cap-4200 weeks the corresponding
  counts are **69/588** and **27/588**. These are observed bookings that an
  earlier split might sacrifice, not predictions of its counterfactual outcome.
- Backlog at competitive quotes: median **29**, peak **51**; **516/858** quotes
  saw more than 25 orders without a driver. Easy comparison seeds s01/s05/s10
  peaked at **23/25/20**. The existing queue's threshold of 25 is well motivated.
- The late option mix is ten `same_day`, twenty `next_day`, one
  `within_3_days`. Raising only same-day admission slack from 480 to 600/720
  would exclude **9/10 observed wins, zero late orders**, on s07. It is a poor
  first protection lever on the supplied evidence.

## Part A — Tweaks to test now

Ranked by the chance of protecting hard-week on time while retaining volume.
All ranks except #7 are accepted existing settings; #7 is a small default-off
code proposal, **not implemented**. Run one intervention at a time on the base
above. Six new queue files contained eleven variants, four seeds each, with
priority 6; none duplicated an existing results arm at submission. One group,
extra pair spare, already failed s07 during the audit and is now dropped below.

### 1. Keep 4200 normally; throttle only backlog above 25

**Already in the live queue; do not queue again.** Use the two
`hard-week-protection` arms already listed in RESULTS:

```json
{
  "capacity_valve": 1,
  "open_low": 15,
  "open_high": 25,
  "win_target_high_bps": 4200,
  "win_target_mid_bps": 4200,
  "win_target_low_bps": 3000
}
```

The second arm changes only `win_target_low_bps` to **2600**. These map to
`gamma.py:388–393,460–475`: the low target applies at **high backlog**, not at
low backlog. The evidence is the 516/858 versus zero easy-seed quotes above
25. Unlike the failed 3/6 and 5/10 intake screens, this preserves the 4200 target
across the observed easy-week backlog range.

Expected direction: fewer new wins during congestion, fewer subsequent
expiries/late orders, unchanged fee formula. It changes the learner target,
not an immediate intake gate: response is delayed, and backlog ignores booked
work that can later drop. The 2600 arm risks surrendering too much hard-week
revenue; evaluate orders and margin against **cap-4200**, as well as qualification.
No new code.

**New measured result:** on s07, target-3000 throttle gives **302 wins,
93.046% on time, EUR 11,893.82**, improving the cap-4200 margin by EUR 431.15
while giving up 47 wins. Target-2600 gives **299 wins, 92.308%, EUR 12,484.06**,
improving margin by EUR 1,021.39 while giving up 50 wins. The 3000 arm's s01
matches cap-4200's 305 wins and EUR 9,711.04 exactly. These are early protection
measurements, not a completed fresh confirmation. Both guards have three
completed f1 weeks at the final recheck; s05 has 337 wins under each versus
340 at cap-4200, so the observed quote-backlog range is not a guarantee of
identical easy-week behavior. The hard-week volume tradeoff is substantial.
The live queue now prioritises the 3000 guard across all 19 f1/f2 weeks and
the 2600 guard on a smaller hard-week subset.

### 2. Leave existing waiting singles alone when searching for a pair

**Queued:** `tweak-waiting-pairs.json`, label `fresh-pairs-only`:

```json
{"pair_with_waiting": 0}
```

`gamma_pairs.py:264–273` removes waiting posted singles from eligibility while
keeping eligible new/unposted orders and all existing route safety checks.
The s07 evidence is 122 rescue pairs out of 124, 76 timer splits and 24 late
orders touched by splits. `_try_pair` withdraws singles only after building a
plan (`gamma_pairs.py:376–413`); this is a scheduling choice, not an unsafe
withdrawal bug.

Expected direction: preserve single-gig exposure and avoid the new pair fee
clock/one-hour hold; quote target and admission stay at 4200, so the intent is
to retain wins while improving booking/service. Risk: it removes most observed
pair opportunities, potentially losing driver reuse and pair fee savings;
expiries or total fees could increase. `fresh-pairs-only` is not “pairing off”
and is distinct from the existing `delta_pairing="off"` ablation, which leaves
`pairs=1` and restores the original 30 km / 300 minute pairing limits. No code.

### 3. Return an unbooked pair to singles after 30 or 45 minutes

**Queued:** `tweak-split-timer.json`:

```json
{
  "split30": {"pair_split_minutes": 30},
  "split45": {"pair_split_minutes": 45}
}
```

`gamma_pairs.py:492–521` wakes/splits using the earlier of the timer and its
safe-start boundary. The current timer is 60 minutes. Six s07 pair booking
events occurred after 30 minutes, only two after 45; 76 splits were already
timer driven. Across eleven cap-4200 weeks, 578 splits were timer driven.

Expected direction: give the singles an earlier chance without changing
quote prices or admitted work; potentially fewer expiry/repost cycles and
better hard-week on time. Risk: lose some of the observed later pair bookings,
pay two single fees, and compete for more drivers. An early split is not a
new notification entitlement: the Handbook says an order normally notifies
each driver once. Do not repeat the existing **split90** screen. No code.

### 4. Shorten the rescue pair's opening-fee hold

**Queued:** `tweak-rescue-hold.json`:

```json
{
  "rescue-flat0": {"pair_rescue_flat_minutes": 0},
  "rescue-flat30": {"pair_rescue_flat_minutes": 30}
}
```

`gamma_pairs.py:235–255` starts rescue pairs at 7800 bps and delays every
higher scheduled rung until at least posting +60. The default split is also
posting +60. Thus a rescue pair cannot receive a higher rung **before** its
ordinary timer split; shortening the hold permits earlier escalation when
the underlying ramp has an earlier rung. It does not force a raise if that
ramp's next rung is later. There were 122 rescue pairs on s07 and 1,133/1,178
pair posts across the eleven candidate weeks.

Expected direction: earlier bookings for some pairs and fewer fallbacks,
preserving quoted volume. Risk: higher driver spend or earlier bookings that
later drop; many schedules will be unchanged, because their ordinary rung is
later than 60 minutes. This differs from the already screened
`pair_rescue_fee_bps=8400`: the opening fee stays unchanged. No code.

### 5. Use the existing service brake, without its blanket admission cuts

**Queued:** `tweak-service-brake.json`, two labels `projected600` and
`projected500`. Both apply this object; the latter changes `brake_soft_bps`
from **600** to **500**:

```json
{
  "brake": 1,
  "brake_soft_bps": 600,
  "brake_hard_bps": 750,
  "brake_soft_warnings": 100000,
  "brake_hard_warnings": 100000,
  "brake_soft_drops": 100000,
  "brake_hold_minutes": 120,
  "brake_caution_target_bps": 3600,
  "brake_target_bps": 3000,
  "brake_caution_bump_bps": 10000,
  "brake_bump_bps": 10000,
  "brake_caution_same_day_slack_minutes": 480,
  "brake_drop_same_day": 0,
  "brake_min_slack_minutes": 480,
  "brake_blocks_long": 0
}
```

`gamma.py:299–358,406–434,460–465` already implements it. The signal is
`(late + 0.5 * warned_open) / max(non_cancelled_won,40)`, in bps; the existing
warned-open set is not restricted to the trailing 24 hours. The large warning
and drop thresholds isolate that projected service signal. Neutral bumps
avoid an extra immediate price increase; admission retains its base filters.

In the frozen cap-4200 trace, s07 has **199/858** quotes at projected lateness
≥600 bps and **297/858** at ≥500, first crossing 600 at world minute **5202**
(Thursday 14:42). Its maximum is **735.736**; s01/s05/s10 never reach 500.
These are baseline signal exposures, not a replay of the enabled controller.

Expected direction: hold 4200 on easy weeks; lower the learner target when
service stress is visible, potentially reducing later load/expiries. Risk:
it first reacts after trouble appears, has a 120-minute hold, and a cumulative
late fraction can keep it engaged long after a transient shock. It may lose
volume without fixing dispatch already in flight. The hard threshold could
be crossed in a changed trajectory even though baseline s07 stays below it.
Do not combine this with #1 until their separate effects are known. No code.

### 6. Pay a higher single-gig opening floor at sparse pickups only

**Queued:** `tweak-scarce-opening.json`:

```json
{
  "scarce95": {
    "town_starved_near30": 10,
    "town_starved_opening_fee_bps": 9500
  },
  "scarce105": {
    "town_starved_near30": 10,
    "town_starved_opening_fee_bps": 10500
  }
}
```

`gamma.py:204–242,567–577` counts initial driver homes within **30 road km**
and takes the maximum of fee floors. This is a supply proxy, not current
positions or the notification's straight-line radius. s07 has 669 roster
drivers; 119 of its 349 noncancelled wins originate at towns with ≤10 nearby
homes, including 17 of its 31 late orders.

Accounting for existing short/premium/long floors, the 9500 floor would affect
**108 wins including 14 late** on s07; 10500 affects **113 including the same
14 late**. For s01/s05/s10 the respective affected-win counts are
99/31/149 at 9500, or 103/33/164 at 10500. These are static eligibility counts,
not actual changed bookings or a saving estimate.

Expected direction: improve single booking chances and reduce hard-week
expiry/late work without lowering the win target; higher driver fees are the
direct cost. Pair schedules have their own fee settings, so this is no
blanket pair price increase. Risk: home counts are an imperfect proxy, and
this also spends on easy weeks; there is no evidence that every affected gig
was underpaid. Distinct from the existing global `opening9000` screen. No code.

### 7. Optional small code arm: require matching single-gig audiences

**Needs code; not queued or implemented.** Proposed setting:
`delta_pair_same_audience=1`, integer 0/1, default 0, on the same base. This
setting does **not** exist at 589daf7 and must not enter that commit's queue.

Bounded implementation contract, roughly 15–25 production lines including
factory plumbing: in a Delta-only `_plan(first, second)` override, when enabled,
compare the exact `audience` dictionaries returned by `_single_action` for
the two orders. On mismatch return `(None, "audience_mismatch")`; otherwise
call the existing planner. Keep the current audience union and every route,
withdrawal, retry and fallback rule unchanged for accepted plans. Validate
strict integer input; test explicit-off action/journal parity, same-audience
acceptance and differing manual/experienced requirements rejected before any
withdrawal. Make no Gamma changes.

The current union in `gamma_pairs.py:306–313` is **legal**, not a bug, but can
reserve an experienced/manual driver for a car that did not need one. Rebuilding
single audience requirements from the frozen note parser and car flags gives
**12/124** mixed-requirement pairs on s07, with **three** mixed pair booking
events; s01/s05/s10 have 8/12/6 such pair posts. This establishes exposure,
not a service benefit or an external team's claimed gain.

Expected direction: preserve specialised-driver capacity for other jobs;
quoted orders stay unchanged. Risk: discard useful pooling, especially when
an experienced/manual driver could economically carry both cars. Small scope
qualifies it for Part A, but its weak hard-week evidence puts it behind all
settings tests. Build only if the earlier screens leave time.

### Queue and selection handoff

All six new files were written atomically into the integration worktree's
`runs/queue/pending/`, using the full commit above, `delta:make_delta`, the exact
base, priority 6, and seeds in this order:
`delta-f1-s07`, `delta-f1-s01`, `delta-f1-s05`, `delta-f1-s10`.
Each contains at most two variants. The files are ignored operational inputs,
not tracked model configuration. The scheduler may move them after ingestion.
All six have now been ingested. **`tweak-pair-spare.json` is rejected**, not a
remaining recommendation: its `spare120`/`spare180` variants set
`pair_spare_minutes` to 120/180 from the base 60. On s07 they deliver only
**89.429% / 89.398% on time**, with 350/349 wins and EUR 10,285.35 / 9,915.38
margin. This was a low-ranked, settings-only safety hypothesis; its live
failure reinforces the warning that less pairing does not necessarily protect
service. No repeat or new file was submitted after those results appeared.

**Construction was executed, not inferred from a signature:** a `git archive`
of 589daf7 was extracted under this research worktree's ignored `runs/`; its
own `PairWorld` fixture from `tests/test_gamma_pairs.py` and `Journal(StringIO)`
were used, as in `tests/test_delta.py`. All eleven variants constructed with
the pinned SDK/Python 3.12 environment, with fixture `act`/`advance` replaced
by functions that fail if called. The base switches, effective 90/720 profile
and every overridden Gamma/driver setting were asserted after construction.
No world/client or team key was used. No model code was implemented.

The pre-existing #1 arms and the five surviving new groups should compare **against
cap-4200 on the same seeds**, not only against selected Delta: a positive
Delta difference can conceal loss of most of the volume improvement. Record
won/noncancelled orders, each week's on-time numerator and denominator,
undelivered, expiry events, pair posts/bookings/splits, paid driver fees,
late refunds and net margin. Fewer expiries alone is not success.

Treat s07 plus the three easy seeds as a diagnostic screen, then inspect the
worst fresh f2 weeks and confirm on independent weeks before promotion.
Legally every week needs ≥90% on time; **92% is a proposed operational cushion,
not the game cutoff or the queue's current rejection rule**. Prefer a repair
that increases hard-week headroom while retaining most of the 4200 arm's
orders/margin. Do not launch additional broad pricing/learner searches tonight.

### Checked and dropped

| Gemini claim or proposal | Check and disposition |
| --- | --- |
| The three dispatcher fixes guarantee +EUR 350–650/week | **Wrong as a forecast.** They already exist. The four-week `all-fixes` result is −EUR 344.91/week; EV alone −EUR 200.44, 0/4 positive. Keep EV off; the selected capacity combination has its own measured evidence. |
| Wide windows eliminate 89.5% of expiries and therefore create a similar economic gain | **Causal claim unsupported.** The mechanism is real and already switched on. My f1 counts are 1,549 selected-Delta expiry events versus 270 at cap-4200, but different wins/dispatches prevent attributing all of the difference to that switch; its isolated four-week margin was −EUR 89.56/week. |
| Private delivery grace can be rescued | **Correct, already implemented.** Rules, Gigs, permits extending other stops, while Rules, Handling cars 5 gives private delivery its +30 minute deadline. It does not permit extending private pickups. The new switch is in the base; paired Gamma economics do not prove a separable +EUR 98.35/week fix. |
| Increase volume further to 5000–5500 | **Already measured and unsafe:** s07 is 88.998%/88.864%; 4600 has only 0.155 percentage points of headroom and a lower f1 mean margin gain than 4200. |
| More pair deadline spare, or reverting extended pairing, must improve safety | **Disproved on s07 during this audit.** Newly queued spare120/spare180 are unranked at 89.429%/89.398%; the existing `delta_pairing="off"` ablation is also unranked at 89.143%. Keep the rejected measurements; do not rerun them. |
| Disable wide windows globally | **Useful attribution, not a retained tonight arm.** On s07 `delta_wide_windows=0` gives 347 wins, 91.643% on time and EUR 12,471.33 (+EUR 1,008.66 against cap-4200), despite 321 expiries versus 71. The queue now labels this arm rejected/stopped while prioritising the backlog guards; its two completed weeks are both legally ranked. Do not requeue it or mistake its stopped status for a sub-90% result. |
| Repeat segments, lanes, trust=50/75, 31–32% low-backlog intake, fastest-only/split learner or dual option spread | **Already tested or close to a failed design.** [Delta results](delta-results.md) records fresh-week failures. The live 3/6 and 5/10 backlog intake screens also lost margin. Trust=75 is not a measured rescue of trust=50; do not reopen broad repricing now. |
| Try transfer=52, drive=480, pair fee 6600/7800/8400, rescue fee 8400, or split90 | **Already in RESULTS.** Do not duplicate. Also a custom 52 km setting is overwritten by `delta_pairing="extended"`; use `off` plus explicit limits only in a genuinely new profile experiment. |
| Tighten same-day slack to protect s07 | **Poor target in our data.** At 600/720 minutes it removes 9/10 observed s07 wins, none late. Twenty of 31 late orders are `next_day`. Park broad menu/admission cuts. |
| Freeze every overnight fee raise because no drivers look | **Wrong premise.** Rules restrict overnight direct-offer reading; the Handbook also restricts notification reading, not every app view. I counted **4,076** overnight public gig views in selected Delta's eleven weeks and **5,524** at cap-4200. Any saved-fee arithmetic holding bookings fixed is not recoverable profit. |
| The reference fee has exactly 14% noise; blending it saves EUR 495/week | **Partly supported only.** Handbook, Typical fee, confirms per-request noise, not 14%. On s07, the low `ref/min(listPrice)<0.8` group has 4/41 late orders, versus 31/349 overall: it does not isolate the dominant hard-week failure. Fit a fee-cost model before changing the anchor. |
| Drop in a 100%-accurate parser v2, fixing 637 cases | **Unverified artifact and accuracy.** No reproducible v2 implementation, corpus manifest or held-out evaluation accompanies the three write-ups. Word-hour parsing already exists in `notes.py:62–83`; summer tyres are absent from `NoteFacts` and require forecast/retry integration, not just another regex. |
| Subtract one minute from every closing time to prevent 17 failed visits | **Not verified for this cohort.** `_daily_window` and `beta.closing` use the stated close; the claimed exclusive simulator boundary is not established by SDK source. Across our eleven selected-Delta weeks there are two `closed` pickup failures, and one at cap-4200; **none** occurs at the site's stated closing minute. Note closes and stated closes need separate evidence. Do not silently subtract from private slots or note deadlines. |
| Shift every delayed-readiness deadline in our model | **Real rule, unsafe blanket fix.** Rules, Your account, and the Handbook say `order_won` already contains the shifted deadline. Quote-time option feasibility may need a distinct correction; shifting won orders again would double-count it. Park until a failing request-level fixture exists. |
| Final stalls are proved to be fsync, 20 ms batching is zero-risk, and rejoin is still a state wipe | **Stale/unproven in this checkout.** Current `gamma.py` has `rejoin_model` and quote-receipt recovery; `capture.py` has batched history recording. Latency attribution needs timings, and event batching changes action time. See [the recovery handoff](final-rejoin-recovery.md); no final runner edits belong to this research task. |
| We lead every team's EUR/order, so the entire gap is volume | **Overstated.** Our saved Test Final 2 numbers yield EUR 50.065/order, above the displayed leaders, but the three write-ups do not prove every team's ratio. Volume/rate decomposition is arithmetic, not evidence that changing policy holds unit margin, service or requests won fixed; different official rounds are not paired model tests. |

## Part B — Parked for the next model

These are research directions, not tonight's implementation queue. External
repositories are leads from the supplied session, not independently reproduced
benchmarks; none of their reported euro improvements transfers to our model.

- **A learner with separate world/day/shock state.** Gamma has a global
  multiplicative win-target learner (`gamma.py:549–563`), and the documented
  level-8 price war/outage makes regime separation plausible. A new design
  needs identifiable world/day/region states, treatment of skipped menu
  feedback, persisted/replayed state, frozen fitting data and fresh-world
  tests; the reported LLR/EKF replay gains are unverified here. The isolated
  `freeze_day_drop_bps` setting is not a substitute: it floors against the
  inherited day's opening markup and can prevent recovery after an outage.

- **Routing/PDPTW, matching and longer chains.** The present planner considers
  sequential two-order routes, chooses by transfer/finish and uses a timed
  fallback; it does not solve fleet routing, maximum matching or a global
  pickup-and-delivery problem. Build a candidate graph with note/calendar,
  audience, charging, repositioning and 720-minute constraints, then an
  optimiser with bounded runtime and full booking/drop/change recovery;
  public roster homes do not reveal drivers' current private schedules.

- **Pair buffers, backhaul-aware quotes and return-trip scoring.** Holding
  fresh high-slack orders for 20–30 minutes, pricing against a feasible return
  partner, or using Clarke–Wright savings could improve matching beyond the
  current immediate greedy choice. The notes attribute these techniques to
  RoutePulse, Halal Team and other repositories, but buffering would need new
  timers, notification/exposure analysis and capacity reservation; the
  observed split churn is not evidence that an additional pre-post delay pays.

- **Town/lane priors and deadline-load capacity.** Geography and the captured
  home roster are real inputs; s07's sparse pickup exposure supports looking
  beyond a single global backlog. Learn priors and deadline-day load from
  frozen data with shrinkage, count unresolved quote reservations, and verify
  robustness on new towns/weeks; do not port another team's 30-town offsets
  or roster percentages as known constants, especially after our lane and
  town-cap failures.

- **Driver booking hazard and a different fee anchor.** The Handbook confirms
  noisy reference fees, expensive evening/private work, waiting for anticipated
  raises and the persistence of order age. Estimating those effects could
  support denoising, daytime fee clocks, flat schedules or capped late rescue,
  but requires censored booking/drop data, an appropriate lane-cost baseline
  and causal paired tests; neither a fixed mixture with list price nor a
  foreign team's 6-hour review is a validated policy for us.

- **Port selected ideas from public repositories.** The supplied inventory
  points to [RoutePulse](https://github.com/source-exp/RoutePulse),
  [Halal Team](https://github.com/ink-waffle/junction26-spread),
  [spreadbahn](https://github.com/expires/spreadbahn-junction), and
  [Bahn](https://github.com/markusmalmivaara-svg/Bahn) for shock filters,
  reservation/load scoring, matching and fee modelling. Before importing a
  technique, pin and inspect its actual commit, verify licence/mechanics and
  reproduce its ablation locally; team identity, leaderboard position and
  claimed causal gains in the Gemini inventory were not independently verified.

- **Notes v2 or an LLM for notes.** The current bounded parser has real scope
  limits, including no tyre capability in `NoteFacts`; the existing
  [Gemini prototype](gemini-notes.md) already provides an offline contract and
  cached adapter, without measured live accuracy or latency. Build an
  independently adjudicated holdout with correction/negation/role tests,
  forecast-aware tyre handling, strict latency limits and deterministic
  fallback before considering inference on the quote path; training-corpus
  parity is not a delivery guarantee.

- **Trade-ins and multi-car private visits.** Rules explicitly protect the
  old-car pickup immediately following the new-car delivery within one
  trade-in gig, whereas a separated old-car pickup must meet its slot.
  Gamma currently rejects multi-leg requests by default; enabling `trade_ins`
  alone would bypass a deliberate admission guard without proving that note
  windows, shared-visit protection, combined driving limits and split recovery
  work together, so this belongs to a dedicated next-model design.

- **Direct offers and a richer availability model.** The rules provide a
  real route around drivers waiting for public raises, with strict offer
  quotas and unread/expired ambiguity. Implement eligibility, per-driver/per-gig
  budgets, offer outcome persistence and restart reconciliation before testing;
  it is not an existing Gamma setting or a sub-40-line fee tweak.

### Provenance and verification limits

The three supplied Gemini write-ups were read only from
`/home/agent/.t3/worktrees/Cheap-Drive/t3-d9eb04e0-62fae69aa9551399/docs/research/`.
They were checked against [Delta results](delta-results.md),
[challenge constraints](../challenge.md), [operational reference](../reference.md),
the SDK at the supplied `t3-a14884b2-9968a1fe51ca69bf/.venv/` path, and the
capacity/bug audits in the supplied `t3-19f5da1b-0a74d232959422e3` and
`t3-ac7588fc-14350bc5646ae7d8` worktrees. I also fetched the public official
[Rules](https://spread.bahnexpress.com/kit/RULES.md) and
[Handbook](https://spread.bahnexpress.com/kit/HANDBOOK.md) read-only on
14 November; rule quotations above take precedence over historical local prose.

Private evidence remains under ignored `runs/research-next-steps/` in this
worktree: frozen source, `audit.py`, `audit.json`, `targeting.json`, construction
script and validated queue payloads. The audit reads selected Delta traces
from the integration worktree's `runs/delta-final/{b5,b6,b8}` and volume traces
from `runs/queue/out/volume-tap/weeks/`. It deduplicates events by sequence,
excludes cancelled orders from service denominators, and uses revealed note
deadlines where tighter than final order deadlines. Posting, booking and split
counts are events, explicitly distinct from orders; conditional exposure does
not identify counterfactual gains.

Not independently reproduced: the purported 32-week Gamma counterfactuals,
10,980-note parser parity, 19 repository dissections and private benchmarks,
14% noise parameter, exact hidden booking-hazard multipliers, after-15:00
threshold coefficient, or the alleged schedule-change notice. No euro gains
for an unmeasured tweak are asserted. Five newly queued groups remain
**unmeasured proposals** at the stated recheck; the sixth, extra pair spare,
already has a negative result and was removed from the ranked recommendations.
