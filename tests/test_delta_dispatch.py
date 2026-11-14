"""Offline contracts for independently switchable dispatcher repairs."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import unittest

from delta import make_delta, rescue_window
from dispatch import Journal, play_model
from notes import NoteFacts
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


class DeltaPrivateDeliveryTests(SwitchContract, unittest.TestCase):
    switch = 'delta_private_delivery_rescue'

    def test_rescue_works_independently_and_keeps_original_deadline_and_slot(self):
        for rescue in (0, 1):
            desk, order = desk_and_order(now=DAY + 800, deadline=DAY + 750,
                                        delta_private_delivery_rescue=1,
                                        delta_rescue_windows=rescue)
            delivery = order['legs'][0]['delivery']
            delivery.update(privateAddress=True, window={'from': DAY + 660, 'to': DAY + 720})
            original = deepcopy(order)
            desk.post(order, [0])
            self.assertEqual(len(desk.outbox), 1)
            self.assertGreater(desk.outbox[0]['stops'][1]['window']['from'], order['deadline'])
            self.assertEqual(order, original)
        desk, order = desk_and_order(now=DAY + 800, deadline=DAY + 750, delta_rescue_windows=1)
        order['legs'][0]['delivery'].update(
            privateAddress=True, window={'from': DAY + 660, 'to': DAY + 720})
        desk.post(order, [0])
        self.assertEqual(desk.outbox, [])

    def test_on_time_private_delivery_keeps_booked_hour(self):
        desk, order = desk_and_order(deadline=900, delta_private_delivery_rescue=1)
        order['legs'][0]['delivery'].update(privateAddress=True, window={'from': 810, 'to': 870})
        desk.post(order, [0])
        self.assertEqual(desk.outbox[0]['stops'][1]['window'], {'from': 810, 'to': 870})

    def test_private_pickup_never_extends_with_either_rescue_setting(self):
        for rescue in (0, 1):
            desk, order = desk_and_order(now=801, delta_private_delivery_rescue=1,
                                        delta_rescue_windows=rescue)
            order['legs'][0]['pickup'].update(
                privateAddress=True, window={'from': 700, 'to': 800})
            desk.post(order, [0])
            self.assertEqual(desk.outbox, [])

    def test_rescue_retains_readiness_recurring_hours_and_weekdays(self):
        place = dict(privateAddress=True, hours=deepcopy(HOURS),
                     window={'from': 4 * DAY + 900, 'to': 4 * DAY + 960})
        facts = NoteFacts(delivery_ready_at=7 * DAY + 600, delivery_opens=660,
                          delivery_closes=900, delivery_weekdays=(0, 1, 2, 3, 4),
                          deadline=4 * DAY + 990)
        self.assertEqual(rescue_window(place, 'delivery', facts, 4 * DAY + 1000,
                                       9 * DAY, private_delivery=True),
                         (7 * DAY + 660, 7 * DAY + 900))
        self.assertIsNone(rescue_window(place, 'delivery', facts, 4 * DAY + 1000,
                                       7 * DAY + 659, private_delivery=True))


if __name__ == '__main__':
    unittest.main()
