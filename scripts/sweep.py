"""Play a grid of model settings on shared practice seeds, unattended, and keep every run.

    python scripts/sweep.py runs/beta/<name> plan.json

plan.json: {"factory": "beta:make_beta", "level": 8, "seeds": [...],
            "base": {settings shared by all}, "variants": {"label": {settings}, ...},
            "fast": true}

"fast" (the default) skips the stops at bookkeeping events and the daily score
reads; every event, action and the end-of-week reveal are still saved.

Each (variant, seed) is one ordinary practice world, never a ranking run. Up to
eight play at once (the team's unfinished-world limit). Finished weeks are
skipped on a rerun, so an interrupted sweep resumes. Outputs under the given
directory (git-ignored): traces/*.jsonl.gz, reveals/*.json.gz, runs.jsonl
(one line per week) and summary.md (one row per variant).

Set SWEEP_PAUSE_FILE to a shared file path for drain-and-resume control.
Creating that file blocks new worlds (including retries) while active weeks
finish. Removing it resumes queued weeks; completed scores are still reused.
"""
from __future__ import annotations

import concurrent.futures as cf
from contextlib import contextmanager, nullcontext, redirect_stdout
from datetime import datetime, timezone
import gzip
import io
import json
import logging
import os
from pathlib import Path
import statistics
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models import resolve_factory

WORKERS = int(os.environ.get("SWEEP_WORKERS", "8"))
LEDGER = ("revenue", "driver_fee", "late_refund", "failed_visit", "release_fee", "waiting", "fine", "penalty")
EVENTS = ("price_request", "order_won", "gig_booked", "gig_dropped", "gig_expired", "deadline_close",
          "visit_failed", "no_show", "order_cancelled")


class LaunchWindowClosed(RuntimeError):
    """A requested launch cutoff has passed; active weeks may still finish."""


def check_launch_cutoff():
    cutoff = os.environ.get('SWEEP_START_BEFORE_UTC')
    if cutoff:
        end = datetime.fromisoformat(cutoff)
        if end.tzinfo is None:
            raise ValueError('SWEEP_START_BEFORE_UTC must include a timezone')
        if datetime.now(timezone.utc) >= end:
            raise LaunchWindowClosed('practice launch cutoff reached')


def wait_for_launch():
    """Pause only at world boundaries; never interfere with an active week."""
    path = os.environ.get("SWEEP_PAUSE_FILE")
    check_launch_cutoff()
    while path and Path(path).exists():
        time.sleep(1)
        check_launch_cutoff()


def wait_for_team_capacity(client):
    limit = int(os.environ.get('SWEEP_TEAM_WORLD_LIMIT', '0'))
    if limit < 0:
        raise ValueError('SWEEP_TEAM_WORLD_LIMIT must be nonnegative')
    if not limit:
        return
    while True:
        wait_for_launch()
        if sum(not world['ended'] for world in client.worlds()) < limit:
            return
        time.sleep(3)


@contextmanager
def world_launch_slot(client, label=None):
    """Serialize lane checks through creation and writing its ownership marker."""
    limit = int(os.environ.get('SWEEP_LANE_WORLD_LIMIT', '0'))
    root = os.environ.get('SWEEP_LANE_ROOT')
    if limit < 0 or limit and not root:
        raise ValueError('a positive lane limit requires SWEEP_LANE_ROOT')
    if limit:
        import fcntl
        lane = Path(root)
        lane.mkdir(parents=True, exist_ok=True)
    while True:
        lock = (lane / '.launch.lock').open('a') if limit else nullcontext()
        with lock as stream:
            if limit:
                fcntl.flock(stream, fcntl.LOCK_EX)
            wait_for_launch()
            disabled = os.environ.get('SWEEP_DISABLED_LABELS_FILE')
            if disabled and label in json.loads(Path(disabled).read_text()):
                raise LaunchWindowClosed('arm disabled by screen monitor')
            wait_for_team_capacity(client)
            full = False
            if limit:
                active = {w['worldId'] for w in client.worlds() if not w['ended']}
                owned = {p.name for directory in lane.glob('*/worlds')
                         for p in directory.iterdir() if p.is_file()}
                full = len(active & owned) >= limit
            if not full:
                check_launch_cutoff()
                yield
                return
        time.sleep(3)


def finish_started_week(world, level, journal, make_desk, *, fast, resumed=False):
    """A started week always finishes; network failures rejoin the same world."""
    from dispatch import play_model
    failures = 0
    journal.practice_recoveries = int(resumed)
    while True:
        def factory(w, l, n, j):
            desk = make_desk(w, l, n, j)
            if resumed:
                from final import full_history
                snapshot = w.initial_snapshot
                history = full_history(world, through=snapshot['now'])
                j.record_history(history)
                desk.rejoin(snapshot, history)
            return desk
        try:
            return play_model(world, level, journal, factory, fast=fast)
        except Exception as error:
            failures += 1
            journal.practice_recoveries += 1
            resumed = True
            journal.record('practice_rejoin_retry', worldId=world.id,
                           failures=failures, errorType=type(error).__name__)
            time.sleep(min(60, 5 * failures))


def play_week(out, factory_name, level, seed, label, settings, fast):
    from performance import PracticeClient as Client
    from compare import MetricsJournal
    from dispatch import play_model
    logging.basicConfig(level=logging.ERROR)
    out = Path(out)
    factory = resolve_factory(factory_name)
    client = Client(url=os.environ.get("SPREAD_URL") or "https://spread.bahnexpress.com")
    tag, last = f"{label}--{seed}", None
    world, attempt, started = None, -1, None
    while True:
        attempt += 1
        resumed = world is not None
        try:
            if world is None:
                with world_launch_slot(client, label):
                    world = client.create(level=level, seed=seed, board=False)
                    started = time.time()
                    (out / "worlds" / world.id).write_text(tag)
            else:
                (out / "worlds" / world.id).write_text(tag)
            name = tag if attempt == 0 else f"{tag}-attempt{attempt + 1}"
            with gzip.open(out / "traces" / f"{name}.jsonl.gz", "wt", encoding="utf-8") as stream:
                journal = MetricsJournal(stream)
                if os.environ.get('SWEEP_FEE_DIAGNOSTICS') == '1':
                    from scripts.sweep_fees import FeeMetricsJournal

                    def nominal_opening(action):
                        stop = action['stops'][0]
                        order = desk.orders[stop['orderId']]
                        typical = desk.requests[order['id']]['referenceFeeCents'] / len(order['legs'])
                        return max(1, int(typical * desk._opening_bps(order) / 10000 + 0.5))

                    journal = FeeMetricsJournal(stream, nominal_opening)

                def make_desk(w, l, n, j):
                    nonlocal desk
                    desk = factory(w, l, n, j, **settings)
                    return desk

                desk = None
                journal.record("run", worldId=world.id, level=level, seed=seed, factory=factory_name,
                               settings=settings, tag=tag, attempt=attempt + 1, fast=fast)
                with redirect_stdout(io.StringIO()):
                    score = finish_started_week(world, level, journal, make_desk, fast=fast, resumed=resumed)
                diag = journal.metrics()
            reveal_file = None
            for wait in (0, 5, 20):
                time.sleep(wait)
                try:
                    reveal = client.call("GET", f"/v1/worlds/{world.id}/reveal")
                    reveal_file = f"{name}.reveal.json.gz"
                    with gzip.open(out / "reveals" / reveal_file, "wt", encoding="utf-8") as f:
                        json.dump({"worldId": world.id, "seed": seed, "level": level, "reveal": reveal}, f)
                    break
                except Exception:
                    pass
            (out / "worlds" / world.id).unlink(missing_ok=True)
            return {"score": score, "ledger": diag["ledger"], "events": diag["events"],
                    **({'fee_escalation': diag['fee_escalation']} if 'fee_escalation' in diag else {}),
                    **({'interventions': diag['interventions']} if 'interventions' in diag else {}),
                    "visit_failures": diag["visit_failures"], "rejections": diag["rejections"],
                    "world_id": world.id, "trace": f"{name}.jsonl.gz", "reveal": reveal_file,
                    "seconds": round(time.time() - started), "attempts": attempt + 1,
                    "rejoins": getattr(journal, "practice_recoveries", int(resumed))}
        except LaunchWindowClosed:
            raise
        except Exception as error:  # network blips, slot races, server restarts
            last = f"{type(error).__name__}: {error}"
            try:
                with (out / "errors.log").open("a") as f:
                    f.write(f"{tag} attempt {attempt + 1}\n{traceback.format_exc()}\n")
            except OSError:
                pass  # A temporary disk failure must not abandon a created world.
            if world is None and attempt >= 3:
                raise RuntimeError(last) from error
            # A created world remains owned across setup, trace and transport
            # failures. Never delete it, replace it, or exhaust its retry budget.
            time.sleep(min(60, 20 * 2 ** min(attempt, 2)))


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def summarize(out, plan):
    rows = [r for r in load(out / "runs.jsonl") if "score" in r]
    seeds = plan["seeds"]
    lines = [f"# Sweep {out.name}\n", f"Level {plan['level']}, seeds: {', '.join(seeds)}. Margins in euros per week.\n",
             "| variant | weeks | ranked | margin | worst | on-time min | on-time mean | won | revenue | driver fees | fee/rev | refunds | failed | booked | dropped | warnings | declined-ish win% |",
             "|" + "---|" * 17]
    table = []
    for label in plan["variants"]:
        weeks = {r["seed"]: r for r in rows if r["label"] == label}
        weeks = [weeks[s] for s in seeds if s in weeks]
        if not weeks:
            continue
        mean = lambda f: statistics.fmean(f(w) for w in weeks)
        led = lambda k: mean(lambda w: w["ledger"].get(k, 0)) / 100
        ev = lambda k: mean(lambda w: w["events"].get(k, 0))
        margin = mean(lambda w: w["score"]["marginCents"]) / 100
        table.append((margin, f"| {label} | {len(weeks)}/{len(seeds)} | {sum(bool(w['score']['ranked']) for w in weeks)} | "
                      f"{margin:,.0f} | {min(w['score']['marginCents'] for w in weeks) / 100:,.0f} | "
                      f"{100 * min(w['score']['onTimeShare'] for w in weeks):.1f} | {100 * mean(lambda w: w['score']['onTimeShare']):.1f} | "
                      f"{mean(lambda w: w['score']['wonOrders']):.0f} | {led('revenue'):,.0f} | {led('driver_fee'):,.0f} | "
                      f"{-led('driver_fee') / max(led('revenue'), 1):.2f} | {led('late_refund'):,.0f} | {led('failed_visit'):,.0f} | "
                      f"{ev('gig_booked'):.0f} | {ev('gig_dropped'):.0f} | {ev('deadline_close'):.0f} | "
                      f"{100 * ev('order_won') / max(ev('price_request'), 1):.0f} |"))
    lines += [row for _, row in sorted(table, reverse=True)]
    lines += ["\n## Per week\n", "| variant | seed | margin | on-time % | won | ranked |", "|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["label"], r["seed"])):
        s = r["score"]
        lines.append(f"| {r['label']} | {r['seed']} | {s['marginCents'] / 100:,.0f} | {100 * s['onTimeShare']:.1f} | {s['wonOrders']} | {s['ranked']} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    return "\n".join(lines[:4 + len(table)])


def planned_jobs(plan, done):
    """Optional explicit ordering keeps different cohorts in one worker queue."""
    jobs = ([(j['label'], j['seed']) for j in plan['jobs']] if 'jobs' in plan else
            [(label, seed) for seed in plan['seeds'] for label in plan['variants']])
    if len(jobs) != len(set(jobs)) or any(label not in plan['variants'] or seed not in plan['seeds']
                                         for label, seed in jobs):
        raise ValueError('jobs must be unique known variant/seed pairs')
    return [(label, seed) for label, seed in jobs if (label, seed) not in done]



def queued_jobs(plan, done):
    """Allow disjoint per-arm seed assignments when peers share the queue."""
    assignments = plan.get("variant_seeds", {})
    if set(assignments) - set(plan["variants"]):
        raise ValueError("variant_seeds contains an unknown variant")
    if any(set(seeds) - set(plan["seeds"]) for seeds in assignments.values()):
        raise ValueError("variant_seeds contains an unknown seed")
    return [(label, seed) for label, seed in planned_jobs(plan, done)
            if seed in assignments.get(label, plan["seeds"])]


def gate_failures(plan, rows):
    """Evaluate only paired completed weeks; the control is never eliminated."""
    gate = plan.get('sequential_gate')
    if not gate:
        return {}
    control = {r['seed']: r for r in rows
               if r.get('label') == gate['control'] and 'score' in r}
    failures = {}
    for label in plan['variants']:
        if label == gate['control']:
            continue
        weeks = {r['seed']: r for r in rows
                 if r.get('label') == label and 'score' in r}
        pairs = [(w, control[seed]) for seed, w in weeks.items() if seed in control]
        if len(pairs) < gate.get('min_pairs', 3):
            continue
        limits = {**gate, **gate.get('overrides', {}).get(label, {})}
        gains = [w['score']['marginCents'] - c['score']['marginCents'] for w, c in pairs]
        worst = min(w['score']['onTimeShare'] for w in weeks.values())
        mean_gain = statistics.fmean(gains)
        gain_fails = (mean_gain <= limits['min_gain_cents'] if limits.get('strict_gain')
                      else mean_gain < limits['min_gain_cents'])
        service_fails = (worst <= limits['min_on_time'] if limits.get('strict_on_time')
                         else worst < limits['min_on_time'])
        if (gain_fails or service_fails or
                (limits.get('half_positive', True) and sum(g > 0 for g in gains) * 2 < len(gains))):
            failures[label] = dict(pairs=len(pairs), mean_gain_cents=statistics.fmean(gains),
                                   positive=sum(g > 0 for g in gains), worst_on_time=worst)
    return failures


def next_job(jobs, active, plan, disabled):
    """Choose a permitted queued job while respecting per-arm concurrency caps."""
    caps = plan.get('variant_workers', {})
    for index, (label, seed) in enumerate(jobs):
        if label in disabled:
            continue
        if sum(job[0] == label for job in active) >= caps.get(label, WORKERS):
            continue
        return jobs.pop(index)
    return None


def main():
    out, plan_path = Path(sys.argv[1]), Path(sys.argv[2])
    plan = json.loads(plan_path.read_text())
    base = plan.pop("base", {})  # settings shared by every variant
    plan["variants"] = {label: {**base, **settings} for label, settings in plan["variants"].items()}
    if not os.environ.get("SPREAD_KEY"):
        sys.exit("SPREAD_KEY missing")
    for sub in ("", "traces", "reveals", "worlds"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    done = {(r["label"], r["seed"]) for r in load(out / "runs.jsonl") if "score" in r}
    jobs = queued_jobs(plan, done)
    print(f"{len(jobs)} weeks to play, {len(done)} already done", flush=True)
    disabled = set()
    with cf.ProcessPoolExecutor(WORKERS) as pool:
        futures = {}
        while jobs or futures:
            rows = load(out / 'runs.jsonl')
            failures = gate_failures(plan, rows)
            for label, evidence in failures.items():
                if label not in disabled:
                    print(f"GATE eliminated {label}: {evidence}", flush=True)
            disabled.update(failures)
            jobs[:] = [job for job in jobs if job[0] not in disabled]
            while len(futures) < WORKERS:
                job = next_job(jobs, list(futures.values()), plan, disabled)
                if job is None:
                    break
                label, seed = job
                future = pool.submit(play_week, str(out), plan['factory'], plan['level'], seed,
                                     label, plan['variants'][label], bool(plan.get('fast', True)))
                futures[future] = job
            if not futures:
                break
            ready, _ = cf.wait(futures, return_when=cf.FIRST_COMPLETED)
            for future in ready:
                label, seed = futures.pop(future)
                row = {"label": label, "seed": seed, "settings": plan["variants"][label]}
                try:
                    row.update(future.result())
                    score = row['score']
                    print(f"{label} {seed}: margin {score['marginCents'] / 100:,.0f} "
                          f"on-time {100 * score['onTimeShare']:.1f}% won {score['wonOrders']} "
                          f"({row['seconds']}s)", flush=True)
                except Exception as error:
                    row['error'] = str(error)
                    print(f"{label} {seed}: FAILED {error}", flush=True)
                with (out / 'runs.jsonl').open('a') as stream:
                    stream.write(json.dumps(row) + '\n')
    print(summarize(out, plan), flush=True)


if __name__ == "__main__":
    main()
