"""A fixed-price practice dispatcher built on the official Spread starter."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import logging
import os
from pathlib import Path
import sys
from typing import Callable

from capture import CapturedWorld, Journal

from spread import Client, SpreadError, World
from spread.starter import DAY, WAKE_ON, WEEKDAYS, Desk, report
from spread.types import Action, ActionResult, DeskEvent, DeskEventKind, FeeStep, Order, PriceRequest, Score

LOG = logging.getLogger("cheap-drive")
WAKE_EVENTS: list[DeskEventKind] = list(dict.fromkeys([
    *WAKE_ON, "order_lost", "gig_booked", "gig_dropped", "no_show", "driver_late", "forecast", "release", "delivered",
]))


def euro_cents(value: str) -> int:
    """Parse exact positive euro amounts without silently rounding a bid."""
    try:
        cents = Decimal(value) * 100
        if not cents.is_finite() or cents <= 0 or cents != cents.to_integral_value():
            raise ValueError
        if cents > 2**53 - 1:
            raise ValueError
        return int(cents)
    except (InvalidOperation, ValueError):
        raise argparse.ArgumentTypeError("use a positive euro amount with at most two decimal places") from None


@dataclass(frozen=True)
class FixedPrices:
    dealer_cents: int = 10_000
    driver_cents: int = 15_000


class JournalDesk(Desk):
    """The official starter with the same trace instrumentation as our models."""

    def __init__(self, world: World, level: int, now: int, journal: Journal):
        super().__init__(world, level, now)
        self.journal = journal

    def handle(self, event: DeskEvent) -> None:
        if not isinstance(self.world, CapturedWorld):
            self.journal.record("event", event=event)
        if event["kind"] not in ("gig_viewed", "ledger"):
            request = event.get("request", {})
            order = event.get("order", {})
            identity = event.get("requestId", event.get("orderId", request.get("id", order.get("id", event.get("gigId", "")))))
            LOG.info("minute=%s event=%s %s", event["at"], event["kind"], identity)
        super().handle(event)

    def read_results(self, actions: list[Action], results: list[ActionResult]) -> None:
        if not isinstance(self.world, CapturedWorld):
            for action, result in zip(actions, results):
                self.journal.record("action_result", at=self.now, action=action, result=result)
        if len(actions) != len(results):
            raise RuntimeError("API returned a different number of action results")
        for action, result in zip(actions, results):
            if not result["ok"]:
                LOG.warning("minute=%s action=%s rejected; inspect the local journal", self.now, action["type"])
            elif action["type"] == "quote":
                LOG.info("minute=%s QUOTE %s %s", self.now, action["requestId"], action["prices"])
            elif action["type"] == "post":
                LOG.info("minute=%s POST %s fee=%s cents", self.now, result["id"], action["schedule"][0]["feeCents"])
        super().read_results(actions, results)


class FixedDesk(JournalDesk):
    """Keep the starter's delivery handling and replace its pricing decisions."""

    def __init__(self, world: World, level: int, now: int, prices: FixedPrices, journal: Journal):
        super().__init__(world, level, now, journal)
        self.prices = prices

    def quote(self, request: PriceRequest) -> None:
        self.requests[request["id"]] = request
        self.outbox.append({"type": "quote", "requestId": request["id"],
                            "prices": {option["kind"]: self.prices.dealer_cents for option in request["options"]}})

    def fees_for(self, order: Order, cars: int) -> list[FeeStep]:
        # One fixed fee per car: a two-car trade-in pays twice the configured amount.
        return [{"at": self.now, "feeCents": self.prices.driver_cents * cars}]

    def raise_fees(self, order_id: str) -> None:
        # Keep even urgent work at the same fee so this stays a constant-price baseline.
        self.urgent.add(order_id)
        LOG.warning("minute=%s order=%s deadline warning; fixed driver fee stays unchanged", self.now, order_id)


DeskFactory = Callable[[World, int, int, Journal], Desk]


def play_model(world: World, level: int, journal: Journal, factory: DeskFactory) -> Score:
    """Run any desk on the same practice clock and wake events."""
    world = CapturedWorld(world, journal)
    snapshot = world.capture("snapshot", world.world.snapshot, "initial")
    world.optional("map", lambda: world.world.client.map(), "initial")
    world.optional("roster", lambda: world.world.roster(), "initial")
    desk = factory(world, level, snapshot["now"], journal)
    while desk.now < snapshot["endsAt"]:
        day = desk.now // DAY
        actions, desk.outbox = desk.outbox, []
        step = world.advance(until=WAKE_EVENTS, max=min(snapshot["endsAt"], (day + 1) * DAY), actions=actions)
        desk.read_results(actions, step["results"])
        desk.now = step["now"]
        for event in step["events"]:
            desk.handle(event)
        if desk.now // DAY > day:
            score = world.world.score()
            report(WEEKDAYS[day % 7], score)
            journal.record("daily_score", at=desk.now, score=score)
    score = world.world.score()
    journal.record("score", at=desk.now, score=score)
    world.optional("snapshot", world.world.snapshot, "end")
    world.optional("roster", lambda: world.world.roster(), "end")
    world.optional("reveal", lambda: world.world.reveal(), "end")
    journal.record("run_end", at=desk.now, endsAt=snapshot["endsAt"])
    return score


def play_practice(world: World, level: int, prices: FixedPrices, journal: Journal) -> Score:
    return play_model(world, level, journal,
                      lambda world, level, now, journal: FixedDesk(world, level, now, prices, journal))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="run a scripted offline example, not a simulation")
    parser.add_argument("--level", type=int, choices=range(1, 9), default=4, help="practice level (default 4: quotes compete)")
    parser.add_argument("--seed", default="cheap-drive-1", help="repeatable practice seed")
    parser.add_argument("--dealer-price", type=euro_cents, default=10_000, metavar="EUROS", help="fixed quote per order/option (default 100)")
    parser.add_argument("--driver-fee", type=euro_cents, default=15_000, metavar="EUROS", help="fixed fee per car (default 150)")
    parser.add_argument("--log", type=Path, help="JSONL trace path (default runs/<time>.jsonl)")
    parser.add_argument("--delete-on-error", action="store_true", help="explicitly delete this invocation's failed practice world; default preserves it")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    prices = FixedPrices(args.dealer_price, args.driver_fee)
    world = None
    try:
        if args.demo:
            from demo import DemoWorld
            print("OFFLINE SCRIPTED DEMO — synthetic events, not Spread performance.", flush=True)
        else:
            if not os.environ.get("SPREAD_KEY"):
                parser.error("set SPREAD_KEY to your team key, or use --demo")
            # Client otherwise defaults to localhost; our default is the challenge server.
            client = Client(url=os.environ.get("SPREAD_URL") or "https://spread.bahnexpress.com")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        log_path = args.log or Path("runs") / f"{timestamp}.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("x", encoding="utf-8") as output:
            journal = Journal(output)
            world = DemoWorld() if args.demo else client.create(level=args.level, seed=args.seed)
            journal.record("run", worldId=world.id, mode="demo" if args.demo else "practice",
                           level=args.level, seed=args.seed, dealerCents=prices.dealer_cents,
                           driverCentsPerCar=prices.driver_cents)
            print(f"World: {world.id}; trace: {log_path}", flush=True)
            score = play_practice(world, args.level, prices, journal)
            report("End", score)
            print("Ranked." if score["ranked"] else "Not ranked. This is a fixed-price plumbing baseline.", flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        # Only ordinary practice worlds created by this process: never a ranking/final world.
        if world is not None and not args.demo and args.delete_on_error:
            try:
                world.delete()
                LOG.warning("Stopped; removed practice world %s to free its slot.", world.id)
            except SpreadError:
                LOG.warning("Could not remove practice world %s; it may still hold a practice slot.", world.id)
        if world is not None and not args.demo and not args.delete_on_error:
            LOG.warning("Stopped; practice world preserved for debugging and may hold an unfinished slot.")
        LOG.error("Stopped: %s; inspect the local journal", "interrupted" if isinstance(error, KeyboardInterrupt) else "operation failed")
        return 130 if isinstance(error, KeyboardInterrupt) else 1


if __name__ == "__main__":
    raise SystemExit(main())
