"""Play the live final (or a test final) with one of our models, from the event stream.

    python final.py models/gamma.json                 # wait for the final, then play it
    python final.py models/gamma.json --rehearse SEED  # dress rehearsal on a paced practice world

The final clock moves by itself: a quote has a few real seconds. This runner
uses the same desks as practice (dispatch.play_model), fed from the WebSocket
stream instead of `advance`. On start, and after the server becomes
unreachable, Gamma/Delta replay their model bookkeeping and reconcile the
server's snapshot, using a local checkpoint and quote receipts when available.
Run the same command again after a crash. Ctrl-C stops our system only; the
final world keeps running.

`--rehearse` creates (or resumes the same seed's unfinished) level-8 practice
world and moves its clock in
real time from a second connection, so the stream, live clock, pair timers,
rate limits and latency are exercised against the official server. Practice
worlds pause between advances; a rehearsal therefore only approximates the
final's pace (--minutes-per-second).

Traces, world-specific checkpoints and rehearsal manifests go to runs/final/
(git-ignored). Keep this directory when restarting in a new process.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import gzip
import hashlib
import json
import logging
import os
import queue
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

    capture_recovery = True

    def advance(self, **_):
        raise RuntimeError("a live world has no advance; the final clock moves by itself")


def full_history(world, *, through=None):
    """Every event through a snapshot minute, oldest first, without repeats.

    Read AFTER the snapshot so its causative events are included. Stop at the
    cut even if a busy live stream keeps producing new events during paging.
    The stream subsequently delivers everything above the returned sequence.
    """
    history, last = [], -1
    while True:
        batch = [event for event in world.events(after=last) if event["seq"] > last]
        if not batch:
            return history
        history += [event for event in batch if through is None or event["at"] <= through]
        if through is not None and batch[-1]["at"] > through:
            return history
        last = batch[-1]["seq"]


class BackgroundReads:
    """Optional reads use separate connections; only the consumer writes the journal.

    Reports observe the score after the requested boundary, not atomically at
    midnight. Clock failures retain the last minute; event times still advance it.
    """
    def __init__(self, clock, score, *, interval=1.0):
        self.clock, self.score, self.interval = clock, score, interval
        self.latest = 0
        self.stopped = threading.Event()
        self.requests, self.results = queue.Queue(), queue.Queue()
        self.threads = [threading.Thread(target=fn, daemon=True, name=name)
                        for fn, name in ((self._clock, "final-clock"), (self._scores, "final-scores"))]
        for thread in self.threads:
            thread.start()

    def _clock(self):
        while not self.stopped.is_set():
            try:
                self.latest = max(self.latest, self.clock())
            except Exception:
                pass  # the stream/action path owns outage recovery
            self.stopped.wait(self.interval)

    def _scores(self):
        while True:
            item = self.requests.get()
            if item is None:
                return
            day, at = item
            try:
                self.results.put((day, at, self.score()))
            except Exception:
                self.results.put((day, at, None))

    def request_score(self, day, at):
        self.requests.put((day, at))

    def drain(self, journal):
        while True:
            try:
                day, at, score = self.results.get_nowait()
            except queue.Empty:
                return
            if score is None:
                journal.record("daily_score_unavailable", at=at)
            else:
                report(WEEKDAYS[day % 7], score)
                journal.record("daily_score", at=at, score=score)

    def close(self):
        self.stopped.set()
        self.requests.put(None)
        # Never wait for the SDK's 20-second timeout or synchronous 429 retry.


def play_live(world, level, journal, factory, *, clock, stats=None, reads=None, checkpoint=None):
    """Rebuild a desk and answer the stream; optional reads never delay a quote."""
    stats = stats if stats is not None else {}
    live = LiveWorld(world, journal)
    snapshot = live.capture("snapshot", world.snapshot, "rejoin")
    history = full_history(world, through=snapshot["now"])
    live.initial_snapshot = snapshot
    live.initial_map = live.optional("map", lambda: world.client.map(), "rejoin")
    live.initial_roster = live.optional("roster", lambda: world.roster(), "rejoin")
    ends_at = snapshot["endsAt"]
    if snapshot["now"] >= ends_at:
        return world.score()
    journal.record("rejoin", at=snapshot["now"], historyEvents=len(history),
                   lastSeq=history[-1]["seq"] if history else -1)
    journal.record_history(history)
    live.recovery_checkpoint = checkpoint.load() if checkpoint else None
    live.recovery_quote_receipts = checkpoint.quote_receipts() if checkpoint else {}
    desk = factory(live, level, snapshot["now"], journal)
    desk.rejoin(snapshot, history)
    desk.send()
    last_seq = history[-1]["seq"] if history else -1
    checkpoint_at = time.monotonic()
    if checkpoint and hasattr(desk, "observe_history"):
        checkpoint.save(desk, last_seq)
    stats.setdefault("events", 0)
    stats.setdefault("slow", 0)
    stats.setdefault("max_seconds", 0.0)
    owned_reads = reads is None
    reads = reads or BackgroundReads(clock, world.score)
    try:
        for event in world.stream(after=last_seq, idle=1.0):
            started = time.perf_counter()
            day = desk.now // DAY
            if event is None:
                desk.now = max(desk.now, reads.latest)
            else:
                if event["seq"] <= last_seq:
                    continue
                last_seq = event["seq"]
                journal.record("event", event=event)
                desk.now = max(desk.now, event["at"])
                live.now = desk.now
                desk.handle(event)
                stats["events"] += 1
            live.now = desk.now
            desk.send()  # also runs pair timers, at the latest observed minute
            if checkpoint and hasattr(desk, "observe_history") and time.monotonic() - checkpoint_at >= 5:
                checkpoint.save(desk, last_seq)
                checkpoint_at = time.monotonic()
            if event is not None:
                took = time.perf_counter() - started
                stats["max_seconds"] = max(stats["max_seconds"], took)
                if took > 1.0:
                    stats["slow"] += 1
                    LOG.warning("minute=%s %s took %.2fs to answer", desk.now, event["kind"], took)
            if desk.now // DAY > day:
                reads.request_score(day, desk.now)
            reads.drain(journal)
            if desk.now >= ends_at:
                break
        score = world.score()  # terminal read: no quote windows remain
        journal.record("score", at=desk.now, score=score)
        live.optional("snapshot", world.snapshot, "end")
        journal.record("run_end", at=desk.now, endsAt=ends_at)
        return score
    finally:
        if owned_reads:
            reads.close()


def play_until_done(world, level, journal, factory, clock, *, retry_seconds=3,
                    score_reader=None, checkpoint=None):
    """The final keeps running while we are away: rebuild and resume after any outage."""
    stats = {}
    reads = BackgroundReads(clock, score_reader or world.score)
    try:
        while True:
            try:
                return play_live(world, level, journal, factory, clock=clock, stats=stats,
                                 reads=reads, checkpoint=checkpoint), stats
            except Unreachable as error:
                journal.record("unreachable", at=None)
                print(f"spread: {error}. Rebuilding from the server in {retry_seconds} s.", file=sys.stderr, flush=True)
                time.sleep(retry_seconds)
    finally:
        reads.close()


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


def rehearsal_world(client, out, seed, model_spec):
    """Repeat --rehearse SEED to resume that model's unfinished rehearsal.

    The practice clock pauses when this process is killed. A completed or
    deleted rehearsal starts a fresh world; an outage must never create one.
    """
    identity = hashlib.sha256(json.dumps([seed, model_spec], sort_keys=True).encode()).hexdigest()[:16]
    path = out / f"rehearsal-{identity}.json"
    try:
        saved = json.loads(path.read_text())
    except (OSError, ValueError):
        saved = None
    if saved and saved.get("seed") == seed and saved.get("model") == model_spec:
        world = client.world(saved["worldId"])
        try:
            snapshot = world.snapshot()
            if snapshot["now"] < snapshot["endsAt"]:
                return world
        except SpreadError as error:
            if error.status != 404:
                raise
    world = client.create(level=8, seed=seed)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as stream:
        json.dump(dict(worldId=world.id, seed=seed, model=model_spec), stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return world


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
    clock_client, score_client = Client(url=url), Client(url=url)
    if args.rehearse:
        world = rehearsal_world(client, out, args.rehearse, model.spec)
        mode, clock_info = "rehearsal", {"seed": args.rehearse, "minutesPerSecond": args.minutes_per_second}
        pacer = Pacer(Client(url=url).world(world.id), args.minutes_per_second)
        clock = lambda: pacer.now
        level = 8
    else:
        world, final = wait_for_final(client)
        mode, clock_info = "final", {"startsAt": final.get("startsAt")}
        clock = lambda: clock_client.final()["now"]
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
                from recovery import CheckpointStore
                checkpoint = CheckpointStore(out / f"{world.id}-checkpoint.json", world.id, model.spec)
                try:
                    score, stats = play_until_done(world, level, journal, model.factory, clock,
                                                  score_reader=score_client.world(world.id).score,
                                                  checkpoint=checkpoint)
                finally:
                    checkpoint.close()
        except KeyboardInterrupt:
            sys.exit(f"Stopped. World {world.id} keeps running without us; rerun this command to rejoin.")
        journal.record("live_stats", **stats, timing=client.timing(),
                       clockTiming=clock_client.timing(), scoreTiming=score_client.timing())
    if pacer and pacer.error:
        print(f"pacer stopped: {pacer.error!r}", file=sys.stderr)
    report("End", score)
    print(f"{world.id}: margin {score['marginCents'] / 100:,.2f} on-time {100 * score['onTimeShare']:.2f}% "
          f"won {score['wonOrders']} ranked {score['ranked']} | events {stats.get('events')} "
          f"slow>1s {stats.get('slow')} max {stats.get('max_seconds', 0):.2f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
