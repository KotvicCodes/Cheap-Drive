"""Default-off B2 lane factors; Gamma owns admission, rounding and feedback."""
from __future__ import annotations

from collections import Counter

from .gamma import GammaSettings


HUBS = frozenset({"vantaa", "helsinki", "espoo", "hyvinkaa", "porvoo"})
REMOTE_DESTINATIONS = frozenset({
    "savonlinna", "kajaani", "kotka", "ylivieska", "kokkola", "seinajoki",
    "mikkeli", "rovaniemi", "vaasa", "lappeenranta", "kouvola", "pori",
})
RETROSPECTIVE_EXCLUDED_ORIGINS = frozenset({"tampere", "lempaala", "raisio"})
# Each value is (inbound bps, outbound bps). One mode prevents accidental arms.
LANE_MODES = {
    "off": (10000, 10000),
    "inbound_9100": (9100, 10000),
    "outbound_10400": (10000, 10400),
    "outbound_10600": (10000, 10600),
    "inbound_9100_outbound_10400": (9100, 10400),
    "inbound_9100_outbound_10600": (9100, 10600),
}


def validate_lanes(mode, settings, driver_settings, *, b1, note_fixes, rescue_windows):
    if type(mode) is not str or mode not in LANE_MODES:
        raise ValueError("delta_lanes must be one of: " + ", ".join(LANE_MODES))
    if mode == "off":
        return
    if b1 != "off":
        raise ValueError("delta_lanes cannot combine with delta_b1 before independent qualification")
    if note_fixes or rescue_windows:
        raise ValueError("delta_lanes cannot combine with Delta note/rescue repairs")
    for name in ("dealer_table", "place_table", "capacity_valve", "supply_scale",
                 "town_caps", "town_reserve_pending"):
        if getattr(settings, name):
            raise ValueError("delta_lanes cannot combine with " + name)
    if settings.markup_scope != "global":
        raise ValueError("delta_lanes requires markup_scope=global")
    defaults = GammaSettings()
    for name in ("learn_bps", "win_target_bps", "trust_bps_per_order"):
        if getattr(settings, name) != getattr(defaults, name):
            raise ValueError("delta_lanes requires unchanged Gamma " + name)
    if driver_settings.fee_shape != "ramp":
        raise ValueError("delta_lanes cannot combine with fee_shape review")


def lane_cohort(request, km):
    """Use Gamma's total route distance and first pickup / final delivery IDs."""
    origin = request["legs"][0]["pickup"]["placeId"]
    destination = request["legs"][-1]["delivery"]["placeId"]
    if km >= 60 and origin not in HUBS and destination in HUBS:
        return "inbound"
    if km >= 100 and destination in REMOTE_DESTINATIONS:
        return "outbound"
    return "other"


class DeltaLanesMixin:
    def __init__(self, *args, delta_lanes="off", **kwargs):
        self.delta_lanes = delta_lanes
        self.delta_lane_counts = Counter()
        super().__init__(*args, **kwargs)

    def lane_factor_bps(self, request, km):
        inbound, outbound = LANE_MODES[self.delta_lanes]
        factor = {"inbound": inbound, "outbound": outbound}.get(lane_cohort(request, km), 10000)
        # Clamp only the NEW factor. Gamma's existing short discount survives.
        return max(10000, factor) if km < 60 else factor

    def option_factors(self, request, option, km, trust):
        factors = super().option_factors(request, option, km, trust)
        if self.delta_lanes != "off":
            factors["deltaLaneBps"] = self.lane_factor_bps(request, km)
        return factors

    def quote(self, request):
        if (self.delta_lanes == "off" or self.level <= 3
                or request["id"] in self.requests or self.now >= request["respondBy"]):
            return super().quote(request)
        super().quote(request)
        if request["id"] not in self.pending:  # Gamma declined; no competitive cohort
            return
        # Observe the final action; never reprice it or replace Gamma's journal.
        action = next(action for action in reversed(self._outbox)
                      if action["type"] == "quote" and action["requestId"] == request["id"])
        km = self.route_km(request)
        cohort = lane_cohort(request, km)
        origin = request["legs"][0]["pickup"]["placeId"]
        retrospective_excluded = cohort == "inbound" and origin in RETROSPECTIVE_EXCLUDED_ORIGINS
        group = "inbound_retrospective_excluded" if retrospective_excluded else cohort
        self.delta_lane_counts[group] += 1
        self.journal.record(
            "delta_lane_quote", at=self.now, requestId=request["id"], arm=self.delta_lanes,
            cohort=cohort, diagnosticGroup=group, retrospectiveExcludedOrigin=retrospective_excluded,
            routeKm=km, pickupPlaceId=origin,
            deliveryPlaceId=request["legs"][-1]["delivery"]["placeId"],
            laneFactorBps=self.lane_factor_bps(request, km),
            optionKeys=tuple(action["prices"]), prices=action["prices"],
            tracker=self.quote_trackers[request["id"]], counts=dict(self.delta_lane_counts))
