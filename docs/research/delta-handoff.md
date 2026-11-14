# Starting Delta

Gamma passed its frozen confirmation; its settings and acceptance gates are in
[Gamma recovery results](gamma-recovery-results.md). Use the selected Gamma as
Delta's fixed baseline. Do not revise Gamma using confirmation outcomes.

## Development status

Repository cleanup established Delta's groundwork. The experimental
`delta:make_delta` factory now isolates note and rescue corrections; Gamma's
settings and supported behavior remain fixed. Delta was later selected as Gamma
plus those two repairs (`models/delta-early.json`, "Early Delta"); the current
`models/delta.json` adds the capacity switches and a 42% win target.
Alpha, Beta and Gamma remain supported baselines. See the
[investigation results](delta-results.md) for the current evidence.

See [Delta next steps](delta-next-steps.md) for tonight's ranked service-protection tweaks, queued settings screens and ideas parked for the next model.

The [evidence review and staged testing plan](delta-testing-plan.md) evaluates
the volume, rescue and pairing hypotheses and provides executable settings-only
screening plans. A1/A2 are complete; the two segment simplifications improved
mean margin but missed the final economic gate. B intake and independent
trust/review and learner screens stopped on their service guards. The lane and
independent note/rescue pilots completed; two lane trajectories exposed an
inherited private-window rescue defect. B4 conditional pricing is implemented
and reviewed offline, with 301 combined tests passing, but has not run live.
At the user's stopping point all owned worlds have completed, controllers have
exited, and further launches are held. Other stages retain their gates.
New [quote/fee hypotheses](delta-quote-fee-leads.md) are staged after A/B; their
completed-trace audit corrects incomplete retry selection and flags omitted
gig-only costs before any net segment margin claims.

Challenge rules and final integration requirements are consolidated in
[challenge constraints](../challenge.md); setup, run limits, event dates and
reporting commands are in the [operational reference](../reference.md).

## First experiments

Four proposed settings-only arms were parked before launch when Gamma was
closed to further tuning. Compare each with Gamma on shared screening seeds:

| Arm | Change from the note/pair/segment candidate | Question |
| --- | --- | --- |
| No segment controls | Disable short quote discount, short/premium opening floors and premium slack floor | Do the segment changes add value once pairs are enabled? |
| Short controls only | Keep short settings; disable premium opening/slack floors | What does the short-route policy contribute? |
| Premium controls only | Keep premium settings; disable short quote discount/opening floor | What does the premium policy contribute? |
| Higher pair opening | `pair_fee_bps=7500`, `pair_rescue_fee_bps=8000` | Does earlier booking offset a modestly higher fee? |

For neutral segment settings, use `short_bps=10000`,
`short_opening_fee_bps=0`, `premium_opening_fee_bps=0` and
`premium_min_slack_minutes=0` as appropriate. Leave the 60-minute rescue flat
period and second-pickup idle limit unchanged when testing pair prices.

The roster-only policy already produced an unranked new screening week
(`gamma-v02`, 88.768% on time). The proposed scaling is not a universal safety
fix. Town caps improved stress-week service but lost margin; do not enable them
by default on the strength of the original impact estimate.

## Remaining note cases

Observed after Gamma's code was frozen; none was patched into the current run:

- Misspelled relative days (`huoomenna`) and weekdays (`Friay`) can leave a
  correct clock attached to the wrong day.
- Misspelled Finnish earliest-time cue (`aikaisiintaan`) can hide readiness.
- `Klo … jälkeen ei enää luovutuksia` means no more pickups after that clock.
  The current parser can misclassify it as a release/readiness instruction.

Use bounded, unambiguous corrections with regressions for clause scope and
date anchoring. Avoid broad fuzzy matching that turns ordinary prose or access
codes into clocks. A failed visit on an unrelated tyre note did not expose a
usable readiness promise; note parsing alone cannot guarantee zero failures.

## Evaluation

Use the exposed Gamma screening seeds for initial comparisons, then reserve a
new shared eight-seed Beta/Gamma/Delta block before selecting Delta settings.
Freeze code and settings before a separate fresh confirmation block. Keep
all practice slots supplied while planned work remains, then drain the queue.

Report paired margin differences, every week's ranking result, worst on time,
long-route lateness, undelivered orders and failed visits. Distinguish unique
failed orders from repeated failed-visit events. Preserve immutable source
manifests and private traces; do not publish raw notes, reveals or credentials.

Practice qualification does not validate a final-clock dispatcher. The current
repository still needs that integration before a model can run in the final.

## Parked: Gemini for dealer notes

The user's standing idea (raised twice on 14 November): a fast Gemini call,
given rich context about the game's note conventions, might read dealer notes
better than the rule-based parser. It is parked, not rejected. An offline
extraction contract, a cached-response adapter and a three-arm benchmark
already exist in [gemini-notes.md](gemini-notes.md), `models/gemini_notes.py` and
`scripts/benchmark_gemini_notes.py`; dispatch never imports them and no
inference has been run. To take it up: label a held-out set of real notes,
run the benchmark with live inference, and compare accuracy, cost and answer
time against `models/notes.py` before letting it influence any action. A quote has a
few real seconds in the final, so the call must fall back to the parser on
timeout.
