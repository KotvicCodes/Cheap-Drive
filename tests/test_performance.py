from contextlib import redirect_stdout
from copy import deepcopy
import gzip
import io
import json
import unittest
from unittest.mock import patch

from spread import Client, SpreadError

from models.alpha import AlphaDesk
from dispatch import Journal, JournalDesk, handle_batch, play_model
from performance import PracticeClient
from test_alpha import MarketWorld
from demo import sample_request


class TransportTests(unittest.TestCase):
    def test_gzip_preserves_payload_and_official_request_validation(self):
        expected = {"events": [{"kind": "future", "unknown": [1, 2]}]}
        compressed = gzip.compress(json.dumps(expected).encode())
        with patch.object(Client, "_send", return_value=(200, {"Content-Encoding": "gzip"}, compressed)) as send:
            client = PracticeClient(url="https://example.test", key="test-only")
            self.assertEqual(client.call("GET", "/v1/worlds/private-id/events?after=123"), expected)
            self.assertEqual(send.call_args.args[-1]["Accept-Encoding"], "gzip")
            timing = client.timing()
            self.assertEqual(timing["wire_bytes"], len(compressed))
            self.assertEqual(timing["routes"], {"GET /v1/worlds/:world/events": 1})
            self.assertNotIn("test-only", json.dumps(timing))
            self.assertNotIn("private-id", json.dumps(timing))
            with self.assertRaises(SpreadError):
                client.call("POST", "/v1/worlds", {"level": 1.5})
            self.assertEqual(send.call_count, 1)

    def test_compressed_429_keeps_sdk_retry_and_error_handling(self):
        responses = [
            (429, {"Retry-After": "0", "Content-Encoding": "gzip"}, gzip.compress(b'{"error":"busy"}')),
            (200, {}, b'{"ok":true}'),
            (400, {"Content-Encoding": "gzip"}, gzip.compress(b'{"error":"bad action"}')),
        ]
        with patch.object(Client, "_send", side_effect=responses):
            client = PracticeClient(url="https://example.test", key="test-only")
            self.assertEqual(client.call("POST", "/v1/worlds"), {"ok": True})
            self.assertEqual(client.timing()["rate_limit_responses"], 1)
            with self.assertRaisesRegex(SpreadError, "bad action"):
                client.call("POST", "/v1/worlds")

    def test_map_cache_copies_data_and_does_not_cache_world_reads(self):
        with patch.object(Client, "_send", return_value=(200, {}, b'{"roads":[]}')) as send:
            client = PracticeClient(url="https://example.test", key="test-only")
            client.map()["roads"].append("mutated")
            self.assertEqual(client.map(), {"roads": []})
            self.assertEqual(send.call_count, 1)
            client.call("GET", "/v1/worlds/a")
            client.call("GET", "/v1/worlds/a")
            self.assertEqual(send.call_count, 3)
            client.reset_timing()
            self.assertEqual(client.timing()["routes"], {})


class LossWorld(MarketWorld):
    """Action-recording tape for coalescing; never an alternative market model."""
    def __init__(self):
        super().__init__()
        self.sent, self.calls, self.reads = [], 0, {"map": 0, "roster": 0, "snapshot": 0}
        self.pending = []
        for index, minute in enumerate((540, 560, 580)):
            request = sample_request()
            request.update(id=f"request-{index}", arrivedAt=minute, respondBy=minute + 15)
            self.pending.extend([
                {"kind": "price_request", "at": minute, "request": request},
                {"kind": "order_lost", "at": minute + 15, "requestId": request["id"]},
            ])
        self.pending.extend([
            {"kind": "gig_started", "at": 550, "gigId": "other", "driverId": "driver-0"},
            {"kind": "forecast", "at": 556},
            {"kind": "release", "at": 576},
        ])

    def act(self, actions):
        self.sent.extend((self.now, deepcopy(action)) for action in actions)
        return [{"ok": True, "id": action.get("requestId", "fixture")} for action in actions]

    def advance(self, **kwargs):
        self.calls += 1
        return super().advance(**kwargs)

    def map(self):
        self.reads["map"] += 1
        return super().map()

    def roster(self):
        self.reads["roster"] += 1
        return super().roster()

    def snapshot(self):
        self.reads["snapshot"] += 1
        return super().snapshot()


class FastClockTests(unittest.TestCase):
    def test_coalesced_alpha_preserves_actions_handler_clocks_and_final_state(self):
        runs = []
        for fast in (False, True):
            world, stream, desks = LossWorld(), io.StringIO(), []

            class InspectAlpha(AlphaDesk):
                passive_wake_events = AlphaDesk.passive_wake_events

                def __init__(self, *args):
                    super().__init__(*args)
                    self.clocks = []

                def handle(self, event):
                    self.clocks.append((event["kind"], event["at"], self.now))
                    super().handle(event)

            def factory(*args):
                desk = InspectAlpha(*args)
                desks.append(desk)
                return desk

            with redirect_stdout(io.StringIO()):
                score = play_model(world, 8, Journal(stream), factory, fast=fast)
            desk = desks[0]
            runs.append((world, score, desk))
            self.assertEqual(world.reads, {"map": 1, "roster": 1 if fast else 2, "snapshot": 2})
            records = [json.loads(line) for line in stream.getvalue().splitlines()]
            self.assertEqual(records[-1]["type"], "run_end")
            self.assertTrue(any(row["type"] == "snapshot" and row["phase"] == "end" for row in records))
        normal, fast = runs
        self.assertEqual(normal[0].sent, fast[0].sent)
        self.assertEqual(normal[1], fast[1])
        self.assertEqual(normal[2].clocks, fast[2].clocks)
        self.assertEqual(normal[2].dealer_margins, fast[2].dealer_margins)
        self.assertEqual(normal[2].reservations, fast[2].reservations)
        self.assertLess(fast[0].calls, normal[0].calls)

    def test_custom_subclass_does_not_inherit_permission_to_coalesce(self):
        class Custom(JournalDesk):
            def handle(self, event):
                if event["kind"] == "order_lost":
                    self.outbox.append({"type": "quote", "requestId": event["requestId"], "prices": {"same_day": 100}})
                super().handle(event)

        worlds = []
        for fast in (False, True):
            world = LossWorld()
            with redirect_stdout(io.StringIO()):
                play_model(world, 8, Journal(io.StringIO()), Custom, fast=fast)
            worlds.append(world)
        self.assertEqual(worlds[0].sent, worlds[1].sent)
        self.assertEqual(worlds[0].calls, worlds[1].calls)

    def test_incorrect_passive_declaration_stops_instead_of_delaying_actions(self):
        desk = JournalDesk(None, 8, 0, Journal(io.StringIO()))
        desk.handle = lambda event: desk.outbox.append({"type": "unexpected"})
        with self.assertRaisesRegex(RuntimeError, "passive wake"):
            handle_batch(desk, [{"kind": "order_lost", "at": 5}], 10, coalesced=True)


if __name__ == "__main__":
    unittest.main()
