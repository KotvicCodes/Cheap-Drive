"""An optional driving cushion must never extend or destroy a legal window."""
import io
import unittest

from dispatch import Journal
from models.delta import make_delta
from spread.starter import Retry
from tests.test_gamma_pairs import PairWorld, pair_order


class PickupBufferTests(unittest.TestCase):
    def action(self, buffer=0, *, deadline=1200, pickup_from=480, private=False):
        desk = make_delta(PairWorld(), 8, 600, Journal(io.StringIO()),
                          delta_wide_windows=1, delta_wide_pickup_buffer_minutes=buffer)
        order = pair_order(desk, 'one', deadline=deadline, private=private)
        order['legs'][0]['pickup']['window']['from'] = pickup_from
        desk.post(order, [0], Retry())
        return desk._outbox[-1]

    def test_trims_pickup_tail_only_and_keeps_delivery_window(self):
        baseline, buffered = self.action(), self.action(30)
        self.assertEqual(baseline['stops'][0]['window']['to'], 1170)
        self.assertEqual(buffered['stops'][0]['window']['to'], 1140)
        self.assertEqual(baseline['stops'][1], buffered['stops'][1])
        self.assertEqual(baseline['schedule'], buffered['schedule'])

    def test_tight_window_falls_back_without_extending_private_slots(self):
        baseline = self.action(0, deadline=650, pickup_from=610, private=True)
        buffered = self.action(30, deadline=650, pickup_from=610, private=True)
        self.assertEqual(buffered, baseline)
        window = buffered['stops'][0]['window']
        self.assertEqual((window['from'], window['to']), (610, 620))

    def test_validation_requires_nonnegative_integer(self):
        for value in (True, False, -1, '30', None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'delta_wide_pickup_buffer_minutes'):
                self.action(value)
