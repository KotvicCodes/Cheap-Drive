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

All trials use level-8 practice via `scripts/sweep.py`. The initial allocation
was `SWEEP_WORKERS=3`; the orchestrator reduced it to 2 at 01:45 UTC.
The quota returned to three at 02:07 UTC after the readiness rehearsal secured its own slot.
Only `summary.md` and `runs.jsonl` are used for live trial analysis. Existing
19-seed Delta references are reused from sibling worktree
`t3-cb1f1e60-3100c14e73a0d169/runs/epsilon/delta-baseline.jsonl`; their settings
match the complete current Delta JSON. No board or final runs are involved.

The screen uses `delta-f1-s07`, `delta-f2-s04`, `delta-f1-s01`, `delta-f1-s10`.
An eligible survivor needs positive paired mean margin and every observed
week >=91.5% on time, then the complete 19 paired seeds and confirmation.
Four new seeds, `epsilon-p5-holdout-20261115-s01..s04`, were reserved at
01:22 UTC before selecting a survivor on all 19 paired weeks. Delta is measured
once on these previously unseen seeds because no cached scores exist. The
existing eight `epsilon-confirm-20261115-s01..s08` references can support extra
comparisons but were already exposed to other Epsilon experiments, so are not
a new global holdout. No existing Delta reference worlds are replayed.

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

The orchestrator prioritized the roster arm at 01:23 UTC. The weaker screen
was drained after three seeds per arm; its fourth-seed jobs were dropped.

| Guarded control | Paired weeks | Mean margin difference | Positive weeks | Worst on time | Status |
|---|---:|---:|---:|---:|---|
| Trade-ins, cap 2 | 3 | +76.33 | 2/3 | 90.591% | Stopped; below service floor |
| Conditional long cap 5, backlog <=12 | 3 | 0.00 | 0/3 | 91.117% | Stopped; no effect |
| Short-job slack 240 min, backlog <=4 | 3 | -242.98 | 0/3 | 90.883% | Stopped; margin/service |

The guarded screen's workers imported code just before commit `8646d19`
(the remaining-leg fee-horizon correction). Its trade-in results describe
the earlier implementation and cannot be pooled with corrected-code
confirmation. The non-trade controls and settings-only roster arm are
unaffected, with default-off parity covered by all 444 passing tests.

The roster extension started at approximately 01:25 UTC on all three slots,
reusing the original four weeks and playing the remaining 15. Fresh paired
confirmation is conditional on a positive 19-week mean and every week >=91.5%.
Exact roster overrides on Delta's complete settings are:

```json
{
  "supply_scale": 1,
  "supply_low_roster": 710,
  "supply_high_roster": 800,
  "supply_low_target_bps": 4000,
  "supply_mid_target_bps": 4500,
  "supply_high_target_bps": 5000
}
```

The enabled supply policy inherits long-route maxima of 550 / 700 / 700 km
for the low / mid / high bands, respectively. Long cap remains 3, long slack
1440 minutes, and all customer price factors remain Delta's.

Detailed practice outputs are under `runs/epsilon-p5/`.


## Completed roster extension and next screen

The original roster policy failed its full cohort despite passing the screen:

| Candidate | Paired weeks | Mean margin difference | Positive weeks | Worst on time | Mean wins difference |
|---|---:|---:|---:|---:|---:|
| Roster 4000/4500/5000 | 19 | -62.28 | 9/19 | 92.711% | +12.00 |

Its previously queued fresh run was cancelled at the orchestrator's quota and
priority update. No holdout worlds have been launched. The two next arms are:

- `scarce4000-normal4200`: same 710/800 roster thresholds and 550/700/700 km
  corridor maxima, but target 4000 / 4200 / 4200. This preserves Delta's target
  on medium/high rosters and tests scarce-roster protection alone.
- `roster-backlog-valve3-12`: original 4000/4500/5000 supply targets combined
  with `capacity_valve=1`, `open_low=3`, `open_high=12`, and target caps
  5000 / 4200 / 4000 as unbooked backlog rises. Gamma takes the smaller of
  its supply and capacity targets. Customer price factors are unchanged.

The four screen seeds are unchanged. Only the highest paired-mean survivor
with every observed week >=91.5% on time will extend to 19 and then the
reserved four unseen confirmation seeds. All remaining older screen worlds
were drained before the new two-worker sweep started.

## Priority change: guarded safe-distance customer prices

At 02:00 UTC the orchestrator redirected this lane to lever 2 of the supplied
`volume-gap.md`. The pending scarce-roster extension was cancelled; the
completed screen found scarce-only +575.37/week (2/4 positive) and backlog valve
+453.15/week (3/4), both with 92.749% worst on time. They are unconfirmed.

`delta_safe_quote_bps=0` is the new default-off control. Enabled factors apply
only to admitted single-leg, nonpremium, nonprivate options at 50–300 km,
with note-aware slack >=720 minutes and unbooked backlog <=15. The exact final
cent-rounded discounted quote must be >=110% of raw reference fee; otherwise
the original factors and price are retained. It changes customer quotes only;
global target stays 4200 and existing admission, fees, and feedback stay intact.
The existing scalar learner can offset the segment discount as wins change,
so net volume and margin must be measured rather than inferred from the pool.

The three strengths are 9900, 9800, and 9600 basis points (1%, 2%, 4% discount).
The frozen base is confirmed Epsilon: Delta settings plus premium slack 1440.
All 19 Epsilon references were recovered from existing `runs.jsonl` rows with
exact matching settings. Both Delta and Epsilon are paired references. Screen
seeds are f1-s07, f2-s04, f1-s01, f1-s05. Every screen arm with positive paired mean versus
Epsilon and Delta and all weeks >=91.5% advances to 19; adoption also needs positive
means versus Delta and Epsilon and every observed week >=91.5% on time, followed
by the four reserved unseen seeds. No pricing/roster controls are bundled.

The quota returned to three after the rehearsal obtained its own slot.
Subsequent sweep commands use `SWEEP_WORKERS=3`, `SWEEP_TEAM_WORLD_LIMIT=12`;
the runner checks `client.worlds()` before each creation (including retries)
and waits while 12 or more worlds are unfinished. The 03:00–03:45 launch pause
remains in force. Revised confirmation/report target is 05:45 UTC, and all
no new worlds may start after 05:30 UTC, all worlds must finish by 05:50 UTC, and the final report is due 05:45 UTC. Tests: 453 passing, including exact-off action/
journal parity, distance/slack/backlog boundaries, exclusions, final rounding,
reference floor, unchanged learning state, recovery, and the team-cap wait.


### Discount screen and tighter service gates

Completed first screen, candidate minus paired references, euros/week:

| Candidate | Weeks | vs Delta | vs Epsilon | Positive vs Epsilon | Worst on time | Wins vs Epsilon |
|---|---:|---:|---:|---:|---:|---:|
| 1% discount | 4 | +50.59 | -162.82 | 2/4 | 91.444% | +1.75 |
| 2% discount | 4 | +116.42 | -96.98 | 2/4 | 90.000% | +1.75 |
| 4% discount | 4 | -188.63 | -402.04 | 1/4 | 88.889% | +5.25 |

All fail the service floor and confirmed Epsilon margin; none advances. The
next screen keeps the same base, distances, floor and seeds, testing 1% and 2%
with backlog <=10, plus 1% with slack >=1440. All screen survivors extend to
19; the strongest full-cohort survivor proceeds to the reserved fresh cohort.

`SWEEP_START_BEFORE_UTC=2026-11-15T05:30:00+00:00` enforces the new launch
cutoff inside pause/capacity waits and immediately before creation. A launch
timer also blocks this lane at 03:00, resumes at 03:45, and blocks at 05:30.
Tests: 455 passing. No recursive cross-worktree filesystem scans are used.


### Separate safe-segment target fallback

Prepared independently of the fixed-discount arms: `delta_safe_target_bps`
(default 0/off) splits only qualified safe requests into a second learner. The
screen uses 4200 (split-only control), 4600 and 5000, with the Early Epsilon
base, the same four screen seeds, default min slack 720 and max backlog 15.
No fixed discount is applied. Requests must be single-leg, nonpremium, both
endpoints nonprivate, 50–300 km, and normal brake mode. **Every admitted menu
option** must have enough note-aware slack and its actual scoped-learner price
must clear 110% of raw reference; otherwise the request keeps ordinary pricing
and learning. This stronger whole-menu gate is necessary because feedback
resolves a request, not each independently quoted option. Admission is unchanged.

The tracker name encodes the quoted target, so feedback, checkpoint restoration
and durable action-receipt replay use that target even if backlog or brake mode
changes later. Off mode preserves actions, calls, scores and journals. Alternate
markup scopes and simultaneous fixed discounts are rejected when this is enabled.

A separate unseen cohort, `epsilon-p5-target-holdout-20261115-s01..s04`, was
reserved at 02:29 UTC before any target-arm screen results, in case the discount
experiment consumes its own holdout. Screen survivors must beat Delta and Early
Epsilon with all weeks >=91.5%; target uplift must also be compared against the
4200 split-only control to distinguish structure from quantity.

A queue handoff briefly duplicated the first guarded screen. The duplicate
sweep was stopped, its single extra world deleted, and the intended three
workers retained. All reported scores come from completed intended worlds.


At 02:30 UTC all three tighter discount arms had failed service on the two
hard seeds: 1%/backlog10 and 1%/slack1440 reached 91.444%, while 2%/backlog10
reached 91.379%. Their pending jobs were cancelled after draining in-flight
third-seed weeks. None extends. The separate target screen follows that drain
and inherits all team, pause and launch-cutoff gates.

The orchestrator renamed the confirmed premium1440 base **Early Epsilon**.
All 34 exact-matching `premium-slack1440` seed references were verified with
no score conflicts and cached locally; the first target extension retains
the specified 19-seed cohort. The target fresh cohort remains unseen.
Tests: 463 passing, including cutoff expiration during both pause and team
capacity waits. A lane-local 05:48 cleanup guard ends any remaining own practice
worlds before the 05:50 hard deadline without touching any other runner.
