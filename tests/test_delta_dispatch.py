"""Offline contracts for independently switchable dispatcher repairs."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import unittest

from delta import make_delta
from dispatch import Journal, play_model
from spread.starter import DAY, Retry
from tests.test_delta import HOURS
from tests.test_gamma_pairs import PairWorld
from tests.test_notes import order_for, request
from tests.test_performance import LossWorld


def desk_and_order(*, now=600, text='', km=100, deadline=2 * DAY + 1080,
                   hours=None, **switches):
    world = PairWorld()
    for road in world.initial_map['roads']:
        if road['from'] == 'a' and road['to'] == 'b':
            road['km'] = km
    desk = make_delta(world, 8, now, Journal(io.StringIO()), **switches)
    req = request(text, deadlines=(deadline,), hours=hours)
    req['legs'][0]['pickup']['placeId'] = 'a'
    req['legs'][0]['delivery']['placeId'] = 'b'
    req['legs'][0]['car'].update(electric=True, chargePercent=20)
    desk.requests[req['id']] = req
    order = order_for(req)
    desk.orders[order['id']] = order
    return desk, order


class SwitchContract:
    switch = None

    def test_explicit_off_is_byte_identical_with_existing_experiments(self):
        for fast in (False, True):
            runs = []
            for knobs in ({}, {self.switch: 0}):
                world, stream = LossWorld(), io.StringIO()
                with redirect_stdout(io.StringIO()):
                    score = play_model(world, 8, Journal(stream),
                                       lambda w, l, n, j: make_delta(
                                           w, l, n, j, pairs=1, delta_note_fixes=1,
                                           delta_rescue_windows=1, **knobs), fast=fast)
                runs.append((world.sent, world.calls, score, stream.getvalue().encode()))
            self.assertEqual(*runs)
        actions = []
        for knobs in ({}, {self.switch: 0}):
            desk, order = desk_and_order(delta_note_fixes=1, delta_rescue_windows=1, **knobs)
            desk.post(order, [0])
            actions.append(deepcopy(desk.outbox))
        self.assertEqual(*actions)

    def test_switch_requires_integer_zero_or_one(self):
        for value in (True, False, 2, -1, '1', None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, self.switch):
                desk_and_order(**{self.switch: value})


class DeltaEVRuleTests(SwitchContract, unittest.TestCase):
    switch = 'delta_ev_rule'

    def test_exact_road_distance_and_charge_thresholds(self):
        for km in (0, 199.9, 200, 200.1, 500):
            for electric, percent in ((True, 0), (True, 29), (True, 30),
                                      (True, None), (False, 20)):
                with self.subTest(km=km, electric=electric, percent=percent):
                    desk, order = desk_and_order(km=km, delta_ev_rule=1)
                    leg = order['legs'][0]
                    leg['car'].update(electric=electric, chargePercent=percent)
                    self.assertEqual(desk._needs_charging(leg),
                                     electric and percent is not None and percent < 30 and km > 200)

    def test_short_route_recovers_40_minutes_in_post_and_latest_route(self):
        routes, stops = [], []
        for enabled in (0, 1):
            desk, order = desk_and_order(delta_ev_rule=enabled)
            facts = desk.note_facts(desk.requests[order['id']])
            stops.append(desk._post_windows(order, [0], facts, Retry()))
            routes.append(desk._latest_note_route(desk.requests[order['id']], 1080))
        self.assertTrue(stops[0][0]['withCharging'])
        self.assertFalse(stops[1][0]['withCharging'])
        self.assertEqual(stops[0][1]['window']['from'] - stops[1][1]['window']['from'], 40)
        self.assertEqual(routes[1][0] - routes[0][0], 40)

    def test_long_route_keeps_charge_time_hours_notes_and_private_pickup_slot(self):
        for km, charge in ((200, 0), (201, 40)):
            desk, order = desk_and_order(
                km=km, text='Ready tomorrow 10:00. Destination closes at 16:00',
                hours=HOURS, delta_ev_rule=1, delta_note_fixes=1, delta_rescue_windows=1)
            pickup = order['legs'][0]['pickup']
            pickup.update(privateAddress=True, window={'from': DAY + 600, 'to': DAY + 660})
            facts = desk.note_facts(desk.requests[order['id']])
            stops = desk._post_windows(order, [0], facts, Retry())
            self.assertEqual(stops[0]['window'], {'from': DAY + 600, 'to': DAY + 660})
            self.assertEqual(stops[0]['withCharging'], bool(charge))
            self.assertEqual(stops[1]['window'], {'from': DAY + 630 + charge, 'to': DAY + 960})
            self.assertLessEqual(stops[1]['window']['to'], order['deadline'])
            desk.now = DAY + 661
            self.assertIsNone(desk._post_windows(order, [0], facts, Retry()))


if __name__ == '__main__':
    unittest.main()
