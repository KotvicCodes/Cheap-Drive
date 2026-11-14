# Delta B2 lane-pricing implementation contract

This is an offline implementation contract for the B2 hypotheses in
`delta-testing-plan.md` and `plans/delta/quote-fee-stages.json`. It does not
release an experiment, qualify a treatment, or claim simulator performance.
No worlds or API calls are required to check it. Gamma source, model settings,
existing research manifests, and running snapshots remain unchanged.

Use `delta:make_delta` with the selected settings in `models/gamma.json` and
one `delta_lanes` value. Omission is identical to `off`.

| Value | Inbound factor | Outbound factor |
| --- | ---: | ---: |
| `off` | 10000 bps | 10000 bps |
| `inbound_9100` | 9100 bps | 10000 bps |
| `outbound_10400` | 10000 bps | 10400 bps |
| `outbound_10600` | 10000 bps | 10600 bps |
| `inbound_9100_outbound_10400` | 9100 bps | 10400 bps |
| `inbound_9100_outbound_10600` | 9100 bps | 10600 bps |

Inbound requires an origin outside exactly `{vantaa, helsinki, espoo, hyvinkaa,
porvoo}`, a destination inside that set, and Gamma `route_km >= 60`. Tampere,
lempaala, and raisio are valid inbound origins. They are reported separately
because the retrospective script excluded them; they are never added to the
five-hub exclusion set.

Outbound requires a destination in exactly `{savonlinna, kajaani, kotka,
ylivieska, kokkola, seinajoki, mikkeli, rovaniemi, vaasa, lappeenranta, kouvola,
pori}` and Gamma `route_km >= 100`. There is no additional origin restriction.
Combined arms enable each rule independently. The destination sets are
disjoint, so a request receives at most one nonneutral lane factor.

Endpoints are the first leg's pickup and final leg's delivery, matching Gamma's
table/journal convention. Distance is Gamma's sum of leg road kilometers;
neither direct endpoint distance nor repositioning travel replaces it. Existing
trade-in eligibility still decides whether a multileg request can be quoted.

`DeltaLanesMixin.option_factors` adds one integer `deltaLaneBps` factor to each
eligible, selected option. Same-day, next-day, within-three-days, single-option,
and multi-option menus use the same lane rule. Gamma retains its exact
`Fraction` composition and one final cent ceiling. There is no intermediate
rounding, queued-action mutation, journal replacement, option reselection, or
change to the request. Below 60 km the new multiplier is explicitly clamped
to at least 10000 bps. Gamma's existing short factors and independent segment
fee/slack controls remain in force, including a configured short band that
overlaps the inbound threshold.

Enabled lanes reject simultaneous non-off `delta_b1`, Delta note/rescue
repairs, dealer/place tables, capacity valve, supply scaling, town caps or
pending reservations, nonglobal markup scope, changed `learn_bps`, changed
`win_target_bps`, changed `trust_bps_per_order` (including B5's 50 bps arm), and
review fee shape. Unknown names, nonstring modes, or multiple-mode containers
are invalid. No B1/lane combination becomes available automatically after a
review: conditional B6 needs a separately reviewed implementation/contract.
With lanes off, the existing Gamma, pair, B1, and other Delta setting validation
continues unchanged. Levels 1–3 retain Gamma's starter quote behavior.

The implementation overrides only option factors and quote diagnostics. Gamma
owns eligibility, practical declines, feedback, trust, intake, dispatch,
pairing, fees, guard state, action receipts, and terminal handling. B2 introduces
no pending lifecycle state or alternative learning path. Given the same
scripted outcomes, its markup follows Gamma exactly; real price changes may
produce different endogenous outcomes. Existing lifecycle and restart/rejoin
limitations are inherited rather than repaired here.

`beta_quote.optionFactors` records the applied lane factor before Gamma builds
and journals prices. `delta_lane_quote` observes the final competitive action
and records its request ID, arm, route distance/endpoints, cohort, exact lane
bps, actual option keys/prices, global tracker, and cumulative quote counts by
diagnostic group. The groups are `inbound`, `inbound_retrospective_excluded`,
`outbound`, and `other`; the retrospective boolean only applies to qualifying
inbound routes. Cohort classification is independent of whether the selected
arm treats it. Counts measure competitive quotes constructed, including
submissions later rejected. They do not measure accepted quotes, outcomes,
updates, arrivals, or booked pairs. Join existing receipts, outcome, ledger and
pair records by request/order ID for those analyses. No raw note text is added
to B2 diagnostics; existing event capture is unchanged.

Off adds no factors or diagnostic records, preserving the selected Gamma/pair
actions and quote journal. Declines, expired/duplicate requests, levels 1–3,
and a failed price construction produce no B2 quote diagnostic. Receipt
rejection and subsequent feedback retain Gamma cleanup/learning semantics.

Focused contracts are in `tests/test_delta_lanes.py`, separately from existing
B1 tests. They cover the exact sets, retrospective origins, 59/60 and 99/100
boundaries, both arms, multi-leg route distance, all option kinds/menus,
unchanged option guards, exact cents, retained short factors, no-cohort
neutrality, default-off journal parity, learner parity, rejected receipts,
actual pair posting/booking/change/cancellation, and segment/urgent fees.
These are in-memory scripted checks. They do not establish economic gains,
exhaustive operational trace parity, complete-week/final-clock qualification,
or restart/rejoin recovery. A frozen executable plan and independent stage
review remain prerequisites for any future simulator screen or release.

Implementation validation on CPython 3.14.4 passed 17 focused tests
(`PYTHONPATH=tests python -m unittest test_delta_lanes -v`), followed by one
full combined offline run: 288 tests passed
(`python -m unittest discover -s tests`). The Python executable came from the
existing `/tmp/cheap-drive-prototype-check` environment with the SDK already
installed. No live worlds, API access, or practice slots were used.
