# Epsilon P1 pair planner and rescue experiments

All policies are opt-in. `models/delta.json` and `models/epsilon.json` remain
unchanged. The base is `origin/t3/epsilon-model`; the comparison uses the
nineteen saved current-Delta weeks, not new Delta worlds.

## Settings

| Setting | Default | Enabled behavior |
| --- | ---: | --- |
| `delta_pair_latest0_windows` | 0 | Delta alias for `pair_tight_windows=1` |
| `pair_tight_windows` | 0 | Clamp four posted stop ends to backward latest(0) visit times |
| `pair_rescue_floor_bps` | 0 | Floor rescue opening at this fraction of the combined current solo offers |
| `pair_rescue_step_minutes` | 0 | Add an early rescue increase after this many minutes |
| `pair_rescue_step_bps` | 600 | Size of the optional step, against combined raw reference fees |
| `pair_retry_limit` | 0 | Allow different partners after failure, up to this many failures per order |
| `pair_retry_transfer_km` | 30 | Transfer bound when either order has a prior failed pair |
| `pair_cancel_cleanup` | 0 | Retire shortened pairs, prune cancelled stops, preserve survivor eligibility |
| `pair_aged_guard_minutes` | 0 | Exclude waiting singles older than this age only when their current fee reaches the guard |
| `pair_aged_guard_bps` | 10000 | Current solo fee threshold for the optional age guard |
| `pair_self_time` | 0 | Count map self-road minutes while retaining zero same-town transfer distance |
| `pair_economic_rank` | 0 | Prefer greatest combined reference less opening fee among feasible pairs |

The numeric step/transfer/guard defaults have no effect unless their policy
is enabled. Existing `delta_pair_self_roads` is reused only in combination;
its standalone negative experiment is not replayed.

## Verified mechanisms and limits

The planner already computes backward feasibility, including calendars,
charging and plates, but originally posts the original solo stop windows.
Latest(0) bounds are captured after calendar/charging handling and before the
30-minute pre-pickup plate allowance. Admission spare, aggregate last start,
latest-safe time, timer and solo windows retain their existing behavior.
Clamping preserves each low bound; an invalid interval is rejected before
withdrawal. Checkpoint and public-gig reconstruction use the same plan.

Rescue pairs reset the fee clock and normally hold the opening for the full
60-minute split interval. The new floor uses actual current solo schedules,
not reference fees as a substitute for an aged offer. An optional early rung
can increase before the timer. Fresh pairs are unaffected. Schedules remain
monotone with unique timestamps.

Bounded re-pairing records failed unordered combinations and per-order failure
counts. It never withdraws booked or started gigs, restores singles after post
failure, and retains the existing confirmed-withdrawal requirement. This arm
needs checkpoint/history persistence before production adoption; the window
and rescue-fee arms introduce no additional recovery state.

Self-road timing and transfer-distance sorting are separate hypotheses. The
existing road flag changes both; `pair_self_time` changes only driving time.
Economic ranking uses a reference-based estimate, not a causal fee-saving
forecast. It may favor long routes and must pass the service gate.

## Evaluation protocol

Use only `scripts/sweep.py`, three workers, ordinary level-eight worlds,
complete Delta JSON base, and separate ignored output beneath
`runs/epsilon-p1/`. Screen seeds include `delta-f1-s07` and `delta-f2-s04`;
initial planner probes use `delta-f1-s06` and `delta-f1-s08` for the other two.
Extend survivors to the exact nineteen-seed union f1 s01..s11 / f2 s01..s08.
Then confirm independently on fresh seeds with retained Delta references.
Read only `summary.md` and `runs.jsonl` for empirical selection.

Promotion requires positive paired mean margin and every observed week at
least 91.5% on time in both existing and fresh cohorts. A screen result is
not promotion, and unchanged Delta itself misses the floor on f1-s07.
No ranking or final worlds are authorized. Stop launching at 03:00 UTC,
resume at 03:45, and drain all worlds by 06:15. Latest report deadline 04:15.
