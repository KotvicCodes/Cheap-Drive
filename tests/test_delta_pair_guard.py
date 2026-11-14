"""Selective rescue gates keep fresh pairing and protect aged waiting work."""
import io
import unittest

from dispatch import Journal
from models.delta import make_delta
from tests.test_gamma_pairs import PairWorld, pair_order


class PairGuardTests(unittest.TestCase):
    def desk(self, **settings):
        return make_delta(PairWorld(), 8, 600, Journal(io.StringIO()), pairs=1, **settings)

    def waiting(self, desk, *, deadline=3000):
        order = pair_order(desk, 'one', deadline=deadline)
        desk.orders['one'] = order
        desk.leg_gigs['one'] = {0: 'g'}
        desk.first_posted['one'] = 360
        return order

    def test_age_boundary_is_inclusive_and_new_orders_stay_eligible(self):
        desk = self.desk(delta_pair_max_wait_minutes=240)
        order = self.waiting(desk)
        self.assertTrue(desk._eligible(order))
        desk.now += 1
        self.assertFalse(desk._eligible(order))
        desk.leg_gigs.clear()
        self.assertTrue(desk._eligible(order))

    def test_slack_boundary_uses_actual_latest_pickup_opportunity(self):
        desk = self.desk(delta_pair_min_slack_minutes=600)
        order = self.waiting(desk)
        order['lastPickupAt'] = 1200
        self.assertTrue(desk._eligible(order))
        desk.now += 1
        self.assertFalse(desk._eligible(order))
        order['lastPickupAt'] = 2000
        desk.requests['one']['note'] = {'text': 'Collect Monday before 14:00'}
        self.assertFalse(desk._eligible(order))

    def test_disabled_gates_preserve_aged_waiting_pairing_and_booked_rules(self):
        desk = self.desk()
        order = self.waiting(desk)
        desk.first_posted['one'] = 0
        order['lastPickupAt'] = 700
        self.assertTrue(desk._eligible(order))
        desk.booked.add('g')
        self.assertFalse(desk._eligible(order))

    def test_controls_reject_boolean_negative_and_nonnumeric_values(self):
        for name in ('delta_pair_max_wait_minutes', 'delta_pair_min_slack_minutes'):
            for value in (True, False, -1, '240', None):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, name):
                    self.desk(**{name: value})
