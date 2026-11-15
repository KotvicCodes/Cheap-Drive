# Cheap-Drive presentation: judging guide and reader notes

[Open the presentation](cheap-drive-alpha-to-gamma.html)

Source: [Spread: how you win](https://spread.bahnexpress.com/judging), checked live on 14 November 2026. Definitions checked against the [official rules](https://spread.bahnexpress.com/kit/RULES.md). Recheck the live page before submission: the guidance can change.

Company branding: the [official Spread homepage](https://spread.bahnexpress.com/) says “A Bahn challenge at Junction 2026” and “What Bahn does”. Use **Bahn** on the title slide; the `bahnexpress.com` domain is not the displayed company name. The embedded monochrome logo mark comes from the [official challenge site’s SVG icon](https://spread.bahnexpress.com/icon-2nt2tvdj.svg), with its background removed and colour matched to the title text. Checked 14 November 2026.

## Use the challenge's words

The judging page says: “Use the challenge’s words: dealer, request, gig, fee, typical fee, deadline. Do not invent new names for them.”

| Word | Meaning and how we use it |
| --- | --- |
| **Dealer** | The customer asking for car transport and comparing our quote with the competitor's |
| **Request** | A dealer's request for a price, before we win the work; it can contain one car or two in a trade-in |
| **Order** | The work we have won after the dealer accepts a quote; retain this term for the scoring denominator |
| **Gig** | One or more car movements in a fixed stop order, posted for one freelance driver; combining cars means sequential driving, not a vehicle transporter |
| **Fee** | What we offer/pay the driver for a gig, through a fee schedule; not the dealer's quote |
| **Typical fee** | The request's benchmark for what a driver is usually paid, exposed in code as `referenceFeeCents`; not a guaranteed minimum or the least a driver would accept |
| **Deadline** | When the car must arrive; also explain readiness and pickup windows, since a delivery deadline alone does not make pickup feasible |
| **Quote / list price** | Our offered price to the dealer / the delivery option's price reference; distinct from the driver's fee |
| **Gross margin** | Dealer revenue minus driver fees, refunds, penalties and other account charges, in simulated euros; not a margin percentage |
| **Delivery minimum / ranked** | At least one won order and at least 90% of won, noncancelled orders on time; undelivered orders count as late. The existing graph's qualified/disqualified legend is shorthand for these conditions |

Say **fee schedule** instead of price clock, **typical fee** instead of reference fee, **delivery minimum** instead of gate, and explain request-type rules rather than saying segments. A request and an order are different stages; do not replace every occurrence of order with request.

## What the jury asks us to show

The final's ten ranked teams with the highest gross margin reach the jury. After that, margin no longer counts. The four official criteria are:

| Criterion | Evidence to explain in our pitch |
| --- | --- |
| **Elegant** | Few parts, each with a reason: the quote rule, gig fee schedule and feasible pickup constraints |
| **Clear** | Follow a dealer request through a quote, won order, posted gig, driver fee and delivery deadline |
| **Creative** | Explain our application of earned dealer trust and compatible-car gigs; acknowledge that the underlying trust rule is provided by the challenge |
| **Robust** | Show results on new weeks and failures; distinguish these results from separately tested restart, network and live-clock behaviour |

For each big idea, use the official structure:

1. **The idea:** what the system does, and in which cases
2. **Why:** what we saw in the world or results that made us try it
3. **The effect:** gross margin and on-time share with and without it, on the same weeks

Start with the answer, keep one claim and its evidence on a slide, and give each number its unit and comparator. Explain decisions with a rule, formula or diagram. Include failures and what would break the system. Choose explainable ideas rather than adding complexity for its own sake. The page asks for 5–10 slides or a short video; it gives no speaking-duration limit. Read every line and keep only what you can explain yourself.

## Remaining presentation work

The current ten-slide deck has terminology and speaker-note updates, not a full redesign to satisfy every judging suggestion. Its reader notes open with the released Delta result. The visible title, iteration and all-run slides retain the current design. Beta and Gamma group their major decisions on a slide. Gamma's four yellow decision headings and compact matched-week results share slide 7. Slides 8 and 9 now show the released Delta's measured results and its capacity/intake decisions, using the merged release at `cae1e58b8ce3234260328f78dcf2283cd2ebced7` as the source. The all-run chart closes the deck on slide 10.

- Add the actual **final result** when available; do not substitute practice or test-final results
- Recheck the **latest verified ranking-round result** before submission. Slide 8 now includes Delta round 9: €75,763.55 across five ranked weeks. Its 21:34:23 UTC standings snapshot was still an open round, so its rank is not final
- Record any demonstrated restart, slow-network and live-clock behaviour separately; the Gamma practice test alone establishes none of these
- The run count uses the frozen saved-file snapshot below; repeated runs are not independent unseen weeks. The 1B token figure is supplied by the presenter, not audited by simulation logs
- Keep Beta's small historical fee/trust tests separate. Do not add their gains or describe them as Gamma effects
- Keep chart footnotes off the graphs, as requested; their context belongs in these notes

A ranking round sums five secret weeks and every week must meet the delivery minimum. The final is one secret level-8 week. Ranking-round totals do not carry into the final.

## Evidence sources

Gamma's claims are in [original results](../docs/research/gamma-results.md), [recovery results](../docs/research/gamma-recovery-results.md), [prototype conventions](../PROTOTYPES.md#gamma) and the [selected settings](../models/gamma.json). Beta's mechanisms are in [Beta results](../docs/research/beta-results.md) and [beta.py](../beta.py). The cent-exact small Beta comparisons were preserved in the local presentation handoff, `EVIDENCE.md` sections 3–4: Beta s2 `B` versus `B-ramp` on `beta-01` to `beta-03`, and s4 `notrust` versus `base` on `beta-01` to `beta-04`. Their key figures are reproduced in slide 5's notes below. They are historical comparisons, not new experiments.

The released Delta evidence is in [Delta results](https://github.com/KotvicCodes/Cheap-Drive/blob/cae1e58b8ce3234260328f78dcf2283cd2ebced7/docs/research/delta-results.md), [round 9](https://github.com/KotvicCodes/Cheap-Drive/blob/cae1e58b8ce3234260328f78dcf2283cd2ebced7/docs/research/delta-board-round9.md) and [the released settings](https://github.com/KotvicCodes/Cheap-Drive/blob/cae1e58b8ce3234260328f78dcf2283cd2ebced7/models/delta.json), pinned to the merged source. The €1,664/week headline compares Delta with **Early Delta**, not Gamma; its 19 weeks combine eleven screening weeks and eight fresh weeks. The fresh-eight-week gain alone is €1,389.22/week. All 19 ranked, but mean on-time share fell from 96.9% to 95.7%. The official €75,763.55 round total is separate from those practice comparisons.

The private prototype-story journal is not included in this presentation bundle.

## Current run-count snapshot

**1,685 completed practice runs**, updated 2026-11-14 22:53 UTC (193 more than the previous 1,492-run chart). Counts are deduplicated by server world ID, with final-score evidence. Three completed timed practice rehearsals count as practice worlds, with restarts deduplicated. Official ranking runs (20 saved worlds), the live test final (1 saved world), demos and 139 identified worlds without final-score evidence are excluded. Practice covers **87 seed-and-level scenarios**, so repeated trials are correlated. All 193 new counted worlds have terminal trace evidence, and the audit found no score conflicts. No simulation was launched for this refresh.

| Model stage | Completed practice runs |
| --- | ---: |
| Baseline | 2 |
| Alpha | 677 |
| Beta | 268 |
| Gamma | 242 |
| Delta | 496 |
| **Total** | **1,685** |

Early and late versions are combined into Beta and Gamma. Gamma controls run during Delta development remain in Gamma; Delta experiments are combined into one category. Original stage membership is retained in run-data.json for comparison. Category averages include unranked weeks and are descriptive, not same-week component effects. The historical Beta and Gamma comparisons retain their original weeks.

- [All-run graph: PNG](all-run-margins.png) and [PDF](all-run-margins.pdf)
- [Frozen scores and group membership](run-data.json)
- [Replot script](plot-runs.py): run `python3 presentations/plot-runs.py` with Matplotlib installed to regenerate the standalone chart files

The HTML embeds the same PNG for offline use. Regenerating standalone files does not replace the HTML image automatically. The local detailed audit is under git-ignored `runs/presentation-refresh-20261114T225305Z/`. The token total shown on slide 3 is **1B**, as supplied by the presenter.

## Reader notes

These match the notes embedded in the HTML.

### Slide 1: Cheap-Drive

Cheap-Drive quotes dealer requests and posts gigs with fees for freelance drivers. Our main result is the released Delta: €1,663.82 more gross margin per week than Early Delta on the same 19 practice weeks, with all 19 ranked, including eight new weeks tested after selection. The official round-9 total is €75,763.55 with five of five weeks ranked. Delta pairs dispatch capacity repairs with a higher request-win target; its mean on-time share is lower than Early Delta's, so qualification headroom remains a risk. Earlier slides explain fee timing, dealer trust, reading notes and combining cars. The final result is still to be added; practice results are not the final.

Use the challenge's words throughout: a dealer sends a request; when our quote wins, we have an order; we post its car in a gig, choose the fee and aim to deliver by the deadline. A gig is work for a driver, not the request or the order itself. All money shown is simulated euros.

Source: https://spread.bahnexpress.com/judging; ../docs/research/gamma-recovery-results.md.

### Slide 2: The goal

The goal: maximise gross margin while meeting the delivery minimum. Gross margin is dealer revenue minus driver fees, refunds, penalties and other account charges. It is euros, not a weighted score or a percentage bonus.

A week is ranked only if we win at least one order and at least 90% of won, noncancelled orders arrive on time. An undelivered order counts as late; a multi-car order is on time only when every leg arrives by its deadline. More gross margin cannot compensate for missing the delivery minimum.

A ranking round sums gross margin over five secret weeks, and every week must meet the delivery minimum. The final is one secret level-8 week; ranking rounds do not carry over. The ten ranked teams with the highest final gross margin reach the jury. After that, gross margin no longer counts: the jury assesses Elegant, Clear, Creative and Robust.

Sources: https://spread.bahnexpress.com/judging; https://spread.bahnexpress.com/kit/RULES.md.

### Slide 3: Prototype. Test. Loop. Repeat.

Why we tested: one profitable practice week can hide a delivery failure on another week. We compared changes on the same weeks, then reserved new weeks to test the chosen Gamma and Delta without changing their settings.

The updated count is 1,685 completed practice runs at the 2026-11-14 22:53 UTC saved-file snapshot, 193 more than the previous 1,492-run snapshot. It includes three completed timed practice rehearsals; restarting a world does not add another run. We deduplicate by world ID and require a completed result or terminal trace score. The 20 saved official ranking worlds, one test-final world, synthetic demos and 139 identified worlds without final-score evidence are excluded from this practice total. All 193 newly counted worlds have terminal trace evidence; no simulation was launched for the refresh.

Those 1,685 runs cover 87 seed-and-level scenarios with repeated configurations; they are not 1,685 independent unseen weeks. Counts show development effort, not the effect of an idea. The four model generations remain Alpha, Beta, Gamma and Delta. We report 1B tokens of development usage, as supplied by the presenter; the simulation logs do not audit this usage figure, and it is not evidence of dispatch quality.

### Slide 4: Alpha: formula tuned by gradient descent

The idea: Alpha quotes each dealer request from estimated route cost, pickup cost, nearby driver supply and a dealer-specific margin. Simplified decision: quote = estimated cost + margin + scarcity allowance. Delivery and the gig fee schedule initially follow the starter.

Why: a flat price ignores how far the car travels and how hard it is to find a suitable driver. We wanted an explainable quote for each request.

The effect shown here is a descriptive gross-margin range of roughly €0–9k per practice week, read from the all-run chart across 677 Alpha runs. It is not a same-week with/without comparison or a guarantee that every Alpha week was ranked. The overnight automatic tuner did not beat the researched manual settings. Use the formula to explain the decision; do not infer an isolated profit gain from the stage range.

Sources: ../docs/research/alpha-results.md; ../PROTOTYPES.md; ../alpha.py.

### Slide 5: Beta: two decisions that paid off

The idea: time the gig's fee increases to the time available for pickup, instead of a fixed five-hour ramp. The fee is what we pay the driver; it is different from the quote we send the dealer. The typical fee is the request's benchmark for usual driver pay, not a guaranteed minimum or a price paid by the dealer.

Why: a car ready the next day was becoming expensive the same evening. Drivers also learned to wait for fee increases. Beta delays increases while there is usable time, and raises the fee as the last feasible pickup before the deadline approaches. Ordinary gigs in the selected Beta open at 80% of the typical fee; that opening setting is a separate policy decision from the timing comparison below.

The effect of fee timing on the same three practice weeks: gross margin €8,433.38 to €9,944.51 per week, a gain of €1,511.13/week. Ranked weeks rose from 2/3 to 3/3, but mean weekly on-time share slightly fell from 94.47% to 94.38%. Do not claim every service metric improved.

The idea: reflect earned dealer trust in quotes. Simplified rule: quote = option list price × learned markup × (1 + 0.01 × counted on-time orders for that dealer), capped at 25. The markup also learns from request wins and losses.

Why: the level-8 rules let a dealer accept a higher price after reliable deliveries; a late order halves its count. We used this known rule, rather than claiming to invent dealer trust.

The effect of using trust in quotes on the same four practice weeks: gross margin €14,036.80 to €14,888.27 per week, a gain of €851.47/week. Mean weekly on-time share rose from 91.94% to 94.16%; both variants ranked 4/4. One week earned slightly less with trust.

These are two small historical development comparisons, with different settings and sample sizes. Do not add the gains or present them as Gamma's measured component effects.

Sources: saved presentation handoff, EVIDENCE.md sections 3–4 (Beta s2 B versus B-ramp; Beta s4 notrust versus base); ../docs/research/beta-results.md; ../beta.py; https://spread.bahnexpress.com/kit/RULES.md.

### Slide 6: Gamma: a try and a fail

The idea: quote selected 500–700 km dealer requests that Beta's 500 km limit rejected, but require at least 24 hours until the last feasible pickup and fewer than three long orders waiting for a driver. Long single-car gigs open at the typical fee; only next-day and within-three-days options are admitted.

Why: Beta left potentially profitable long routes to the competitor. We tested whether enough pickup time and a cap on waiting long orders made those requests safe to win.

The effect on the same eight new level-8 practice weeks: Beta averaged €9,552.34 gross margin/week and the first Gamma €10,382.78, a gain of €830.44/week. But ranked weeks fell from 8/8 to 7/8, and worst on-time share fell from 91.705% to 89.956%. The failed week is below the 90% delivery minimum; rounding to 90.0% would hide the failure. The separate eight development weeks had shown about €1,232/week more gross margin.

What did not work: both brake follow-ups also failed that difficult week. We kept unchanged Beta for ranking round 6 while repairing Gamma. Beta ranked in all five weeks, with total gross margin €59,528.62. Higher average gross margin alone did not justify promoting the first Gamma.

Source: ../docs/research/gamma-results.md.

### Slide 7: Gamma: what we changed

The idea: turn dealer notes into constraints before quoting a request and posting its gig. Readiness dates anchor to request arrival; pickup hours, delivery hours and tighter promises affect gig stop windows, the last feasible pickup and the fee schedule. Plates, charging and manual-licence requirements remain enforced. “Ready tomorrow at 11:30” is an illustrative supported note, not a new measured example.

Why: a driver sent before a car is ready or after a site closes can fail the visit even when the nominal deadline looks generous. A bounded Finnish/Swedish/English reader still misses some phrases and dates.

The idea: combine compatible cars from two won orders into one gig with sequential stops for one driver. This does not mean transporting both cars simultaneously or accepting all trade-in requests. Fresh two-car gigs open at 72% of the sum of their typical fees; gigs rescuing a waiting car open at 78% with a fresh 60-minute flat period. The fee schedule starts when the combined gig is posted; fallback single-car gigs keep the original order age. Waiting idle before the second pickup is capped at 60 minutes.

Why: the old combined-gig fee was not providing the intended discount, and an old order timestamp could make the new gig open at an already-increased fee. We repaired this timing rather than paying as though it were two independent gigs.

The idea: adjust quotes, opening fees and feasible pickup time by request type. Under 45 km, quotes are 8% lower and the gig opens at 110% of the typical fee. Premium cars open at 105% and require ten hours until the last feasible pickup. Ordinary single-car gigs open at 80%. The original guarded 700 km corridor remains: at least 24 hours until the last feasible pickup and a cap on waiting long orders, with long single-car gigs opening at 100% of the typical fee. Overlapping opening-fee floors combine by maximum.

The effect: on the same four development weeks, adding corrected two-car gigs to notes plus request-type rules added €1,202.75 gross margin/week. Adding request-type rules to notes plus guarded routes added €459.19/week. Adding notes to the request-type variant reduced failed-visit events from 22 to 1 and raised worst-week on-time share from 91.698% to 94.961%, while reducing mean gross margin by €154.91/week. These compare combinations, not independent component effects; do not add them. The paired comparison's on-time change is not isolated for every component, so do not invent it. The old buggy combined-gig implementation was not replayed on these weeks.

What did not work: the corrected-brake variant lost €329.89 gross margin/week; supply scaling alone failed one of four weeks at 88.768% on time. Brakes, roster scaling and town caps stayed disabled. The comparison on this slide tests the complete chosen combination after its code and settings were frozen.

Sources: ../PROTOTYPES.md#gamma; ../docs/research/gamma-results.md; ../docs/research/gamma-recovery-results.md; ../models/gamma.json; ../gamma_notes.py; ../gamma_pairs.py; ../gamma.py.

Results shown on this slide

The idea: test the chosen complete Gamma on weeks it had never seen. We selected it on eight development weeks and checked three known difficult weeks, then froze the code, settings and pass criteria at 13:58 UTC, before any Gamma outcome on the next eight weeks. We made no further choices using those results.

Why: the first Gamma had earned more on average while failing the delivery minimum. A new test had to demonstrate both gross margin and on-time delivery, against unchanged Beta on the same weeks.

The effect on those eight new level-8 practice weeks: mean gross margin €10,047.87/week for Beta versus €12,078.71/week for Gamma, a gain of €2,030.845/week (+20.21%), positive in every week. Both systems ranked 8/8. Mean weekly on-time share rose from 95.692% to 98.062%, and worst-week on-time share from 93.671% to 96.947%. One of 148 long-route orders was late, including undelivered work. This measures the chosen combination; it does not assign the whole gain to each idea above.

Limits: there were still 12 undelivered orders and 22 failed-visit events across 11 distinct orders. Eight new ordinary-practice weeks do not prove every future week will rank, or that the system survives restarts, a slow network or the final's live clock. No such operational robustness is claimed by these results. We stopped tuning Gamma and carried the remaining work forward to Delta.

Sources: ../docs/research/gamma-recovery-results.md; ../docs/research/delta-handoff.md.

The compact table displays worst-week on-time share, not the mean weekly share: Beta 93.67%, Gamma 96.95%. Gross margins are rounded to whole euros for the slide: €10,048 and €12,079 per week. The gain of 20.21% uses the unrounded values. Both policies ranked in all eight weeks. The four visible yellow headings retain the decisions; their implementation details remain in these notes.

### Slide 8: Delta in production

The effect: released Delta earned €1,663.82 more gross margin per week than Early Delta on the same 19 level-8 practice weeks. It was ahead in 17 of 19 weeks, and all 19 Delta weeks ranked. This is the capacity combination versus Early Delta, not versus Gamma. Early Delta is the former note-fix and rescue-window model, now saved as models/delta-early.json.

The eleven screening weeks, delta-f1-s01..s11, gained €1,863.53/week with 10 positive weeks. After the 42% arm was chosen, eight previously unseen weeks, delta-f2-s01..s08, gained €1,389.22/week with seven positive weeks and all eight ranked. The headline rounds the pooled 19-week gain to €1,664; it is not the fresh-eight-week result alone. Early Delta won about 257 orders/week versus Delta's 342 on these paired weeks. Mean on-time share fell from 96.9% to 95.7%; Delta's lowest week was 91.1%, against Early Delta's 93.7%. Both policies qualified on every week, but Delta has less service headroom. Do not imply that the profit gain improved on-time delivery.

Separate official evidence: Delta's five level-8 ranking-round-9 weeks total €75,763.55 gross margin, 1,798 won orders and 96.72% on time, with all five ranked. The lowest week was 93.58%. The slide rounds the total to €75,764. Public snapshot: 14 November 2026, 21:34:23 UTC, rank 31 of 52 ranked teams while the round was still open. The ranking runs used the settings now named Delta, from code 589daf7ad8b17d6c2402bb45f7cab7856cd777b9. The public feed verifies results, while the model provenance comes from the ranking-run handoff. This is a ranking round, not the actual final; it must not be compared causally with Gamma's round 7 or Early Delta's round 8 because the secret weeks differ. Do not present the open-round rank as a final standing.

The actual final result still needs to be added when available. The older Test Final 2 result was produced before this capacity model and must not be presented as its measured effect. The all-run graph remains the explicitly frozen 22:53 UTC development snapshot; it includes candidate experiments, not only the released Delta.

Sources: https://github.com/KotvicCodes/Cheap-Drive/blob/cae1e58b8ce3234260328f78dcf2283cd2ebced7/docs/research/delta-results.md; https://github.com/KotvicCodes/Cheap-Drive/blob/cae1e58b8ce3234260328f78dcf2283cd2ebced7/docs/research/delta-board-round9.md; https://github.com/KotvicCodes/Cheap-Drive/blob/cae1e58b8ce3234260328f78dcf2283cd2ebced7/models/delta.json.

### Slide 9: Delta: the next iteration

The idea: use capacity freed by dispatch repairs to win more dealer requests. The released Delta retains Early Delta's bounded note corrections and rescue-window handling, then enables wider gig windows, private-delivery rescue, extended pairing and a 42% request-win target instead of 30%. It uses the same dealer, request, gig, fee, typical fee and deadline concepts as earlier slides.

Why: the capacity audit of eleven Early Delta weeks found about 433 gigs posted and 141 expiring unbooked per week. A more reliable gig posting does not automatically win more work while the price learner keeps the same request-win target. We therefore tested dispatch capacity and intake together, rather than assuming an isolated repair would create the full profit gain.

The idea: offer wider gig windows when the order allows them, while preserving readiness, recurring dealer hours and fixed private pickup slots. Rescue overdue private deliveries within the challenge's rules. These enable delta_wide_windows and delta_private_delivery_rescue, alongside the existing delta_rescue_windows and delta_note_fixes. Do not describe private pickup appointments as freely extendable.

The idea: pair compatible cars across a wider area. The extended profile permits up to 90 km of transfer and 720 minutes of combined driving; it still means sequential car movements by one driver, not simultaneous transport. Pair fees and fallback handling remain part of the inherited system. Removing extended pairing made the exposed difficult week unranked at 89.1%, so it stayed in the chosen combination.

The idea: raise the request-win target from 30% to 42% so the quote learner seeks more work. The effect of the complete combination is the preceding slide's +€1,663.82/week on 19 paired weeks, with about 342 orders/week instead of 257. On the eleven f1 weeks, expired-gig events fell from roughly 141/week for Early Delta to 25/week for this combination. These are event counts on the f1 cohort, not independent orders or an isolated effect of wider windows. The eight fresh f2 weeks confirmed a +€1,389.22/week gain. Do not add an assumed gain for each switch to the measured combined result.

What did not work: the EV charging-rule change lost €200/week across four weeks and remains off. Capacity switches at a 30% win target barely changed orders won. Raising the target to 50% or 55% failed the 90% delivery minimum on one of eleven screening weeks; 46% left only 90.2% on the weakest week. A backlog brake gave up about €190/week across 19 weeks without improving the fresh difficult weeks, so it was excluded. Broad learner, lane and conditional-option pricing experiments did not establish a reliable replacement. These failures explain why we selected 42% and kept the remaining controls.

Limits: mean on time is lower than Early Delta's, and the weakest practice week has only about 1.1 percentage points of headroom above 90%. Nineteen paired practice weeks and one five-week ranking round do not guarantee qualification in the actual final. Runtime/restart repairs have their own engineering evidence; these economic measurements do not establish universal recovery or latency guarantees. Before submission, add the actual final outcome and recheck the latest verified ranking-round result.

Sources: https://github.com/KotvicCodes/Cheap-Drive/blob/cae1e58b8ce3234260328f78dcf2283cd2ebced7/docs/research/delta-results.md; https://github.com/KotvicCodes/Cheap-Drive/blob/cae1e58b8ce3234260328f78dcf2283cd2ebced7/models/delta.json; https://github.com/KotvicCodes/Cheap-Drive/blob/cae1e58b8ce3234260328f78dcf2283cd2ebced7/docs/research/delta-capacity-levers.md; https://spread.bahnexpress.com/judging.

### Slide 10: 1,685 practice runs

This chart shows gross margin in euros for all 1,685 completed practice runs in the 2026-11-14 22:53 UTC snapshot. Each dot is one server world, deduplicated across traces and summaries. Blue dots marked qualified meet the week's ranking conditions; red crosses marked disqualified do not. The pitch-black plus in each category is its arithmetic mean gross margin, including unranked runs.

Categories: Baseline 2, Alpha 677, Beta 268, Gamma 242, Delta 496. Early and late versions are combined within each model family. These total 1,685 runs across 87 seed-and-level scenarios. Unchanged Gamma controls tested during Delta development belong to Gamma. Delta experiments are combined into one category. Three completed timed practice rehearsals are included; official ranking worlds and the live test final are separate. Repeated seeds and changing settings make observations correlated. Horizontal jitter separates marks visually; it is not elapsed time. Comparing category averages does not measure an idea's effect on the same weeks.

The 193 added worlds all belong to Delta experiments, taking Delta from 303 to 496 runs; they include rejected alternatives as well as selected models. The all-run chart is a development inventory, not a test of the released configuration alone. Delta's historical paired practice and ranking-round results retain their own frozen evidence on slide 8.
