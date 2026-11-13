"""Compare two dispatch models on paired practice weeks and emit Markdown."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib
import inspect
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

from spread import Client

from dispatch import DeskFactory, FixedDesk, FixedPrices, Journal, JournalDesk, euro_cents, play_model
from leaderboard import render_markdown


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
        module, attribute = name.split(":", 1)
        factory = getattr(importlib.import_module(module), attribute)
    else:
        raise ValueError(f"{path}: factory must be fixed, starter, or module:callable")
    inspect.signature(factory).bind(None, None, None, None, **settings)

    def make_desk(world, level, now, journal):
        desk = factory(world, level, now, journal, **settings)
        if not isinstance(desk, JournalDesk):
            raise TypeError("model factories must return a JournalDesk subclass so diagnostics are captured")
        return desk

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
        if kind == "event":
            event = fields["event"]
            self.events[event["kind"]] += 1
            if event["kind"] == "visit_failed":
                self.visit_failures[event["reason"]] += 1
            if event["kind"] == "ledger":
                line = event["line"]
                self.ledger[line["kind"]] += line["cents"]
        elif kind == "action_result" and not fields["result"]["ok"]:
            self.rejections[fields["result"]["reason"]] += 1

    def metrics(self):
        return {"events": dict(self.events), "rejections": dict(self.rejections),
                "visit_failures": dict(self.visit_failures), "ledger": dict(self.ledger)}


def code_revision():
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
        return {"commit": revision, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": "unknown", "dirty": None}


def save_results(path, results):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_comparison(client, models, levels, seeds, output: Path):
    """Sequential paired runs; never create a ranking/final world or overwrite a run."""
    if len(models) != 2 or models[0].spec["name"] == models[1].spec["name"]:
        raise ValueError("choose two models with distinct names")
    if not levels or len(set(levels)) != len(levels) or any(level not in range(1, 9) for level in levels):
        raise ValueError("levels must be distinct numbers from 1 to 8")
    if not seeds or len(set(seeds)) != len(seeds) or any(not seed.strip() for seed in seeds):
        raise ValueError("seeds must be distinct nonempty strings")
    output.mkdir(parents=True, exist_ok=False)
    results = {"schema_version": 1, "status": "running", "mode": "practice",
               "created_at": datetime.now(timezone.utc).isoformat(), "code": code_revision(),
               "models": [model.spec for model in models], "levels": levels, "seeds": seeds, "runs": []}
    result_path = output / "results.json"
    save_results(result_path, results)
    for level in levels:
        for seed_index, seed in enumerate(seeds):
            # Alternate order to avoid always running one model first.
            for index in ((0, 1) if seed_index % 2 == 0 else (1, 0)):
                model = models[index]
                trace = f"level-{level}-seed-{seed_index + 1}-model-{'ab'[index]}.jsonl"
                run = {"model": index, "level": level, "seed": seed, "trace": trace, "status": "running"}
                results["runs"].append(run)
                world = None
                try:
                    print(f"Level {level}, seed {seed}, model {model.spec['name']}", file=sys.stderr, flush=True)
                    with (output / trace).open("x", encoding="utf-8") as stream:
                        journal = MetricsJournal(stream)
                        world = client.create(level=level, seed=seed, board=False)
                        run["world_id"] = world.id
                        journal.record("run", worldId=world.id, mode="practice", level=level,
                                       seed=seed, model=model.spec, code=results["code"])
                        with redirect_stdout(sys.stderr):
                            run["score"] = play_model(world, level, journal, model.factory)
                        run["diagnostics"] = journal.metrics()
                    run["status"] = "complete"
                except (Exception, KeyboardInterrupt) as error:
                    run.update(status="failed", error="interrupted" if isinstance(error, KeyboardInterrupt) else str(error))
                    results["status"] = "failed"
                    if world is not None:
                        try:
                            world.delete()
                        except Exception as cleanup_error:
                            run["cleanup_error"] = str(cleanup_error)
                            print(f"Could not delete practice world {world.id}; it may hold a slot.", file=sys.stderr)
                    save_results(result_path, results)
                    raise
                save_results(result_path, results)
    results["status"] = "complete"
    save_results(result_path, results)
    markdown = render_markdown(results)
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
            client = Client(url=os.environ.get("SPREAD_URL") or "https://spread.bahnexpress.com")
            markdown = run_comparison(client, models, args.levels, args.seeds, args.output)
            print(f"Saved report, results and traces to {args.output}", file=sys.stderr)
        print(markdown, end="")
        return 0
    except (Exception, KeyboardInterrupt) as error:
        print(f"Comparison stopped: {'interrupted' if isinstance(error, KeyboardInterrupt) else error}", file=sys.stderr)
        return 130 if isinstance(error, KeyboardInterrupt) else 1


if __name__ == "__main__":
    raise SystemExit(main())
