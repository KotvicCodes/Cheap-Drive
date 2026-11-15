from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from compare import MetricsJournal, load_model, main, run_comparison
from demo import DemoWorld
from dispatch import JournalDesk
from compare import render_markdown


ROOT = Path(__file__).resolve().parents[1]


class PracticeWorld(DemoWorld):
    def __init__(self, identity):
        super().__init__()
        self.id = identity
        self.deleted = False

    def delete(self):
        self.deleted = True


class PracticeClient:
    def __init__(self):
        self.calls = []
        self.worlds = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        world = PracticeWorld(f"world-{len(self.calls)}")
        self.worlds.append(world)
        return world


class FailingClient(PracticeClient):
    def create(self, **kwargs):
        raise RuntimeError("private fixture error")


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        cache = ROOT / ".cache" / "tmp"
        cache.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=cache)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.output = self.directory / "comparison"
        self.models = [load_model(ROOT / "models" / name) for name in ("fixed.json", "starter.json")]
        self.client = PracticeClient()
        self.addCleanup(patch.stopall)
        patch("compare.code_revision", return_value={"commit": "test-revision", "dirty": False}).start()
        self.stdout, self.stderr = io.StringIO(), io.StringIO()

    def run_suite(self, levels, seeds, **kwargs):
        with redirect_stdout(self.stdout), redirect_stderr(self.stderr):
            return run_comparison(self.client, self.models, levels, seeds, self.output, **kwargs)

    def test_all_levels_pair_identical_seeds_and_preserve_scores_and_diagnostics(self):
        levels, seeds = list(range(1, 9)), ["seed-a", "../seed|b"]
        markdown = self.run_suite(levels, seeds)
        self.assertEqual(len(self.client.calls), 32)
        for level in levels:
            for seed in seeds:
                self.assertEqual(self.client.calls.count({"level": level, "seed": seed, "board": False}), 2)
        results = json.loads((self.output / "results.json").read_text())
        self.assertEqual(results["status"], "complete")
        self.assertEqual([run["model"] for run in results["runs"][:4]], [0, 1, 1, 0])
        self.assertEqual(len(list(self.output.glob("*.jsonl"))), 32)
        self.assertFalse(any(world.deleted for world in self.client.worlds))
        for run in results["runs"]:
            self.assertEqual(run["diagnostics"]["events"]["delivered"], 1)
            self.assertLess(run["diagnostics"]["ledger"]["driver_fee"], 0)
            trace = [json.loads(line) for line in (self.output / run["trace"]).read_text().splitlines()]
            self.assertEqual(trace[0]["code"]["commit"], "test-revision")
            self.assertEqual(next(row["score"] for row in reversed(trace) if row["type"] == "score"), run["score"])
        self.assertIn("All levels (1–8)", markdown)
        self.assertEqual((self.output / "leaderboard.md").read_text(), markdown)

    def test_failed_run_saves_partial_results_preserves_world_and_has_no_leaderboard(self):
        with patch("compare.play_model", side_effect=RuntimeError("broken policy")):
            with self.assertRaisesRegex(RuntimeError, "broken policy"):
                self.run_suite([8], ["seed"])
        self.assertFalse(self.client.worlds[0].deleted)
        results = json.loads((self.output / "results.json").read_text())
        self.assertEqual(results["status"], "failed")
        self.assertEqual(results["runs"][0]["error"], "operation failed")
        self.assertFalse((self.output / "leaderboard.md").exists())
        with self.assertRaisesRegex(ValueError, "complete"):
            render_markdown(results)

    def test_failed_world_cleanup_requires_explicit_opt_in(self):
        with patch("compare.play_model", side_effect=RuntimeError("private fixture error")):
            with self.assertRaises(RuntimeError):
                self.run_suite([8], ["seed"], delete_on_error=True)
        self.assertTrue(self.client.worlds[0].deleted)
        self.assertNotIn("private fixture error", (self.output / "results.json").read_text())

    def test_interrupt_and_cleanup_failure_preserve_world_identity(self):
        with patch("compare.play_model", side_effect=KeyboardInterrupt), patch.object(PracticeWorld, "delete", side_effect=RuntimeError("offline")):
            with self.assertRaises(KeyboardInterrupt):
                self.run_suite([8], ["seed"], delete_on_error=True)
        run = json.loads((self.output / "results.json").read_text())["runs"][0]
        self.assertEqual(run["error"], "interrupted")
        self.assertEqual(run["cleanup_error"], "cleanup failed")
        self.assertIn(run["world_id"], self.stderr.getvalue())

    def test_reject_invalid_or_duplicate_selection_before_creating_worlds(self):
        for levels, seeds in (([1, 1], ["x"]), ([0], ["x"]), ([], ["x"]), ([8], ["x", "x"]), ([8], []), ([8], [" "])):
            with self.subTest(levels=levels, seeds=seeds), self.assertRaises(ValueError):
                self.run_suite(levels, seeds)
        self.models[1].spec["name"] = self.models[0].spec["name"]
        with self.assertRaisesRegex(ValueError, "distinct names"):
            self.run_suite([8], ["x"])
        self.assertEqual(self.client.calls, [])
        self.assertFalse(self.output.exists())

    def test_existing_output_is_never_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / "results.json"
        sentinel.write_text("keep me")
        with self.assertRaises(FileExistsError):
            self.run_suite([8], ["seed"])
        self.assertEqual(sentinel.read_text(), "keep me")
        self.assertEqual(self.client.calls, [])

    def test_resume_reuses_complete_weeks_and_retains_failed_attempts(self):
        from dispatch import play_model
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("fixture failure")
            return play_model(*args, **kwargs)

        with patch("compare.play_model", side_effect=fail_second), self.assertRaises(RuntimeError):
            self.run_suite([8], ["seed"])
        before = json.loads((self.output / "results.json").read_text())
        complete_trace = self.output / before["runs"][0]["trace"]
        trace_bytes = complete_trace.read_bytes()
        self.run_suite([8], ["seed"], resume=True)
        after = json.loads((self.output / "results.json").read_text())
        self.assertEqual(len(self.client.calls), 3)
        self.assertEqual(trace_bytes, complete_trace.read_bytes())
        self.assertEqual(after["runs"][1]["attempts"][0]["world_id"], before["runs"][1]["world_id"])
        self.assertNotEqual(after["runs"][1]["trace"], before["runs"][1]["trace"])
        self.assertTrue((self.output / before["runs"][1]["trace"]).exists())
        self.run_suite([8], ["seed"], resume=True)
        self.assertEqual(len(self.client.calls), 3)

    def test_resume_rejects_changed_clock_model_code_and_missing_trace(self):
        self.run_suite([8], ["seed"])
        with self.assertRaisesRegex(ValueError, "identical"):
            self.run_suite([8], ["seed"], resume=True, fast=True)
        self.models[0].spec["settings"]["dealer_price"] = "999"
        with self.assertRaisesRegex(ValueError, "identical"):
            self.run_suite([8], ["seed"], resume=True)
        self.models[0] = load_model(ROOT / "models/fixed.json")
        with patch("compare.code_revision", return_value={"commit": "different", "dirty": False}):
            with self.assertRaisesRegex(ValueError, "identical"):
                self.run_suite([8], ["seed"], resume=True)
        next(self.output.glob("*.jsonl")).unlink()
        with self.assertRaisesRegex(ValueError, "trace is missing"):
            self.run_suite([8], ["seed"], resume=True)

    def test_spawned_workers_capture_all_paired_results(self):
        self.run_suite([8], ["one", "two"], workers=2, fast=True, client_factory=PracticeClient)
        results = json.loads((self.output / "results.json").read_text())
        self.assertEqual(results["status"], "complete")
        self.assertEqual(len(results["runs"]), 4)
        self.assertTrue(all(run["status"] == "complete" for run in results["runs"]))
        self.assertTrue(all(run["seconds"] >= 0 for run in results["runs"]))
        self.assertEqual(len(list(self.output.glob("*.jsonl"))), 4)

    def test_worker_failure_checkpoints_without_starting_queued_worlds(self):
        with self.assertRaisesRegex(RuntimeError, "worker failed"):
            self.run_suite([8], ["one", "two"], workers=2, client_factory=FailingClient)
        text = (self.output / "results.json").read_text()
        results = json.loads(text)
        self.assertEqual(results["status"], "failed")
        self.assertEqual([run["status"] for run in results["runs"]], ["failed", "failed", "pending", "pending"])
        self.assertNotIn("private fixture error", text)

    def test_occupied_slots_do_not_create_or_delete_worlds(self):
        from unittest.mock import Mock
        client = Mock()
        client.url, client.compression = "https://example.test", True
        client.worlds.return_value = [{"ended": False, "kind": "practice"}] * 8
        with self.assertRaisesRegex(RuntimeError, "slots are occupied"):
            run_comparison(client, self.models, [8], ["seed"], self.output, workers=8)
        client.create.assert_not_called()

    def test_workers_outside_team_limit_are_rejected(self):
        for workers in (0, 9, True, 1.5):
            with self.subTest(workers=workers), self.assertRaises(ValueError):
                self.run_suite([8], ["seed"], workers=workers)
        self.assertFalse(self.output.exists())

    def test_running_workers_receive_interrupt_and_checkpoint_before_return(self):
        from concurrent.futures import wait
        interrupted = False

        def interrupt_once(*args, **kwargs):
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                raise KeyboardInterrupt
            return wait(*args, **kwargs)

        with patch("compare.wait", side_effect=interrupt_once), self.assertRaises(KeyboardInterrupt):
            self.run_suite([8], ["one", "two"], workers=2, client_factory=PracticeClient)
        results = json.loads((self.output / "results.json").read_text())
        self.assertEqual(results["status"], "failed")
        self.assertEqual([run["status"] for run in results["runs"]], ["failed", "failed", "pending", "pending"])

    def test_concurrent_resume_controller_is_rejected_by_output_lock(self):
        from dispatch import play_model

        def attempt_concurrent_resume(*args, **kwargs):
            with self.assertRaisesRegex(ValueError, "another runner"):
                self.run_suite([8], ["seed"], resume=True)
            return play_model(*args, **kwargs)

        with patch("compare.play_model", side_effect=attempt_concurrent_resume):
            self.run_suite([8], ["seed"])

    def test_requested_workers_are_reduced_to_free_team_slots(self):
        class LimitedClient:
            def __init__(self):
                self.calls = []

            def worlds(self):
                return [{"kind": "practice", "ended": False}] * 7

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return PracticeWorld(f"limited-{len(self.calls)}")

        client = LimitedClient()
        with redirect_stdout(self.stdout), redirect_stderr(self.stderr):
            run_comparison(client, self.models, [8], ["seed"], self.output, workers=8)
        results = json.loads((self.output / "results.json").read_text())
        self.assertEqual(results["workers"], 1)
        self.assertEqual(len(client.calls), 2)

    def test_model_settings_and_custom_factory(self):
        spec_path = self.directory / "model.json"
        spec_path.write_text(json.dumps({"name": "custom", "factory": "dispatch:JournalDesk"}))
        model = load_model(spec_path)
        self.assertIsInstance(model.factory(None, 8, 0, None), JournalDesk)
        for settings in ({"dealer_price": "1.001"}, {"driver_fee": 0}, {"unsupported": True}):
            spec_path.write_text(json.dumps({"name": "bad", "factory": "fixed", "settings": settings}))
            with self.subTest(settings=settings), self.assertRaises((ValueError, TypeError)):
                load_model(spec_path)

    def test_cli_report_needs_no_credentials_and_refuses_to_overwrite(self):
        self.run_suite([8], ["seed"])
        report_path = self.directory / "report.md"
        arguments = ["report", str(self.output / "results.json"), "--output", str(report_path)]
        with patch.dict("os.environ", {}, clear=True), redirect_stdout(self.stdout), redirect_stderr(self.stderr):
            self.assertEqual(main(arguments), 0)
            self.assertEqual(main(arguments), 1)
        self.assertTrue(report_path.read_text().startswith("# Model comparison"))

    def test_cli_run_defaults_to_all_levels_and_outputs_only_markdown(self):
        with patch.dict("os.environ", {"SPREAD_KEY": "test-only"}), patch("compare.Client", return_value=self.client):
            with redirect_stdout(self.stdout), redirect_stderr(self.stderr):
                code = main(["run", "--seeds", "cli-smoke", "--output", str(self.output)])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.client.calls), 16)
        self.assertEqual({call["level"] for call in self.client.calls}, set(range(1, 9)))
        self.assertEqual(self.stdout.getvalue(), (self.output / "leaderboard.md").read_text())

    def test_captured_batches_preserve_comparison_diagnostics(self):
        from capture import CapturedWorld
        class World:
            def act(self, actions):
                return [{"ok": False, "reason": "fixture rejection"} for _ in actions]
            def advance(self, actions, **parameters):
                return {"now": 1, "results": self.act(actions), "events": [
                    {"kind": "visit_failed", "reason": "licence"},
                    {"kind": "ledger", "line": {"kind": "driver_fee", "cents": -100}}]}
        journal = MetricsJournal(io.StringIO())
        CapturedWorld(World(), journal).advance(actions=[{"type": "withdraw"}] * 51, max=1)
        metrics = journal.metrics()
        self.assertEqual(metrics["rejections"], {"fixture rejection": 51})
        self.assertEqual(metrics["visit_failures"], {"licence": 1})
        self.assertEqual(metrics["ledger"], {"driver_fee": -100})
        self.assertEqual(metrics["events"], {"visit_failed": 1, "ledger": 1})

    def test_diagnostics_count_rejections_and_failed_visit_reasons(self):
        trace = io.StringIO()
        journal = MetricsJournal(trace)
        desk = JournalDesk(None, 8, 0, journal)
        desk.read_results([{"type": "withdraw", "gigId": "missing"}], [{"ok": False, "reason": "Unknown gig"}])
        journal.record("event", event={"kind": "visit_failed", "reason": "licence"})
        journal.record("event", event={"kind": "visit_failed", "reason": "licence"})
        journal.record("event", event={"kind": "visit_failed", "reason": "closed"})
        metrics = journal.metrics()
        self.assertEqual(metrics["rejections"], {"Unknown gig": 1})
        self.assertEqual(metrics["visit_failures"], {"licence": 2, "closed": 1})
        self.assertEqual(metrics["events"]["visit_failed"], 3)


def sample_results():
    def score(margin, ranked=True):
        return {"marginCents": margin, "revenueCents": 100_000, "wonOrders": 10,
                "onTimeShare": 0.95 if ranked else 0.5, "undeliveredShare": 0.0 if ranked else 0.3,
                "ranked": ranked}

    # B wins qualification, A wins margin, exact tie, neither qualifies.
    pairs = [(score(90_000, False), score(1_000)), (score(3_000), score(2_000)),
             (score(2_000), score(2_000)), (score(90_000, False), score(-10_000, False))]
    runs = []
    for level in (1, 8):
        for seed, pair in zip(("one", "two", "three", "four"), pairs):
            for model, outcome in enumerate(pair):
                runs.append({"model": model, "level": level, "seed": seed, "status": "complete", "score": outcome,
                             "diagnostics": {"events": {"visit_failed": 1}, "ledger": {"driver_fee": -100},
                                             "visit_failures": {"licence": 1}, "rejections": {"Bad | stop": 1}}})
    return {"schema_version": 1, "status": "complete", "mode": "practice", "levels": [1, 8],
            "seeds": ["one", "two", "three", "four"], "models": [{"name": "A"}, {"name": "B"}],
            "runs": runs, "created_at": "test", "code": {"commit": "abc", "dirty": False}}


class LeaderboardTests(unittest.TestCase):
    def test_qualification_beats_profitable_failures_and_deltas_include_all_weeks(self):
        report = render_markdown(sample_results())
        self.assertIn("Overall leader on these weeks: **B**", report)
        self.assertIn("Use **B** as the level 8 candidate", report)
        self.assertIn("| 1 | B | 6/8 | €-12.50 |", report)
        self.assertIn("| 1 | €-475.00 | €+0.00 | +11.2 | -7.5 | 1 / 1 / 1 / 1 |", report)
        self.assertIn("Bad &#124; stop", report)
        self.assertIn("licence (8 occurrences)", report)
        self.assertIn("inspect driver_fee", report)
        self.assertIn("Selected levels: 1, 8", report)

    def test_no_recommendation_when_neither_qualifies(self):
        results = sample_results()
        for run in results["runs"]:
            run["score"]["ranked"] = False
        report = render_markdown(results)
        self.assertIn("Neither model qualified any week", report)
        self.assertIn("Neither model qualifies at level 8", report)
        self.assertNotIn("Overall leader on these weeks:", report)
        self.assertIn("| — | A |", report)

    def test_exact_ties_remain_ties(self):
        results = sample_results()
        for run in results["runs"]:
            run["score"].update(ranked=True, marginCents=100)
        report = render_markdown(results)
        self.assertIn("Overall result: tie", report)
        self.assertIn("Level 8 is tied", report)
        self.assertIn("0 / 0 / 4 / 0", report)

    def test_rejects_incomplete_duplicate_failed_or_nonfinite_results(self):
        original = sample_results()
        invalid = []
        missing = deepcopy(original)
        missing["runs"].pop()
        invalid.append(missing)
        duplicate = deepcopy(original)
        duplicate["runs"].append(duplicate["runs"][0])
        invalid.append(duplicate)
        failed = deepcopy(original)
        failed["runs"][0]["status"] = "failed"
        invalid.append(failed)
        nan = deepcopy(original)
        nan["runs"][0]["score"]["marginCents"] = float("nan")
        invalid.append(nan)
        for results in invalid:
            with self.subTest(results=results), self.assertRaises(ValueError):
                render_markdown(results)


if __name__ == "__main__":
    unittest.main()
