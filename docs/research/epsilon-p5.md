# Epsilon P5: selective intake experiments

Published branch: `t3/epsilon-p5b` (continued from `t3/epsilon-p5`, originally based on `origin/t3/epsilon-model`).
Production `models/delta.json` and `models/epsilon.json` remain unchanged.

**Current protocol (03:28 UTC user order):** one ordered deep queue with
three workers: admission360/cap4/max700 on all19 paired then four reserved fresh
seeds, followed by segmented SAFE5000 and5500 on the same cohorts. Fresh Delta/
Early Epsilon references run last; retained baseline worlds are never replayed.
Every new world checks the team12 and own-lane3 limits. Launches stop05:30;
active worlds drain, with own-world cleanup before05:50. No PR or merge.
Earlier protocols below are historical and superseded.

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


### Verified zero-code admission fallbacks

The orchestrator supplied `gem-vol-6-mechanics.md` at 02:40 UTC. Its levers 4A
and 5A use real GammaSettings keys: `trade_ins`, `min_slack_minutes`,
`same_day_min_slack_minutes`, `long_open_cap`, and `long_max_km`. All four plans
instantiate successfully on the synthetic map with the Early Epsilon base.

Prepared if selective pricing fails: bare `trade_ins=1`; slack300/cap6/max850
with same-day slack480 and target4200; the same with Gemini's full target4800;
and a conservative slack360/cap4/max700 arm with target4200. The exact Gemini
bundle and admission-only variants are separate so global target changes do not
get attributed to admission. Bare trade-ins retain strict return-leg windows:
this screen makes no claim to implement lever4B's same-visit repair, and the
prior guarded-trade screen failed service. None of these mechanisms has an
established gain. Four unused admission holdout seeds were reserved at 02:42
UTC before any admission-screen outcomes. All existing slot, pause, cutoff,
full-cohort and fresh confirmation requirements remain unchanged.


Publication moved to `t3/epsilon-p5b` after shared ref/history rewrites caused
non-fast-forward push rejections. The current local history was retained at
the orchestrator's direction; no force push, merge or PR was performed. The
model/test source is unchanged by this publication issue. Retained paired
reference scores are copied to `plans/epsilon-p5/paired-references.json` so
result differences are reviewable without an API call or replaying baselines.


### New priority: direct decline-admission screens

The orchestrator supplied `gem-vol-3-declines.md` at 02:54 UTC and requested
A–D ahead of the weak selective-pricing lead. All settings keys and the comma-
separated long-option enum validate in the existing factory. The screen chooses
the permitted safer same-day threshold360: A=slack240/same-day360; B=A plus
long cap10/max900/all three options; C=B plus bare trade-ins; D=C plus global
target4600. Premium1440 and long minimum slack1440 remain enforced. The
previous narrower slack360/cap4/max700 arm is retained for comparison, reusing
its first completed score; other rejected admission variants stop. Gemini's
claimed euro improvements are scenarios, not confirmed effects. No admission
code changes or automatic free-release behavior are implied by these settings.

The selective target4600 screen completed: +290.20/week vs Delta, +76.79 vs
Early Epsilon, 3/4 positive, 91.781% minimum service, +0.50 wins/week. It is
held for a possible later extension while the newly prioritized admission arms
run. The split4200 control failed service at90.286%; target5000 at90.028%.

A coordinator unexpectedly exited with SIGTERM while its workers continued;
the fallback advanced early. Launches were paused and all admission workers
drained before switching screens. An additional default-off lane gate now
serializes slot checks, world creation and ownership-marker writes with a file
lock. This lane uses `SWEEP_LANE_WORLD_LIMIT=3` and `SWEEP_LANE_ROOT=runs/epsilon-p5`
in addition to the team12 gate. Tests:465 passing.


### Converged queue: A–D only, exact240/300 settings

At 02:58 UTC the orchestrator requested convergence on A–D and immediate
loop-manager handoff after their four-seed screen. The final screen therefore
uses base slack240/same-day300, with A alone; B adding long cap10/max900/all
three long options; C adding trade-ins; and D adding target4600. All four exact
configs instantiate successfully. They use new unique labels/output so the
earlier permitted360-minute variants cannot be pooled by mistake. The narrower
360/cap4 comparison and all pricing follow-ups are stopped.

Only these A–D arms run after the old weeks drain. The handoff is atomically
written to the requested scratchpad `admission-best.json` with complete
settings, overrides, paired Delta/Early Epsilon statistics and per-seed scores.
Only the best positive-mean, ranked, all-weeks>=91.5% screen arm extends to the
19 paired seeds, then the reserved admission fresh cohort if it survives.
If no arm qualifies, the handoff explicitly says no eligible survivor and no
extension is launched. The existing03:00–03:45 pause and05:30/05:50 deadlines
remain enforced. Long slack1440 and premium1440 remain unchanged in A–D.


### User-requested two-pool SAFE/REST learner

At 03:03 UTC the orchestrator requested one additional default-off build:
`delta_segmented_targets=1`, `win_target_safe_bps=5000` or5500, with REST
fixed4200. SAFE requires total route<=300 km, maximum offered deadline minus
request arrival>=2160 minutes, and final-delivery `near30 >5`. Unknown delivery
supply stays REST. This uses delivery supply as explicitly requested; Gemini's
related timing analysis used pickup supply, so its forecasts do not validate
this exact classifier. `near30` counts frozen public homes by directed road km,
not available compatible drivers. Maximum lead is not note-aware option slack.

Separate tracker keys retain SAFE and REST markups, daily starts and pending
feedback; target values encoded in the keys survive existing checkpoint and
action-receipt replay. SAFE outcomes never train REST or the old global markup.
REST stays4200 even if a former admission bundle used global4600 or an optional
capacity/brake policy asks for a lower target. No discounts, markup offsets,
reference floors or extra admission changes are bundled. Concurrent use of the
older safe-price experiments or alternative markup scopes is rejected.

The standalone A–D controller was stopped while its sweep continues, so it
cannot automatically extend before the new comparison. After all four-seed
admission results, the best eligible arm (or best observed arm, explicitly
marked unsafe if none qualifies) is handed off. Its admission settings become
the base of the two segmented screens; global target is kept4200 in their
plan because SAFE/REST supply the targets. The best combined survivor extends
against cached Delta/Early Epsilon and its admission-only control to19, then
uses a separately reserved unseen cohort of four segmented holdout seeds.
Reported volume will be compared against both Early Epsilon and the admission
control; a margin increase alone does not establish the requested volume gain.


### Converged strong-signal protocol and current screen

The ranking pause ended early at03:17 UTC on the orchestrator's instruction.
A–D then all failed: A (2seeds) -1073.74/week vs Early Epsilon,87.696% worst;
B (2seeds) -2606.36,86.146%; C (1seed) -2917.36,87.692%; D (1seed) -2159.89,
87.560%. Remaining jobs were stopped after current worlds drained.

The best prior admission observation was the narrower slack360/same-day480/
long cap4/max700: +1387.74 vs Early Epsilon,93.239% on the first hard seed,
+7wins. This is **one seed, not a confirmed winner**. It is the provisional
base of the newly requested SAFE5000/5500 screens, and its remaining three
control seeds run alongside them. The existing first score is reused.

The runner's optional `SWEEP_DISABLED_LABELS_FILE` allows a score-only monitor
to stop future worlds immediately when an arm fails service, while active
weeks finish. Tests:473 passing. Current handoff is the requested scratchpad
`admission-best.json`; `segmented-volume-results.json` is the retained copy.
Only the strongest four-seed arm reaching +500/week,380wins and91.5% service
will get eight more seeds. Those eight were fixed before screen outcomes:
f1-s02,s03,s04,s08 and f2-s01,s02,s03,s05. No admission-control extension or
full19/fresh cohort is queued under the revised protocol.


### Ordered deep queue (latest user direction)

The user explicitly replaced the four-plus-eight screening protocol with a
deep queue. `volume-deep-queue.json` uses the optional explicit `jobs` list to
order whole cohorts in one three-worker ProcessPoolExecutor: primary admission
19+fresh4, segmented5000 19+fresh4, segmented5500 19+fresh4, and the eight new
fresh-reference worlds. No disabled-arm flag is supplied to this requested
research queue, so known service failures remain visible rather than causing
the ordered cohort to be silently shortened. Existing exact-setting scores are
reused across output directories; no known Delta/Early Epsilon week is replayed.

The primary admission control failed its second hard seed (91.223% worst over
two); segmented5500 failed its first (88.773%). These findings cannot qualify
for promotion, irrespective of later cohort averages. The user nevertheless
requested completing their research queue. The runner's05:30 cutoff drains
pending jobs without starting worlds; active weeks still finish. Tests:474
passing, including explicit job ordering, reuse and invalid-job rejection.
