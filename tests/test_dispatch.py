import argparse
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import unittest

from demo import DemoWorld, sample_request
from dispatch import FixedDesk, FixedPrices, Journal, euro_cents, play_practice


class RecordingWorld:
    """Contract stub that can reject a combined trade-in while accepting each car."""

    def __init__(self):
        self.actions = []

    def act(self, actions):
        self.actions.extend(deepcopy(actions))
        results = []
        for index, action in enumerate(actions):
            if action["type"] == "post" and len(action["stops"]) > 2:
                results.append({"ok": False, "reason": "Combined driving exceeds 12 hours"})
            else:
                results.append({"ok": True, "id": f"gig-{len(self.actions)}-{index}"})
        return results


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.trace = io.StringIO()
        self.world = RecordingWorld()
        self.desk = FixedDesk(self.world, 4, 555, FixedPrices(31_234, 14_567), Journal(self.trace))

    def order(self, legs=1):
        request = sample_request()
        request["legs"] *= legs
        self.desk.requests[request["id"]] = request
        return {"id": request["id"], "dealerId": request["dealerId"], "option": "same_day",
                "priceCents": 31_234, "deadline": 1200, "legs": request["legs"],
                "status": "waiting", "deliveredAt": [None] * legs, "lastPickupAt": 1080}

    def test_exact_currency_and_invalid_inputs(self):
        self.assertEqual(euro_cents("312.34"), 31_234)
        for value in ("0", "-10", "1.001", "NaN", "Infinity", "bad", "1e100"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                euro_cents(value)

    def test_all_options_keep_same_quote_despite_reference_prices(self):
        request = sample_request()
        request["options"].append({"kind": "next_day", "deadline": 2640, "listPriceCents": 99_999})
        request["referenceFeeCents"] = 999_999
        self.desk.quote(request)
        self.assertEqual(self.desk.outbox[0]["prices"], {"same_day": 31_234, "next_day": 31_234})

    def test_warning_and_time_do_not_escalate_fees(self):
        order = self.order()
        self.desk.win(order)
        self.desk.send()
        self.desk.now = 900
        self.desk.raise_fees(order["id"])
        self.assertEqual(self.desk.outbox, [])
        self.assertEqual(self.desk.fees_for(order, 1), [{"at": 900, "feeCents": 14_567}])

    def test_rejected_trade_in_splits_without_double_paying_each_car(self):
        self.desk.win(self.order(legs=2))
        self.desk.send()
        posts = [action for action in self.world.actions if action["type"] == "post"]
        self.assertEqual([action["schedule"][0]["feeCents"] for action in posts], [29_134, 14_567, 14_567])
        self.assertEqual([len(action["stops"]) for action in posts], [4, 2, 2])
        self.assertEqual(len(self.desk.gigs_of("demo-order")), 2)

    def test_failed_manual_pickup_reposts_with_correct_audience_and_fixed_fee(self):
        self.desk.win(self.order())
        self.desk.send()
        self.desk.handle({"seq": 1, "at": 580, "kind": "visit_failed", "gigId": "gig-1-0",
                          "orderId": "demo-order", "leg": 0, "reason": "licence"})
        retry = self.desk.outbox[0]
        self.assertTrue(retry["audience"]["manualLicence"])
        self.assertEqual(retry["schedule"][0]["feeCents"], 14_567)

    def test_action_rejections_are_written_to_trace(self):
        self.desk.read_results([{"type": "withdraw", "gigId": "unknown"}], [{"ok": False, "reason": "Unknown gig"}])
        record = json.loads(self.trace.getvalue())
        self.assertFalse(record["result"]["ok"])
        self.assertEqual(record["result"]["reason"], "Unknown gig")

    def test_offline_flow_uses_our_prices_through_delivery_and_ledger(self):
        with redirect_stdout(io.StringIO()):
            score = play_practice(DemoWorld(), 4, FixedPrices(40_000, 17_500), Journal(self.trace))
        records = [json.loads(line) for line in self.trace.getvalue().splitlines()]
        kinds = [record["event"]["kind"] for record in records if record["type"] == "event"]
        self.assertIn("price_request", kinds)
        self.assertIn("order_won", kinds)
        self.assertIn("gig_booked", kinds)
        self.assertIn("delivered", kinds)
        self.assertEqual(kinds.count("ledger"), 2)
        self.assertEqual(score["revenueCents"], 40_000)
        self.assertEqual(score["marginCents"], 22_500)
        self.assertTrue(score["ranked"])


if __name__ == "__main__":
    unittest.main()
