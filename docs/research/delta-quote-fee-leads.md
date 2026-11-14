# Additional Delta quote and fee leads

These hypotheses extend the staged plan **after A/B**, without modifying the
running A1 screen. They are observed mechanisms on exposed Gamma weeks, not
measured Delta gains. Frozen Gamma remains the control. The executable settings
and candidate implementation must be frozen before each release; new arms are
specified in [the staged manifest](plans/delta/quote-fee-stages.json).

## Saved-week selection audit

The supplied retrospective script was rerun offline, then repeated with the
exact completed trace named by each `runs.jsonl` record and its matching reveal
world ID. All 16 completed scores reconcile to their full captured ledgers.
Three of the script's lexicographically last traces were incomplete retries.
Changing only file selection produces these descriptive differences:

| Cohort | Supplied script | Exact completed traces |
| --- | ---: | ---: |
| Full-menu quotes/week; wins | 579.7; 32.6% | 669.9; 32.4% |
| Skipped-fastest quotes/week; wins | 180.2; 20.8% | 204.1; 21.3% |
| Long inbound-hub quotes/week; wins | 91; 10.2% | 104.6; 10.0% |
| Remote outbound quotes/week; wins | 124; 46.9% | 142.4; 46.3% |
| Dual-menu same-day wins; late | 1,165; 30 | 1,258; 35 |
| Dual-menu next-day wins; late | 288; 2 | 329; 2 |

Counts use the original script's reveal-based won definition, which includes
41 subsequently cancelled wins across the 16 weeks. The learner audit should
retain the actual competitive win/loss learning lifecycle; business outcome
reports must separately reconcile cancellations and noncancelled won counts.
The menu also includes within-three-days choices when both faster options were
quoted; same-day/next-day counts are not the complete menu denominator.

The script's per-order economics omit **€14,296.04 total (€893.50/week)** in
driver fees whose ledger entries have no `orderId`. These costs must remain in
full-score comparisons and be allocated or reported separately for paired gigs.
Do not treat the reported €64.29 inbound or €61.73 outbound per-order figures
as reconciled net margins. Similar caveats apply to reference-fee buckets.
A sanitized source-hash audit is retained in
[the provenance record](plans/delta/quote-fee-evidence-audit.json).

Inbound retrospective membership excludes eight origin towns: the five named
hubs plus tampere, lempaala and raisio. The new experiment deliberately uses
exactly the five named hubs as its origin exclusion/destination set, and routes
≥60 km. Recompute this exact cohort separately before comparing treatment
outcomes to retrospective figures. Outbound means a listed remote destination
and ≥100 km, with no extra origin restriction.

## Mechanisms worth screening

1. **Skipped-fastest feedback:** roughly 23% of completed-trace competitive quotes
   omit the original fastest option. Their lower win rate can depress a shared
   markup while full menus overshoot the 30% target. Compare feedback exclusion,
   exclusion plus a 0.92 price factor, and a separate tracker. Preserve pending
   cleanup and all trust/outcome handling. Independent trackers receive fewer
   outcomes, so startup and adaptation may erase the apparent opportunity.
2. **Directional lanes:** long hub-inbound quotes win rarely while remote
   outbound quotes win often. A 0.91 inbound factor and 1.04/1.06 outbound factors
   are plausible quote-only screens. Accepted inbound work's zero observed
   lateness does not establish safety for marginal orders. Do not discount short
   hub trips or change segment controls based on these data.
3. **Reference-fee anchoring:** high reference/minimum-list groups have worse
   attributed unit economics. Reference can still encode driver difficulty.
   First check booking latency, escalation and complete shared-gig fees. Only
   then trial the proposed 40/60 reference/list anchor on routes ≥45 km, with an
   explicit decision covering direct pair fees as well as `fees_for()`.
4. **Conditional option spread:** charge 1.04 for same-day and 0.98 for next-day
   only after both survive the actual quote gate. Different historical lateness
   by chosen option is selected-outcome evidence, not proof customers will move
   to next-day or that the change improves total margin.
5. **Trust 50 and review fees:** independent small arms on Gamma's current stack.
   The prior “notrust” result used zero on another stack, so it does not measure
   this 50-bps proposal. Review schedules need whole-stack single/pair validation.

Competitor code examples and prior experiment anecdotes are reported leads,
not independently verified evidence here. They motivate tests rather than set
expected gains. Learner and lane screens remain separate before an optional
four-arm interaction screen. Existing safety and final eligibility gates,
development seeds and untouched confirmation are unchanged.
