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
from contextlib import redirect_stdout
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


def wait_for_launch():
    """Pause only at world boundaries; never interfere with an active week."""
    path = os.environ.get("SWEEP_PAUSE_FILE")
    while path and Path(path).exists():
        time.sleep(1)


def play_week(out, factory_name, level, seed, label, settings, fast):
    from performance import PracticeClient as Client
    from compare import MetricsJournal
    from dispatch import play_model
    logging.basicConfig(level=logging.ERROR)
    out = Path(out)
    factory = resolve_factory(factory_name)
    client = Client(url=os.environ.get("SPREAD_URL") or "https://spread.bahnexpress.com")
    tag, last = f"{label}--{seed}", None
    for attempt in range(4):
        world = None
        try:
            wait_for_launch()
            world = client.create(level=level, seed=seed, board=False)
            (out / "worlds" / world.id).write_text(tag)
            started = time.time()
            name = tag if attempt == 0 else f"{tag}-attempt{attempt + 1}"
            with gzip.open(out / "traces" / f"{name}.jsonl.gz", "wt", encoding="utf-8") as stream:
                journal = MetricsJournal(stream)
                journal.record("run", worldId=world.id, level=level, seed=seed, factory=factory_name,
                               settings=settings, tag=tag, attempt=attempt + 1, fast=fast)
                with redirect_stdout(io.StringIO()):
                    score = play_model(world, level, journal, lambda w, l, n, j: factory(w, l, n, j, **settings), fast=fast)
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
                    "visit_failures": diag["visit_failures"], "rejections": diag["rejections"],
                    "world_id": world.id, "trace": f"{name}.jsonl.gz", "reveal": reveal_file,
                    "seconds": round(time.time() - started), "attempts": attempt + 1}
        except Exception as error:  # network blips, slot races, server restarts
            last = f"{type(error).__name__}: {error}"
            with (out / "errors.log").open("a") as f:
                f.write(f"{tag} attempt {attempt + 1}\n{traceback.format_exc()}\n")
            if world is not None:  # only a world this worker made
                try:
                    world.delete()
                    (out / "worlds" / world.id).unlink(missing_ok=True)
                except Exception:
                    pass
            time.sleep(20 * 2 ** attempt)
    raise RuntimeError(last)


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
    jobs = [(label, seed) for seed in plan["seeds"] for label in plan["variants"] if (label, seed) not in done]
    print(f"{len(jobs)} weeks to play, {len(done)} already done", flush=True)
    with cf.ProcessPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(play_week, str(out), plan["factory"], plan["level"], seed, label,
                               plan["variants"][label], bool(plan.get("fast", True))): (label, seed)
                   for label, seed in jobs}
        for future in cf.as_completed(futures):
            label, seed = futures[future]
            row = {"label": label, "seed": seed, "settings": plan["variants"][label]}
            try:
                row.update(future.result())
                s = row["score"]
                print(f"{label} {seed}: margin {s['marginCents'] / 100:,.0f} on-time {100 * s['onTimeShare']:.1f}% "
                      f"won {s['wonOrders']} ({row['seconds']}s)", flush=True)
            except Exception as error:
                row["error"] = str(error)
                print(f"{label} {seed}: FAILED {error}", flush=True)
            with (out / "runs.jsonl").open("a") as f:
                f.write(json.dumps(row) + "\n")
    print(summarize(out, plan), flush=True)


if __name__ == "__main__":
    main()
