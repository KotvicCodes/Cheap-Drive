import io
import unittest
from unittest.mock import patch

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


class BackgroundReadTests(unittest.TestCase):
    def test_blocked_clock_and_daily_score_do_not_delay_stream_quotes(self):
        import threading
        clock_entered, score_entered, release = threading.Event(), threading.Event(), threading.Event()

        def clock():
            clock_entered.set()
            release.wait(5)
            return 2000

        def score():
            score_entered.set()
            release.wait(5)
            return world.score()

        class BusyWorld(FakeWorld):
            def snapshot(self):
                return {**super().snapshot(), 'endsAt': 2000}

            def stream(self, **kwargs):
                self_outer.assertTrue(clock_entered.wait(1))
                for seq, at in enumerate((1441, 1442, 2000)):
                    if seq == 1:
                        self_outer.assertTrue(score_entered.wait(1))
                        self_outer.assertFalse(release.is_set())
                    yield dict(seq=seq, at=at, kind='price_request',
                               request=dict(id=f'r{seq}', options=[dict(kind='standard', listPriceCents=5000)]))
                    self_outer.assertEqual(len(self.acted), seq + 1)

        self_outer, world = self, BusyWorld()
        reads = final.BackgroundReads(clock, score)
        try:
            result = final.play_live(world, 8, Journal(io.StringIO()), factory,
                                     clock=clock, reads=reads)
            self.assertEqual(len(world.acted), 3)
            self.assertFalse(release.is_set())
            self.assertEqual(result['wonOrders'], 0)
        finally:
            release.set()
            reads.close()
            for thread in reads.threads:
                thread.join(timeout=1)

    def test_failed_score_is_optional_and_clock_never_moves_backwards(self):
        import threading
        seen = threading.Event()
        def unavailable():
            seen.set()
            raise Unreachable(0, 'offline read')
        reads = final.BackgroundReads(lambda: 120, unavailable)
        try:
            reads.request_score(0, 1440)
            self.assertTrue(seen.wait(1))
            for thread in reads.threads:
                if thread.name == 'final-clock':
                    self.assertGreaterEqual(reads.latest, 120)
            # Wait for exactly this queued result, without a timing-based sleep.
            result = reads.results.get(timeout=1)
            reads.results.put(result)
            journal = Journal(io.StringIO())
            reads.drain(journal)
            self.assertIn('daily_score_unavailable', journal.output.getvalue())
        finally:
            reads.close()


class RehearsalTests(unittest.TestCase):
    def test_same_seed_resumes_unfinished_world_after_process_restart(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        class Client:
            created = 0
            def create(self, **kwargs):
                self.created += 1
                world = FakeWorld()
                world.id = f'offline-{self.created}'
                self.saved = world
                return world
            def world(self, identity):
                self_outer.assertEqual(identity, self.saved.id)
                return self.saved
        self_outer, client = self, Client()
        with TemporaryDirectory() as directory:
            out = Path(directory)
            first = final.rehearsal_world(client, out, 'seed', {'name': 'Delta'})
            again = final.rehearsal_world(client, out, 'seed', {'name': 'Delta'})
            self.assertIs(first, again)
            self.assertEqual(client.created, 1)

            first.now = 200
            fresh = final.rehearsal_world(client, out, 'seed', {'name': 'Delta'})
            self.assertNotEqual(first.id, fresh.id)

    def test_outage_while_resuming_never_creates_a_replacement_world(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        class Client:
            created = 0
            def create(self, **kwargs):
                self.created += 1
                world = FakeWorld(); world.id = 'offline'
                return world
            def world(self, identity):
                class Down:
                    def snapshot(self):
                        raise Unreachable(0, 'fixture outage')
                return Down()
        client = Client()
        with TemporaryDirectory() as directory:
            out = Path(directory)
            final.rehearsal_world(client, out, 'seed', {})
            with self.assertRaises(Unreachable):
                final.rehearsal_world(client, out, 'seed', {})
            self.assertEqual(client.created, 1)


class HistoryFenceTests(unittest.TestCase):
    def test_history_stops_at_snapshot_cut_and_leaves_future_events_for_stream(self):
        class World:
            calls = 0
            def events(self, after=-1):
                self.calls += 1
                if self.calls > 1:
                    raise AssertionError('followed a continuously growing stream past the snapshot')
                return [dict(seq=0, at=99), dict(seq=1, at=100), dict(seq=2, at=101)]
        self.assertEqual(final.full_history(World(), through=100),
                         [dict(seq=0, at=99), dict(seq=1, at=100)])


class PacerTests(unittest.TestCase):
    def exercise(self, latency):
        class Clock:
            now = 0.0
            def monotonic(self):
                return self.now
            def sleep(self, seconds):
                self.now += seconds

        clock = Clock()
        class World:
            now = 0
            ticks = []
            answered = False
            def snapshot(self):
                return dict(now=self.now, endsAt=20)
            def advance(self, *, to):
                self.ticks.append((clock.now, to - self.now))
                # A request born at 2, due at 17, becomes visible only after
                # this atomic advance. The simulated consumer answers at once.
                if self.now < 2 <= to:
                    self.answered = to < 17
                self.now = to
                clock.now += latency
                return dict(now=to)

        world = World()
        with patch.object(final, 'time', clock):
            pacer = final.Pacer(world, 9)
            pacer.run()
        self.assertIsNone(pacer.error)
        self.assertEqual(world.now, 20)
        self.assertTrue(world.answered, 'request expired inside a catch-up advance')
        return world.ticks

    def test_slow_advance_never_skips_a_request_response_window(self):
        # A 3-second HTTP stall used to cause a 27-minute atomic catch-up,
        # creating AND expiring a request before the stream could answer it.
        ticks = self.exercise(3)
        self.assertEqual([step for _, step in ticks], [1] * 20)

    def test_fast_transport_keeps_the_requested_pace(self):
        ticks = self.exercise(.01)
        for (before, _), (after, _) in zip(ticks, ticks[1:]):
            self.assertAlmostEqual(after - before, 1 / 9)

    def test_slow_transport_does_not_build_a_catch_up_budget(self):
        ticks = self.exercise(.5)
        self.assertTrue(all(after - before >= .5 - 1e-9
                            for (before, _), (after, _) in zip(ticks, ticks[1:])))

    def test_invalid_paces_are_rejected_before_reading_a_world(self):
        for pace in (0, -1, float('inf'), float('nan')):
            with self.subTest(pace=pace), self.assertRaises(ValueError):
                final.Pacer(None, pace)


if __name__ == "__main__":
    unittest.main()
