from contextlib import redirect_stdout
import gzip
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import board
from spread import SpreadError


class BoardTests(unittest.TestCase):
    def run_board(self, arguments, client, play):
        model = SimpleNamespace(spec={"name": "fixture"}, factory=object())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(board, "ROOT", root), \
                    patch("sys.argv", ["board.py", "model.json", *arguments]), \
                    patch.dict("os.environ", {"SPREAD_KEY": "fixture-only"}), \
                    patch("performance.PracticeClient", return_value=client), \
                    patch("compare.load_model", return_value=model), \
                    patch("dispatch.play_model", side_effect=play), \
                    redirect_stdout(io.StringIO()):
                board.main()
            traces = []
            for path in (root / "runs" / "board").glob("*.jsonl.gz"):
                with gzip.open(path, "rt") as stream:
                    traces.extend(json.loads(line) for line in stream)
            return traces

    def test_fast_runs_finish_before_next_world_is_created(self):
        client, order = Mock(), []

        def create(**kwargs):
            self.assertEqual(kwargs, {"level": 8, "board": True})
            identity = f"world-{len(client.create.call_args_list)}"
            order.append(("create", identity))
            return SimpleNamespace(id=identity)

        def play(world, level, journal, factory, *, fast):
            self.assertTrue(fast)
            order.append(("finish", world.id))
            return {"marginCents": 100, "onTimeShare": 1, "wonOrders": 1, "ranked": True}

        client.create.side_effect = create
        traces = self.run_board(["--runs", "2", "--fast"], client, play)
        self.assertEqual(order, [("create", "world-1"), ("finish", "world-1"),
                                 ("create", "world-2"), ("finish", "world-2")])
        self.assertEqual([row["mode"] for row in traces], ["board", "board"])

    def test_creation_conflict_stops_without_retries_or_deletion(self):
        client, play = Mock(), Mock()
        client.create.side_effect = SpreadError(409, "ranking run has not ended")
        with self.assertRaisesRegex(SystemExit, "No ranking run created"):
            self.run_board(["--runs", "5"], client, play)
        self.assertEqual(client.create.call_count, 1)
        play.assert_not_called()
        client.world.assert_not_called()


if __name__ == "__main__":
    unittest.main()
