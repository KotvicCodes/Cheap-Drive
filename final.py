"""Play the live final (or a test final) with one of our models, from the event stream.

    python final.py models/gamma.json                 # wait for the final, then play it
    python final.py models/gamma.json --rehearse SEED  # dress rehearsal on a paced practice world

The final clock moves by itself: a quote has a few real seconds. This runner
uses the same desks as practice (dispatch.play_model), fed from the WebSocket
stream instead of `advance`. On start, and after the server becomes
unreachable, the desk is rebuilt from the server's snapshot and event history
(the starter's `rejoin`), so a restart of this process is safe: run the same
command again. Ctrl-C stops our system only; the final world keeps running.

`--rehearse` creates an ordinary level-8 practice world and moves its clock in
real time from a second connection, so the stream, live clock, pair timers,
rate limits and latency are exercised against the official server. Practice
worlds pause between advances; a rehearsal therefore only approximates the
final's pace (--minutes-per-second).

Traces go to runs/final/ (git-ignored) as gzip JSONL in the practice format.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import gzip
import logging
import os
from pathlib import Path
import sys
import threading
import time

from capture import CapturedWorld
from spread import SpreadError
from spread.client import Unreachable
from spread.starter import DAY, WEEKDAYS, report

LOG = logging.getLogger("cheap-drive.final")
ROOT = Path(__file__).resolve().parent


class LiveWorld(CapturedWorld):
    """CapturedWorld for a world whose clock moves by itself: there is no advance."""

    def advance(self, **_):
        raise RuntimeError("a live world has no advance; the final clock moves by itself")


def full_history(world):
    """Every event so far, oldest first, without repeats."""
    history, last = [], -1
    while True:
        batch = [event for event in world.events(after=last) if event["seq"] > last]
        if not batch:
            return history
        history += batch
        last = batch[-1]["seq"]


def play_live(world, level, journal, factory, *, clock, stats=None):
    """Rebuild a desk from the server, then answer streamed events until the week ends.

    `clock()` returns the world's current minute (client.final()["now"] in the final).
    Returns the score, or raises Unreachable for the caller to rebuild and resume.
    """
    stats = stats if stats is not None else {}
    live = LiveWorld(world, journal)
    history = full_history(world)
    snapshot = live.capture("snapshot", world.snapshot, "rejoin")
    live.initial_snapshot = snapshot
    live.initial_map = live.optional("map", lambda: world.client.map(), "rejoin")
    live.initial_roster = live.optional("roster", lambda: world.roster(), "rejoin")
    ends_at = snapshot["endsAt"]
    if snapshot["now"] >= ends_at:
        return world.score()
    journal.record("rejoin", at=snapshot["now"], historyEvents=len(history),
                   lastSeq=history[-1]["seq"] if history else -1)
    for event in history:
        journal.record("history_event", event=event)
    desk = factory(live, level, snapshot["now"], journal)
    desk.rejoin(snapshot, history)
    desk.send()
    last_seq = history[-1]["seq"] if history else -1
    stats.setdefault("events", 0)
    stats.setdefault("slow", 0)
    stats.setdefault("max_seconds", 0.0)
    for event in world.stream(after=last_seq, idle=1.0):
        started = time.perf_counter()
        day = desk.now // DAY
        if event is None:
            desk.now = max(desk.now, clock())
        else:
            if event["seq"] <= last_seq:  # replay after a reconnect
                continue
            last_seq = event["seq"]
            journal.record("event", event=event)
            desk.now = max(desk.now, event["at"])
            live.now = desk.now
            desk.handle(event)
            stats["events"] += 1
        live.now = desk.now
        desk.send()  # reading the outbox also runs the pair timers at desk.now
        if event is not None:
            took = time.perf_counter() - started
            stats["max_seconds"] = max(stats["max_seconds"], took)
            if took > 1.0:
                stats["slow"] += 1
                LOG.warning("minute=%s %s took %.2fs to answer", desk.now, event["kind"], took)
        if desk.now // DAY > day:
            score = world.score()
            report(WEEKDAYS[day % 7], score)
            journal.record("daily_score", at=desk.now, score=score)
        if desk.now >= ends_at:
            break
    score = world.score()
    journal.record("score", at=desk.now, score=score)
    live.optional("snapshot", world.snapshot, "end")
    journal.record("run_end", at=desk.now, endsAt=ends_at)
    return score


def play_until_done(world, level, journal, factory, clock, *, retry_seconds=3):
    """The final keeps running while we are away: rebuild and resume after any outage."""
    stats = {}
    while True:
        try:
            return play_live(world, level, journal, factory, clock=clock, stats=stats), stats
        except Unreachable as error:
            journal.record("unreachable", at=None)
            print(f"spread: {error}. Rebuilding from the server in {retry_seconds} s.", file=sys.stderr, flush=True)
            time.sleep(retry_seconds)


def wait_for_final(client):
    """The final (or test final) that is set or running. Organisers set a test final 15 minutes
    before it starts and the final 30 minutes before."""
    said = False
    while True:
        try:
            final = client.final()
            world = client.world(final["worldId"])
            snapshot = world.snapshot()
            if snapshot["now"] < snapshot["endsAt"]:
                return world, final
        except Unreachable as error:
            print(f"spread: {error}; retrying.", file=sys.stderr, flush=True)
        except SpreadError as error:
            if error.status != 404:
                raise
        if not said:
            print("No live final yet; waiting (checks every 5 s).", flush=True)
            said = True
        time.sleep(5)


class Pacer(threading.Thread):
    """Moves a practice world's clock in real time from its own connection (rehearsal only)."""

    def __init__(self, world, minutes_per_second, step=1):
        super().__init__(daemon=True)
        self.world, self.rate, self.step = world, minutes_per_second, step
        self.snapshot = world.snapshot()
        self.now, self.ends_at = self.snapshot["now"], self.snapshot["endsAt"]
        self.error = None

    def run(self):
        try:
            started, start_minute = time.monotonic(), self.now
            while self.now < self.ends_at:
                target = min(self.ends_at, start_minute + int((time.monotonic() - started) * self.rate))
                if target > self.now:
                    self.now = self.world.advance(to=target)["now"]
                else:
                    time.sleep(self.step / self.rate / 2)
        except BaseException as error:  # surface in the main thread's summary
            self.error = error


def main(argv=None):
    from compare import MetricsJournal, load_model
    from performance import PracticeClient as Client
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("model", type=Path, help="model JSON, e.g. models/gamma.json")
    parser.add_argument("--rehearse", metavar="SEED", help="play a paced level-8 practice world instead of the final")
    parser.add_argument("--minutes-per-second", type=float, default=5.0,
                        help="rehearsal pace in world minutes per real second (final averages ~5)")
    parser.add_argument("--quiet", action="store_true", help="send per-event desk logs to the trace only")
    args = parser.parse_args(argv)
    model = load_model(args.model)  # validate before touching the server
    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO, format="%(message)s", stream=sys.stderr)
    if not os.environ.get("SPREAD_KEY"):
        parser.error("set SPREAD_KEY")
    url = os.environ.get("SPREAD_URL") or "https://spread.bahnexpress.com"
    client = Client(url=url)
    out = ROOT / "runs" / "final"
    out.mkdir(parents=True, exist_ok=True)
    pacer = None
    if args.rehearse:
        world = client.create(level=8, seed=args.rehearse)
        mode, clock_info = "rehearsal", {"seed": args.rehearse, "minutesPerSecond": args.minutes_per_second}
        pacer = Pacer(Client(url=url).world(world.id), args.minutes_per_second)
        clock = lambda: pacer.now
        level = 8
    else:
        world, final = wait_for_final(client)
        mode, clock_info = "final", {"startsAt": final.get("startsAt")}
        clock = lambda: client.final()["now"]
        level = next((w.get("level", 8) for w in client.worlds() if w.get("worldId") == world.id), 8)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out / f"{stamp}-{mode}-{world.id}.jsonl.gz"
    print(f"{mode.title()} world {world.id} with {model.spec['name']}; trace {path}", flush=True)
    print("Ctrl-C stops our system only; run the same command again to rejoin.", flush=True)
    # Append so a restarted process never overwrites an earlier trace of the same world.
    with gzip.open(path, "at", encoding="utf-8") as stream:
        journal = MetricsJournal(stream)
        journal.record("run", worldId=world.id, mode=mode, level=level, model=model.spec, **clock_info)
        if pacer:
            pacer.start()
        try:
            with redirect_stdout(sys.stderr) if args.quiet else redirect_stdout(sys.stdout):
                score, stats = play_until_done(world, level, journal, model.factory, clock)
        except KeyboardInterrupt:
            sys.exit(f"Stopped. World {world.id} keeps running without us; rerun this command to rejoin.")
        journal.record("live_stats", **stats, timing=client.timing())
    if pacer and pacer.error:
        print(f"pacer stopped: {pacer.error!r}", file=sys.stderr)
    report("End", score)
    print(f"{world.id}: margin {score['marginCents'] / 100:,.2f} on-time {100 * score['onTimeShare']:.2f}% "
          f"won {score['wonOrders']} ranked {score['ranked']} | events {stats.get('events')} "
          f"slow>1s {stats.get('slow')} max {stats.get('max_seconds', 0):.2f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
