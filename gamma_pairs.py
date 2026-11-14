"""Opt-in driver fee review and two-order gigs; defaults preserve the base desk.

Factories take ordinary sweep keyword settings. No SDK requests occur at import.
"""
from __future__ import annotations

from dataclasses import dataclass, fields

from beta import BetaDesk, BetaSettings, FEE_CAP, FEE_STEPS, WARNING
from spread.starter import DAY, HOUR, Retry


@dataclass(frozen=True)
class DriverSideSettings:
    fee_shape: str = "ramp"
    review_after_minutes: int = 360
    review_fee_bps: int = 11000
    cap_before_last_pickup_minutes: int = 360
    review_skip_night: int = 1
    pairs: int = 0
    pair_transfer_km: int = 30
    pair_max_drive_minutes: int = 300
    pair_arrival_allowance_minutes: int = 180
    pair_spare_minutes: int = 60
    pair_fee_bps: int = 8000
    pair_with_waiting: int = 1
    pair_split_minutes: int = 60
    pair_once: int = 1

    def __post_init__(self):
        if self.fee_shape not in ("ramp", "review"):
            raise ValueError("fee_shape must be ramp or review")
        for name, value in vars(self).items():
            if name != "fee_shape" and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a nonnegative integer")
        for name in ("review_skip_night", "pairs", "pair_with_waiting", "pair_once"):
            if getattr(self, name) not in (0, 1):
                raise ValueError(f"{name} must be 0 or 1")
        if not 0 < self.pair_max_drive_minutes <= 720:
            raise ValueError("pair_max_drive_minutes must be between 1 and 720")
        for name in ("review_fee_bps", "pair_fee_bps", "pair_split_minutes"):
            if getattr(self, name) == 0:
                raise ValueError(f"{name} must be positive")


class DriverSideMixin:
    """Cooperative hooks for BetaDesk and GammaCoreDesk."""

    def __init__(self, *args, driver_settings=DriverSideSettings(), **kwargs):
        self.driver_settings = driver_settings
        self.first_posted: dict[str, int] = {}
        super().__init__(*args, **kwargs)
        if driver_settings.pair_fee_bps > self._fee_cap():
            raise ValueError("pair_fee_bps must be <= the base fee_cap_bps")

    def _fee_cap(self):
        return getattr(self.settings, "fee_cap_bps", FEE_CAP)

    def _opening_bps(self, order):
        hook = getattr(self, "opening_fee_for", None)
        return hook(order) if hook else self.settings.opening_fee_bps

    def _review_schedule(self, typical, opening_bps, first_at, last_pickup):
        s = self.driver_settings
        review_at = first_at + s.review_after_minutes
        if s.review_skip_night:
            clock = review_at % DAY
            if clock >= 23 * HOUR:
                review_at = (review_at // DAY + 1) * DAY + 7 * HOUR
            elif clock < 7 * HOUR:
                review_at = review_at // DAY * DAY + 7 * HOUR
        cap = max(opening_bps, self._fee_cap())
        steps = [(first_at, opening_bps),
                 (review_at, max(opening_bps, min(cap, s.review_fee_bps))),
                 (last_pickup - max(WARNING, s.cap_before_last_pickup_minutes), cap)]
        current, future = opening_bps, []
        for at, fee in sorted(steps):
            current = max(current, fee)
            if at <= self.now:
                continue
            future.append((at, current))
        # Evaluate the current step independently: a future cap must not leak into now.
        current = max([opening_bps, *(fee for at, fee in steps if at <= self.now)])
        result = [{"at": self.now, "feeCents": max(1, int(typical * current / 10000 + 0.5))}]
        for at, fee in future:
            cents = max(result[-1]["feeCents"], int(typical * fee / 10000 + 0.5))
            if cents > result[-1]["feeCents"]:
                if at == result[-1]["at"]:
                    result[-1]["feeCents"] = cents
                else:
                    result.append({"at": at, "feeCents": cents})
        return result

    def fees_for(self, order, cars):
        if (self.driver_settings.fee_shape == "ramp" or order["id"] in self.urgent or self.level == 1):
            return super().fees_for(order, cars)
        typical = self.requests[order["id"]]["referenceFeeCents"] * cars / len(order["legs"])
        return self._review_schedule(typical, self._opening_bps(order),
                                     self.first_posted.get(order["id"], self.now), order["lastPickupAt"])

    def post(self, order, legs, retry=Retry()):
        self.first_posted.setdefault(order["id"], self.now)
        return super().post(order, legs, retry)


def _split_settings(base_type, settings):
    driver_names = {f.name for f in fields(DriverSideSettings)}
    base_names = {f.name for f in fields(base_type)}
    unknown = settings.keys() - driver_names - base_names
    if unknown:
        raise TypeError(f"unknown settings: {', '.join(sorted(unknown))}")
    return (base_type(**{k: v for k, v in settings.items() if k in base_names}),
            DriverSideSettings(**{k: v for k, v in settings.items() if k in driver_names}))


def make_pairs_beta(world, level, now, journal, **settings):
    class PairsBetaDesk(DriverSideMixin, BetaDesk):
        passive_wake_events = BetaDesk.passive_wake_events

    base, driver = _split_settings(BetaSettings, settings)
    return PairsBetaDesk(world, level, now, journal, base, driver_settings=driver)


def make_gamma_pairs(world, level, now, journal, **settings):
    # Gamma may be updated independently while a sweep imports this module.
    from gamma import GammaCoreDesk, GammaSettings

    class GammaPairsDesk(DriverSideMixin, GammaCoreDesk):
        passive_wake_events = GammaCoreDesk.passive_wake_events

    base, driver = _split_settings(GammaSettings, settings)
    return GammaPairsDesk(world, level, now, journal, base, driver_settings=driver)
