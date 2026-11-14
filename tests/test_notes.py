"""Offline note parsing and dispatch contracts; no network clients or secrets."""
from copy import deepcopy
from dataclasses import asdict
import io
import json
import unittest

from beta import BetaDesk, WARNING
from demo import sample_request
from dispatch import Journal
from gamma_notes import make_gamma_notes, make_gamma_notes_pairs, visit_window
from notes import NoteFacts, parse_note
from spread.starter import DAY, Retry
from tests.test_alpha import MarketWorld


def request(text='', *, arrived=540, deadlines=(1200, 2640, 4080), hours=None):
    req = sample_request()
    req.update(arrivedAt=arrived, respondBy=arrived + 15,
               note={'text': text, 'language': 'en'} if text else None)
    req['options'] = [dict(kind=kind, deadline=deadline, listPriceCents=25000)
                      for kind, deadline in zip(('same_day', 'next_day', 'within_3_days'), deadlines)]
    for kind in ('pickup', 'delivery'):
        req['legs'][0][kind].update(window={'from': 0, 'to': 14 * DAY}, hours=deepcopy(hours))
    return req


def order_for(req, deadline=None):
    deadline = req['options'][-1]['deadline'] if deadline is None else deadline
    return dict(id=req['id'], dealerId=req['dealerId'], option=req['options'][-1]['kind'],
                priceCents=30000, deadline=deadline, legs=deepcopy(req['legs']),
                status='waiting', deliveredAt=[None], lastPickupAt=deadline - 180)


class NoteParserTests(unittest.TestCase):
    def test_relative_days_weekdays_and_negated_tomorrow_anchor_to_arrival(self):
        cases = [
            ('Huolto kesken, valmis huomenna klo 10.30', 540, 'ready_at', DAY + 630),
            ('Auto valmis vasta ylihuomenna klo 13', 540, 'ready_at', 2 * DAY + 780),
            ('Valmiina ylihuomenna kello 12 alkaen', DAY + 700, 'ready_at', 3 * DAY + 720),
            ('Ready Wednesday 13:00', 540, 'ready_at', 2 * DAY + 780),
            ('Voi noutaa ke klo 13 alkaen (ei huomenna)', 540, 'ready_at', 2 * DAY + 780),
            ('Noudettavissa aikaisintaan torstaina klo 10', 540, 'ready_at', 3 * DAY + 600),
            ('maksun jälkeen, ei ennen perjantaina klo 13', 540, 'released_at', 4 * DAY + 780),
            ('Luovutus vasta kun maksettu, aikkaisintaan pe klo 11', 540, 'released_at', 4 * DAY + 660),
            ('Released after payment, not before tomorrow 12:00', DAY + 600, 'released_at', 2 * DAY + 720),
            ('Lämnas ut efter betalning, tidigast i morgon kl 11.30', 4 * DAY + 600, 'released_at', 5 * DAY + 690),
            ('Klar imorgon kl 10', 540, 'ready_at', DAY + 600),
            ('Klar i övermorgon kl 10', 540, 'ready_at', 2 * DAY + 600),
            ('Auto vamis vasta ke klo 14', 540, 'ready_at', 2 * DAY + 840),
            ('valmis huomenna kahdelta', 540, 'ready_at', DAY + 840),
        ]
        for text, at, field, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(getattr(parse_note(text, at), field), expected)

    def test_delivery_and_pickup_clauses_have_independent_scope(self):
        facts = parse_note('Kohde auki 8.00-21.00. Huolto kesken, valmis huomenna klo 10.30', DAY + 700)
        self.assertEqual((facts.delivery_opens, facts.delivery_closes), (480, 1260))
        self.assertEqual(facts.ready_at, 2 * DAY + 630)
        facts = parse_note('collect before 14:00. must be at destination by tomorrow 18:30', 540)
        self.assertEqual(facts.pickup_closes, 840)
        self.assertEqual(facts.deadline, DAY + 1110)
        self.assertTrue(facts.deadline_explicit_day)
        facts = parse_note('Destination open weekdays 9:00-20:00. Ready for pickup from Thursday 12:00', 540)
        self.assertEqual((facts.delivery_opens, facts.delivery_closes), (540, 1200))
        self.assertEqual(facts.delivery_weekdays, (0, 1, 2, 3, 4))
        self.assertEqual(facts.ready_at, 3 * DAY + 720)
        self.assertIsNone(facts.pickup_closes)
        facts = parse_note('Nouto arkisin 10-15.30. Oltava perillä viim. ma klo 13', 2 * DAY + 600)
        self.assertEqual(facts.deadline, 7 * DAY + 780)
        self.assertEqual(facts.pickup_closes, 930)
        facts = parse_note('pickup after 12:00 and arrive before tomorrow 18:00', 540)
        self.assertEqual(facts.ready_at, 720)
        self.assertEqual(facts.deadline, DAY + 1080)

    def test_daily_closings_do_not_become_readiness_and_have_no_absolute_day(self):
        for text, expected in [('Nobody here after 14:30', 870), ('We close at 16:00', 960),
                               ('nouto ennen klo 17', 1020), ('Täällä ei ketään kello 18 jälkeen', 1080)]:
            with self.subTest(text=text):
                facts = parse_note(text, 540)
                self.assertEqual(facts.pickup_closes, expected)
                self.assertIsNone(facts.ready_at)
        facts = parse_note('Täällä ei ketään kello 18 jälkeen. Saa hakea vasta huomenna kello 12 jälkeen', DAY + 700)
        self.assertEqual((facts.pickup_closes, facts.ready_at), (1080, 2 * DAY + 720))

    def test_delivery_site_hours_and_availability_do_not_become_pickup_constraints(self):
        facts = parse_note('Destination closes at 16:00. Recipient available from 10:00', 540)
        self.assertEqual((facts.delivery_opens, facts.delivery_closes), (600, 960))
        self.assertIsNone(facts.deadline)
        self.assertIsNone(facts.ready_at)
        facts = parse_note('Recipient available from tomorrow 10:00', 540)
        self.assertEqual(facts.delivery_ready_at, DAY + 600)
        self.assertIsNone(facts.ready_at)
        self.assertIsNone(facts.pickup_opens)

    def test_numeric_am_pm_and_word_hours(self):
        for text, expected in [('Ready tmrw 10:30am', DAY + 630), ('Ready tomorrow 12am', DAY),
                               ('Ready tomorrow 12pm', DAY + 720), ('Ready tomorrow at ten', DAY + 600),
                               ('Valmis huomenna klo kaksitoista', DAY + 720),
                               ('Klar i morgon kl halv elva', DAY + 630),
                               ('Ready tomorrow at half past ten', DAY + 630),
                               ('Ready tomorrow at quarter past ten', DAY + 615)]:
            with self.subTest(text=text):
                self.assertEqual(parse_note(text, 540).ready_at, expected)
        self.assertEqual(parse_note('valmis huomenna puoli kolme', 540).ready_at, DAY + 870)
        self.assertEqual(parse_note('klar imorgon kl halv tre', 540).ready_at, DAY + 870)
        self.assertEqual(parse_note('ready tomorrow at two am', 540).ready_at, DAY + 120)
        for text, expected in [('Opening hours 9am–4pm', (540, 960)),
                               ('noudettavissa arkisin klo 9-18', (540, 1080)),
                               ('Opening hours nine am to four pm', (540, 960)),
                               ('aukioloajat: klo 10-15.30', (600, 930))]:
            with self.subTest(text=text):
                facts = parse_note(text, 540)
                self.assertEqual((facts.pickup_opens, facts.pickup_closes), expected)

    def test_invalid_clocks_counts_and_unrelated_english_to_are_not_days(self):
        for text in ('Ready tomorrow 25:00', 'Ready tomorrow 10:99', 'Ready tomorrow 24:30',
                     'Spare wheels 4, booking reference 123456'):
            with self.subTest(text=text):
                self.assertEqual(parse_note(text, 540), NoteFacts())
        facts = parse_note('deliver to destination by 18:30', 540)
        self.assertEqual(facts.deadline, 1110)
        self.assertFalse(facts.deadline_explicit_day)

    def test_manual_typo_plate_flags_and_serializable_facts(self):
        for text in ("it's a maual.", 'manuaalivaihteisto', 'manuell', 'manual gearbox'):
            self.assertTrue(parse_note(text, 540).manual)
        self.assertTrue(parse_note('kilvet puuttuvat', 540).plates)
        self.assertTrue(parse_note('without plates', 540).plates)
        self.assertEqual(parse_note(None, 540), NoteFacts())
        json.dumps(asdict(parse_note('Ready tomorrow at ten', 540)))


class NoteDispatchTests(unittest.TestCase):
    def desk(self, factory=make_gamma_notes, *, now=540, **settings):
        self.stream = io.StringIO()
        return factory(MarketWorld(), 8, now, Journal(self.stream), **settings)

    def post(self, desk, req, deadline=None, retry=Retry()):
        desk.requests[req['id']] = req
        order = order_for(req, deadline)
        desk.orders[order['id']] = order
        desk.post(order, [0], retry)
        return order, desk.outbox[-1]

    def test_quote_uses_release_readiness_and_exact_eight_hour_slack(self):
        for cue in ('Ready tomorrow 10:30', 'Released after payment, not before tomorrow 10:30'):
            for delta, accepted in ((479, False), (480, True)):
                with self.subTest(cue=cue, delta=delta):
                    desk = self.desk()
                    ready = DAY + 630
                    req = request(cue, deadlines=(1200, ready + delta + 180))
                    self.assertEqual(desk.slack(req, req['options'][1]), delta)
                    desk.quote(req)
                    self.assertEqual(bool(desk.pending), accepted)
                    if accepted:
                        self.assertEqual(set(desk.outbox[-1]['prices']), {'next_day'})

    def test_explicit_note_deadline_filters_slow_options_and_uses_note_clock(self):
        desk = self.desk()
        req = request('collect before 14:00. must be at destination by tomorrow 18:30',
                      deadlines=(1200, DAY + 1200, 2 * DAY + 1200))
        self.assertEqual(desk.slack(req, req['options'][1]), DAY + 840 - 555)
        self.assertEqual(desk.slack(req, req['options'][2]), -1)
        desk.quote(req)
        self.assertEqual(set(desk.outbox[-1]['prices']), {'next_day'})

    def test_business_calendar_saturday_override_and_sunday_do_not_invent_hours(self):
        hours = dict(opens=480, closes=1200, weekdays=[0, 1, 2, 3, 4],
                     saturday={'opens': 600, 'closes': 840})
        facts = parse_note('Opening hours 9am-6pm', 540)
        place = request(hours=hours)['legs'][0]['pickup']
        self.assertEqual(visit_window(place, 'pickup', facts, 5 * DAY, 5 * DAY + 1439),
                         (5 * DAY + 600, 5 * DAY + 840))
        self.assertIsNone(visit_window(place, 'pickup', facts, 6 * DAY, 6 * DAY + 1439))
        self.assertEqual(visit_window(place, 'pickup', facts, 6 * DAY, 8 * DAY),
                         (7 * DAY + 540, 7 * DAY + 1080))
        weekday_facts = parse_note('Nouto arkisin 9-18', 540)
        self.assertIsNone(visit_window(place, 'pickup', weekday_facts, 5 * DAY, 6 * DAY))

    def test_post_respects_day_anchor_and_independent_delivery_hours(self):
        desk = self.desk(now=DAY + 800)
        req = request('Kohde auki 8.00-21.00. Huolto kesken, valmis huomenna klo 10.30',
                      arrived=DAY + 700, deadlines=(3 * DAY + 1200,))
        _, action = self.post(desk, req)
        pickup, delivery = action['stops']
        self.assertEqual(pickup['window']['from'], 2 * DAY + 630)
        self.assertLessEqual(delivery['window']['to'] % DAY, 1260)
        desk.now = 2 * DAY + 700
        desk.outbox = []
        desk.post(desk.orders[req['id']], [0])
        self.assertEqual(desk.outbox[0]['stops'][0]['window']['from'], desk.now)

    def test_daily_closing_rolls_repost_to_next_business_day(self):
        hours = dict(opens=480, closes=1200, weekdays=[0, 1, 2, 3, 4], saturday=None)
        desk = self.desk(now=4 * DAY + 600)
        req = request('Opening hours 9am-4pm. Manual car without plates',
                      arrived=4 * DAY + 540, deadlines=(8 * DAY + 1200,), hours=hours)
        req['legs'][0]['car'].update(electric=True, chargePercent=20, premium=True)
        order, action = self.post(desk, req)
        self.assertEqual(action['stops'][0]['window']['to'], 4 * DAY + 960)
        actions, desk.outbox = desk.outbox, []
        desk.read_results(actions, [{'ok': True, 'id': 'old'}])
        desk.now = 4 * DAY + 961
        desk.repost('old')
        action = desk.outbox[-1]
        self.assertEqual(action['stops'][0]['window'], {'from': 7 * DAY + 540, 'to': 7 * DAY + 960})
        self.assertEqual(action['audience'], {'experienced': True, 'manualLicence': True})
        self.assertTrue(action['stops'][0]['withPlates'])
        self.assertTrue(action['stops'][0]['withCharging'])
        self.assertEqual(desk.gigs_of(order['id']), [])
        count = len(desk.outbox)
        desk.repost('old')
        self.assertEqual(len(desk.outbox), count)

    def test_retry_preserves_flags_and_does_not_drop_closing_window(self):
        desk = self.desk(now=1000)
        req = request('Opening hours 9am-4pm', deadlines=(4 * DAY + 1200,))
        _, action = self.post(desk, req, retry=Retry(1100, True, True))
        self.assertEqual(action['stops'][0]['window'], {'from': DAY + 540, 'to': DAY + 960})
        self.assertTrue(action['audience']['manualLicence'])
        self.assertTrue(action['stops'][0]['withPlates'])

    def test_exact_closing_expiry_moves_to_next_day_for_both_factories(self):
        for factory in (make_gamma_notes, make_gamma_notes_pairs):
            with self.subTest(factory=factory.__name__):
                desk = self.desk(factory, **({'pairs': 1} if factory is make_gamma_notes_pairs else {}))
                req = request('Opening hours 9am-2pm', deadlines=(4 * DAY + 1200,))
                _, action = self.post(desk, req)
                actions, desk.outbox = desk.outbox, []
                desk.read_results(actions, [{'ok': True, 'id': 'expired'}])
                desk.now = 840
                desk.repost('expired')
                self.assertEqual(desk.outbox[0]['stops'][0]['window'],
                                 {'from': DAY + 540, 'to': DAY + 840})

    def test_post_searches_later_pickup_day_when_first_day_cannot_meet_destination(self):
        hours = dict(opens=540, closes=960, weekdays=[0, 1, 2, 3, 4], saturday=None)
        desk = self.desk()
        req = request('Destination open 9-10. Deliver by 18:00', deadlines=(1200,), hours=hours)
        _, action = self.post(desk, req)
        self.assertGreaterEqual(action['stops'][0]['window']['from'], DAY)
        self.assertTrue(all('window' in stop for stop in action['stops']))

    def test_tradein_backward_slack_includes_empty_transfer_drive(self):
        desk = self.desk(trade_ins=1)
        req = request(deadlines=(1200,))
        req['legs'] *= 2
        # Three180-minute drives: first car, empty return, second car.
        self.assertEqual(desk.slack(req, req['options'][0]), 1200 - 540 - 555)

    def test_true_pickup_and_fees_account_for_charging_plates_and_hidden_close(self):
        desk = self.desk()
        req = request('collect before 14:00. deliver by 18:30. Manual car without plates',
                      deadlines=(1200,))
        req['legs'][0]['car'].update(electric=True, chargePercent=20)
        order, action = self.post(desk, req)
        self.assertEqual(desk.true_last_pickup(order), 840)
        self.assertEqual(desk.slack(req, req['options'][0]), 840 - 30 - 555)
        self.assertEqual(action['schedule'][-1], {'at': 840 - WARNING, 'feeCents': 18000})
        req['note'] = {'text': 'deliver by 18:30', 'language': 'en'}
        self.assertEqual(desk.true_last_pickup(order), 1110 - 180 - 40)

    def test_already_urgent_and_level_one_keep_official_steep_schedule(self):
        desk = self.desk()
        req = request('collect before 14:00', deadlines=(1200,))
        order, _ = self.post(desk, req)
        desk.urgent.add(order['id'])
        self.assertEqual([s['feeCents'] for s in desk.fees_for(order, 1)], [18000, 21000, 24000, 27000, 30000])
        desk.level = 1
        self.assertEqual(len(desk.fees_for(order, 1)), 1)

    def test_note_pair_factory_routes_fees_and_posts_through_note_mixin(self):
        for shape in ('ramp', 'review'):
            with self.subTest(shape=shape):
                desk = self.desk(make_gamma_notes_pairs, pairs=1, fee_shape=shape)
                req = request('collect before 14:00. Manual car without plates', deadlines=(1200,))
                _, action = self.post(desk, req)
                self.assertEqual(action['schedule'][-1], {'at': 540 if shape == 'review' else 660,
                                                         'feeCents': 18000})
                self.assertEqual(action['stops'][0]['window']['to'], 840)
                self.assertTrue(action['audience']['manualLicence'])
                self.assertTrue(action['stops'][0]['withPlates'])

    def test_note_pair_factory_builds_four_stops_with_scoped_windows_and_flags(self):
        desk = self.desk(make_gamma_notes_pairs, pairs=1, pair_max_drive_minutes=400)
        one = request('Ready tomorrow 10:00. Opening hours 9-16. Manual car without plates',
                      deadlines=(5 * DAY + 1200,))
        two = request('Ready tomorrow 10:00', deadlines=(5 * DAY + 1200,))
        two['id'] = 'second'
        two['legs'][0]['pickup']['placeId'] = 'demo-tampere'
        two['legs'][0]['delivery']['placeId'] = 'demo-helsinki'
        for req in (one, two):
            desk.requests[req['id']] = req
            order = order_for(req)
            desk.handle(dict(seq=1, at=540, kind='order_won', order=order))
        self.assertEqual(len(desk.outbox), 1)
        action = desk.outbox[0]
        self.assertEqual(len(action['stops']), 4)
        self.assertTrue(action['audience']['manualLicence'])
        pickup = next(s for s in action['stops'] if s['orderId'] == one['id'] and s['kind'] == 'pickup')
        self.assertTrue(pickup['withPlates'])
        self.assertEqual(pickup['window'], {'from': DAY + 600, 'to': DAY + 960})
        self.assertEqual(action['schedule'][0]['feeCents'], 17280)

    def test_beta_baseline_is_unchanged(self):
        desk = BetaDesk(MarketWorld(), 8, 540, Journal(io.StringIO()))
        req = request("it's a maual.", deadlines=(1200,))
        desk.requests[req['id']] = req
        desk.post(order_for(req), [0])
        self.assertFalse(desk.outbox[0]['audience']['manualLicence'])


if __name__ == '__main__':
    unittest.main()
