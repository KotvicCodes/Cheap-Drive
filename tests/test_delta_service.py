"""Service protection contracts, including neutral behavior and recovery."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import unittest

from dispatch import Journal, play_model
from models.delta import make_delta
from recovery import model_state, restore_state
from tests.test_gamma_pairs import PairWorld, pair_order
from tests.test_performance import LossWorld


class DeltaServiceTests(unittest.TestCase):
    def desk(self, **settings):
        return make_delta(PairWorld(), 8, 600, Journal(io.StringIO()),
                          win_target_bps=4200, **settings)

    def add_order(self, desk, identity, deadline=6000):
        order = pair_order(desk, identity, 'a', 'b', deadline=deadline)
        desk.orders[identity] = order
        return order

    def test_explicit_off_preserves_actions_timers_score_and_journal(self):
        outcomes = []
        for knobs in ({}, {'delta_service_brake': 0}):
            world, stream = LossWorld(), io.StringIO()
            with redirect_stdout(io.StringIO()):
                score = play_model(world, 8, Journal(stream),
                                   lambda w, l, n, j: make_delta(w, l, n, j, pairs=1, **knobs))
            outcomes.append((world.sent, world.calls, score, stream.getvalue()))
        self.assertEqual(*outcomes)

    def test_near_deadline_unbooked_orders_lower_target_and_clear_after_booking(self):
        desk = self.desk(delta_service_brake=1, delta_service_soft_orders=1,
                         delta_service_hard_orders=2)
        self.add_order(desk, 'far')
        self.assertEqual(desk.win_target(), 4200)
        self.add_order(desk, 'near', deadline=1000)
        self.assertEqual(desk.win_target(), 3000)
        self.add_order(desk, 'near2', deadline=1000)
        self.assertEqual(desk.win_target(), 2400)
        desk.leg_gigs['near'] = {0: 'g'}
        desk.booked.add('g')
        self.assertEqual(desk.service_risk_orders(), {'near2'})
        self.assertEqual(desk.win_target(), 3000)
        desk.orders['near2']['status'] = 'cancelled'
        self.assertEqual(desk.win_target(), 4200)

    def test_closing_time_and_note_bounds_are_earlier_than_absolute_deadline(self):
        desk = self.desk(delta_service_brake=1)
        order = self.add_order(desk, 'closing')
        order['legs'][0]['pickup']['window']['to'] = 900
        self.assertIn('closing', desk.service_risk_orders())
        order['legs'][0]['pickup']['window']['to'] = 6000
        desk.requests['closing']['note'] = {'text': 'Collect Monday before 14:00'}
        self.assertIn('closing', desk.service_risk_orders())

    def test_existing_brake_is_never_relaxed_and_recovery_keeps_signal(self):
        desk = self.desk(delta_service_brake=1, delta_service_soft_orders=1)
        self.add_order(desk, 'near', deadline=1000)
        desk.brake_mode = 'brake'
        self.assertEqual(desk.win_target(), 2200)
        other = self.desk(delta_service_brake=1, delta_service_soft_orders=1)
        restore_state(other, deepcopy(model_state(desk)))
        self.assertEqual(other.service_risk_orders(), desk.service_risk_orders())
        self.assertEqual(other.win_target(), desk.win_target())

    def test_invalid_controls_fail_at_construction(self):
        for knobs in ({'delta_service_brake': True}, {'delta_service_brake': 2},
                      {'delta_service_horizon_minutes': -1},
                      {'delta_service_soft_orders': 0},
                      {'delta_service_soft_orders': 7},
                      {'delta_service_target_bps': 10000},
                      {'delta_service_hard_target_bps': 3500}):
            with self.subTest(knobs=knobs), self.assertRaises(ValueError):
                self.desk(**knobs)
