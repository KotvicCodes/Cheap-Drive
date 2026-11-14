from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, fields
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from beta import BetaDesk, BetaSettings
from compare import load_model
from demo import sample_request
from dispatch import Journal, JournalDesk, handle_batch, play_model
from gamma import (BIG_DEALERS, DEALER_FACTORS, DELIVERY_FACTORS, LANE_FACTORS, PLACE_IDS,
                   GammaCoreDesk, GammaDesk, GammaSettings, make_gamma)
from spread.starter import DAY
from tests.test_alpha import MarketWorld
from tests.test_beta import roomy_request


ROOT = Path(__file__).resolve().parents[1]


class GammaWorld:
    """Public map and action receipts only; never connects to a client."""
    def __init__(self):
        self.initial_map = {'places': [{'id': p} for p in PLACE_IDS],
                            'roads': [{'from': a, 'to': b, 'km': 200 if a != b else 0,
                                       'minutes': 180 if a != b else 0} for a in PLACE_IDS for b in PLACE_IDS]}
        self.actions = []

    def act(self, actions):
        results = []
        for action in actions:
            self.actions.append(deepcopy(action))
            results.append({'ok': True, 'id': f'fake-{len(self.actions)}'})
        return results


def request(identity='one', dealer='D01', slacks=(600,), pickup='helsinki', delivery='tampere'):
    result = sample_request()
    result.update(id=identity, dealerId=dealer, arrivedAt=500, respondBy=515)
    for stop, place in (('pickup', pickup), ('delivery', delivery)):
        result['legs'][0][stop].update(placeId=place, hours=None, window={'from': 0, 'to': 20000})
    result['options'] = [{'kind': kind, 'deadline': 515 + 180 + slack, 'listPriceCents': price}
                         for kind, slack, price in zip(('same_day', 'next_day', 'within_3_days'),
                                                       slacks, (25000, 20001, 18000))]
    return result


class GammaTests(unittest.TestCase):
    def desk(self, **settings):
        trace = io.StringIO()
        desk = make_gamma(GammaWorld(), 8, 500, Journal(trace), **settings)
        desk.trace = trace
        return desk

    def quote(self, desk, req=None, **changes):
        req = request(**changes) if req is None else req
        desk.quote(req)
        return desk.outbox[-1]['prices']

    def record(self, desk, kind='beta_quote'):
        return [r for r in map(json.loads, desk.trace.getvalue().splitlines()) if r['type'] == kind][-1]

    def event(self, desk, kind, **data):
        desk.handle({'seq': 1, 'at': desk.now, 'kind': kind, **data})

    def win(self, desk, req):
        order = {'id': req['id'], 'dealerId': req['dealerId'], 'option': req['options'][0]['kind'],
                 'priceCents': 37500, 'deadline': req['options'][0]['deadline'],
                 'legs': deepcopy(req['legs']), 'status': 'waiting',
                 'deliveredAt': [None] * len(req['legs']), 'lastPickupAt': req['options'][0]['deadline'] - 180}
        self.event(desk, 'order_won', order=order)
        return order

    def receipt(self, desk):
        actions, desk.outbox = desk.outbox, []
        results = desk.world.act(actions)
        desk.read_results(actions, results)

    def test_defaults_send_identical_actions_through_scripted_events(self):
        for settings in ({}, {'max_km': 0, 'win_target_bps': 4200, 'opening_fee_bps': 11000}):
            beta = BetaDesk(MarketWorld(), 8, 500, Journal(io.StringIO()), BetaSettings(**settings))
            gamma = GammaDesk(MarketWorld(), 8, 500, Journal(io.StringIO()), GammaSettings(**settings))
            desks = (beta, gamma)

            def event(kind, **data):
                for desk in desks:
                    desk.handle(deepcopy({'seq': 1, 'at': desk.now, 'kind': kind, **data}))
                self.assertEqual(gamma.outbox, beta.outbox)
                self.assertEqual(gamma.markup, beta.markup)
                self.assertEqual(gamma.trust, beta.trust)

            def flush():
                self.assertEqual(gamma.outbox, beta.outbox)
                for desk in desks:
                    actions, desk.outbox = desk.outbox, []
                    desk.read_results(actions, [{'ok': True, 'id': f'gig-{i}'} for i in range(len(actions))])

            req = roomy_request()
            req['note'] = {'text': 'Manual, no plates', 'language': 'en'}
            req['options'].append({'kind': 'next_day', 'deadline': 2640, 'listPriceCents': 20001})
            event('price_request', request=req)
            flush()
            order = {'id': req['id'], 'dealerId': req['dealerId'], 'option': 'same_day',
                     'priceCents': 37500, 'deadline': 1200, 'legs': deepcopy(req['legs']),
                     'status': 'waiting', 'deliveredAt': [None], 'lastPickupAt': 1080}
            event('order_won', order=order)
            flush()
            event('gig_booked', gigId='gig-0', driverId='driver', feeCents=9600)
            event('gig_dropped', gigId='gig-0', driverId='driver')
            event('no_show', gigId='gig-0', driverId='driver')
            event('visit_failed', gigId='gig-0', orderId=req['id'], leg=0, reason='licence')
            flush()
            event('deadline_close', orderId=req['id'])
            flush()
            for kind in ('revenue', 'late_refund'):
                event('ledger', line={'kind': kind, 'orderId': req['id'], 'at': 700, 'cents': 100, 'gigId': None, 'detail': ''})
                if kind == 'revenue':
                    trusted = roomy_request()
                    trusted['id'] = 'trusted'
                    event('price_request', request=trusted)
                    event('order_lost', requestId='trusted')
            event('delivered', orderId=req['id'], leg=0, gigId='gig-0', placeId='demo-tampere')
            for identity, changes in [('lost', {}), ('trade', {'legs': req['legs'] * 2}),
                                      ('tight', {'respondBy': 1000}), ('reject', {})]:
                next_req = roomy_request()
                next_req.update(id=identity, **changes)
                event('price_request', request=next_req)
                if identity == 'reject':
                    for desk in desks:
                        desk.read_results([desk.outbox[-1]], [{'ok': False, 'reason': 'offline rejection'}])
                event('order_lost', requestId=identity)
            for desk in desks:
                desk.roads['demo-helsinki', 'demo-tampere']['km'] = 600
            far = roomy_request()
            far['id'] = 'far'
            event('price_request', request=far)
            event('order_cancelled', orderId=req['id'])
            beta_records = list(map(json.loads, beta.journal.output.getvalue().splitlines()))
            gamma_records = [r for r in map(json.loads, gamma.journal.output.getvalue().splitlines())
                             if r['type'] != 'gamma_trust']
            self.assertEqual(len(beta_records), len(gamma_records))
            for expected, actual in zip(beta_records, gamma_records):
                self.assertEqual({k: actual[k] for k in expected}, expected)

    def test_low_levels_keep_starter_and_fast_wake_declaration(self):
        for level in (1, 2, 3):
            beta = BetaDesk(MarketWorld(), level, 540, Journal(io.StringIO()))
            gamma = GammaDesk(MarketWorld(), level, 540, Journal(io.StringIO()))
            for desk in (beta, gamma):
                desk.quote(sample_request())
            self.assertEqual(beta.outbox, gamma.outbox)
        self.assertEqual(GammaDesk.__dict__['passive_wake_events'], JournalDesk.passive_wake_events)
        self.assertIs(GammaCoreDesk, GammaDesk)

    def test_tables_lane_precedence_strength_fallback_and_clamp(self):
        cases = [({}, 'D01', 'espoo', 'vantaa', 37500),
                 ({'dealer_table': 1}, 'D01', 'espoo', 'vantaa', 39000),
                 ({'place_table': 1}, 'D01', 'espoo', 'vantaa', 33750),
                 ({'dealer_table': 1, 'place_table': 1}, 'D01', 'espoo', 'vantaa', 35100),
                 ({'place_table': 1}, 'other', 'turku', 'vantaa', 35625),
                 ({'place_table': 1}, 'other', 'turku', 'oulu', 37500),
                 ({'dealer_table': 1, 'place_table': 1}, 'D08', 'espoo', 'vantaa', 33000),
                 ({'dealer_table': 1, 'place_table': 1, 'table_strength': 0}, 'D08', 'espoo', 'vantaa', 37500),
                 ({'dealer_table': 1, 'place_table': 1, 'table_strength': 50}, 'D01', 'espoo', 'vantaa', 36338)]
        for settings, dealer, pickup, delivery, price in cases:
            with self.subTest(settings=settings, dealer=dealer, pickup=pickup, delivery=delivery):
                desk = self.desk(**settings)
                self.assertEqual(self.quote(desk, dealer=dealer, pickup=pickup, delivery=delivery), {'same_day': price})
        with patch.dict(DEALER_FACTORS, {'D01': 1.20}):
            desk = self.desk(dealer_table=1, place_table=1)
            self.assertEqual(self.quote(desk, delivery='lappeenranta')['same_day'], 43125)
            self.assertEqual(self.record(desk)['tableFactor'], 1.15)

    def test_every_roadmap_factor_is_present(self):
        self.assertEqual(DEALER_FACTORS, {'D01': 1.04, 'D03': 0.97, 'D08': 0.91, 'D10': 0.95, 'D19': 0.94})
        self.assertEqual(len(DELIVERY_FACTORS), 9)
        self.assertEqual(len(LANE_FACTORS), 6)
        for delivery, factor in DELIVERY_FACTORS.items():
            desk = self.desk(place_table=1)
            self.quote(desk, pickup='oulu', delivery=delivery)
            self.assertEqual(self.record(desk)['placeFactor'], factor)
        for (pickup, delivery), factor in LANE_FACTORS.items():
            desk = self.desk(place_table=1)
            self.quote(desk, pickup=pickup, delivery=delivery)
            self.assertEqual(self.record(desk)['placeFactor'], factor)

    def test_unknown_table_place_and_missing_map_place_raise_at_construction(self):
        with patch.dict(DELIVERY_FACTORS, {'typo-town': 1.1}):
            with self.assertRaisesRegex(ValueError, 'typo-town'):
                self.desk()
        world = GammaWorld()
        world.initial_map['roads'] = [r for r in world.initial_map['roads'] if 'rauma' not in (r['from'], r['to'])]
        with self.assertRaisesRegex(ValueError, 'rauma'):
            GammaDesk(world, 8, 500, Journal(io.StringIO()), GammaSettings(place_table=1))

    def test_trust_build_all_conditions_and_per_option_discount(self):
        self.assertEqual(BIG_DEALERS, ('D01', 'D02', 'D03', 'D04'))
        for dealer, count, km, slack, day, until, discounted in [
            ('D01', 0, 200, 720, 0, 7, True), ('D04', 24, 199, 721, 1, 2, True),
            ('D01', 25, 200, 720, 0, 7, False), ('D05', 0, 200, 720, 0, 7, False),
            ('D01', 0, 201, 720, 0, 7, False), ('D01', 0, 200, 719, 0, 7, False),
            ('D01', 0, 200, 720, 2, 2, False), ('D01', 0, 200, 720, 7, 7, True)]:
            with self.subTest(dealer=dealer, count=count, km=km, slack=slack, day=day):
                desk = self.desk(trust_build_bps=1000, trust_build_until_day=until)
                desk.now = day * DAY + 500
                desk.trust[dealer] = count
                desk.roads['helsinki', 'tampere']['km'] = km
                req = request(dealer=dealer, slacks=(slack,))
                req['respondBy'] += day * DAY
                req['options'][0]['deadline'] += day * DAY
                price = self.quote(desk, req)['same_day']
                self.assertEqual(price, 37500 * (100 + count) * (90 if discounted else 100) // 10000)
                self.assertEqual(self.record(desk)['trustBuildApplied'], discounted)
        desk = self.desk(trust_build_bps=500)
        self.assertEqual(self.quote(desk, slacks=(719, 720)), {'same_day': 37500, 'next_day': 28502})

    def test_trust_guard_only_filters_risky_options_of_established_big_dealers(self):
        for dealer, count, guarded in [('D01', 10, True), ('D04', 25, True), ('D01', 9, False), ('D05', 25, False)]:
            desk = self.desk(trust_guard=1)
            desk.trust[dealer] = count
            prices = self.quote(desk, dealer=dealer, slacks=(719, 720))
            self.assertEqual(set(prices), {'next_day'} if guarded else {'same_day', 'next_day'})
            self.assertEqual(self.record(desk)['trustGuardApplied'], guarded)
        desk = self.desk(trust_guard=1)
        desk.trust['D01'] = 10
        self.quote(desk)
        self.assertEqual(self.record(desk, 'beta_decline')['reason'], 'trust guard')

    def test_trust_charge_knob_and_change_journal(self):
        for charge, expected in [(0, 37500), (50, 39375), (100, 41250), (200, 45000)]:
            desk = self.desk(trust_bps_per_order=charge)
            desk.trust['D01'] = 10
            self.assertEqual(self.quote(desk)['same_day'], expected)
        desk = self.desk()
        req = request()
        self.quote(desk, req)
        self.win(desk, req)
        for kind in ('revenue', 'revenue', 'late_refund'):
            self.event(desk, 'ledger', line={'kind': kind, 'orderId': req['id']})
        records = [r for r in map(json.loads, desk.trace.getvalue().splitlines()) if r['type'] == 'gamma_trust']
        self.assertEqual([(r['dealer'], r['before'], r['after'], r['cause']) for r in records],
                         [('D01', 0, 1, 'revenue'), ('D01', 1, 2, 'revenue'), ('D01', 2, 0, 'late_refund')])

    def test_capacity_uses_all_undelivered_legs_and_starter_booking_state(self):
        desk = self.desk(trade_ins=1)
        req = request()
        req['legs'] *= 2
        self.quote(desk, req)
        self.win(desk, req)
        self.assertEqual(desk.orders_without_driver(), {'one'})
        # Split the accepted combined gig to exercise partial booking coverage.
        desk.leg_gigs['one'] = {0: 'a', 1: 'b'}
        self.event(desk, 'gig_booked', gigId='a')
        self.assertEqual(desk.orders_without_driver(), {'one'})
        self.event(desk, 'gig_booked', gigId='b')
        self.assertEqual(desk.orders_without_driver(), set())
        for kind in ('gig_dropped', 'no_show'):
            self.event(desk, kind, gigId='a')
            self.assertEqual(desk.orders_without_driver(), {'one'})
            self.event(desk, 'gig_booked', gigId='a')
        self.event(desk, 'no_show', gigId='a')
        self.event(desk, 'delivered', orderId='one', leg=0)
        self.assertEqual(desk.orders_without_driver(), set())
        self.event(desk, 'no_show', gigId='b')
        self.assertEqual(desk.orders_without_driver(), {'one'})
        self.event(desk, 'delivered', orderId='one', leg=1)
        self.assertEqual(desk.orders_without_driver(), set())
        self.event(desk, 'order_cancelled', orderId='one')
        self.assertEqual(desk.orders_without_driver(), set())
        expired = self.desk()
        self.quote(expired)
        self.win(expired, expired.requests['one'])
        self.receipt(expired)
        gig = expired.leg_gigs['one'][0]
        self.event(expired, 'gig_booked', gigId=gig)
        self.event(expired, 'gig_expired', gigId=gig)
        self.assertEqual(expired.orders_without_driver(), {'one'})
        self.assertEqual(expired.outbox[-1]['type'], 'post')
        self.event(expired, 'order_cancelled', orderId='one')
        self.assertEqual(expired.orders_without_driver(), set())

    def test_capacity_valve_thresholds_and_decision_time_target(self):
        desk = self.desk(capacity_valve=1)
        for count, target in [(0, 3400), (5, 3400), (6, 3000), (10, 3000), (11, 2600)]:
            with patch.object(desk, 'orders_without_driver', return_value=set(map(str, range(count)))):
                self.assertEqual(desk.win_target(), target)
                req = request(identity=f'n-{count}')
                self.quote(desk, req)
                self.assertEqual(self.record(desk)['winTargetBps'], target)
                start = desk.markup
                self.event(desk, 'order_lost', requestId=req['id'])
                self.assertEqual(desk.markup, start * (1 - 0.02 * target / 10000))
        custom = self.desk(capacity_valve=1, open_low=0, open_high=1,
                           win_target_low_bps=1000, win_target_mid_bps=2000, win_target_high_bps=4000)
        for count, expected in [(0, 4000), (1, 2000), (2, 1000)]:
            with patch.object(custom, 'orders_without_driver', return_value=set(map(str, range(count)))):
                self.assertEqual(custom.win_target(), expected)
        self.assertEqual(self.desk(win_target_bps=3700).win_target(), 3700)

    def test_long_route_boundaries_options_slack_cap_and_opening_fee(self):
        for km, slack, expected in [(500, 1000, {'same_day', 'next_day', 'within_3_days'}),
                                     (501, 1439, None), (600, 1440, {'next_day', 'within_3_days'}),
                                     (601, 2000, None)]:
            desk = self.desk(long_max_km=600)
            desk.roads['helsinki', 'tampere']['km'] = km
            self.quote(desk, slacks=(slack, slack, slack))
            self.assertEqual(set(desk.outbox[-1]['prices']) if desk.pending else None, expected)
        desk = self.desk(long_max_km=600, long_markup_bps=11000, learn_bps=0)
        desk.roads['helsinki', 'tampere']['km'] = 550
        for i in range(3):
            req = request(identity=f'long-{i}', slacks=(1600, 1600))
            self.assertEqual(self.quote(desk, req), {'next_day': 33002})
            order = self.win(desk, req)
            self.assertEqual(desk.fees_for(order, 1)[0]['feeCents'], 12000)
            self.receipt(desk)
        self.assertEqual(len(desk.long_orders_without_driver()), 3)
        self.quote(desk, identity='capped', slacks=(1600, 1600))
        self.assertEqual(self.record(desk, 'beta_decline')['reason'], 'long route capacity')
        gig = desk.leg_gigs['long-0'][0]
        self.event(desk, 'gig_booked', gigId=gig)
        self.quote(desk, identity='room', slacks=(1600, 1600))
        self.assertIn('room', desk.pending)
        self.event(desk, 'gig_dropped', gigId=gig)
        self.quote(desk, identity='capped-again', slacks=(1600, 1600))
        self.assertNotIn('capped-again', desk.pending)
        custom = self.desk(max_km=150, long_max_km=250, long_options='same_day',
                           long_min_slack_minutes=700, long_opening_fee_bps=12500)
        req = request(slacks=(700, 1700))
        self.assertEqual(set(self.quote(custom, req)), {'same_day'})
        order = self.win(custom, req)
        self.assertEqual(custom.fees_for(order, 1)[0]['feeCents'], 15000)
        self.assertEqual(self.desk(max_km=250).settings.long_max_km, 250)
        off = self.desk(max_km=0, long_max_km=600)
        self.assertFalse(off.is_long_route(550))

    def test_option_and_short_route_factors_round_once(self):
        desk = self.desk(same_day_bps=9000, next_day_bps=11000, within_3_days_bps=12000,
                         short_km=201, short_bps=9500)
        self.assertEqual(self.quote(desk, slacks=(600, 1000, 2000)),
                         {'same_day': 32063, 'next_day': 31352, 'within_3_days': 30780})
        record = self.record(desk)
        self.assertEqual(record['optionFactors']['same_day']['shortBps'], 9500)
        boundary = self.desk(short_km=200, short_bps=5000)
        self.assertEqual(self.quote(boundary)['same_day'], 37500)

    def test_quote_option_modes_select_from_admissible_options(self):
        for mode, expected in [('all', {'same_day', 'next_day', 'within_3_days'}),
                               ('cheapest_only', {'within_3_days'}), ('slowest_only', {'within_3_days'}),
                               ('no_same_day', {'next_day', 'within_3_days'})]:
            self.assertEqual(set(self.quote(self.desk(quote_options=mode), slacks=(600, 1000, 2000))), expected)
        desk = self.desk(quote_options='no_same_day')
        self.assertEqual(set(self.quote(desk)), {'same_day'})
        req = request(slacks=(600, 1000, 2000))
        req['options'][0]['listPriceCents'] = 100
        req['options'][0]['deadline'] = 600
        self.assertEqual(set(self.quote(self.desk(quote_options='cheapest_only'), req)), {'within_3_days'})
        req['options'][0]['deadline'] = 10000
        self.assertEqual(set(self.quote(self.desk(quote_options='slowest_only'), req)), {'same_day'})

    def test_markup_settings_learning_bounds_and_scope_isolation(self):
        desk = self.desk(start_markup_bps=10000, markup_min_bps=9000, markup_max_bps=11000, learn_bps=10000)
        self.assertEqual(self.quote(desk)['same_day'], 25000)
        self.event(desk, 'order_lost', requestId='one')
        self.assertEqual(desk.markup, 9000)
        self.quote(desk, identity='two')
        self.win(desk, desk.requests['two'])
        self.assertEqual(desk.markup, 11000)
        unchanged = self.desk(learn_bps=0)
        self.quote(unchanged)
        self.event(unchanged, 'order_lost', requestId='one')
        self.assertEqual(unchanged.markup, 15000)
        for scope, cases in [('dealer', [('D01', 200, 'D01'), ('D02', 200, 'D02'), ('D08', 200, 'other'), ('D19', 200, 'other')]),
                             ('km', [('D01', 99, 'under_100'), ('D01', 100, '100_to_300'),
                                     ('D01', 300, '100_to_300'), ('D01', 301, 'over_300')])]:
            desk = self.desk(markup_scope=scope)
            for i, (dealer, km, tracker) in enumerate(cases):
                desk.roads['helsinki', 'tampere']['km'] = km
                self.quote(desk, identity=str(i), dealer=dealer)
                record = self.record(desk)
                self.assertEqual(record['tracker'], tracker)
                self.event(desk, 'order_lost', requestId=str(i))
                self.assertAlmostEqual(desk.markups[tracker], record['trackerMarkupBps'] * 0.994)
            self.assertEqual(desk.markup, 15000)
            self.assertEqual(set(desk.markups), {c[2] for c in cases})

    def test_rejections_declines_and_duplicate_decisions_do_not_train(self):
        desk = self.desk(markup_scope='dealer')
        self.quote(desk)
        desk.read_results([desk.outbox[-1]], [{'ok': False, 'reason': 'offline rejection'}])
        self.event(desk, 'order_lost', requestId='one')
        self.assertEqual(desk.markups['D01'], 15000)
        self.assertEqual(desk.quote_trackers, {})
        self.quote(desk, identity='tight', slacks=(479,))
        self.event(desk, 'order_lost', requestId='tight')
        self.assertEqual(desk.markups['D01'], 15000)
        self.quote(desk, identity='lost')
        self.event(desk, 'order_lost', requestId='lost')
        value = desk.markups['D01']
        self.event(desk, 'order_lost', requestId='lost')
        self.assertEqual(desk.markups['D01'], value)

    def test_freeze_floor_is_relative_to_first_quote_each_day_and_tracker(self):
        desk = self.desk(freeze_day_drop_bps=100, markup_scope='dealer')
        for i in range(5):
            self.quote(desk, identity=str(i))
            self.event(desk, 'order_lost', requestId=str(i))
        self.assertEqual(desk.markups['D01'], 14850)
        self.quote(desk, identity='other', dealer='D02')
        self.event(desk, 'order_lost', requestId='other')
        self.assertEqual(desk.markups['D02'], 14910)
        desk.now += DAY
        for i in range(5):
            req = request(identity=f'day-2-{i}')
            req['respondBy'] += DAY
            req['options'][0]['deadline'] += DAY
            self.quote(desk, req)
            self.event(desk, 'order_lost', requestId=req['id'])
        self.assertEqual(desk.markups['D01'], 14850 * 0.99)
        # An old day's floor must not constrain feedback before today's first quote.
        global_desk = self.desk(freeze_day_drop_bps=100)
        self.quote(global_desk)
        global_desk.now += DAY
        self.event(global_desk, 'order_lost', requestId='one')
        self.assertEqual(global_desk.markup, 14910)

    def test_slack_limit_trade_ins_and_decline_reasons(self):
        for settings, req, reason in [({}, request(slacks=(479,)), 'no option leaves a driver enough time'),
                                     ({'max_km': 100}, request(), 'route too long'),
                                     ({}, request(), 'trade-in')]:
            if reason == 'trade-in':
                req['legs'] *= 2
            desk = self.desk(**settings)
            self.quote(desk, req)
            self.assertEqual(self.record(desk, 'beta_decline')['reason'], reason)
            self.assertFalse(desk.pending)
        self.assertEqual(self.quote(self.desk(min_slack_minutes=600))['same_day'], 37500)
        loose = self.desk(min_slack_minutes=0)
        self.assertEqual(self.quote(loose, slacks=(1,))['same_day'], 37500)
        desk = self.desk(trade_ins=1)
        req = request(slacks=(1200,))
        req['legs'] *= 2
        self.assertEqual(self.quote(desk, req)['same_day'], 37500)
        self.win(desk, req)
        posts = [a for a in desk.world.actions if a['type'] == 'post']
        self.assertEqual(len(posts[0]['stops']), 4)
        self.assertEqual(posts[0]['schedule'][0]['feeCents'], 9600)

    def test_fee_controls_leave_rescue_unchanged_and_notes_use_beta(self):
        desk = self.desk(opening_fee_bps=6000, fee_cap_bps=20000, fee_steps=3)
        req = request()
        req['note'] = {'text': 'manual, no plates', 'language': 'en'}
        self.quote(desk, req)
        order = self.win(desk, req)
        post = desk.outbox[-1]
        self.assertEqual([s['feeCents'] for s in post['schedule']], [7200, 15600, 24000])
        self.assertEqual(post['schedule'][-1]['at'], order['lastPickupAt'] - 181)  # Beta floors the interval.
        self.assertTrue(post['audience']['manualLicence'])
        self.assertTrue(post['stops'][0]['withPlates'])
        desk.urgent.add('one')
        self.assertEqual(desk.fees_for(order, 1)[0]['feeCents'], 18000)
        flat = self.desk(fee_steps=1)
        self.quote(flat, req)
        order = self.win(flat, req)
        self.assertEqual(flat.fees_for(order, 1), [{'at': 500, 'feeCents': 9600}])

    def test_quote_journal_has_analysis_inputs(self):
        desk = self.desk(dealer_table=1, place_table=1, trust_build_bps=500, trust_guard=1)
        desk.trust['D01'] = 10
        self.quote(desk, slacks=(600, 1000), pickup='espoo', delivery='vantaa')
        record = self.record(desk)
        for name, expected in {'routeKm': 200, 'pickupPlaceId': 'espoo', 'deliveryPlaceId': 'vantaa',
                               'dealerFactor': 1.04, 'placeFactor': 0.90, 'tableFactor': 0.936,
                               'tracker': 'global', 'trackerMarkupBps': 15000, 'winTargetBps': 3000,
                               'trust': 10, 'trustBuildApplied': True, 'trustGuardApplied': True,
                               'trustGuardDropped': ['same_day'], 'longRoute': False, 'openOrders': 0,
                               'longOpenOrders': 0}.items():
            self.assertEqual(record[name], expected, name)
        self.assertEqual(record['optionFactors']['next_day'],
                         {'optionBps': 10000, 'shortBps': 10000, 'longBps': 10000, 'trustBuildBps': 9500})

    def test_model_defaults_and_factory_run_offline_full_and_fast(self):
        model = load_model(ROOT / 'models' / 'gamma.json')
        self.assertEqual(model.spec['settings'], {
            'win_target_bps': 3000, 'opening_fee_bps': 8000, 'max_km': 500, 'long_max_km': 700,
        })
        for fast in (False, True):
            world = MarketWorld()
            req = world.pending[0]['request']
            req['options'][0]['deadline'] = 1380
            for stop in ('pickup', 'delivery'):
                req['legs'][0][stop]['window']['to'] = 1380
                req['legs'][0][stop]['hours']['closes'] = 1380
            score = play_model(world, 8, Journal(io.StringIO()), model.factory, fast=fast)
            self.assertEqual(score['wonOrders'], 1)
            self.assertEqual(score['revenueCents'], 37500)

    def brake_orders(self, desk, count=1, legs=1):
        for i in range(count):
            req = request(identity=f'won-{i}', slacks=(1200, 1800, 2400))
            req['legs'] *= legs
            desk.requests[req['id']] = req
            self.win(desk, req)

    def brake_quote(self, desk, identity=None, **changes):
        req = request(identity=identity or f'quote-{len(desk.requests)}', **changes)
        shift = desk.now - 500
        req['respondBy'] += shift
        for option in req['options']:
            option['deadline'] += shift
        return self.quote(desk, req)

    def risk_event(self, desk, kind, order='won-0'):
        if kind == 'late_refund':
            self.event(desk, 'ledger', line={'kind': kind, 'orderId': order})
        elif kind == 'deadline_close':
            self.event(desk, kind, orderId=order)
        else:
            self.event(desk, kind, gigId='offline-gig')

    def test_brake_projected_thresholds_denominator_and_warned_weight(self):
        for count, late, warned, expected, projected in [
                (40, 1, 0, 'normal', 250), (40, 2, 0, 'caution', 500),
                (40, 3, 0, 'brake', 750), (41, 2, 0, 'normal', 20000 / 41),
                (4, 0, 4, 'caution', 500), (6, 0, 6, 'brake', 750),
                (1, 1, 0, 'normal', 250)]:
            with self.subTest(count=count, late=late, warned=warned):
                desk = self.desk(brake=1, brake_soft_warnings=1000, brake_hard_warnings=1000)
                self.brake_orders(desk, count)
                for i in range(late):
                    self.risk_event(desk, 'late_refund', f'won-{i}')
                for i in range(late, late + warned):
                    self.risk_event(desk, 'deadline_close', f'won-{i}')
                self.brake_quote(desk, slacks=(1200, 1800))
                record = self.record(desk)
                self.assertEqual(record['mode'], expected)
                self.assertAlmostEqual(record['projectedLateBps'], projected)
                self.assertEqual((record['won'], record['late'], record['warnedOpen']), (count, late, warned))
        for weight, expected in [(0, 'normal'), (33, 'normal'), (34, 'caution'), (100, 'brake')]:
            desk = self.desk(brake=1, brake_warned_weight_pct=weight, brake_min_orders=10,
                             brake_soft_bps=335, brake_hard_bps=900)
            self.brake_orders(desk)
            self.risk_event(desk, 'deadline_close')
            self.brake_quote(desk, slacks=(1200, 1800))
            self.assertEqual(self.record(desk)['mode'], expected)

    def test_brake_warning_and_drop_thresholds_and_trailing_event_clock(self):
        for warnings, expected in [(0, 'normal'), (5, 'normal'), (6, 'caution'), (11, 'caution'), (12, 'brake')]:
            desk = self.desk(brake=1)
            for _ in range(warnings):
                self.risk_event(desk, 'deadline_close', 'unknown')
            self.brake_quote(desk, slacks=(1200, 1800))
            self.assertEqual(self.record(desk)['mode'], expected)
            self.assertEqual(self.record(desk)['warn24'], warnings)
        desk = self.desk(brake=1, brake_soft_drops=3, brake_hold_minutes=0)
        self.risk_event(desk, 'gig_dropped')
        desk.now += 1
        self.risk_event(desk, 'no_show')
        self.brake_quote(desk)
        self.assertEqual(self.record(desk)['mode'], 'normal')
        self.risk_event(desk, 'gig_dropped')
        self.brake_quote(desk, slacks=(1200, 1800))
        self.assertEqual((self.record(desk)['mode'], self.record(desk)['drops24']), ('caution', 3))
        desk.now = 500 + DAY
        self.brake_quote(desk)
        self.assertEqual((self.record(desk)['mode'], self.record(desk)['drops24']), ('normal', 2))
        desk.now += 1
        self.brake_quote(desk)
        self.assertEqual(self.record(desk)['drops24'], 0)
        # Event timestamps, not the later batch clock, determine window membership.
        desk.handle({'kind': 'deadline_close', 'at': 500, 'orderId': 'unknown'})
        self.brake_quote(desk)
        self.assertEqual(self.record(desk)['warn24'], 0)

    def test_brake_counts_distinct_orders_partial_delivery_refunds_and_cancellation(self):
        desk = self.desk(brake=1, trade_ins=1, brake_hold_minutes=0)
        self.brake_orders(desk, 2, legs=2)
        self.risk_event(desk, 'deadline_close')
        self.risk_event(desk, 'deadline_close')
        self.event(desk, 'delivered', orderId='won-0', leg=0)
        self.assertEqual(desk.brake_inputs()['warnedOpen'], 1)
        self.event(desk, 'delivered', orderId='won-0', leg=1)
        self.assertEqual(desk.brake_inputs()['warnedOpen'], 0)
        self.risk_event(desk, 'deadline_close', 'won-1')
        self.risk_event(desk, 'late_refund', 'won-1')
        self.risk_event(desk, 'late_refund', 'won-1')
        inputs = desk.brake_inputs()
        self.assertEqual((inputs['won'], inputs['late'], inputs['warnedOpen'], inputs['warn24']), (2, 1, 0, 3))
        self.event(desk, 'order_cancelled', orderId='won-1')
        self.risk_event(desk, 'late_refund', 'won-1')
        self.risk_event(desk, 'deadline_close', 'won-0')
        self.event(desk, 'order_cancelled', orderId='won-0')
        self.brake_quote(desk)
        record = self.record(desk)
        self.assertEqual((record['won'], record['late'], record['warnedOpen']), (0, 0, 0))
        # Rolling event counts retain the events even after their orders cancel.
        self.assertEqual(record['warn24'], 4)

    def test_brake_hysteresis_tracks_last_condition_between_quotes(self):
        desk = self.desk(brake=1, brake_soft_bps=100, brake_hard_bps=200)
        self.brake_orders(desk)
        self.risk_event(desk, 'late_refund')
        self.brake_quote(desk, slacks=(1200, 1800))
        self.assertEqual(self.record(desk)['mode'], 'brake')
        desk.now += 1000  # No quotes while the hard condition continues to hold.
        self.event(desk, 'order_cancelled', orderId='won-0')
        desk.now += 239
        self.brake_quote(desk, slacks=(1200, 1800))
        self.assertEqual(self.record(desk)['mode'], 'brake')
        desk.now += 1
        self.brake_quote(desk)
        self.assertEqual(self.record(desk)['mode'], 'normal')
        transitions = [r for r in map(json.loads, desk.trace.getvalue().splitlines()) if r['type'] == 'gamma_brake']
        self.assertEqual([(r['from'], r['to']) for r in transitions], [('normal', 'brake'), ('brake', 'normal')])
        self.assertEqual(transitions[-1]['at'], 1740)
        self.assertEqual(transitions[-1]['late'], 0)

    def test_brake_hysteresis_warning_expiry_and_severity_downgrade(self):
        desk = self.desk(brake=1, brake_soft_warnings=1, brake_hard_warnings=2)
        self.risk_event(desk, 'deadline_close', 'unknown')
        desk.now += 100
        self.risk_event(desk, 'deadline_close', 'unknown')
        self.brake_quote(desk, slacks=(1200, 1800))
        self.assertEqual(self.record(desk)['mode'], 'brake')
        desk.now = 500 + DAY + 239
        self.brake_quote(desk, slacks=(1200, 1800))
        self.assertEqual(self.record(desk)['mode'], 'brake')
        desk.now += 1
        self.brake_quote(desk, slacks=(1200, 1800))
        self.assertEqual(self.record(desk)['mode'], 'caution')
        self.assertEqual(desk.markup, 16200)
        self.brake_quote(desk, slacks=(1200, 1800))
        self.assertEqual(desk.markup, 16200)
        desk.now = 600 + DAY + 240
        self.brake_quote(desk)
        self.assertEqual(self.record(desk)['mode'], 'normal')
        immediate = self.desk(brake=1, brake_hold_minutes=0, brake_soft_warnings=1)
        self.risk_event(immediate, 'deadline_close', 'unknown')
        self.brake_quote(immediate, slacks=(1200, 1800))
        immediate.now += DAY
        self.brake_quote(immediate)
        self.assertEqual(self.record(immediate)['mode'], 'normal')

    def test_brake_targets_override_capacity_and_can_be_ablated(self):
        for capacity in (0, 1):
            for warnings, target in [(0, 3400 if capacity else 3800), (6, 3000), (12, 2200)]:
                desk = self.desk(brake=1, capacity_valve=capacity, win_target_bps=3800)
                for _ in range(warnings):
                    self.risk_event(desk, 'deadline_close', 'unknown')
                self.brake_quote(desk, slacks=(1200, 1800))
                self.assertEqual(self.record(desk)['winTargetBps'], target)
                identity = desk.outbox[-1]['requestId']
                markup = desk.markup
                self.event(desk, 'order_lost', requestId=identity)
                self.assertAlmostEqual(desk.markup, markup * (1 - 0.02 * target / 10000))
        desk = self.desk(brake=1, brake_soft_warnings=1, brake_hard_warnings=2, win_target_bps=3800,
                         brake_caution_target_bps=3800, brake_target_bps=3800)
        for _ in range(2):
            self.risk_event(desk, 'deadline_close', 'unknown')
            self.brake_quote(desk, slacks=(1200, 1800))
            self.assertEqual(desk.win_target(), 3800)

    def test_brake_downgrade_preserves_all_tracker_markups_and_reescalation_bumps(self):
        for scope, trackers in [('global', ['global']), ('dealer', [*BIG_DEALERS, 'other']),
                                ('km', ['under_100', '100_to_300', 'over_300'])]:
            with self.subTest(scope=scope):
                desk = self.desk(brake=1, markup_scope=scope, brake_soft_warnings=1, brake_hard_warnings=2)
                self.risk_event(desk, 'deadline_close', 'unknown')
                desk.now += 100
                self.risk_event(desk, 'deadline_close', 'unknown')
                desk.update_brake()
                self.assertEqual([desk.tracker_markup(t) for t in trackers], [16200] * len(trackers))
                desk.now = 500 + DAY + 240
                self.assertEqual(desk.update_brake()['mode'], 'caution')
                self.assertEqual([desk.tracker_markup(t) for t in trackers], [16200] * len(trackers))
                for _ in range(2):
                    self.risk_event(desk, 'deadline_close', 'unknown')
                self.assertEqual(desk.update_brake()['mode'], 'brake')
                for tracker in trackers:
                    self.assertAlmostEqual(desk.tracker_markup(tracker), 17496)

    def test_brake_entry_bumps_once_each_entry_and_bounds_every_tracker(self):
        for scope, trackers in [('global', []), ('dealer', [*BIG_DEALERS, 'other']),
                                ('km', ['under_100', '100_to_300', 'over_300'])]:
            with self.subTest(scope=scope):
                desk = self.desk(brake=1, markup_scope=scope, brake_soft_warnings=1, brake_hard_warnings=2,
                                 brake_hold_minutes=0, learn_bps=0, markup_max_bps=17000)
                self.risk_event(desk, 'deadline_close', 'unknown')
                self.brake_quote(desk, slacks=(1200, 1800))
                self.assertEqual(desk.markup, 15450)
                for tracker in trackers:
                    self.assertEqual(desk.tracker_markup(tracker), 15450)
                self.brake_quote(desk, slacks=(1200, 1800))
                self.assertEqual(desk.markup, 15450)
                self.risk_event(desk, 'deadline_close', 'unknown')
                self.brake_quote(desk, slacks=(1200, 1800))
                self.assertEqual(desk.markup, 16686)
                self.brake_quote(desk, slacks=(1200, 1800))
                self.assertEqual(desk.markup, 16686)
                desk.now += DAY
                self.brake_quote(desk)
                self.risk_event(desk, 'deadline_close', 'unknown')
                self.brake_quote(desk, slacks=(1200, 1800))
                self.assertEqual(desk.markup, 17000)
                for tracker in trackers:
                    self.assertEqual(desk.tracker_markup(tracker), 17000)
        # Both bounds apply even to unusual experimental multipliers.
        desk = self.desk(brake=1, brake_soft_warnings=1, brake_caution_bump_bps=1)
        self.risk_event(desk, 'deadline_close', 'unknown')
        self.brake_quote(desk, slacks=(1200, 1800))
        self.assertEqual(desk.markup, desk.settings.markup_min_bps)

    def test_brake_bump_ablation_and_custom_multipliers(self):
        for caution, hard, expected in [(10000, 10000, (15000, 15000)), (11000, 12000, (16500, 19800))]:
            desk = self.desk(brake=1, brake_soft_warnings=1, brake_hard_warnings=2,
                             brake_caution_bump_bps=caution, brake_bump_bps=hard)
            for markup in expected:
                self.risk_event(desk, 'deadline_close', 'unknown')
                self.brake_quote(desk, slacks=(1200, 1800))
                self.assertEqual(desk.markup, markup)

    def test_brake_option_filters_boundaries_ablation_and_selection(self):
        for warnings, changes, slacks, expected in [
                (6, {}, (719, 600, 720), {'next_day', 'within_3_days'}),
                (6, {}, (720, 600, 720), {'same_day', 'next_day', 'within_3_days'}),
                (6, {'brake_caution_same_day_slack_minutes': 0}, (600, 600), {'same_day', 'next_day'}),
                (12, {}, (1200, 719, 720), {'within_3_days'}),
                (12, {'brake_drop_same_day': 0}, (600, 719, 720), {'same_day', 'within_3_days'}),
                (12, {'brake_min_slack_minutes': 0}, (1200, 600), {'next_day'}),
                (12, {'brake_drop_same_day': 0, 'brake_min_slack_minutes': 0}, (600, 600), {'same_day', 'next_day'}),
                (6, {'quote_options': 'cheapest_only'}, (600, 800), {'next_day'})]:
            with self.subTest(warnings=warnings, changes=changes, slacks=slacks):
                desk = self.desk(brake=1, **changes)
                for _ in range(warnings):
                    self.risk_event(desk, 'deadline_close', 'unknown')
                self.assertEqual(set(self.brake_quote(desk, slacks=slacks)), expected)
        for warnings in (6, 12):
            desk = self.desk(brake=1)
            for _ in range(warnings):
                self.risk_event(desk, 'deadline_close', 'unknown')
            prices = self.brake_quote(desk, slacks=(600,))
            self.assertEqual(prices, {'same_day': 250000})
            record = self.record(desk, 'beta_decline')
            self.assertEqual(record['reason'], 'on-time brake')
            self.assertEqual(record['warn24'], warnings)
            self.assertFalse(desk.pending)

    def test_brake_long_route_block_and_all_route_cap_with_ablations(self):
        for warnings, blocked in [(0, False), (6, False), (12, True)]:
            for blocks in (0, 1):
                desk = self.desk(brake=1, long_max_km=600, brake_blocks_long=blocks)
                desk.roads['helsinki', 'tampere']['km'] = 600
                for _ in range(warnings):
                    self.risk_event(desk, 'deadline_close', 'unknown')
                self.brake_quote(desk, slacks=(1800, 1800))
                if blocks and blocked:
                    self.assertEqual(self.record(desk, 'beta_decline')['reason'], 'on-time brake')
                else:
                    self.assertTrue(desk.pending)
        for max_km in (0, 500):
            for warnings, cap, km, accepted in [(6, 300, 301, True), (12, 300, 300, True),
                                               (12, 300, 301, False), (12, 0, 400, True)]:
                desk = self.desk(brake=1, max_km=max_km, brake_max_km=cap)
                desk.roads['helsinki', 'tampere']['km'] = km
                for _ in range(warnings):
                    self.risk_event(desk, 'deadline_close', 'unknown')
                self.brake_quote(desk, slacks=(1800, 1800))
                self.assertEqual(bool(desk.pending), accepted)
                if not accepted:
                    self.assertEqual(self.record(desk, 'beta_decline')['reason'], 'on-time brake')

    def test_caution_long_routes_still_require_all_long_route_guards(self):
        for settings, reason in [({}, None), ({'long_max_km': 599}, 'route too long'),
                                 ({'long_min_slack_minutes': 1801}, 'no eligible long route option'),
                                 ({'long_open_cap': 0}, 'long route capacity'),
                                 ({'long_options': 'within_3_days'}, 'no eligible long route option')]:
            with self.subTest(settings=settings):
                desk = self.desk(brake=1, **({'long_max_km': 600} | settings))
                desk.roads['helsinki', 'tampere']['km'] = 600
                for _ in range(6):
                    self.risk_event(desk, 'deadline_close', 'unknown')
                self.brake_quote(desk, slacks=(1800, 1800))
                self.assertEqual(bool(desk.pending), reason is None)
                if reason:
                    self.assertEqual(self.record(desk, 'beta_decline')['reason'], reason)

    def test_same_day_slack_inherits_general_setting_and_is_independent(self):
        self.assertEqual(GammaSettings(min_slack_minutes=123).same_day_min_slack_minutes, 123)
        for general, same_day, expected in [(480, 720, {'next_day'}), (720, 480, {'same_day'}),
                                             (480, 480, {'same_day', 'next_day'})]:
            desk = self.desk(min_slack_minutes=general, same_day_min_slack_minutes=same_day)
            self.assertEqual(set(self.brake_quote(desk, slacks=(600, 600))), expected)

    def test_brake_batch_events_use_prior_events_and_journal_each_transition(self):
        desk = self.desk(brake=1, brake_soft_bps=200, brake_hard_bps=400, brake_hold_minutes=0)
        self.brake_orders(desk, 3)
        events = [
            {'kind': 'ledger', 'line': {'kind': 'late_refund', 'orderId': 'won-0'}},
            {'kind': 'ledger', 'line': {'kind': 'late_refund', 'orderId': 'won-0'}},
            {'kind': 'deadline_close', 'orderId': 'won-1'},
            {'kind': 'gig_dropped', 'gigId': 'unknown'},
            {'kind': 'no_show', 'gigId': 'unknown'},
            {'kind': 'price_request', 'request': request('caution', slacks=(1200, 1800))},
            {'kind': 'ledger', 'line': {'kind': 'late_refund', 'orderId': 'won-1'}},
            {'kind': 'price_request', 'request': request('brake', slacks=(1200, 1800))},
            {'kind': 'order_cancelled', 'orderId': 'won-0'},
            {'kind': 'order_cancelled', 'orderId': 'won-1'},
            {'kind': 'price_request', 'request': request('normal', slacks=(1200, 1800))}]
        handle_batch(desk, [{'seq': i, 'at': 500, **event} for i, event in enumerate(events)], 500)
        records = list(map(json.loads, desk.trace.getvalue().splitlines()))
        quotes = [r for r in records if r['type'] == 'beta_quote']
        self.assertEqual([r['mode'] for r in quotes], ['caution', 'brake', 'normal'])
        self.assertEqual([(r['late'], r['warnedOpen'], r['won']) for r in quotes], [(1, 1, 3), (2, 0, 3), (0, 0, 1)])
        self.assertTrue(all(r['drops24'] == 2 and r['warn24'] == 1 for r in quotes))
        transitions = [r for r in records if r['type'] == 'gamma_brake']
        self.assertEqual([(r['from'], r['to']) for r in transitions],
                         [('normal', 'caution'), ('caution', 'brake'), ('brake', 'normal')])
        for transition, quote in zip(transitions, quotes):
            for key in ('at', 'projectedLateBps', 'warn24', 'drops24', 'late', 'warnedOpen', 'won'):
                self.assertEqual(transition[key], quote[key])

    def test_disabled_brake_ignores_risk_and_keeps_all_effects_off(self):
        desk = self.desk(long_max_km=600, win_target_bps=3800, brake_max_km=1)
        desk.roads['helsinki', 'tampere']['km'] = 600
        for _ in range(20):
            self.risk_event(desk, 'deadline_close', 'unknown')
            self.risk_event(desk, 'gig_dropped')
        self.brake_quote(desk, slacks=(1800, 1800))
        self.assertEqual(self.record(desk)['mode'], 'normal')
        self.assertEqual(desk.markup, 15000)
        self.assertEqual(desk.win_target(), 3800)
        self.assertTrue(desk.pending)
        records = list(map(json.loads, desk.trace.getvalue().splitlines()))
        self.assertFalse(any(r['type'] == 'gamma_brake' for r in records))

    def test_brake_settings_validation(self):
        for changes in [{'brake_min_orders': 0}, {'brake_warned_weight_pct': 101},
                        {'brake_caution_bump_bps': 0}, {'brake_bump_bps': 0},
                        {'brake_caution_target_bps': 0}, {'brake_caution_target_bps': 10000},
                        {'brake_target_bps': 0}, {'brake_target_bps': 10000},
                        {'brake': 2}, {'brake_drop_same_day': 2}, {'brake_blocks_long': 2}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                GammaSettings(**changes)

    def test_settings_are_frozen_validated_and_json_serializable(self):
        settings = GammaSettings()
        json.dumps(asdict(settings))
        with self.assertRaises(FrozenInstanceError):
            settings.max_km = 600
        for field in fields(settings):
            if isinstance(getattr(settings, field.name), int):
                for value in (-1, True, 1.5, '1'):
                    with self.subTest(name=field.name, value=value), self.assertRaises(ValueError):
                        GammaSettings(**{field.name: value})
        for changes in [{'win_target_bps': 0}, {'win_target_bps': 10000}, {'win_target_low_bps': 0},
                        {'win_target_mid_bps': 10000}, {'win_target_high_bps': 2000},
                        {'opening_fee_bps': 0}, {'opening_fee_bps': 16000}, {'fee_steps': 0},
                        {'long_opening_fee_bps': 0}, {'long_opening_fee_bps': 16000},
                        {'markup_min_bps': 0}, {'start_markup_bps': 11000}, {'markup_max_bps': 14000},
                        {'learn_bps': 10001}, {'trust_build_bps': 10000}, {'table_strength': 101},
                        {'trust_build_until_day': 0}, {'trust_build_until_day': 8}, {'freeze_day_drop_bps': 10001},
                        {'open_low': 11}, {'same_day_bps': 0}, {'next_day_bps': 0}, {'within_3_days_bps': 0},
                        {'short_bps': 0}, {'long_markup_bps': 0}, {'quote_options': 'random'},
                        {'quote_options': 1}, {'markup_scope': 'world'}, {'markup_scope': 0},
                        {'long_options': ''}, {'long_options': 'same_day,same_day'}, {'long_options': 'unknown'},
                        {'long_options': []}] + [{name: 2} for name in ('trade_ins', 'dealer_table', 'place_table', 'trust_guard', 'capacity_valve')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                GammaSettings(**changes)


if __name__ == '__main__':
    unittest.main()
