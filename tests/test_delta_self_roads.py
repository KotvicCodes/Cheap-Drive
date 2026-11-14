"""Same-town repositioning still consumes the public map's driving time."""
import io
import unittest

from dispatch import Journal
from models.delta import make_delta
from tests.test_gamma_pairs import PairWorld, pair_order


class SelfRoadTests(unittest.TestCase):
    def desk(self, enabled=0):
        desk = make_delta(PairWorld(), 8, 600, Journal(io.StringIO()), pairs=1,
                          delta_pairing='extended', delta_pair_self_roads=enabled)
        desk.roads['b', 'b'] = {'km': 12, 'minutes': 25}
        return desk

    def test_map_time_counts_for_two_different_orders_in_the_same_town(self):
        for enabled, expected in ((0, 60), (1, 85)):
            desk = self.desk(enabled)
            first = pair_order(desk, 'one', 'a', 'b')
            second = pair_order(desk, 'two', 'b', 'c')
            plan, reason = desk._plan(first, second)
            self.assertIsNone(reason)
            self.assertEqual(plan.drive_minutes, expected)

    def test_real_transfer_time_rejects_a_pair_over_twelve_hours(self):
        desk = self.desk(1)
        first = pair_order(desk, 'one', 'a', 'b', deadline=6000)
        second = pair_order(desk, 'two', 'b', 'c', deadline=6000)
        for route in (('a', 'b'), ('b', 'c')):
            desk.roads[route] = {'km': 350, 'minutes': 350}
        self.assertEqual(desk._plan(first, second), (None, 'drive_too_long'))

    def test_missing_self_road_retains_synthetic_fixture_support(self):
        desk = self.desk(1)
        del desk.roads['b', 'b']
        self.assertEqual(desk._road('b', 'b'), {'km': 0, 'minutes': 0})

    def test_switch_requires_integer_zero_or_one(self):
        for value in (True, False, -1, 2, '1', None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'delta_pair_self_roads'):
                self.desk(value)
