"""Default-off B1 feedback experiments, composed around frozen Gamma hooks."""
from __future__ import annotations

from collections import Counter

from .gamma import GammaSettings


B1_MODES = ("off", "fastest_learning_only",
            "fastest_learning_only_skipped_9200", "split_skipped_tracker")
SKIPPED_TRACKER = "delta_b1_skipped_fastest"


def validate_b1(mode, settings, driver_settings, *, note_fixes, rescue_windows):
    if type(mode) is not str or mode not in B1_MODES:
        raise ValueError("delta_b1 must be one of: " + ", ".join(B1_MODES))
    if mode == "off":
        return
    if note_fixes or rescue_windows:
        raise ValueError("delta_b1 cannot combine with Delta note/rescue repairs")
    for name in ("dealer_table", "place_table", "capacity_valve", "supply_scale", "town_caps", "town_reserve_pending"):
        if getattr(settings, name):
            raise ValueError("delta_b1 cannot combine with " + name)
    if settings.markup_scope != "global":
        raise ValueError("delta_b1 requires markup_scope=global")
    defaults = GammaSettings()
    if settings.learn_bps != defaults.learn_bps:
        raise ValueError("delta_b1 requires unchanged Gamma learn_bps")
    if settings.win_target_bps != defaults.win_target_bps:
        raise ValueError("delta_b1 requires unchanged Gamma win_target_bps")
    if driver_settings.fee_shape != "ramp":
        raise ValueError("delta_b1 cannot combine with fee_shape review")


class DeltaB1Mixin:
    """Use Gamma's menu, exact price builder and learner without copying quote().

    eligible_options returns the final selected menu; Gamma's only later guard
    can decline the entire quote (town capacity). tracker_for and option_factors
    therefore see precisely the keys Gamma will submit for a competitive quote.
    No outbox price mutation or replacement journal is needed.

    Keep this mixin before DriverSideMixin: pairs intercept order_changed before
    Gamma/Beta's handle, but must not intercept B1 pending-state cleanup.
    """

    def __init__(self, *args, delta_b1="off", **kwargs):
        self.delta_b1 = delta_b1
        self.delta_b1_pending: dict[str, str] = {}
        self.delta_b1_counts = {cohort: Counter(quotes=0, outcomes=0, updates=0, wins=0, losses=0)
                                for cohort in ("fastest_present", "skipped_fastest")}
        self._delta_b1_menu = None
        super().__init__(*args, **kwargs)

    def eligible_options(self, request, km, trust):
        options, reason = super().eligible_options(request, km, trust)
        if self._delta_b1_menu is not None:
            self._delta_b1_menu = tuple(option["kind"] for option in options)
        return options, reason

    def _b1_skipped(self, request):
        return self._delta_b1_menu is not None and request["options"][0]["kind"] not in self._delta_b1_menu

    def tracker_for(self, request, km):
        if self.delta_b1 == "split_skipped_tracker" and self._b1_skipped(request):
            return SKIPPED_TRACKER
        return super().tracker_for(request, km)

    def option_factors(self, request, option, km, trust):
        factors = super().option_factors(request, option, km, trust)
        if self.delta_b1 == "fastest_learning_only_skipped_9200" and self._b1_skipped(request):
            # Gamma multiplies all bps as Fractions before its one cent ceiling.
            factors["deltaB1SkippedBps"] = 9200
        return factors

    def quote(self, request):
        if (self.delta_b1 == "off" or self.level <= 3
                or request["id"] in self.requests or self.now >= request["respondBy"]):
            return super().quote(request)
        self._delta_b1_menu = ()
        try:
            super().quote(request)
        finally:
            self._delta_b1_menu = None
        identity = request["id"]
        if identity not in self.pending:  # deliberate decline; never a training example
            return
        action = next(action for action in reversed(self._outbox)
                      if action["type"] == "quote" and action["requestId"] == identity)
        keys = tuple(action["prices"])
        cohort = "fastest_present" if request["options"][0]["kind"] in keys else "skipped_fastest"
        self.delta_b1_pending[identity] = cohort
        self.delta_b1_counts[cohort]["quotes"] += 1
        tracker = self.quote_trackers[identity]
        self.journal.record("delta_b1_quote", at=self.now, requestId=identity, arm=self.delta_b1,
                            cohort=cohort, originalFirst=request["options"][0]["kind"],
                            optionKeys=keys, prices=action["prices"], tracker=tracker,
                            markupBps=self.tracker_markup(tracker),
                            counts=dict(self.delta_b1_counts[cohort]))

    def _b1_clear(self, identity):
        cohort = self.delta_b1_pending.pop(identity, None)
        self.pending.discard(identity)
        self.quote_trackers.pop(identity, None)
        self.town_pending.pop(identity, None)
        return cohort

    def _b1_abort(self, identity, reason):
        cohort = self._b1_clear(identity)
        if cohort is not None:
            self.delta_b1_counts[cohort][reason] += 1
            self.journal.record("delta_b1_cleanup", at=self.now, requestId=identity,
                                cohort=cohort, reason=reason, counts=dict(self.delta_b1_counts[cohort]))

    def learn(self, request_id, won):
        if self.delta_b1 == "off":
            return super().learn(request_id, won)
        cohort = self.delta_b1_pending.get(request_id)
        if cohort is None or request_id not in self.pending:
            return
        tracker = self.quote_trackers[request_id]
        before = self.tracker_markup(tracker)
        excluded = cohort == "skipped_fastest" and self.delta_b1 != "split_skipped_tracker"
        target = self.win_target()
        if excluded:
            self._b1_clear(request_id)
        else:
            # Same initial markup, per-outcome step, live target, bounds and
            # day-start/freeze semantics as Gamma, independently per tracker.
            super().learn(request_id, won)
            self.delta_b1_pending.pop(request_id)
        counts = self.delta_b1_counts[cohort]
        counts["outcomes"] += 1
        counts["wins" if won else "losses"] += 1
        counts["updates"] += int(not excluded)
        self.journal.record("delta_b1_outcome", at=self.now, requestId=request_id, cohort=cohort,
                            won=won, updated=not excluded, tracker=tracker, winTargetBps=target,
                            beforeBps=before, afterBps=self.tracker_markup(tracker), counts=dict(counts))

    def handle(self, event):
        if self.delta_b1 != "off":
            kind = event["kind"]
            if kind in ("order_cancelled", "delivered"):
                self._b1_abort(event["orderId"], kind)
            elif kind == "order_changed":
                self._b1_abort(event["order"]["id"], kind)
        return super().handle(event)

    def read_results(self, actions, results):
        super().read_results(actions, results)
        if self.delta_b1 != "off":
            for action, result in zip(actions, results):
                if action["type"] == "quote" and not result["ok"]:
                    self._b1_abort(action["requestId"], "rejected")
