"""Compare two dispatch models on paired practice weeks and emit Markdown."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
import inspect
import json
import logging
import math
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import signal
from statistics import mean
import time
import hashlib

from performance import PracticeClient as Client

from dispatch import DeskFactory, FixedDesk, FixedPrices, Journal, JournalDesk, euro_cents, play_model
from models import persisted_factory_name, resolve_factory


def fixed(world, level, now, journal, *, dealer_price="100", driver_fee="150"):
    return FixedDesk(world, level, now,
                     FixedPrices(euro_cents(str(dealer_price)), euro_cents(str(driver_fee))), journal)


@dataclass
class Model:
    spec: dict
    factory: DeskFactory


def load_model(path: Path) -> Model:
    """Load trusted local code; validate configuration before creating any world."""
    spec = json.loads(path.read_text(encoding="utf-8"))
    return model_from_spec(spec, str(path))


def model_from_spec(spec, path="model") -> Model:
    if not isinstance(spec, dict) or set(spec) - {"name", "factory", "settings"}:
        raise ValueError(f"{path}: use name, factory and optional settings")
    if not isinstance(spec.get("name"), str) or not spec["name"].strip():
        raise ValueError(f"{path}: name must be a nonempty string")
    settings = spec.setdefault("settings", {})
    if not isinstance(settings, dict):
        raise ValueError(f"{path}: settings must be an object")
    name = spec.get("factory")
    if name == "fixed":
        for key in ("dealer_price", "driver_fee"):
            if key in settings:
                try:
                    euro_cents(str(settings[key]))
                except argparse.ArgumentTypeError as error:
                    raise ValueError(f"{path}: {key}: {error}") from error
        factory = fixed
    elif name == "starter":
        factory = JournalDesk
    elif isinstance(name, str) and ":" in name:
        factory = resolve_factory(name)
    else:
        raise ValueError(f"{path}: factory must be fixed, starter, or module:callable")
    inspect.signature(factory).bind(None, None, None, None, **settings)

    def make_desk(world, level, now, journal):
        desk = factory(world, level, now, journal, **settings)
        if not isinstance(desk, JournalDesk):
            raise TypeError("model factories must return a JournalDesk subclass so diagnostics are captured")
        return desk

    # Persist the original identity so final/recovery can reuse saved state.
    # Leave the caller's spec and JSON files in their supplied spelling.
    persisted_name = persisted_factory_name(name)
    if persisted_name != name:
        spec = {**spec, "factory": persisted_name}
    return Model(spec, make_desk)


class MetricsJournal(Journal):
    def __init__(self, output, **kwargs):
        super().__init__(output, **kwargs)
        self.events = Counter()
        self.rejections = Counter()
        self.visit_failures = Counter()
        self.ledger = Counter()

    def record(self, kind, **fields):
        super().record(kind, **fields)
        events, results = [], []
        if kind == "event":
            events = [fields["event"]]
        elif kind == "action_result":
            results = [fields["result"]]
        elif kind == "act_result":
            results = fields["results"]
        elif kind == "advance_batch":
            events = fields["response"]["events"]
            results = fields["response"]["results"]
        for event in events:
            self.events[event["kind"]] += 1
            if event["kind"] == "visit_failed":
                self.visit_failures[event["reason"]] += 1
            if event["kind"] == "ledger":
                line = event["line"]
                self.ledger[line["kind"]] += line["cents"]
        for result in results:
            if not result["ok"]:
                self.rejections[result["reason"]] += 1

    def metrics(self):
        return {"events": dict(self.events), "rejections": dict(self.rejections),
                "visit_failures": dict(self.visit_failures), "ledger": dict(self.ledger)}


def code_revision():
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
        paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "*.py"], text=True).splitlines()
        sources = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
                   for name in sorted(set(paths)) if Path(name).is_file()}
        return {"commit": revision, "dirty": dirty, "source_sha256": sources}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": "unknown", "dirty": None}


def save_results(path, results):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _play_run(client, model, run, output, code, *, fast, delete_on_error, stop_requested=None):
    world = None
    started = time.perf_counter()
    if hasattr(client, "reset_timing"):
        client.reset_timing()
    try:
        run["status"] = "running"
        print(f"Level {run['level']}, seed {run['seed']}, model {model.spec['name']}", file=sys.stderr, flush=True)
        with (output / run["trace"]).open("x", encoding="utf-8") as stream:
            journal = MetricsJournal(stream)
            if stop_requested and stop_requested():
                raise KeyboardInterrupt
            world = client.create(level=run["level"], seed=run["seed"], board=False)
            run["world_id"] = world.id
            journal.record("run", worldId=world.id, mode="practice", level=run["level"],
                           seed=run["seed"], model=model.spec, code=code, fast=fast)
            print(f"World {world.id}; trace {output / run['trace']}", file=sys.stderr, flush=True)
            with redirect_stdout(sys.stderr):
                run["score"] = play_model(world, run["level"], journal, model.factory,
                                          fast=fast, stop_requested=stop_requested)
            run["diagnostics"] = journal.metrics()
            if hasattr(client, "timing"):
                run["timing"] = client.timing()
                journal.record("timing", **run["timing"])
        run["status"] = "complete"
    except (Exception, KeyboardInterrupt) as error:
        run.update(status="failed", error="interrupted" if isinstance(error, KeyboardInterrupt) else "operation failed")
        if world is not None and delete_on_error:
            try:
                world.delete()
            except Exception:
                run["cleanup_error"] = "cleanup failed"
                print(f"Could not delete practice world {world.id}; it may hold a slot.", file=sys.stderr)
        raise
    finally:
        run["seconds"] = round(time.perf_counter() - started, 3)


_worker_client = _worker_stop = None


def _start_worker(url, key, compression, stop, client_factory):
    global _worker_client, _worker_stop
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    _worker_stop = stop
    _worker_client = client_factory() if client_factory else Client(url=url, key=key, compression=compression)


def _worker_run(spec, run, output, code, fast, delete_on_error):
    try:
        model = model_from_spec(spec)
        _play_run(_worker_client, model, run, output, code, fast=fast,
                  delete_on_error=delete_on_error, stop_requested=_worker_stop.is_set)
    except (Exception, KeyboardInterrupt):
        run.setdefault("error", "operation failed")
        run["status"] = "failed"
    return run


def run_comparison(client, models, levels, seeds, output: Path, *, delete_on_error=False,
                   workers=1, fast=False, resume=False, client_factory=None):
    """Only one controller may write a comparison directory, including resumes."""
    import fcntl

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_name(f".{output.name}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("another runner is already using this output directory") from None
        return _run_comparison(client, models, levels, seeds, output,
                               delete_on_error=delete_on_error, workers=workers, fast=fast,
                               resume=resume, client_factory=client_factory)


def _run_comparison(client, models, levels, seeds, output: Path, *, delete_on_error=False,
                   workers=1, fast=False, resume=False, client_factory=None):
    """Paired official runs with isolated workers and completed-week checkpoints."""
    if len(models) != 2 or models[0].spec["name"] == models[1].spec["name"]:
        raise ValueError("choose two models with distinct names")
    if not levels or len(set(levels)) != len(levels) or any(level not in range(1, 9) for level in levels):
        raise ValueError("levels must be distinct numbers from 1 to 8")
    if not seeds or len(set(seeds)) != len(seeds) or any(not seed.strip() for seed in seeds):
        raise ValueError("seeds must be distinct nonempty strings")
    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= 8:
        raise ValueError("workers must be between 1 and 8")
    code = code_revision()
    execution = {"fast": fast, "server": getattr(client, "url", "test"),
                 "compression": getattr(client, "compression", False)}
    selection = {"models": [model.spec for model in models], "levels": levels, "seeds": seeds}
    result_path = output / "results.json"
    if resume:
        results = json.loads(result_path.read_text(encoding="utf-8"))
        if (results.get("schema_version") != 1 or results.get("mode") != "practice"
                or any(results.get(key) != value for key, value in selection.items())
                or results.get("code") != code or results.get("execution") != execution):
            raise ValueError("resume requires identical code, model settings, server, clock and selections")
        expected = {(model, level, seed) for model in (0, 1) for level in levels for seed in seeds}
        keys = [(run["model"], run["level"], run["seed"]) for run in results["runs"]]
        if set(keys) != expected or len(keys) != len(expected):
            raise ValueError("resume checkpoint has missing or duplicate runs")
        for run in results["runs"]:
            # Checkpoints are trusted local data, but cannot escape their directory.
            if Path(run["trace"]).name != run["trace"]:
                raise ValueError("invalid checkpoint trace path")
            if run["status"] == "complete":
                if not (output / run["trace"]).is_file():
                    raise ValueError("completed checkpoint trace is missing")
                continue
            if run["status"] != "pending" or (output / run["trace"]).exists():
                previous = {key: value for key, value in run.items() if key != "attempts"}
                attempts = run.setdefault("attempts", [])
                attempts.append(previous)
                for key in ("world_id", "score", "diagnostics", "timing", "error", "cleanup_error", "seconds"):
                    run.pop(key, None)
                base = f"level-{run['level']}-seed-{seeds.index(run['seed']) + 1}-model-{'ab'[run['model']]}"
                run["trace"] = f"{base}-attempt-{len(attempts) + 1}.jsonl"
            run["status"] = "pending"
    else:
        output.mkdir(parents=True, exist_ok=False)
        results = {"schema_version": 1, "status": "running", "mode": "practice",
                   "created_at": datetime.now(timezone.utc).isoformat(), "code": code,
                   "execution": execution, **selection, "runs": []}
        for level in levels:
            for seed_index, seed in enumerate(seeds):
                for index in ((0, 1) if seed_index % 2 == 0 else (1, 0)):
                    trace = f"level-{level}-seed-{seed_index + 1}-model-{'ab'[index]}.jsonl"
                    results["runs"].append({"model": index, "level": level, "seed": seed,
                                            "trace": trace, "status": "pending"})
    pending = [run for run in results["runs"] if run["status"] != "complete"]
    results["status"] = "running"
    save_results(result_path, results)
    # Do not create competing worlds when another experiment holds the slots.
    if pending and callable(getattr(client, "worlds", None)):
        occupied = sum(not world["ended"] and world.get("kind", "practice") == "practice" for world in client.worlds())
        available = max(0, 8 - occupied)
        if not available:
            results["status"] = "failed"
            save_results(result_path, results)
            print("All eight practice slots are occupied; resume this suite when a slot is free.", file=sys.stderr)
            raise RuntimeError("all eight practice slots are occupied; existing worlds were left untouched")
        workers = min(workers, available)
    results["workers"] = workers
    try:
        if workers == 1:
            for run in pending:
                run["status"] = "running"
                save_results(result_path, results)
                try:
                    _play_run(client, models[run["model"]], run, output, code,
                              fast=fast, delete_on_error=delete_on_error)
                finally:
                    save_results(result_path, results)
        elif pending:
            context = multiprocessing.get_context("spawn")
            stop = context.Event()
            with ProcessPoolExecutor(max_workers=workers, mp_context=context,
                                     initializer=_start_worker,
                                     initargs=(execution["server"], getattr(client, "key", None),
                                               execution["compression"], stop, client_factory)) as pool:
                todo, active, failure = iter(pending), {}, None

                def submit_next():
                    run = next(todo, None)
                    if run is not None:
                        run["status"] = "running"
                        future = pool.submit(_worker_run, models[run["model"]].spec, dict(run), output,
                                             code, fast, delete_on_error)
                        active[future] = run

                for _ in range(min(workers, len(pending))):
                    submit_next()
                save_results(result_path, results)
                while active:
                    try:
                        finished, _ = wait(active, return_when=FIRST_COMPLETED)
                    except KeyboardInterrupt:
                        failure = KeyboardInterrupt()
                        stop.set()
                        continue
                    for future in finished:
                        run = active.pop(future)
                        try:
                            run.update(future.result())
                        except Exception:
                            run.update(status="failed", error="worker failed; inspect its trace")
                        if run["status"] != "complete" and failure is None:
                            failure = RuntimeError("practice worker failed; inspect checkpoint and trace")
                        save_results(result_path, results)
                    # On failure, finish already running worlds but start no more.
                    if failure is None:
                        for _ in finished:
                            submit_next()
                if failure is not None:
                    raise failure
    except (Exception, KeyboardInterrupt):
        results["status"] = "failed"
        save_results(result_path, results)
        raise
    results["status"] = "complete"
    save_results(result_path, results)
    markdown = render_markdown(results)
    if not (output / "leaderboard.md").exists():
        (output / "leaderboard.md").write_text(markdown, encoding="utf-8")
    return markdown


# Pure reporting for complete, paired comparisons.
def _report_cell(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(
        ">", "&gt;").replace("|", "&#124;").replace("\r", " ").replace("\n", " ")


def _report_euros(cents, signed=False):
    return f"€{cents / 100:+,.2f}" if signed else f"€{cents / 100:,.2f}"


def _report_table(headers, rows):
    return ["| " + " | ".join(map(_report_cell, headers)) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *("| " + " | ".join(map(_report_cell, row)) + " |" for row in rows), ""]


def _report_validate(results):
    if results.get("schema_version") != 1 or results.get("mode") != "practice" or results.get("status") != "complete":
        raise ValueError("leaderboards require a complete schema-version-1 practice comparison")
    models, levels, seeds = (results[key] for key in ("models", "levels", "seeds"))
    if len(models) != 2 or models[0]["name"] == models[1]["name"]:
        raise ValueError("results must describe two distinctly named models")
    if (not levels or not seeds or len(set(levels)) != len(levels) or len(set(seeds)) != len(seeds)
            or any(level not in range(1, 9) for level in levels)):
        raise ValueError("results must contain distinct levels (1–8) and seeds")
    expected = {(model, level, seed) for model in (0, 1) for level in levels for seed in seeds}
    actual = set()
    for run in results["runs"]:
        key = (run["model"], run["level"], run["seed"])
        if run["status"] != "complete" or key in actual or key not in expected:
            raise ValueError("results contain failed, duplicate or unexpected runs")
        actual.add(key)
        score = run["score"]
        for field in ("marginCents", "revenueCents", "wonOrders", "onTimeShare", "undeliveredShare"):
            value = score[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"invalid score field: {field}")
        if (not isinstance(score["ranked"], bool) or score["wonOrders"] < 0
                or any(not 0 <= score[field] <= 1 for field in ("onTimeShare", "undeliveredShare"))):
            raise ValueError("invalid qualification or delivery score")
    if actual != expected:
        raise ValueError("incomplete pairing: each model needs every level/seed combination")


def _report_average(runs, field):
    return mean(run["score"][field] for run in runs)


def _report_qualified(runs):
    return sum(run["score"]["ranked"] for run in runs)


def _report_winner(groups):
    """More qualified weeks first, then mean gross margin across all weeks."""
    if not any(_report_qualified(group) for group in groups):
        return None
    keys = [(_report_qualified(group), _report_average(group, "marginCents")) for group in groups]
    return None if keys[0] == keys[1] else int(keys[1] > keys[0])


def render_markdown(results):
    _report_validate(results)
    names = [model["name"] for model in results["models"]]
    levels, seeds, runs = results["levels"], results["seeds"], results["runs"]
    groups = [[run for run in runs if run["model"] == model] for model in (0, 1)]
    by_level = {level: [[run for run in group if run["level"] == level] for group in groups] for level in levels}
    label = lambda index: _report_cell(names[index])
    scope = "All levels (1–8)" if set(levels) == set(range(1, 9)) else "Selected levels: " + ", ".join(map(str, levels))
    lines = ["# Model comparison leaderboard", "", f"{scope}; {len(seeds)} paired seed(s) per level; {len(runs)} practice runs.",
             "", "Local comparison of ordinary practice worlds; this is not the official Spread leaderboard.", "",
             "Ranking rule: more qualified weeks wins; if equal, higher mean gross margin across **all** weeks wins. "
             "If neither model qualifies any week, neither is recommended. Exact ties remain ties. "
             "Qualification uses the simulator's `ranked` flag, not an average delivery rate.", "",
             "All averages below are per week, including unqualified weeks. Delivery shares are mean weekly shares, "
             "not pooled order rates. These are descriptive results on the selected seeds, not statistical proof.", "",
             "## Overall leaderboard", ""]
    best = _report_winner(groups)
    order = [best, 1 - best] if best is not None else [0, 1]
    rows = []
    for index in order:
        group = groups[index]
        rank = "—" if not any(_report_qualified(g) for g in groups) else 1 if best is None else order.index(index) + 1
        rows.append([rank, names[index], f"{_report_qualified(group)}/{len(group)}",
                     _report_euros(_report_average(group, "marginCents")), _report_euros(_report_average(group, "revenueCents")),
                     f"{_report_average(group, 'onTimeShare'):.1%}", f"{_report_average(group, 'undeliveredShare'):.1%}",
                     f"{_report_average(group, 'wonOrders'):.1f}"])
    lines += _report_table(["Rank", "Model", "Qualified weeks", "Mean margin", "Mean revenue", "Mean on-time", "Mean undelivered", "Mean won orders"], rows)
    if not any(_report_qualified(group) for group in groups):
        lines += ["Neither model qualified any week. Margin alone does not establish a usable winner.", ""]
    elif best is None:
        lines += ["Overall result: tie under the stated ranking rule.", ""]
    else:
        lines += [f"Overall leader on these weeks: **{label(best)}**.", ""]

    lines += ["## Leaderboard by level", ""]
    rows = []
    for level in levels:
        pair = by_level[level]
        lead = _report_winner(pair)
        for index, group in enumerate(pair):
            rank = "—" if not any(_report_qualified(g) for g in pair) else 1 if lead is None or lead == index else 2
            rows.append([level, rank, names[index], f"{_report_qualified(group)}/{len(group)}",
                         _report_euros(_report_average(group, "marginCents")), f"{_report_average(group, 'onTimeShare'):.1%}",
                         f"{_report_average(group, 'undeliveredShare'):.1%}", f"{_report_average(group, 'wonOrders'):.1f}"])
    lines += _report_table(["Level", "Rank", "Model", "Qualified weeks", "Mean margin", "Mean on-time", "Mean undelivered", "Mean won orders"], rows)

    lines += ["## Paired differences", "", f"All deltas are **B − A**: A = {label(0)}; B = {label(1)}. "
              "Positive margin/on-time is better; positive undelivered is worse. Shares use percentage points (pp).", "",
              "A paired win means only that model qualifies, or both qualify and it earns more margin. "
              "Weeks where neither qualifies are counted separately.", ""]
    rows = []
    for level in levels:
        pair = by_level[level]
        scores = [{run["seed"]: run["score"] for run in group} for group in pair]
        counts = Counter()
        for seed in seeds:
            a, b = (score[seed] for score in scores)
            if not a["ranked"] and not b["ranked"]:
                counts["neither"] += 1
            elif a["ranked"] != b["ranked"]:
                counts["b" if b["ranked"] else "a"] += 1
            else:
                counts["b" if b["marginCents"] > a["marginCents"] else "a" if a["marginCents"] > b["marginCents"] else "tie"] += 1
        delta = lambda field: _report_average(pair[1], field) - _report_average(pair[0], field)
        rows.append([level, _report_euros(delta("marginCents"), True), _report_euros(delta("revenueCents"), True),
                     f"{100 * delta('onTimeShare'):+.1f}", f"{100 * delta('undeliveredShare'):+.1f}",
                     f"{counts['a']} / {counts['b']} / {counts['tie']} / {counts['neither']}"])
    lines += _report_table(["Level", "Δ mean margin", "Δ mean revenue", "Δ on-time pp", "Δ undelivered pp", "A wins / B wins / ties / neither"], rows)

    lines += ["## Diagnostics", "", "Event counts include retries and individual legs; they are not counts of unique failed orders. "
              "Signed ledger amounts are totals across all sampled weeks (negative = net expense).", ""]
    counters = []
    for group in groups:
        summary = {key: Counter() for key in ("events", "rejections", "visit_failures", "ledger")}
        for run in group:
            for key in summary:
                summary[key].update(run["diagnostics"][key])
        counters.append(summary)
    rows = [[event, *[summary["events"][event] for summary in counters]] for event in (
        "order_lost", "deadline_close", "gig_dropped", "no_show", "visit_failed", "gig_expired")]
    rows.append(["rejected actions", *[sum(summary["rejections"].values()) for summary in counters]])
    lines += _report_table(["Event/action", *names], rows)
    for key, heading, currency in (("ledger", "Ledger category", True), ("visit_failures", "Failed-visit reason", False),
                                   ("rejections", "Rejected-action reason", False)):
        keys = sorted(set(counters[0][key]) | set(counters[1][key]))
        if keys:
            lines += _report_table([heading, *names], [[reason, *[_report_euros(c[key][reason]) if currency else c[key][reason]
                                                          for c in counters]] for reason in keys])

    lines += ["## Where to iterate next", ""]
    if 8 in by_level:
        lead = _report_winner(by_level[8])
        if not any(_report_qualified(group) for group in by_level[8]):
            lines.append("- Neither model qualifies at level 8. Prioritize capacity selection and delivery reliability before tuning margin.")
        elif lead is None:
            lines.append("- Level 8 is tied. Use additional held-out seeds to choose the final-level strategy.")
        else:
            lines.append(f"- Use **{label(lead)}** as the level 8 candidate under the stated rule; confirm on held-out weeks before adopting it.")
    else:
        lines.append("- Include level 8 before selecting a strategy for the final.")
    for index, group in enumerate(groups):
        weak = [str(level) for level in levels if _report_qualified(by_level[level][index]) < len(seeds)]
        if weak:
            lines.append(f"- **{label(index)}** misses qualification at level(s) {', '.join(weak)}. Inspect those traces for late/undelivered work and order-selection limits.")
        for key, action in (("rejections", "Fix the rejected action"), ("visit_failures", "Investigate pickup constraints")):
            if counters[index][key]:
                reason, count = counters[index][key].most_common(1)[0]
                lines.append(f"- **{label(index)}**: {action}: {_report_cell(reason)} ({count} occurrences).")
        expenses = [(amount, kind) for kind, amount in counters[index]["ledger"].items() if amount < 0]
        if expenses:
            amount, kind = min(expenses)
            lines.append(f"- **{label(index)}**: inspect {_report_cell(kind)}, the largest observed net expense ({_report_euros(amount)} total). Test one cost-control change while protecting qualification.")
    deltas = [(_report_average(pair[1], "marginCents") - _report_average(pair[0], "marginCents"), level) for level, pair in by_level.items()]
    delta, level = max(deltas, key=lambda item: abs(item[0]))
    if delta:
        pair = by_level[level]
        revenue_delta = _report_average(pair[1], "revenueCents") - _report_average(pair[0], "revenueCents")
        lines.append(f"- The largest mean margin gap is at level {level}: B − A = {_report_euros(delta, True)}, "
                     f"with revenue {_report_euros(revenue_delta, True)} and net costs {_report_euros(revenue_delta - delta, True)}. "
                     "Use paired traces to test whether quoting, order volume or fulfillment costs explain the gap.")
    else:
        lines.append("- No mean margin gap was observed. Check per-seed outcomes and expand seed coverage before concluding the strategies are equivalent.")
    lines += ["- Change one policy at a time, rerun the same seeds, then validate on a separate 10–20-seed set. Averages can hide individual weeks that fail qualification.", "",
              "## Reproduction", "", f"Created: {_report_cell(results['created_at'])}. Commit: {_report_cell(results['code']['commit'])}; "
              f"working tree dirty: {results['code']['dirty']}.", "", "Seeds: " + ", ".join(_report_cell(seed) for seed in seeds) + ".", "",
              "Model configurations (trusted local factories):", "", "```json",
              json.dumps(results["models"], ensure_ascii=False, indent=2).replace("`", "\\u0060"), "```", "",
              "`results.json` contains every final score, world ID, diagnostic summary and trace filename. "
              "Trace paths are relative to the results directory. Failed/incomplete suites cannot produce a leaderboard.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run two models on the same seeds and levels")
    run.add_argument("--model-a", type=Path, default=Path("models/fixed.json"))
    run.add_argument("--model-b", type=Path, default=Path("models/starter.json"))
    run.add_argument("--levels", type=int, choices=range(1, 9), nargs="+", default=list(range(1, 9)))
    run.add_argument("--seeds", nargs="+", default=[f"cheap-drive-eval-{i}" for i in range(1, 11)])
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run.add_argument("--output", type=Path, default=Path("runs") / f"comparison-{timestamp}")
    run.add_argument("--delete-on-error", action="store_true", help="delete this invocation's failed practice world; default preserves it")
    run.add_argument("--workers", type=int, choices=range(1, 9), default=1,
                     help="parallel official worlds, reduced to currently free team slots (default 1)")
    run.add_argument("--fast", action="store_true", help="coalesce declared bookkeeping wakes; skip daily scores and end reveal/roster")
    run.add_argument("--resume", action="store_true", help="reuse completed weeks in --output; require identical code and configuration")
    run.add_argument("--no-compression", action="store_true", help="disable gzip for a transport benchmark")
    report = commands.add_parser("report", help="regenerate Markdown from completed results without a key")
    report.add_argument("results", type=Path)
    report.add_argument("--output", type=Path, help="fresh Markdown file (otherwise stdout only)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)
    try:
        if args.command == "report":
            markdown = render_markdown(json.loads(args.results.read_text(encoding="utf-8")))
            if args.output:
                with args.output.open("x", encoding="utf-8") as stream:
                    stream.write(markdown)
        else:
            models = [load_model(args.model_a), load_model(args.model_b)]
            if not os.environ.get("SPREAD_KEY"):
                parser.error("set SPREAD_KEY to your team key to run actual practice comparisons")
            client = Client(url=os.environ.get("SPREAD_URL") or "https://spread.bahnexpress.com", compression=not args.no_compression)
            markdown = run_comparison(client, models, args.levels, args.seeds, args.output,
                                      delete_on_error=args.delete_on_error, workers=args.workers,
                                      fast=args.fast, resume=args.resume)
            print(f"Saved report, results and traces to {args.output}", file=sys.stderr)
        print(markdown, end="")
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print(f"Comparison stopped: {'interrupted' if isinstance(error, KeyboardInterrupt) else 'operation failed; inspect local results'}", file=sys.stderr)
        return 130 if isinstance(error, KeyboardInterrupt) else 1


if __name__ == "__main__":
    raise SystemExit(main())
