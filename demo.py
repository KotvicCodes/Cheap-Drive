"""Scripted request-to-delivery walkthrough, NOT a replacement for the simulator."""
from __future__ import annotations

from copy import deepcopy

from spread.types import Action, ActionResult, Advanced, DeskEvent, DeskSnapshot, PriceRequest, Score


def sample_request() -> PriceRequest:
    hours = {"opens": 480, "closes": 1200, "weekdays": [0, 1, 2, 3, 4], "saturday": None}
    return {
        "id": "demo-order", "dealerId": "demo-dealer", "batchId": None,
        "arrivedAt": 540, "respondBy": 555, "referenceFeeCents": 12_000, "note": None,
        "options": [{"kind": "same_day", "deadline": 1200, "listPriceCents": 25_000}],
        "legs": [{
            "car": {"premium": False, "electric": False, "chargePercent": None},
            "pickup": {"placeId": "demo-helsinki", "privateAddress": False,
                       "window": {"from": 540, "to": 1200}, "hours": deepcopy(hours)},
            "delivery": {"placeId": "demo-tampere", "privateAddress": False,
                         "window": {"from": 540, "to": 1200}, "hours": deepcopy(hours)},
        }],
    }


class DemoWorld:
    """Accepts one quote and one gig, then emits a synthetic successful delivery.

    No market, driver decisions, randomness or competition is simulated here.
    It exists so the real dispatch loop can be exercised without a team key.
    """

    id = "offline-demo"

    def __init__(self):
        self.now, self.seq = 0, -1
        self.pending: list[dict] = [{"kind": "price_request", "at": 540, "request": sample_request()}]
        self.order = None
        self.posted = False
        self.revenue = self.driver_cost = 0

    def snapshot(self) -> DeskSnapshot:
        return {"worldId": self.id, "now": self.now, "endsAt": 780,
                "openRequests": [], "orders": [], "gigs": [], "driverPositions": [], "score": self.score()}

    def act(self, actions: list[Action]) -> list[ActionResult]:
        results = []
        for action in actions:
            if action["type"] == "quote" and self.order is None and self.now < 555:
                self.order = {"id": "demo-order", "dealerId": "demo-dealer", "option": "same_day",
                              "priceCents": action["prices"]["same_day"], "deadline": 1200,
                              "legs": sample_request()["legs"], "status": "waiting",
                              "deliveredAt": [None], "lastPickupAt": 1080}
                self.pending.append({"kind": "order_won", "at": 555, "order": deepcopy(self.order)})
                results.append({"ok": True, "id": "demo-order"})
            elif action["type"] == "post" and self.order is not None and not self.posted:
                self.posted = True
                fee = action["schedule"][0]["feeCents"]
                self.pending.extend([
                    {"kind": "gig_booked", "at": 560, "gigId": "demo-gig", "driverId": "demo-driver", "feeCents": fee},
                    {"kind": "gig_started", "at": 565, "gigId": "demo-gig", "driverId": "demo-driver"},
                    {"kind": "picked_up", "at": 580, "gigId": "demo-gig", "orderId": "demo-order", "leg": 0, "placeId": "demo-helsinki"},
                    {"kind": "delivered", "at": 700, "gigId": "demo-gig", "orderId": "demo-order", "leg": 0, "placeId": "demo-tampere"},
                    {"kind": "ledger", "at": 700, "line": {"at": 700, "kind": "revenue", "cents": self.order["priceCents"], "orderId": "demo-order", "gigId": None, "detail": "Scripted demo revenue"}},
                    {"kind": "ledger", "at": 700, "line": {"at": 700, "kind": "driver_fee", "cents": -fee, "orderId": None, "gigId": "demo-gig", "detail": "Scripted demo driver fee"}},
                ])
                results.append({"ok": True, "id": "demo-gig"})
            else:
                results.append({"ok": False, "reason": "Action is outside the scripted demo's one-order flow"})
        return results

    def advance(self, *, until: list[str], max: int, actions: list[Action]) -> Advanced:
        results = self.act(actions)
        self.pending.sort(key=lambda event: event["at"])
        self.now = min(max, next((event["at"] for event in self.pending if event["kind"] in until), max))
        events: list[DeskEvent] = []
        while self.pending and self.pending[0]["at"] <= self.now:
            event = self.pending.pop(0)
            self.seq += 1
            event["seq"] = self.seq
            if event["kind"] == "delivered":
                self.order["status"] = "delivered"
                self.order["deliveredAt"][0] = event["at"]
            elif event["kind"] == "ledger":
                if event["line"]["kind"] == "revenue":
                    self.revenue += event["line"]["cents"]
                else:
                    self.driver_cost -= event["line"]["cents"]
            events.append(event)
        return {"now": self.now, "events": events, "results": results}

    def score(self) -> Score:
        delivered = self.order is not None and self.order["status"] == "delivered"
        margin = self.revenue - self.driver_cost
        return {"marginCents": margin, "revenueCents": self.revenue,
                "marginShare": margin / self.revenue if self.revenue else 0.0,
                "wonOrders": int(self.order is not None), "onTimeShare": float(delivered),
                "undeliveredShare": float(self.order is not None and not delivered), "ranked": delivered}
