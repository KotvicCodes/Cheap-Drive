"""Offline supply trials: public capture only, observable batch admission and fees."""
from copy import deepcopy
from dataclasses import fields
import io
import json
import unittest

from beta import BetaDesk, BetaSettings
from dispatch import Journal, handle_batch
from gamma import GammaDesk, GammaSettings
from gamma_notes import make_gamma_notes, make_gamma_notes_pairs
from spread.starter import DAY
from tests.test_gamma import GammaWorld, request


MISSING = object()


def roster(count, home='helsinki', prefix='d'):
    return [dict(id=f'{prefix}{i}', homePlaceId=home) for i in range(count)]


class SupplyWorld(GammaWorld):
    def __init__(self, drivers=MISSING):
        super().__init__()
        if drivers is not MISSING:
            self.initial_roster = drivers

    def roster(self):
        raise AssertionError('supply must never fetch the SDK roster')


class GammaSupplyTests(unittest.TestCase):
    def desk(self, drivers=MISSING, world=None, now=500, **settings):
        return GammaDesk(world or SupplyWorld(drivers), 8, now, Journal(io.StringIO()), GammaSettings(**settings))

    def quote(self, desk, identity='one', **changes):
        req = request(identity, **changes)
        desk.quote(req)
        return req

    def win(self, desk, req, at=None):
        order = dict(id=req['id'], dealerId=req['dealerId'], option=req['options'][0]['kind'],
                     priceCents=37500, deadline=req['options'][0]['deadline'],
                     legs=deepcopy(req['legs']), status='waiting', deliveredAt=[None] * len(req['legs']),
                     lastPickupAt=req['options'][0]['deadline'] - 180)
        event = dict(seq=1, at=desk.now if at is None else at, kind='order_won', order=order)
        desk.handle(event)
        return event

    def event(self, desk, kind, **data):
        desk.handle(dict(seq=1, at=desk.now, kind=kind, **data))

    def declines(self, desk):
        return [r for r in map(json.loads, desk.journal.output.getvalue().splitlines())
                if r['type'] == 'beta_decline']

    def test_neutral_defaults_preserve_beta_with_public_rosters(self):
        settings = GammaSettings()
        for name in ('supply_scale', 'town_caps', 'town_reserve_pending', 'town_starved_opening_fee_bps'):
            self.assertEqual(getattr(settings, name), 0)
        for drivers in (MISSING, None, [], roster(3), roster(850)):
            with self.subTest(drivers='missing' if drivers is MISSING else len(drivers or [])):
                beta = BetaDesk(SupplyWorld(drivers), 8, 500, Journal(io.StringIO()), BetaSettings())
                gamma = self.desk(drivers)
                for identity in ('won', 'lost', 'rejected'):
                    req = request(identity, slacks=(600, 1500, 2000))
                    for desk in (beta, gamma):
                        desk.quote(deepcopy(req))
                    self.assertEqual(gamma.outbox, beta.outbox)
                    if identity == 'won':
                        event = self.win(gamma, req)
                        beta.handle(deepcopy(event))
                        self.assertEqual(gamma.fees_for(event['order'], 1), beta.fees_for(event['order'], 1))
                    elif identity == 'lost':
                        for desk in (beta, gamma):
                            self.event(desk, 'order_lost', requestId=identity)
                    else:
                        for desk in (beta, gamma):
                            desk.read_results([desk.outbox[-1]], [{'ok': False, 'reason': 'test'}])
                    self.assertEqual(gamma.markup, beta.markup)
                    self.assertEqual(gamma.pending, beta.pending)

    def test_supply_thresholds_are_exact_and_configurable(self):
        for count, target, longest in ((709, 2900, 550), (710, 3500, 700),
                                       (809, 3500, 700), (810, 3800, 700)):
            with self.subTest(count=count):
                desk = self.desk(roster(count), supply_scale=1, long_max_km=800)
                self.assertEqual(desk.win_target(), target)
                self.assertEqual(desk.effective_long_max_km(), longest)
                self.assertTrue(desk.is_long_route(longest))
                self.assertFalse(desk.is_long_route(longest + .001))
                desk.roads['helsinki', 'tampere']['km'] = longest
                self.quote(desk, 'boundary', slacks=(2000, 2000, 2000))
                self.assertIn('boundary', desk.pending)
                desk.roads['helsinki', 'tampere']['km'] = longest + .001
                self.quote(desk, 'beyond', slacks=(2000, 2000, 2000))
                self.assertNotIn('beyond', desk.pending)
        custom = self.desk(roster(4), supply_scale=1, supply_low_roster=3, supply_high_roster=4,
                           supply_high_target_bps=4100, supply_high_long_max_km=650, long_max_km=700)
        self.assertEqual((custom.win_target(), custom.effective_long_max_km()), (4100, 650))

    def test_missing_and_none_rosters_fall_back_but_empty_is_known_zero(self):
        for drivers in (MISSING, None):
            desk = self.desk(drivers, supply_scale=1, town_caps=1, town_reserve_pending=1,
                             town_starved_opening_fee_bps=11000, win_target_bps=4100, long_max_km=800)
            self.assertIsNone(desk.supply_roster_size)
            self.assertEqual((desk.win_target(), desk.effective_long_max_km()), (4100, 800))
            req = self.quote(desk)
            self.assertIsNone(desk.town_cap_for(req))
            self.assertFalse(desk.town_pending)
            self.assertEqual(desk.opening_fee_for(dict(id=req['id'], legs=req['legs'])), 8000)
        empty = self.desk([], supply_scale=1, town_starved_opening_fee_bps=11000, long_max_km=800)
        req = self.quote(empty)
        self.assertEqual((empty.supply_roster_size, empty.win_target(), empty.effective_long_max_km()), (0, 2900, 550))
        self.assertEqual(empty.town_cap_for(req), 2)
        self.assertEqual(empty.opening_fee_for(dict(id=req['id'], legs=req['legs'])), 11000)

    def test_capture_cache_is_read_only_and_supply_is_frozen(self):
        world = SupplyWorld(roster(4))
        original = deepcopy((world.initial_roster, world.initial_map))
        desk = self.desk(world=world, supply_scale=1, town_starved_opening_fee_bps=11000)
        self.assertEqual((world.initial_roster, world.initial_map), original)
        world.initial_roster[0]['homePlaceId'] = 'tampere'
        world.initial_roster.extend(roster(1000, prefix='other'))
        for road in world.initial_map['roads']:
            road['km'] = 0
        world.initial_map['roads'].clear()
        self.assertEqual((desk.supply_roster_size, desk.near30['helsinki'], desk.near30['tampere']), (4, 4, 0))
        self.assertEqual(desk.win_target(), 2900)

    def test_actual_home_field_directed_road_boundary_self_and_no_double_count(self):
        world = SupplyWorld(roster(1) + roster(1) + roster(1, 'espoo', 'e') + roster(1, 'vantaa', 'v'))
        world.initial_map['roads'] = [r for r in world.initial_map['roads'] if r['from'] != r['to']]
        for road in world.initial_map['roads']:
            if (road['from'], road['to']) == ('espoo', 'helsinki'):
                road['km'] = 30
            elif (road['from'], road['to']) == ('vantaa', 'helsinki'):
                road['km'] = 30.001
            elif (road['from'], road['to']) == ('helsinki', 'vantaa'):
                road['km'] = 1
        desk = self.desk(world=world)
        self.assertEqual(desk.supply_roster_size, 3)
        self.assertEqual(desk.near30['helsinki'], 2)  # same town + exactly 30km
        self.assertEqual(desk.near30['vantaa'], 2)  # directed reverse distance matters

    def test_unknown_homes_conflicting_ids_and_missing_roads_are_not_zero_supply(self):
        for drivers in ([{'id': 'd'}], roster(1, 'unknown'),
                        roster(1) + roster(1, 'tampere'), [{'homePlaceId': 'helsinki'}]):
            desk = self.desk(drivers, town_caps=1, town_reserve_pending=1, town_starved_opening_fee_bps=11000)
            req = self.quote(desk)
            self.assertIsNone(desk.town_cap_for(req))
            self.assertEqual(desk.opening_fee_for(dict(id=req['id'], legs=req['legs'])), 8000)
            self.assertFalse(desk.town_pending)
        world = SupplyWorld(roster(1, 'espoo'))
        world.initial_map['roads'] = [r for r in world.initial_map['roads']
                                      if (r['from'], r['to']) != ('espoo', 'helsinki')]
        desk = self.desk(world=world, town_starved_opening_fee_bps=11000)
        self.assertIsNone(desk.near30['helsinki'])
        self.assertEqual(desk.near30['espoo'], 1)
        self.assertEqual(desk.near30['tampere'], 0)
        self.assertIsNone(desk.town_cap_for(request()))

    def test_supply_cannot_enable_long_routes_or_relax_long_guards(self):
        for settings, expected in (({}, False), ({'long_max_km': 540}, False),
                                   ({'long_max_km': 700}, True), ({'max_km': 0}, False)):
            desk = self.desk(roster(810), supply_scale=1, **settings)
            self.assertEqual(desk.is_long_route(600), expected)
            if not settings:
                desk.roads['helsinki', 'tampere']['km'] = 600
                self.quote(desk)
                self.assertEqual(self.declines(desk)[-1]['reason'], 'route too long')
        desk = self.desk(roster(709), supply_scale=1, long_max_km=700)
        desk.roads['helsinki', 'tampere']['km'] = 600
        self.quote(desk)
        self.assertEqual(self.declines(desk)[-1]['reason'], 'route too long')
        for settings, slacks, reason in (({'long_open_cap': 0}, (2000, 2000, 2000), 'long route capacity'),
                                         ({}, (2000,), 'no eligible long route option'),
                                         ({}, (2000, 1439, 1439), 'no eligible long route option')):
            desk = self.desk(roster(810), supply_scale=1, long_max_km=700, **settings)
            desk.roads['helsinki', 'tampere']['km'] = 600
            self.quote(desk, slacks=slacks)
            self.assertEqual(self.declines(desk)[-1]['reason'], reason)

    def test_brake_and_capacity_targets_take_precedence(self):
        desk = self.desk(roster(810), supply_scale=1, capacity_valve=1, long_max_km=700)
        self.assertEqual(desk.win_target(), 3400)
        desk.orders_without_driver = lambda: set(range(6))
        self.assertEqual(desk.win_target(), 3000)
        desk.orders_without_driver = lambda: set(range(11))
        self.assertEqual(desk.win_target(), 2600)
        for mode, target in (('caution', 3000), ('brake', 2200)):
            desk.brake_mode = mode
            self.assertEqual(desk.win_target(), target)
        desk.brake_mode = 'brake'
        self.assertEqual(desk.eligible_options(request(slacks=(2000, 2000, 2000)), 600, 0), ([], 'on-time brake'))
        low = self.desk(roster(709), supply_scale=1, capacity_valve=1)
        self.assertEqual(low.win_target(), 2900)

    def test_bulk_same_decision_minute_is_bounded_only_with_pending_opt_in(self):
        for reserve, admitted in ((0, 12), (1, 2)):
            desk = self.desk([], town_caps=1, town_reserve_pending=reserve)
            requests = [request(str(i)) for i in range(12)]
            handle_batch(desk, [dict(seq=i, at=500, kind='price_request', request=req)
                                for i, req in enumerate(requests)], 500)
            self.assertEqual(len(desk.pending), admitted)
            self.assertEqual(len(self.declines(desk)), 12 - admitted)
            self.assertEqual(len(desk.outbox), 12)  # every dealer receives a response
            for action in desk.outbox[admitted:]:
                self.assertEqual(action['prices'], {'same_day': 250000})
            self.win(desk, requests[0], at=515)
            self.win(desk, requests[1], at=515)
            self.quote(desk, 'after-wins')
            self.assertEqual(self.declines(desk)[-1]['reason'], 'town supply capacity')

    def test_losses_rejections_and_cancellations_release_reservations(self):
        for outcome in ('lost', 'rejected', 'cancelled'):
            with self.subTest(outcome=outcome):
                desk = self.desk([], town_caps=1, town_reserve_pending=1)
                self.quote(desk, 'a')
                self.quote(desk, 'b')
                self.quote(desk, 'blocked')
                self.assertNotIn('blocked', desk.pending)
                if outcome == 'lost':
                    self.event(desk, 'order_lost', requestId='a')
                    self.event(desk, 'order_lost', requestId='a')
                elif outcome == 'rejected':
                    action = desk.outbox[0]
                    desk.read_results([action], [{'ok': False, 'reason': 'offline rejection'}])
                    self.assertNotIn('a', desk.pending)
                    self.assertNotIn('a', desk.quote_trackers)
                else:
                    self.event(desk, 'order_cancelled', orderId='a')
                    self.event(desk, 'order_cancelled', orderId='a')
                self.quote(desk, 'replacement')
                self.assertIn('replacement', desk.pending)
                self.quote(desk, 'still-blocked')
                self.assertNotIn('still-blocked', desk.pending)
                self.assertEqual(set(desk.town_pending), {'b', 'replacement'})

    def test_win_moves_reservation_once_and_cancelled_wins_retain_daily_intake(self):
        desk = self.desk([], town_caps=1, town_reserve_pending=1)
        req = self.quote(desk, 'a')
        event = self.win(desk, req, at=515)
        desk.handle(deepcopy(event))
        self.assertFalse(desk.town_pending)
        self.event(desk, 'order_cancelled', orderId='a')
        req = self.quote(desk, 'b')
        self.assertIn('b', desk.pending)
        self.win(desk, req, at=515)
        self.quote(desk, 'c')
        self.assertNotIn('c', desk.pending)
        self.assertEqual(desk.town_wins[0]['helsinki'], 2)

    def test_wins_use_event_day_even_when_handler_clock_is_later(self):
        desk = self.desk([], town_caps=1, town_reserve_pending=1)
        reqs = [self.quote(desk, identity) for identity in ('a', 'b')]
        desk.now = DAY + 500
        for req in reqs:
            self.win(desk, req, at=515)
        self.assertEqual(desk.town_wins[0]['helsinki'], 2)
        for identity in ('new-a', 'new-b', 'new-c'):
            req = request(identity)
            req['respondBy'] += DAY
            req['options'][0]['deadline'] += DAY
            desk.quote(req)
        self.assertIn('new-a', desk.pending)
        self.assertIn('new-b', desk.pending)
        self.assertNotIn('new-c', desk.pending)

    def test_midnight_quotes_reserve_the_decision_day_not_quote_day(self):
        desk = self.desk([], now=DAY - 5, town_caps=1, town_reserve_pending=1)
        for identity in ('a', 'b', 'c'):
            req = request(identity)
            req['respondBy'] = DAY + 10
            req['options'][0]['deadline'] = DAY + 2000
            desk.quote(req)
        self.assertEqual(set(desk.pending), {'a', 'b'})
        desk.now = DAY + 1
        req = request('d')
        req['respondBy'] = DAY + 20
        req['options'][0]['deadline'] = DAY + 2000
        desk.quote(req)
        self.assertNotIn('d', desk.pending)
        self.event(desk, 'order_lost', requestId='a')
        req['id'] = 'e'
        desk.quote(req)
        self.assertIn('e', desk.pending)

    def test_town_formula_uses_first_pickup_last_delivery_and_floor(self):
        drivers = roster(8) + roster(20, 'tampere', 't') + roster(40, 'espoo', 'e')
        desk = self.desk(drivers, trade_ins=1, town_caps=1, town_reserve_pending=1)
        for i in range(4):
            req = request(str(i), delivery='espoo', slacks=(2000,))
            leg = deepcopy(req['legs'][0])
            leg['pickup']['placeId'], leg['delivery']['placeId'] = 'espoo', 'tampere'
            req['legs'].append(leg)
            desk.quote(req)
        self.assertEqual(len(desk.pending), 3)  # floor(.25 * 8 + .05 * 20)
        self.assertEqual(len(self.declines(desk)), 1)
        ordinary = self.desk(roster(7) + roster(19, 'tampere', 't'))
        self.assertEqual(ordinary.town_cap_for(request()), 2)  # floor(1.75 + .95)
        self.assertEqual(self.desk([], town_cap_min=0).town_cap_for(request()), 0)

    def test_town_counts_do_not_spend_another_pickup_towns_cap(self):
        desk = self.desk([], town_caps=1, town_reserve_pending=1)
        for identity in ('a', 'b'):
            self.win(desk, self.quote(desk, identity))
        self.quote(desk, 'full')
        self.assertNotIn('full', desk.pending)
        self.quote(desk, 'elsewhere', pickup='espoo')
        self.assertIn('elsewhere', desk.pending)

    def test_starved_fee_changes_only_driver_floor_and_keeps_urgent_schedule(self):
        base = self.desk([])
        active = self.desk([], town_starved_opening_fee_bps=11000)
        for desk in (base, active):
            req = self.quote(desk)
        self.assertEqual(base.outbox, active.outbox)
        order = dict(id=req['id'], legs=req['legs'], lastPickupAt=2000)
        for desk in (base, active):
            desk.urgent.add(req['id'])
        self.assertEqual(base.fees_for(order, 1), active.fees_for(order, 1))

    def test_starved_opening_boundary_and_max_with_short_premium_long(self):
        for count, expected in ((4, 11000), (5, 8000)):
            desk = self.desk(roster(count), town_starved_opening_fee_bps=11000)
            req = self.quote(desk)
            self.assertEqual(desk.opening_fee_for(dict(id=req['id'], legs=req['legs'])), expected)
        for overrides, expected in (({}, 11000), ({'short_opening_fee_bps': 12000}, 12000),
                                    ({'premium_opening_fee_bps': 13000}, 13000),
                                    ({'long_opening_fee_bps': 14000}, 14000),
                                    ({'opening_fee_bps': 15000}, 15000)):
            settings = dict(max_km=30, long_max_km=70, town_starved_opening_fee_bps=11000)
            settings.update(overrides)
            desk = self.desk([], **settings)
            desk.roads['helsinki', 'tampere']['km'] = 40
            req = request(slacks=(2000, 2000, 2000))
            req['legs'][0]['car']['premium'] = True
            desk.quote(req)
            order = dict(id=req['id'], legs=req['legs'], lastPickupAt=2000)
            self.assertEqual(desk.opening_fee_for(order), expected)
            fees = desk.fees_for(order, 1)
            self.assertEqual(fees[0]['feeCents'], 12000 * expected // 10000)
            self.assertEqual(fees[-1]['feeCents'], 18000)
            self.assertEqual([s['feeCents'] for s in fees], sorted(s['feeCents'] for s in fees))

    def test_reservations_are_not_taken_for_ineligible_or_duplicate_quotes(self):
        desk = self.desk([], town_caps=1, town_reserve_pending=1)
        self.quote(desk, 'ineligible', slacks=(479,))
        self.assertFalse(desk.town_pending)
        self.quote(desk, 'a')
        self.quote(desk, 'a')
        self.quote(desk, 'b')
        self.quote(desk, 'c')
        self.assertEqual(set(desk.pending), {'a', 'b'})
        self.assertEqual(len(desk.outbox), 4)
        disabled = self.desk([], town_reserve_pending=1)
        for i in range(5):
            self.quote(disabled, str(i))
        self.assertEqual(len(disabled.pending), 5)
        self.assertFalse(disabled.town_pending)

    def test_note_factories_accept_supply_settings_and_keep_batch_cap(self):
        for factory in (make_gamma_notes, make_gamma_notes_pairs):
            desk = factory(SupplyWorld([]), 8, 500, Journal(io.StringIO()),
                           supply_scale=1, town_caps=1, town_reserve_pending=1,
                           town_starved_opening_fee_bps=11000)
            for i in range(3):
                self.quote(desk, str(i), slacks=(2000,))
            self.assertEqual(len(desk.pending), 2)
            self.assertEqual(desk.win_target(), 2900)

    def test_supply_setting_validation(self):
        new_fields = [f.name for f in fields(GammaSettings)
                      if f.name.startswith(('supply_', 'town_'))]
        for name in new_fields:
            for value in (-1, True, False, 1.5, '1', None):
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(ValueError, name):
                        GammaSettings(**{name: value})
        for name in ('supply_scale', 'town_caps', 'town_reserve_pending'):
            with self.assertRaisesRegex(ValueError, name):
                GammaSettings(**{name: 2})
        for name in ('supply_low_target_bps', 'supply_mid_target_bps', 'supply_high_target_bps'):
            for value in (0, 10000):
                with self.assertRaisesRegex(ValueError, name):
                    GammaSettings(**{name: value})
        with self.assertRaisesRegex(ValueError, 'supply_low_roster'):
            GammaSettings(supply_low_roster=811)
        with self.assertRaisesRegex(ValueError, 'town_starved_opening_fee_bps'):
            GammaSettings(town_starved_opening_fee_bps=15001)


if __name__ == '__main__':
    unittest.main()
