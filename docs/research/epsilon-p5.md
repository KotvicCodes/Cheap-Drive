# Epsilon P5: selective intake experiments

Branch: `t3/epsilon-p5`, based on `origin/t3/epsilon-model`.
Production `models/delta.json` and `models/epsilon.json` remain unchanged.

## Evidence and selection rule

The supplied top-7 strategy and its `top7-vetted.md` P5 review were checked
against `models/gamma.py`, `models/gamma_notes.py`, `models/gamma_pairs.py`,
`models/delta.py`, the installed SDK starter, and prior Epsilon summaries.
The proposed euro gains are hypotheses, not forecasts established by those
traces. In particular, admitting more long routes need not retain the observed
96.5% service of previously won routes. Trade-ins have no Delta dispatch
baseline, and later changes can still force a combined trade-in to split.

All trials use level-8 practice via `scripts/sweep.py`, `SWEEP_WORKERS=3`.
Only `summary.md` and `runs.jsonl` are used for live trial analysis. Existing
19-seed Delta references are reused from sibling worktree
`t3-cb1f1e60-3100c14e73a0d169/runs/epsilon/delta-baseline.jsonl`; their settings
match the complete current Delta JSON. No board or final runs are involved.

The screen uses `delta-f1-s07`, `delta-f2-s04`, `delta-f1-s01`, `delta-f1-s10`.
An eligible survivor needs positive paired mean margin and every observed
week >=91.5% on time, then the complete 19 paired seeds and confirmation.
The eight `epsilon-confirm-20261115-s01..s08` references are reserved for
confirmation before choosing a P5 survivor. These are fresh to this P5 lane,
but already exposed to other Epsilon experiments; they are not a new global
holdout. No Delta reference worlds are replayed.

## Default-off controls

`DeltaIntakeMixin` adds independent guarded admission paths without changing
customer-price factors, quote learning, pairing policy or existing fee curves.

- `delta_guarded_trade_ins=1` requires `trade_ins=1`. Only two-leg round trips
  through a private customer are admitted, with <=540 combined driving minutes,
  <=500 km per leg, at most two unbooked trade-in orders, and total unbooked
  backlog <=20. The opening fee floor is 10000 basis points. Optional roster
  eligibility uses frozen public initial supply, not driver availability.
- Trade-in planning applies dealer-note facts to leg 0 in both quote feasibility
  and posting. The outgoing pickup starts on the appointment's driving day;
  backward bounds leave time to return the old car. The old-car pickup has no
  explicit window only in a combined shared visit. A separated leg retains its
  strict private slot. Explicit retry plates still apply to either car.
- `delta_corridor_open_cap>0` expands the existing unbooked long-route cap only
  when backlog and optional roster guards permit. Original option/slack/brake
  checks are reused. It does not shrink or expand the 500–700 km band.
- `delta_relaxed_slack_minutes>0` can recover otherwise-declined ordinary
  single-leg work at <=150 km with at least four hours of note-aware slack,
  subject to backlog/roster guards. It excludes premium/private work and leaves
  already-admitted menus unchanged.

Other parameters and defaults are in `DeltaIntakeSettings`. Flags are strict
integers; zero disables each mechanism. Neutral action/call/score/journal parity,
shared versus split visits, retry plates, return feasibility, booking releases,
roster thresholds and checkpoint restoration have offline coverage.

The settings-only roster screen intentionally retains Gamma's existing low-band
550 km long-route limit. Its label describes target bands, not a pure target-only
intervention. Any follow-up that retains 700 km in all bands must be a separate
arm with that explicit setting.

## Results

Four-seed settings screen (candidate minus stored Delta, euros/week):

| Candidate | Paired weeks | Mean margin difference | Positive weeks | Worst on time | Mean wins difference | Status |
|---|---:|---:|---:|---:|---:|---|
| Roster 4000/4500/5000, low-band long max 550 | 4 | +786.13 | 3/4 | 92.749% | +8.25 | Extend to 19 |
| Long cap 5, original 24h slack | 4 | +328.48 | 3/4 | 90.323% | +2.00 | Reject: service |
| Long cap 6, 18h slack | 4 | -109.62 | 2/4 | 90.000% | +6.50 | Reject: margin/service |

The guarded-intake screen is still in flight. Its worker processes imported
code just before commit `8646d19` (the remaining-leg fee-horizon correction).
Its trade-in results therefore describe the earlier implementation and cannot
be pooled with corrected-code confirmation. The two non-trade controls and
settings-only roster arm are unaffected by that correction, with default-off
parity covered by the full suite (444 tests passing).

Detailed practice outputs are under `runs/epsilon-p5/`.
