# Delta B4 conditional dual-menu implementation contract

Offline implementation of B4 in `delta-testing-plan.md` and
`plans/delta/quote-fee-stages.json`. This does not release a pilot, change the
stage prerequisites, select a model, or claim economic improvement. Parent
review and a separately frozen executable plan/snapshot remain necessary.

Use `delta:make_delta` with the settings from `models/gamma.json` and
`delta_option_spread="dual_10400_9800"`. Omission or `"off"` preserves existing
Gamma/Delta behavior, factors, actions and journals. Only these two strings are
accepted; invalid selectors and unqualified combinations fail at factory
construction, before initializing a desk. The normal `compare.load_model`
configuration path binds the selector and validates it when constructing the
desk, as it does other factory settings. No `models/delta.json` is added.

For a competitive quote at level >3, determine the actual eligible, selected
menu first. If and only if it contains **both** `same_day` and `next_day`, add
`deltaOptionSpreadBps=10400` to same-day factors and `9800` to next-day factors.
Other options retain their Gamma factors. Gamma's `price_option` composes these
integer bps with its existing `Fraction` math before its single final cent
ceiling. There is no intermediate rounding or mutation of queued prices,
requests, unconditional option settings, or existing journal records.

Same-day-only and next-day-only final menus remain Gamma even when the
original request contained both. The same holds when either appears alongside
`within_3_days` without the other. Readiness, note promises, business/private
windows, ordinary slack, premium slack and long-route gating remain Gamma's.
The existing selected short discount and global learner/trust pricing remain
in force. Given identical scripted outcomes, learning and driver behavior
remain Gamma; changed live prices could change those outcomes.

`DeltaOptionSpreadMixin` precedes the existing B1, lanes, driver-side, notes
and Gamma core mixins. It wraps only `quote`, `eligible_options` and
`option_factors`; it does not copy the quote implementation or override
learning, receipts, fees or lifecycle handling. Audited Gamma currently calls
`eligible_options` after all option gating/selection; the sole later admission
guard can decline the entire menu for town capacity. It does not remove an
individual option. B4 additionally rejects active town caps/reservations.
If upstream code adds later partial-menu gating, this hook must be reviewed.
The pairing outbox getter can process timers during Gamma's quote append;
diagnostics find the fresh request's action by identity, without assuming
earlier queue indices survive timer processing.

The quote context is restricted to the same request object and restored with
`try/finally`, including on errors. Calls to option hooks outside an active B4
quote cannot apply the spread. No B4 pending-outcome state survives the call.
Pairing's `order_changed` interception therefore requires no B4 cleanup;
Gamma's ordinary pair splitting, booked-pair changes, cancellation, delivery,
fees and learner ownership remain intact. B1's lifecycle interception pattern
is deliberately unnecessary here. Duplicate requests, expired requests,
levels 1–3 and practical declines follow Gamma, without B4 quote records.
Failed construction restores the B4 context and inherits Gamma's partial
request bookkeeping; it does not implement a new retry/recovery policy.

Active B4 rejects non-off B1 or lanes, note/rescue repairs, trade-ins, tables,
capacity/supply/town experiments, trust build/guard, brake and daily learner
freeze. It requires Gamma defaults for markup scope, learner step, win target,
trust bps, option selector, unconditional option bps, table strength and trust
build horizon. Review fee shape or changed review parameters also fail.
Ordinary distance/slack guards, short pricing and fee controls, markup bounds,
and existing pair settings remain available; the pilot should use the frozen
selected Gamma configuration, not treat this as qualification of overrides.
With B4 off these additional restrictions disappear; existing B1/B2 validators
and supported Gamma/Delta combinations retain their behavior.

Active competitive quotes add `delta_option_spread_quote`, observed from the
actual newly emitted action. Sanitized fields are request ID, time, selector,
actual ordered option keys/prices, all applied option factors, explicit spread
bps by submitted option (10000 when unchanged), and one observable cohort:

| Cohort | Actual submitted menu |
| --- | --- |
| `dual_menu` | Contains both same-day and next-day, with or without a third option |
| `same_day_without_next_day` | Same-day present, next-day absent |
| `next_day_without_same_day` | Next-day present, same-day absent |
| `neither` | Neither option present |

Gamma's existing `beta_quote.optionFactors` also contains the factors it
actually priced. Both records match the outbox prices. B4 adds no raw notes,
customer text or credentials; ordinary existing event capture is unchanged.
Records count competitive quotes constructed, including later receipt
rejections; they do not establish accepted/won quotes or causal switching.
Join existing action receipts, chosen orders, pair/gig records and ledger lines
to audit choice shares, fees, shared costs, refunds and service. B4 adds no
outcome attribution or cost allocation policy.

Focused in-memory contracts in `tests/test_delta_option_spread.py` cover all
option combinations and order, third-option neutrality, original dual menus
gated to either lone option, real readiness/premium/slack/long gating, the
one-cent exact-composition boundary, existing short/trust factors, sanitized
journal/action consistency, declines including the later town guard,
duplicates/expiry/low levels, exception cleanup, receipts and learner parity,
actual pair booking/intercepted change/cancel/delivery, a pending-pair timer
processed during quote append, default-off event/action parity with both
dispatcher clocks, config loading and invalid combinations.
No simulator worlds, holdouts, API clients, credentials, paid model calls or
live controllers are used. These checks do not qualify economics, final clocks,
complete-week service, restart/rejoin recovery or unqualified interactions.

The pilot reviewer separately reported an inherited frozen-Gamma dispatch
limitation: inbound-091 and outbound-106 trajectories each produced rescue
posts extending R00345's private delivery window `[3660,3720]` to `3750` and
`4319`, respectively. B4 does not repair or qualify that rescue behavior.
Offline quote correctness cannot establish service or economic release
readiness. B4 live runs remain held pending parent review and release gates.

Validation on CPython 3.14.4 using the existing
`/tmp/cheap-drive-prototype-check/bin/python`: 13 focused B4 tests passed
(`PYTHONPATH=tests .../python -m unittest test_delta_option_spread -q`), and
the final full offline suite passed **301 tests**, up from the parent's 288
(`.../python -m unittest discover -s tests`). Existing B1/B2 tests passed as
part of the focused Delta checks and the full suite. Frozen Gamma files and
configuration, existing B1/B2 sources, and staged research plans are unchanged.
