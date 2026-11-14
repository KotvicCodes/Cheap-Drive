import io
import unittest

from capture import Journal
from dispatch import JournalDesk
from spread.client import Unreachable
import final


class FakeClient:
    def map(self):
        return {"places": []}


class FakeWorld:
    """A live world: two price requests arrive on the stream, one replayed after a reconnect."""

    def __init__(self, fail_first_stream=False):
        self.client, self.acted, self.fail = FakeClient(), [], fail_first_stream
        self.now = 100

    def events(self, after=-1, limit=None):
        return []

    def snapshot(self):
        return {"now": self.now, "endsAt": 200, "gigs": [], "orders": [], "openRequests": []}

    def roster(self):
        return []

    def score(self):
        return {"marginCents": 0, "revenueCents": 0, "wonOrders": 0, "onTimeShare": 0, "undeliveredShare": 0, "ranked": False}

    def act(self, actions):
        self.acted += actions
        return [{"ok": True} for _ in actions]

    def stream(self, after=None, idle=None):
        def request(seq, at, rid):
            return {"seq": seq, "at": at, "kind": "price_request",
                    "request": {"id": rid, "options": [{"kind": "standard", "listPriceCents": 5000}]}}
        if self.fail:
            self.fail = False
            yield request(0, 110, "r1")
            raise Unreachable(0, "fixture outage")
        yield request(0, 110, "r1")  # replayed: skipped
        yield request(1, 120, "r2")
        yield None  # idle: clock moves to the end
        yield request(2, 130, "never")


def factory(world, level, now, journal):
    return JournalDesk(world, level, now, journal)


class FinalTests(unittest.TestCase):
    def test_answers_stream_dedupes_and_stops_at_end(self):
        world = FakeWorld()
        score, stats = final.play_until_done(world, 8, Journal(io.StringIO()), factory, clock=lambda: 200)
        self.assertEqual([a["requestId"] for a in world.acted], ["r1", "r2"])
        self.assertEqual(stats["events"], 2)
        self.assertFalse(score["ranked"])

    def test_rebuilds_after_unreachable(self):
        world = FakeWorld(fail_first_stream=True)
        final.time.sleep, original = (lambda s: None), final.time.sleep
        try:
            score, stats = final.play_until_done(world, 8, Journal(io.StringIO()), factory, clock=lambda: 200)
        finally:
            final.time.sleep = original
        self.assertIn("r2", [a["requestId"] for a in world.acted])

    def test_live_world_refuses_advance(self):
        with self.assertRaises(RuntimeError):
            final.LiveWorld(FakeWorld(), Journal(io.StringIO())).advance(by=1)


if __name__ == "__main__":
    unittest.main()
