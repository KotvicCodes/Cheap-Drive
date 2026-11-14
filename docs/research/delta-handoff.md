# Starting Delta

Gamma passed its frozen confirmation; its settings and acceptance gates are in
[Gamma recovery results](gamma-recovery-results.md). Use the selected Gamma as
Delta's fixed baseline. Do not revise Gamma using confirmation outcomes.

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
