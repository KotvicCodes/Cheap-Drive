"""Offline policy boundaries; synthetic requests do not measure market profit."""
from copy import deepcopy
import io
import json
import unittest

from models.beta import BetaDesk, BetaSettings
from dispatch import Journal
from models.gamma import GammaDesk, GammaSettings
from tests.test_gamma import GammaWorld, request


class GammaSegmentTests(unittest.TestCase):
    def desk(self, km=200, **settings):
        desk = GammaDesk(GammaWorld(), 8, 500, Journal(io.StringIO()), GammaSettings(**settings))
        desk.roads['helsinki', 'tampere']['km'] = km
        return desk

    def request(self, premium=False, slacks=(600, 1000, 2000)):
        req = request(slacks=slacks)
        req['legs'][0]['car']['premium'] = premium
        return req

    def order(self, desk, req):
        desk.requests[req['id']] = req
        return dict(id=req['id'], legs=deepcopy(req['legs']),
                    lastPickupAt=req['options'][-1]['deadline'] - 180)

    def reason(self, desk):
        records = map(json.loads, desk.journal.output.getvalue().splitlines())
        return [r['reason'] for r in records if r['type'] == 'beta_decline'][-1]

    def test_defaults_preserve_beta_quotes_and_fees_for_short_and_premium(self):
        defaults = GammaSettings()
        self.assertEqual((defaults.short_fee_km, defaults.short_opening_fee_bps,
                          defaults.premium_opening_fee_bps, defaults.premium_min_slack_minutes),
                         (45, 0, 0, 0))
        for km in (44.999, 45, 49.999, 200, 500):
            for premium in (False, True):
                with self.subTest(km=km, premium=premium):
                    gamma = self.desk(km=km)
                    beta = BetaDesk(GammaWorld(), 8, 500, Journal(io.StringIO()), BetaSettings())
                    beta.roads['helsinki', 'tampere']['km'] = km
                    req = self.request(premium=premium, slacks=(480, 599, 600))
                    for desk in (beta, gamma):
                        desk.quote(deepcopy(req))
                    self.assertEqual(gamma.outbox, beta.outbox)
                    order = self.order(gamma, req)
                    self.assertEqual(gamma.fees_for(order, 1), beta.fees_for(order, 1))

    def test_new_settings_reject_nonintegers_and_negative_values(self):
        for name in ('short_fee_km', 'short_opening_fee_bps',
                     'premium_opening_fee_bps', 'premium_min_slack_minutes'):
            for value in (-1, True, False, 1.0, '600', None):
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(ValueError, name):
                        GammaSettings(**{name: value})
        for name in ('short_opening_fee_bps', 'premium_opening_fee_bps'):
            for cap in (10000, 15000):
                with self.subTest(name=name, cap=cap):
                    self.assertEqual(getattr(GammaSettings(fee_cap_bps=cap, **{name: cap}), name), cap)
                    self.assertEqual(getattr(GammaSettings(fee_cap_bps=cap, **{name: 0}), name), 0)
                    with self.assertRaisesRegex(ValueError, name):
                        GammaSettings(fee_cap_bps=cap, **{name: cap + 1})

    def test_short_proposal_uses_strict_45_km_for_quote_and_fee(self):
        for km, price, fee in ((44.999, 34500, 13200), (45, 37500, 9600),
                               (45.001, 37500, 9600), (49.999, 37500, 9600)):
            with self.subTest(km=km):
                desk = self.desk(km=km, short_km=45, short_bps=9200,
                                 short_fee_km=45, short_opening_fee_bps=11000)
                req = self.request()
                desk.quote(req)
                self.assertEqual(desk.outbox[-1]['prices']['same_day'], price)
                self.assertEqual(desk.fees_for(self.order(desk, req), 1)[0]['feeCents'], fee)

    def test_short_fee_threshold_is_independent_of_quote_threshold(self):
        desk = self.desk(km=47, short_bps=9200, short_opening_fee_bps=11000)
        req = self.request()
        desk.quote(req)
        self.assertEqual(desk.outbox[-1]['prices']['same_day'], 34500)  # existing short_km=50
        self.assertEqual(desk.opening_fee_for(self.order(desk, req)), 8000)  # short_fee_km=45
        disabled = self.desk(km=0, short_fee_km=0, short_opening_fee_bps=11000)
        self.assertEqual(disabled.opening_fee_for(self.order(disabled, req)), 8000)

    def test_premium_slack_is_inclusive_at_ten_hours_for_each_option(self):
        for kind_index, kind in enumerate(('same_day', 'next_day', 'within_3_days')):
            for slack in (599, 600, 601):
                with self.subTest(kind=kind, slack=slack):
                    desk = self.desk(premium_min_slack_minutes=600)
                    req = self.request(premium=True, slacks=(slack,) * 3)
                    req['options'] = [req['options'][kind_index]]
                    self.assertEqual(desk.slack(req, req['options'][0]), slack)
                    desk.quote(req)
                    self.assertEqual(req['id'] in desk.pending, slack >= 600)
                    if slack < 600:
                        self.assertEqual(self.reason(desk), 'premium slack')

    def test_premium_filters_options_before_cheapest_selection(self):
        desk = self.desk(premium_min_slack_minutes=600, quote_options='cheapest_only')
        req = self.request(premium=True, slacks=(599, 600, 601))
        req['options'][0]['listPriceCents'] = 1
        desk.quote(req)
        self.assertEqual(set(desk.outbox[-1]['prices']), {'within_3_days'})
        all_options = self.desk(premium_min_slack_minutes=600)
        all_options.quote(req)
        self.assertEqual(set(all_options.outbox[-1]['prices']), {'next_day', 'within_3_days'})

    def test_premium_settings_do_not_affect_nonpremium_requests(self):
        base = self.desk(km=44.999)
        active = self.desk(km=44.999, premium_min_slack_minutes=6000,
                           premium_opening_fee_bps=15000)
        req = self.request(slacks=(480, 599, 600))
        for desk in (base, active):
            desk.quote(deepcopy(req))
        self.assertEqual(base.outbox, active.outbox)
        order = self.order(active, req)
        self.assertEqual(base.fees_for(order, 1), active.fees_for(order, 1))

    def test_premium_floor_does_not_relax_normal_or_same_day_slack(self):
        desk = self.desk(min_slack_minutes=720, same_day_min_slack_minutes=800,
                         premium_min_slack_minutes=600)
        req = self.request(premium=True, slacks=(799, 719, 720))
        desk.quote(req)
        self.assertEqual(set(desk.outbox[-1]['prices']), {'within_3_days'})

    def test_premium_long_options_require_both_slack_floors(self):
        for premium_slack, slacks, expected in (
                (600, (2000, 1439, 1440), {'within_3_days'}),
                (1600, (2000, 1599, 1600), {'within_3_days'})):
            with self.subTest(premium_slack=premium_slack):
                desk = self.desk(km=600, long_max_km=700,
                                 premium_min_slack_minutes=premium_slack)
                req = self.request(premium=True, slacks=slacks)
                desk.quote(req)
                self.assertIn(req['id'], desk.pending)
                self.assertEqual(set(desk.outbox[-1]['prices']), expected)
        capped = self.desk(km=600, long_max_km=700, long_open_cap=0,
                           premium_min_slack_minutes=600)
        capped.quote(self.request(premium=True))
        self.assertEqual(self.reason(capped), 'long route capacity')

    def test_premium_does_not_bypass_brake_option_or_route_restrictions(self):
        req = self.request(premium=True, slacks=(600, 719, 720))
        for mode, expected in (('caution', {'next_day', 'within_3_days'}),
                               ('brake', {'within_3_days'})):
            desk = self.desk(premium_min_slack_minutes=600)
            desk.brake_mode = mode
            options, reason = desk.eligible_options(req, 200, 0)
            self.assertEqual(reason, '')
            self.assertEqual({o['kind'] for o in options}, expected)
        for settings, km in (({'long_max_km': 700}, 600), ({'brake_max_km': 100}, 200)):
            desk = self.desk(premium_min_slack_minutes=600, **settings)
            desk.brake_mode = 'brake'
            options, reason = desk.eligible_options(self.request(premium=True), km, 0)
            self.assertEqual((options, reason), ([], 'on-time brake'))

    def test_premium_on_second_trade_in_leg_controls_admission_and_fees(self):
        desk = self.desk(km=20, trade_ins=1, premium_min_slack_minutes=600,
                         premium_opening_fee_bps=10500)
        req = self.request(slacks=(779, 780, 781))
        second = deepcopy(req['legs'][0])
        second['car']['premium'] = True
        req['legs'].append(second)
        self.assertFalse(req['legs'][0]['car']['premium'])
        self.assertEqual([desk.slack(req, o) for o in req['options']], [599, 600, 601])
        desk.quote(req)
        self.assertEqual(set(desk.outbox[-1]['prices']), {'next_day', 'within_3_days'})
        order = self.order(desk, req)
        self.assertEqual(desk.opening_fee_for(order), 10500)
        self.assertEqual(desk.fees_for(order, 1)[0]['feeCents'], 6300)
        self.assertEqual(desk.fees_for(order, 2)[0]['feeCents'], 12600)
        blocked = self.desk(km=20, premium_min_slack_minutes=600)
        blocked.quote(req)
        self.assertEqual(self.reason(blocked), 'trade-in')

    def test_short_premium_and_long_opening_floors_combine_by_maximum(self):
        cases = (
            ({}, False, 11000),
            ({}, True, 11000),
            ({'premium_opening_fee_bps': 12000}, True, 12000),
            ({'opening_fee_bps': 13000}, True, 13000),
            ({'max_km': 30, 'long_max_km': 70}, True, 11000),
            ({'max_km': 30, 'long_max_km': 70, 'long_opening_fee_bps': 14000}, True, 14000),
            ({'max_km': 30, 'long_max_km': 70, 'long_opening_fee_bps': 9000,
              'opening_fee_bps': 12000}, True, 12000),
            ({'premium_opening_fee_bps': 15000}, True, 15000),
        )
        for overrides, premium, expected in cases:
            with self.subTest(overrides=overrides, premium=premium):
                settings = dict(short_opening_fee_bps=11000, premium_opening_fee_bps=10500)
                settings.update(overrides)
                desk = self.desk(km=40, **settings)
                req = self.request(premium=premium)
                order = self.order(desk, req)
                self.assertEqual(desk.opening_fee_for(order), expected)
                fees = [step['feeCents'] for step in desk.fees_for(order, 1)]
                self.assertEqual(fees[0], 12000 * expected // 10000)
                self.assertEqual(fees[-1], 18000)
                self.assertEqual(fees, sorted(fees))
                self.assertTrue(all(type(fee) is int and 0 < fee <= 18000 for fee in fees))

    def test_premium_long_fee_uses_larger_floor_and_disabled_segments_keep_baseline(self):
        for premium_fee, expected in ((0, 10000), (9000, 10000), (10500, 10500)):
            desk = self.desk(km=600, long_max_km=700, premium_opening_fee_bps=premium_fee)
            self.assertEqual(desk.opening_fee_for(self.order(desk, self.request(premium=True))), expected)
        ordinary = self.desk(km=44.999)
        self.assertEqual(ordinary.opening_fee_for(self.order(ordinary, self.request())), 8000)

    def test_segment_fee_and_slack_do_not_add_quote_price_factors(self):
        settings = dict(short_km=45, short_bps=9200, same_day_bps=9000, next_day_bps=11000,
                        within_3_days_bps=12000)
        base = self.desk(km=44.999, **settings)
        active = self.desk(km=44.999, short_opening_fee_bps=11000,
                           premium_opening_fee_bps=10500, premium_min_slack_minutes=600, **settings)
        req = self.request(premium=True, slacks=(600, 1000, 2000))
        for desk in (base, active):
            desk.quote(deepcopy(req))
        self.assertEqual(active.outbox, base.outbox)
        self.assertEqual(active.outbox[-1]['prices'],
                         {'same_day': 31050, 'next_day': 30362, 'within_3_days': 29808})


if __name__ == '__main__':
    unittest.main()
