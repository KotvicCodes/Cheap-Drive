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
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import signal
import time
import hashlib

from performance import PracticeClient as Client

from dispatch import DeskFactory, FixedDesk, FixedPrices, Journal, JournalDesk, euro_cents, play_model
from leaderboard import render_markdown
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
    def __init__(self, output):
        super().__init__(output)
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
