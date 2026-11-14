"""Play ranking runs with a model, so the team appears in the public practice rankings.

    python scripts/board.py models/beta.json            # the next ranking run at level 8
    python scripts/board.py models/beta.json --runs 5 --fast   # the round, one after another

A ranking run is public and final: it cannot be copied, revealed or taken back,
and a run that is deleted or stops still plays to its end and counts. A round
has five worlds per level; a team is ranked only when all five meet the 90%
delivery minimum. Play a model here only after it qualifies on our own seeds.
The server permits only one unfinished ranking run per level; do not launch
parallel copies. --runs completes each world before creating the next one.
Traces go to runs/board/ (git-ignored).
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import gzip
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from spread import SpreadError
    from performance import PracticeClient as Client
    from compare import MetricsJournal, load_model
    from dispatch import play_model
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("model", type=Path)
    parser.add_argument("--level", type=int, choices=range(1, 9), default=8)
    parser.add_argument("--runs", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--fast", action="store_true", help="coalesce passive wakes and skip optional diagnostics")
    args = parser.parse_args()
    model = load_model(args.model)
    if not os.environ.get("SPREAD_KEY"):
        parser.error("set SPREAD_KEY")
    client = Client(url=os.environ.get("SPREAD_URL") or "https://spread.bahnexpress.com")
    out = ROOT / "runs" / "board"
    out.mkdir(parents=True, exist_ok=True)
    for _ in range(args.runs):
        try:
            world = client.create(level=args.level, board=True)
        except SpreadError as error:  # five runs played: wait for the next round
            sys.exit(f"No ranking run created: {error}")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        with gzip.open(out / f"{stamp}-level{args.level}-{world.id}.jsonl.gz", "wt", encoding="utf-8") as stream:
            journal = MetricsJournal(stream)
            journal.record("run", worldId=world.id, mode="board", level=args.level, model=model.spec, fast=args.fast)
            print(f"Started ranking world {world.id}", flush=True)
            with redirect_stdout(sys.stderr):
                score = play_model(world, args.level, journal, model.factory, fast=args.fast)
        print(f"{world.id}: margin {score['marginCents'] / 100:,.2f} on-time {100 * score['onTimeShare']:.1f}% "
              f"won {score['wonOrders']} ranked {score['ranked']}", flush=True)


if __name__ == "__main__":
    main()
