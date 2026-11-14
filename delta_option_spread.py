"""Default-off B4 pricing on Gamma's final competitive option menu."""
from __future__ import annotations

from gamma import GammaSettings
from gamma_pairs import DriverSideSettings


OPTION_SPREAD_MODES = ("off", "dual_10400_9800")


def validate_option_spread(mode, settings, driver_settings, *, b1, lanes,
                           note_fixes, rescue_windows):
    if type(mode) is not str or mode not in OPTION_SPREAD_MODES:
        raise ValueError("delta_option_spread must be one of: " + ", ".join(OPTION_SPREAD_MODES))
    if mode == "off":
        return
    if b1 != "off" or lanes != "off":
        raise ValueError("delta_option_spread cannot combine with delta_b1 or delta_lanes")
    if note_fixes or rescue_windows:
        raise ValueError("delta_option_spread cannot combine with Delta note/rescue repairs")
    for name in ("dealer_table", "place_table", "capacity_valve", "supply_scale",
                 "town_caps", "town_reserve_pending", "trust_build_bps", "trust_guard",
                 "brake", "trade_ins", "freeze_day_drop_bps"):
        if getattr(settings, name):
            raise ValueError("delta_option_spread cannot combine with " + name)
    defaults = GammaSettings()
    for name in ("markup_scope", "learn_bps", "win_target_bps", "trust_bps_per_order",
                 "quote_options", "same_day_bps", "next_day_bps", "within_3_days_bps",
                 "table_strength", "trust_build_until_day"):
        if getattr(settings, name) != getattr(defaults, name):
            raise ValueError("delta_option_spread requires unchanged Gamma " + name)
    driver_defaults = DriverSideSettings()
    for name in ("fee_shape", "review_after_minutes", "review_fee_bps",
                 "cap_before_last_pickup_minutes", "review_skip_night"):
        if getattr(driver_settings, name) != getattr(driver_defaults, name):
            raise ValueError("delta_option_spread cannot combine with changed " + name)


class DeltaOptionSpreadMixin:
    """Observe post-gating menus and add factors before Gamma's single ceiling.

    Gamma's only guard after eligible_options is an entire-menu town decline.
    No option can be removed between this hook and price_option. Pairing does
    not intercept quote/pricing; B4 owns no pending or lifecycle state.
    """

    def __init__(self, *args, delta_option_spread="off", **kwargs):
        self.delta_option_spread = delta_option_spread
        self._delta_option_spread_context = None
        super().__init__(*args, **kwargs)

    def eligible_options(self, request, km, trust):
        options, reason = super().eligible_options(request, km, trust)
        context = self._delta_option_spread_context
        if context is not None and context["request"] is request:
            context["menu"] = tuple(option["kind"] for option in options)
        return options, reason

    def option_factors(self, request, option, km, trust):
        factors = super().option_factors(request, option, km, trust)
        context = self._delta_option_spread_context
        if context is not None and context["request"] is request:
            if {"same_day", "next_day"} <= set(context["menu"]):
                factor = {"same_day": 10400, "next_day": 9800}.get(option["kind"])
                if factor is not None:
                    factors["deltaOptionSpreadBps"] = factor
            context["factors"][option["kind"]] = dict(factors)
        return factors

    def quote(self, request):
        if (self.delta_option_spread == "off" or self.level <= 3
                or request["id"] in self.requests or self.now >= request["respondBy"]):
            return super().quote(request)
        previous = self._delta_option_spread_context
        context = {"request": request, "menu": (), "factors": {}}
        self._delta_option_spread_context = context
        try:
            result = super().quote(request)
        finally:
            self._delta_option_spread_context = previous
        if request["id"] not in self.pending:  # Gamma practical decline
            return result
        # DriverSideMixin.outbox can process pair timers during Gamma's append.
        # Do not assume earlier queue indices survive that processing. The
        # duplicate guard above guarantees this request has no earlier quote.
        action = next(action for action in reversed(self._outbox)
                      if action["type"] == "quote" and action["requestId"] == request["id"])
        keys = tuple(action["prices"])
        same, next_day = "same_day" in keys, "next_day" in keys
        cohort = ("dual_menu" if same and next_day else
                  "same_day_without_next_day" if same else
                  "next_day_without_same_day" if next_day else "neither")
        self.journal.record(
            "delta_option_spread_quote", at=self.now, requestId=request["id"],
            arm=self.delta_option_spread, cohort=cohort, optionKeys=keys,
            prices=action["prices"], optionFactors=context["factors"],
            spreadFactorsBps={key: context["factors"][key].get("deltaOptionSpreadBps", 10000)
                              for key in keys})
        return result
