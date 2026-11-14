# Delta B1 implementation contract

This is an offline implementation specification, not an executable sweep or
evidence of an economic improvement. Frozen `models/gamma.py` and `models/gamma.json`
remain unchanged. No worlds are needed to exercise these contracts.

Use factory `delta:make_delta`, retaining the settings in `models/gamma.json`,
and add exactly one `delta_b1` setting:

| Value | Feedback | Extra pricing factor |
| --- | --- | --- |
| `off` (default) | Selected Gamma behavior | None |
| `fastest_learning_only` | Exclude skipped-fastest outcomes | None |
| `fastest_learning_only_skipped_9200` | Exclude skipped-fastest outcomes | 9200 bps on skipped-fastest quotes only |
| `split_skipped_tracker` | Global tracker for fastest-present; separate tracker for skipped-fastest | None |

For example, a single candidate model uses this configuration (not a sweep):

```json
{
  "name": "Delta B1 split candidate",
  "factory": "delta:make_delta",
  "settings": {
    "max_km": 500,
    "win_target_bps": 3000,
    "opening_fee_bps": 8000,
    "long_max_km": 700,
    "pairs": 1,
    "short_fee_km": 45,
    "short_opening_fee_bps": 11000,
    "short_km": 45,
    "short_bps": 9200,
    "premium_opening_fee_bps": 10500,
    "premium_min_slack_minutes": 600,
    "delta_b1": "split_skipped_tracker"
  }
}
```

The original `request.options[0].kind` defines fastest. A competitive submission
is skipped-fastest if its actual price keys omit that kind. A lone offered
original-first option is fastest-present; a two-option menu can be
skipped-fastest. No sorting, request mutation, or re-anchoring of note dates
occurs. Gamma's final eligible/selected menu drives the tracker and factor
hooks. Its only subsequent guard can decline the whole quote. Classification
for logging and delayed feedback is captured from the queued action's keys.

The 9200 bps factor is multiplied with Gamma's other exact `Fraction` factors
before its single cent ceiling. Delta never reprices a queued action, so
`beta_quote`, B1 diagnostics, action results, and submitted prices agree.

The split tracker starts at Gamma's configured initial markup and delegates
every update to `Gamma.learn`. Bounds, live outcome-time target, per-outcome
learning step, and per-tracker quote-day starts/freezes remain Gamma's. No extra
updates or learning-rate adjustment compensate for smaller cohorts. B1 enforces
the unchanged 200 bps step and 3000 bps base target. Existing Gamma bounds and
freeze controls remain usable for offline boundary checks.

An enabled arm rejects dealer/place tables, capacity valve, supply scaling,
town caps/reservations, nonglobal markup scope, review fee shape, and Delta
note/rescue repairs. One enumerated mode prevents combining the learner arms.
Gamma's selected long/short/premium and pairing settings remain in effect.
This factory is not a release mechanism: compare against the same selected
Gamma settings and retain the B1 stage's existing review gates.

`pending` and `quote_trackers` retain competitive quotes until feedback, including
excluded quotes. Win/loss consumes the cohort once; rejected receipts,
cancellation, order changes, and delivered events clear it without learning.
Cleanup runs outside the pair mixin so intercepted changes cannot bypass it.
Deliberate declines and levels 1–3 create no B1 training state. Feedback exclusion
does not bypass Beta/Gamma outcome, dealer trust, order ownership, posting,
pairing, or cancellation handling. Day boundaries and `respondBy` do not expire
pending cohorts: a valid outcome may arrive later. Per-tracker day-start state
is retained for Gamma's freeze calculation and has at most two tracker keys.

`delta_b1_quote` records original-first kind, actual price keys/prices, cohort,
tracker, markup, and cumulative cohort counts. `quotes` counts competitive
quotes constructed; rejected submissions are separately counted in
`delta_b1_cleanup`. `delta_b1_outcome` records wins/losses, feedback eligibility,
target, before/after markup, and outcome/update counts. Cleanup records its
reason without adding an outcome. These diagnostics distinguish unchanged
markup due to exclusion from a bounded/frozen update.

Parity coverage is offline: selected Gamma settings, pairs enabled/disabled,
ordinary/coalesced capture, scripted outcomes and actual pair posting/booking.
It does not establish simulator economics, exhaustive trace equivalence,
restart/rejoin recovery, or final-clock qualification. Like Gamma, the factory
expects action receipts before their resulting events; no new persistence or
reconnection protocol is introduced.
