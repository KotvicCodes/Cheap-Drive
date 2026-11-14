"""Delta experiments on offline contracts; these checks do not measure profit."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import unittest

from delta import make_delta, parse_delta_note, rescue_window
from dispatch import Journal, play_model
from gamma_notes import make_gamma_notes_pairs, visit_window
from notes import NoteFacts, parse_note
from spread.starter import DAY, Retry
from tests.test_gamma_pairs import PairWorld, pair_order
from tests.test_notes import order_for, request
from tests.test_performance import LossWorld


HOURS = {'opens': 540, 'closes': 1080, 'weekdays': [0, 1, 2, 3, 4], 'saturday': None}


class DeltaNoteTests(unittest.TestCase):
    def test_observed_typos_use_arrival_day_and_keep_release_scope(self):
        cases = [
            ('Valmis huoomenna klo 11', DAY + 660, None),
            ('Ready Friay 13:00', 4 * DAY + 780, None),
            ('Noudettavissa aikaisiintaan huomenna klo 12', DAY + 720, None),
            ('Luovutus maksun jälkeen, aikaisiintaan pe klo 11', None, 4 * DAY + 660),
        ]
        for text, ready, released in cases:
            with self.subTest(text=text):
                facts = parse_delta_note(text, 540)
                self.assertEqual((facts.ready_at, facts.released_at), (ready, released))
        self.assertEqual(parse_delta_note('Ready Friay 13:00', 2 * DAY + 540).ready_at,
                         4 * DAY + 780)

    def test_negative_pickup_clause_is_closing_not_release_or_readiness(self):
        for text in ('Klo 16.30 jälkeen ei enää luovutuksia',
                     'KLO 16:30 JÄLKEEN EI ENÄÄ LUOVUTUKSIA'):
            facts = parse_delta_note(text, 540)
            self.assertEqual(facts.pickup_closes, 990)
            self.assertIsNone(facts.ready_at)
            self.assertIsNone(facts.released_at)
        facts = parse_delta_note('Valmis huoomenna klo 11. Klo 16 jälkeen ei enää luovutuksia', 540)
        self.assertEqual((facts.ready_at, facts.pickup_closes), (DAY + 660, 960))
        facts = parse_delta_note('Destination open 8-20; Klo 16 jälkeen ei enää luovutuksia', 540)
        self.assertEqual((facts.delivery_opens, facts.delivery_closes, facts.pickup_closes), (480, 1200, 960))

    def test_bounded_corrections_do_not_create_clocks_from_codes_or_prose(self):
        for text in ('Door code Friay 123456', 'Booking reference huoomenna 123456',
                     'Ready Friay 25:00', 'Spare wheels 4, booking 123456',
                     'Aikaisiintaan is a spelling example', 'Ready friayish at 25:00'):
            with self.subTest(text=text):
                self.assertEqual(parse_delta_note(text, 540), NoteFacts())
        for text in ('Ready tomorrow at ten', 'Recipient available from tomorrow 10:00',
                     'Täällä ei ketään klo 18 jälkeen. Valmis huomenna klo 12',
                     'Manual car without plates; collect before 14:00'):
            self.assertEqual(parse_delta_note(text, 540), parse_note(text, 540))

    def test_negated_typos_do_not_override_the_affirmative_date(self):
        for text in ('Ready Saturday (not Friay) at 13:00',
                     'Klar lördag (inte Friay) kl 13:00'):
            self.assertEqual(parse_delta_note(text, 540).ready_at, 5 * DAY + 780)
        facts = parse_delta_note('Valmis pe klo 11 (ei huoomenna)', 540)
        self.assertEqual(facts.ready_at, 4 * DAY + 660)


class DeltaRescueTests(unittest.TestCase):
    def place(self, *, day=1, private=False):
        return dict(window={'from': day * DAY + 540, 'to': day * DAY + 1200},
                    hours=deepcopy(HOURS), privateAddress=private)

    def test_closed_today_with_future_absolute_end_can_rescue_next_business_day(self):
        place = self.place()
        low, high = DAY + 1141, 4 * DAY
        self.assertIsNone(visit_window(place, 'pickup', NoteFacts(), low, high, rescue=True))
        self.assertEqual(rescue_window(place, 'pickup', NoteFacts(), low, high),
                         (2 * DAY + 540, 2 * DAY + 1080))

    def test_strict_window_inclusive_close_is_preferred_before_late_rescue(self):
        place = self.place()
        for low in (DAY + 540, DAY + 1079, DAY + 1080):
            with self.subTest(low=low):
                self.assertEqual(rescue_window(place, 'pickup', NoteFacts(), low, 4 * DAY),
                                 visit_window(place, 'pickup', NoteFacts(), low, 4 * DAY))
        self.assertEqual(rescue_window(place, 'pickup', NoteFacts(), DAY + 1081, 4 * DAY),
                         (2 * DAY + 540, 2 * DAY + 1080))

    def test_private_booked_slots_are_never_extended(self):
        place = self.place(private=True)
        place['hours'] = None
        self.assertEqual(rescue_window(place, 'pickup', NoteFacts(), DAY + 1100, 4 * DAY),
                         (DAY + 1100, DAY + 1200))
        for kind in ('pickup', 'delivery'):
            self.assertIsNone(rescue_window(place, kind, NoteFacts(), DAY + 1201, 4 * DAY))

    def test_weekends_readiness_and_recurring_hours_survive_relaxed_promises(self):
        place = self.place(day=4)
        facts = NoteFacts(ready_at=7 * DAY + 660, released_at=7 * DAY + 720,
                          pickup_opens=600, pickup_closes=960, pickup_deadline=4 * DAY + 1200)
        self.assertEqual(rescue_window(place, 'pickup', facts, 4 * DAY + 1141, 9 * DAY),
                         (7 * DAY + 720, 7 * DAY + 960))
        facts = NoteFacts(delivery_ready_at=7 * DAY + 780, delivery_closes=1020,
                          deadline=4 * DAY + 1200)
        self.assertEqual(rescue_window(place, 'delivery', facts, 4 * DAY + 1141, 9 * DAY),
                         (7 * DAY + 780, 7 * DAY + 1020))
        self.assertIsNone(rescue_window(place, 'pickup', NoteFacts(), 4 * DAY + 1141, 7 * DAY + 539))
        self.assertIsNone(rescue_window(place, 'pickup', NoteFacts(pickup_weekdays=()), 4 * DAY, 9 * DAY))

    def test_repaired_post_keeps_flags_and_route_travel_and_leaves_gamma_unchanged(self):
        outputs = []
        for factory, knobs in ((make_gamma_notes_pairs, {}), (make_delta, {'delta_rescue_windows': 1})):
            desk = factory(PairWorld(), 8, DAY + 1141, Journal(io.StringIO()), pairs=1, **knobs)
            req = request('Manual car without plates', deadlines=(DAY + 1200,), hours=HOURS)
            req['legs'][0]['pickup']['placeId'] = 'a'
            req['legs'][0]['delivery']['placeId'] = 'b'
            req['legs'][0]['pickup']['window']['to'] = DAY + 1200
            req['legs'][0]['delivery']['window']['to'] = DAY + 1200
            req['legs'][0]['car'].update(electric=True, chargePercent=20, premium=True)
            desk.requests[req['id']] = req
            order = order_for(req)
            desk.orders[order['id']] = order
            desk.post(order, [0], Retry(DAY + 1142, True, True))
            outputs.append(deepcopy(desk.outbox))
        self.assertEqual(outputs[0], [])
        self.assertEqual(len(outputs[1]), 1)
        action = outputs[1][0]
        pickup, delivery = action['stops']
        self.assertEqual(action['audience'], {'experienced': True, 'manualLicence': True})
        self.assertTrue(pickup['withPlates'] and pickup['withCharging'])
        self.assertEqual(pickup['window']['from'], 2 * DAY + 540)
        self.assertGreaterEqual(delivery['window']['from'], pickup['window']['from'] + 30 + 40)


class DeltaFactoryTests(unittest.TestCase):
    def test_neutral_delta_matches_gamma_actions_timers_and_score_under_both_capture_modes(self):
        for fast in (False, True):
            runs = []
            for factory in (make_gamma_notes_pairs, make_delta):
                world, stream = LossWorld(), io.StringIO()
                with redirect_stdout(io.StringIO()):
                    score = play_model(world, 8, Journal(stream),
                                       lambda w, l, n, j: factory(w, l, n, j, pairs=1), fast=fast)
                runs.append((world.sent, world.calls, score, stream.getvalue()))
            self.assertEqual(*runs)

    def test_neutral_delta_matches_gamma_pair_creation_and_booking(self):
        outcomes = []
        for factory in (make_gamma_notes_pairs, make_delta):
            world = PairWorld()
            desk = factory(world, 8, 600, Journal(io.StringIO()), pairs=1)
            for identity, pickup, delivery in (('one', 'a', 'b'), ('two', 'b', 'c')):
                order = pair_order(desk, identity, pickup, delivery)
                desk.handle(dict(seq=len(desk.orders) + 1, at=600, kind='order_won', order=order))
            actions, desk.outbox = deepcopy(desk.outbox), []
            desk.read_results(actions, world.act(actions))
            outcomes.append((actions, desk.leg_gigs, desk.next_pair_wake()))
        self.assertEqual(*outcomes)
        self.assertEqual(len(outcomes[0][0][0]['stops']), 4)

    def test_note_switch_is_independent_and_cache_tracks_text_and_arrival(self):
        desk = make_delta(PairWorld(), 8, 540, Journal(io.StringIO()), delta_note_fixes=1)
        req = request('Valmis huoomenna klo 11')
        self.assertEqual(desk.note_facts(req).ready_at, DAY + 660)
        req['arrivedAt'] += DAY
        self.assertEqual(desk.note_facts(req).ready_at, 2 * DAY + 660)
        req['note']['text'] = 'Ready Friay 13:00'
        self.assertEqual(desk.note_facts(req).ready_at, 4 * DAY + 780)
        neutral = make_delta(PairWorld(), 8, 540, Journal(io.StringIO()))
        self.assertEqual(neutral.note_facts(req), parse_note(req['note'], req['arrivedAt']))

    def test_flags_validate_without_changing_baseline_settings(self):
        for name in ('delta_note_fixes', 'delta_rescue_windows'):
            for value in (True, False, 2, -1, '1', None):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, name):
                    make_delta(PairWorld(), 8, 540, Journal(io.StringIO()), **{name: value})


if __name__ == '__main__':
    unittest.main()
