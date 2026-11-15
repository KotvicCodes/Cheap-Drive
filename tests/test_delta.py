"""Delta experiments on offline contracts; these checks do not measure profit."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from fractions import Fraction
from pathlib import Path
import unittest
from unittest.mock import patch

from models.delta import make_delta, parse_delta_note, rescue_window
from models.delta_b1 import B1_MODES, SKIPPED_TRACKER
from dispatch import Journal, play_model
from models.gamma_notes import make_gamma_notes_pairs, visit_window
from models.notes import NoteFacts, parse_note
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


class DeltaPairingTests(unittest.TestCase):
    def desk(self, profile='off', **settings):
        return make_delta(PairWorld(), 8, 600, Journal(io.StringIO()),
                          pairs=1, delta_pairing=profile, **settings)

    def orders(self, desk, minutes=180, transfer_km=45):
        first = pair_order(desk, 'one', 'a', 'b', deadline=6000)
        second = pair_order(desk, 'two', 'c', 'd', deadline=6000)
        for a, b in (('a', 'b'), ('c', 'd')):
            desk.roads[a, b] = {'km': minutes, 'minutes': minutes}
        desk.roads['b', 'c'] = {'km': transfer_km, 'minutes': 60}
        return first, second

    def test_explicit_off_preserves_actions_timers_and_journal(self):
        outcomes = []
        for settings in ({}, {'delta_pairing': 'off'}):
            world, stream = LossWorld(), io.StringIO()
            with redirect_stdout(io.StringIO()):
                score = play_model(world, 8, Journal(stream),
                                   lambda w, l, n, j: make_delta(w, l, n, j, pairs=1,
                                       delta_note_fixes=1, delta_rescue_windows=1, **settings))
            outcomes.append((world.sent, world.calls, score, stream.getvalue()))
        self.assertEqual(*outcomes)

    def test_regional_allows_route_rejected_by_original_distance_and_drive_limits(self):
        baseline = self.desk()
        first, second = self.orders(baseline)
        self.assertEqual(baseline._plan(first, second)[1], 'transfer_too_far')
        regional = self.desk('regional', delta_note_fixes=1, delta_rescue_windows=1)
        first, second = self.orders(regional)
        plan, reason = regional._plan(first, second)
        self.assertIsNone(reason)
        self.assertEqual(plan.drive_minutes, 420)
        self.assertEqual(plan.transfer_km, 45)
        self.assertEqual(regional.driver_settings.pair_arrival_allowance_minutes, 180)
        self.assertEqual(regional.driver_settings.pair_spare_minutes, 60)
        self.assertEqual(regional.driver_settings.pair_split_minutes, 60)

    def test_extended_accepts_legal_long_pair_and_rejects_over_twelve_hours(self):
        regional = self.desk('regional')
        first, second = self.orders(regional, minutes=270, transfer_km=75)
        self.assertEqual(regional._plan(first, second)[1], 'transfer_too_far')
        extended = self.desk('extended')
        first, second = self.orders(extended, minutes=270, transfer_km=75)
        plan, reason = extended._plan(first, second)
        self.assertIsNone(reason)
        self.assertEqual(plan.drive_minutes, 600)
        extended.roads['a', 'b']['minutes'] = 391
        self.assertEqual(extended._plan(first, second)[1], 'drive_too_long')

    def test_explicit_broader_pair_search_retains_deadline_and_drive_caps(self):
        extended = self.desk('extended')
        first, second = self.orders(extended, minutes=270, transfer_km=105)
        self.assertEqual(extended._plan(first, second)[1], 'transfer_too_far')
        broader = self.desk('off', pair_transfer_km=120, pair_max_drive_minutes=720)
        first, second = self.orders(broader, minutes=270, transfer_km=105)
        self.assertIsNone(broader._plan(first, second)[1])
        first['deadline'] = 700
        self.assertEqual(broader._plan(first, second)[1], 'windows')
        first['deadline'] = 6000
        broader.roads['a', 'b']['minutes'] = 391
        self.assertEqual(broader._plan(first, second)[1], 'drive_too_long')

    def test_wider_limits_keep_window_and_audience_safety_checks(self):
        desk = self.desk('extended', delta_note_fixes=1, delta_rescue_windows=1)
        first, second = self.orders(desk)
        first['deadline'] = 700
        self.assertEqual(desk._plan(first, second)[1], 'windows')
        first['deadline'] = 6000
        first['legs'][0]['car']['premium'] = True
        desk.world.initial_roster[0]['rating'] = 4.0
        self.assertEqual(desk._plan(first, second)[1], 'audience')

    def test_regional_posts_pair_and_retains_timed_fallback(self):
        desk = self.desk('regional', delta_note_fixes=1, delta_rescue_windows=1)
        first, second = self.orders(desk)
        for order in (first, second):
            desk.handle(dict(seq=len(desk.orders), at=desk.now, kind='order_won', order=order))
        actions, desk.outbox = desk.outbox, []
        self.assertEqual(len(actions), 1)
        self.assertEqual(len(actions[0]['stops']), 4)
        desk.read_results(actions, desk.world.act(actions))
        self.assertEqual(desk.next_pair_wake(), 660)
        desk.now = 660
        desk.poll_driver_side()
        self.assertEqual(len(desk.outbox), 2)
        self.assertTrue(all(len(action['stops']) == 2 for action in desk.outbox))

    def test_profile_validation_and_gamma_defaults_are_unchanged(self):
        for value in (None, True, 1, [], 'wide'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'delta_pairing'):
                self.desk(value)
        with self.assertRaisesRegex(ValueError, 'pairs=1'):
            make_delta(PairWorld(), 8, 600, Journal(io.StringIO()), delta_pairing='regional')
        gamma = make_gamma_notes_pairs(PairWorld(), 8, 600, Journal(io.StringIO()), pairs=1)
        self.assertEqual((gamma.driver_settings.pair_transfer_km,
                          gamma.driver_settings.pair_max_drive_minutes), (30, 300))


class DeltaB1Tests(unittest.TestCase):
    def desk(self, mode="fastest_learning_only", *, factory=make_delta, level=8, **settings):
        stream = io.StringIO()
        knobs = dict(delta_b1=mode) if factory is make_delta else {}
        desk = factory(PairWorld(), level, 500, Journal(stream), **knobs, **settings)
        desk.trace = stream
        return desk

    def req(self, identity='one', *, full=False, pickup='a', delivery='b', text=''):
        req = request(text, arrived=500, deadlines=(1600 if full else 800, 2600, 4000))
        req.update(id=identity, dealerId='D01')
        req['legs'][0]['pickup']['placeId'] = pickup
        req['legs'][0]['delivery']['placeId'] = delivery
        return req

    def event(self, desk, kind, **data):
        desk.handle(dict(seq=1, at=desk.now, kind=kind, **data))

    def flush(self, desk, *, ok=True):
        actions, desk.outbox = desk.outbox, []
        results = desk.world.act(actions) if ok else [dict(ok=False, reason='offline rejection') for _ in actions]
        desk.read_results(actions, results)
        return deepcopy(actions)

    def records(self, desk, kind):
        return [row for row in map(json.loads, desk.trace.getvalue().splitlines()) if row['type'] == kind]

    def assert_clean(self, desk):
        self.assertEqual(desk.pending, set())
        self.assertEqual(desk.quote_trackers, {})
        self.assertEqual(desk.delta_b1_pending, {})
        self.assertEqual(desk.town_pending, {})
        self.assertIsNone(desk._delta_b1_menu)

    def test_classification_uses_original_first_and_final_keys_not_menu_size(self):
        cases = [
            (False, None, 'skipped_fastest', ['next_day', 'within_3_days']),
            (True, None, 'fastest_present', ['same_day', 'next_day', 'within_3_days']),
            (True, slice(0, 1), 'fastest_present', ['same_day']),
            (True, slice(1, 3), 'fastest_present', ['next_day', 'within_3_days']),
            (False, [2, 0, 1], 'fastest_present', ['within_3_days', 'next_day']),
        ]
        for full, selection, cohort, expected_keys in cases:
            with self.subTest(full=full, selection=selection):
                desk, req = self.desk(), self.req(full=full)
                if isinstance(selection, slice):
                    req['options'] = req['options'][selection]
                elif selection:
                    req['options'] = [req['options'][index] for index in selection]
                original = deepcopy(req)
                desk.quote(req)
                self.assertEqual(list(desk.outbox[-1]['prices']), expected_keys)
                self.assertEqual(desk.delta_b1_pending, {'one': cohort})
                self.assertEqual(req, original)
                self.assertEqual(self.records(desk, 'delta_b1_quote')[0]['optionKeys'], expected_keys)
                self.assertIsNone(desk._delta_b1_menu)
        desk, req = self.desk(), self.req()
        req['options'][0]['kind'], req['options'][1]['kind'] = 'next_day', 'same_day'
        desk.quote(req)
        self.assertEqual(list(desk.outbox[-1]['prices']), ['same_day', 'within_3_days'])
        self.assertEqual(desk.delta_b1_pending['one'], 'skipped_fastest')

    def test_guards_and_option_selection_determine_cohort_before_pricing(self):
        cases = [
            ({'premium_min_slack_minutes': 1200}, 'premium'),
            ({'same_day_min_slack_minutes': 1200}, None),
            ({'trust_guard': 1}, 'trust'),
            ({'max_km': 5, 'long_max_km': 20}, None),
            ({'quote_options': 'slowest_only'}, None),
            ({'quote_options': 'cheapest_only'}, None),
            ({'quote_options': 'no_same_day'}, None),
            ({}, 'readiness'),
            ({'brake': 1}, 'brake'),
        ]
        for settings, guard in cases:
            with self.subTest(settings=settings, guard=guard):
                desks = [self.desk('fastest_learning_only_skipped_9200', **settings),
                         self.desk(factory=make_gamma_notes_pairs, **settings)]
                req = self.req(full=True)
                req['options'][0]['deadline'] = 1200  # 655 minutes; trust guard needs 720
                req['options'][1]['listPriceCents'] = 20001
                req['options'][2]['listPriceCents'] = 18000
                if guard == 'premium':
                    req['legs'][0]['car']['premium'] = True
                if guard == 'readiness':
                    req['note'] = dict(text='Ready tomorrow at 10:00', language='en')
                for desk in desks:
                    if guard == 'trust':
                        desk.trust[req['dealerId']] = 10
                    if guard == 'brake':
                        desk.brake_warnings.extend([desk.now] * desk.settings.brake_hard_warnings)
                    desk.quote(deepcopy(req))
                actual, control = desks
                prices = actual.outbox[-1]['prices']
                self.assertNotIn('same_day', prices)
                self.assertEqual(prices.keys(), control.outbox[-1]['prices'].keys())
                self.assertEqual(actual.delta_b1_pending['one'], 'skipped_fastest')
                for kind, factors in self.records(actual, 'beta_quote')[0]['optionFactors'].items():
                    self.assertEqual(factors['deltaB1SkippedBps'], 9200)

    def test_discount_composes_exactly_once_and_journal_matches_submission(self):
        for skipped in (False, True):
            desk = self.desk('fastest_learning_only_skipped_9200', short_bps=9200, next_day_bps=9801)
            req = self.req(full=not skipped)
            desk.trust[req['dealerId']] = 3
            # Pick a cent boundary that distinguishes early rounding from one ceiling.
            for list_price in range(10001, 10100):
                raw = Fraction(list_price * 15000 * 10300, 100_000_000) * Fraction(9200 * 9801, 100_000_000)
                ceil = lambda value: -(-value.numerator // value.denominator)
                if ceil(raw * Fraction(9200, 10000)) != ceil(Fraction(ceil(raw) * 9200, 10000)):
                    break
            else:
                self.fail('fixture must expose a premature cent ceiling')
            req['options'][1]['listPriceCents'] = list_price
            desk.quote(req)
            prices = deepcopy(desk.outbox[-1]['prices'])
            expected = ceil(raw * (Fraction(9200, 10000) if skipped else 1))
            self.assertEqual(prices['next_day'], expected)
            self.assertEqual(self.records(desk, 'beta_quote')[0]['prices'], prices)
            self.assertEqual(self.records(desk, 'delta_b1_quote')[0]['prices'], prices)
            submitted = self.flush(desk)
            self.assertEqual(submitted[0]['prices'], prices)
            self.assertEqual(self.records(desk, 'action_result')[0]['action']['prices'], prices)

    def test_exclusion_changes_only_feedback_and_keeps_win_trust_and_posting(self):
        for mode in B1_MODES[1:3]:
            for won in (False, True):
                desk = self.desk(mode, pairs=1)
                req = self.req()
                desk.quote(req)
                self.assertIn('one', desk.pending)
                self.flush(desk)
                # No timeout pruning: delayed decisions still use the recorded cohort.
                desk.now = 2 * DAY
                req['options'] = req['options'][1:]
                before = desk.markup
                if won:
                    self.event(desk, 'order_won', order=order_for(req))
                    self.assertIn('one', desk.orders)
                    self.assertEqual(desk.dealers['one'], req['dealerId'])
                    self.assertTrue(any(a['type'] == 'post' for a in desk.outbox))
                    for kind, expected in (('revenue', 1), ('late_refund', 0)):
                        self.event(desk, 'ledger', line={'kind': kind, 'orderId': 'one'})
                        self.assertEqual(desk.trust[req['dealerId']], expected)
                    self.event(desk, 'order_cancelled', orderId='one', gigs=[])
                    self.assertNotIn('one', desk.orders)
                else:
                    self.event(desk, 'order_lost', requestId='one')
                self.assertEqual(desk.markup, before)
                self.assert_clean(desk)
                desk.learn('one', won)  # duplicate outcomes cannot update or recount
                counts = desk.delta_b1_counts['skipped_fastest']
                self.assertEqual((counts['quotes'], counts['outcomes'], counts['updates']), (1, 1, 0))

    def test_fastest_present_feedback_remains_gamma_and_does_not_follow_chosen_option(self):
        for mode in B1_MODES[1:]:
            for won in (False, True):
                desks = [self.desk(mode), self.desk(factory=make_gamma_notes_pairs)]
                for desk in desks:
                    req = self.req(full=True)
                    desk.quote(req)
                    self.flush(desk)
                    if won:
                        # Dealer chooses the slowest; the original first was still offered.
                        self.event(desk, 'order_won', order=order_for(req))
                    else:
                        self.event(desk, 'order_lost', requestId='one')
                self.assertEqual(desks[0].markup, desks[1].markup)
                self.assertEqual(desks[0].outbox, desks[1].outbox)
                self.assertEqual(desks[0].delta_b1_counts['fastest_present']['updates'], 1)
                self.assert_clean(desks[0])

    def test_rejection_decline_duplicates_expired_and_low_levels_do_not_train(self):
        for mode in B1_MODES[1:]:
            for full in (False, True):
                desk, req = self.desk(mode), self.req(full=full)
                desk.quote(req)
                desk.quote(req)
                self.assertEqual(len(self.records(desk, 'delta_b1_quote')), 1)
                with self.assertLogs('cheap-drive', level='WARNING'):
                    self.flush(desk, ok=False)
                desk.learn('one', True)
                desk.learn('one', False)
                self.event(desk, 'order_won', order=order_for(req))
                self.assertIn('one', desk.orders)
                self.assertEqual(desk.dealers['one'], req['dealerId'])
                self.assert_clean(desk)
                self.assertEqual(desk.markup, 15000)
                self.assertEqual(sum(c['updates'] for c in desk.delta_b1_counts.values()), 0)
            for decline in ('no_time', 'trade_in', 'too_long'):
                desk, req = self.desk(mode), self.req()
                if decline == 'no_time':
                    for option in req['options']:
                        option['deadline'] = 600
                elif decline == 'trade_in':
                    req['legs'] *= 2
                else:
                    desk.roads['a', 'b']['km'] = 1000
                desk.quote(req)
                self.assertEqual(desk.outbox[-1]['prices'], {'same_day': 250000})
                self.flush(desk)
                desk.learn('one', False)
                self.assert_clean(desk)
                self.assertEqual(desk.markup, 15000)
                self.assertFalse(self.records(desk, 'delta_b1_quote'))
            # Even a practical decline that unexpectedly wins retains ownership,
            # while contributing no feedback sample.
            desk, req = self.desk(mode), self.req()
            desk.roads['a', 'b']['km'] = 1000
            desk.quote(req)
            self.flush(desk)
            self.event(desk, 'order_won', order=order_for(req))
            self.assertIn('one', desk.orders)
            self.assertEqual(desk.dealers['one'], req['dealerId'])
            self.assertEqual(desk.markup, 15000)
            self.assert_clean(desk)
            for level in (1, 2, 3):
                desk = self.desk(mode, level=level)
                desk.quote(self.req())
                self.assertEqual(desk.outbox[-1]['prices'], {'same_day': 25000})
                self.assert_clean(desk)
            desk, req = self.desk(mode), self.req()
            desk.now = req['respondBy']
            desk.quote(req)
            self.assertEqual(desk.outbox, [])
            self.assert_clean(desk)

    def test_cancellation_change_and_terminal_cleanup_prevent_late_feedback(self):
        for mode in B1_MODES[1:]:
            for full in (False, True):
                for kind in ('order_cancelled', 'order_changed', 'delivered'):
                    with self.subTest(mode=mode, full=full, kind=kind):
                        desk, req = self.desk(mode, pairs=1), self.req(full=full)
                        desk.quote(req)
                        self.flush(desk)
                        data = {'orderId': 'one', 'gigs': [], 'leg': 0}
                        if kind == 'order_changed':
                            data = {'order': order_for(req)}
                        self.event(desk, kind, **data)
                        desk.learn('one', True)
                        desk.learn('one', False)
                        self.assert_clean(desk)
                        self.assertEqual(desk.markup, 15000)
                        self.assertEqual(desk.markups.get(SKIPPED_TRACKER, 15000), 15000)
                        self.assertEqual(sum(c['outcomes'] for c in desk.delta_b1_counts.values()), 0)

    def test_split_matches_independent_gamma_learners_with_bounds_and_daily_freeze(self):
        for freeze in (0, 25):
            settings = dict(markup_min_bps=14900, markup_max_bps=15100, freeze_day_drop_bps=freeze)
            desk = self.desk('split_skipped_tracker', **settings)
            controls = {cohort: self.desk(factory=make_gamma_notes_pairs, **settings)
                        for cohort in ('fastest_present', 'skipped_fastest')}
            schedule = [(0, False, False), (0, True, True), (1, False, False), (1, True, False),
                        (1, False, True), (2, True, True), (2, False, True)]
            for index, (day, full, won) in enumerate(schedule):
                cohort = 'fastest_present' if full else 'skipped_fastest'
                tracker = 'global' if full else SKIPPED_TRACKER
                control = controls[cohort]
                for current in (desk, control):
                    current.now = day * DAY + 500
                    req = self.req(str(index), full=full)
                    req['arrivedAt'] += day * DAY
                    req['respondBy'] += day * DAY
                    for option in req['options']:
                        option['deadline'] += day * DAY
                    current.quote(req)
                    self.flush(current)
                self.assertEqual(desk.day_starts[tracker], control.day_starts['global'])
                if index == 0:
                    # A delayed decision across midnight must not apply yesterday's floor.
                    desk.now = control.now = DAY + 100
                desk.learn(str(index), won)
                control.learn(str(index), won)
                self.assertEqual(desk.tracker_markup(tracker), control.markup)
                other_tracker = SKIPPED_TRACKER if full else 'global'
                other = controls['skipped_fastest' if full else 'fastest_present']
                self.assertEqual(desk.tracker_markup(other_tracker), other.markup)
                self.assert_clean(desk)
            for cohort, counts in desk.delta_b1_counts.items():
                expected = sum(('fastest_present' if full else 'skipped_fastest') == cohort
                               for _, full, _ in schedule)
                self.assertEqual((counts['quotes'], counts['outcomes'], counts['updates']), (expected,) * 3)
            paths = self.records(desk, 'delta_b1_outcome')
            self.assertEqual(len(paths), len(schedule))
            self.assertTrue(all(row['winTargetBps'] == 3000 for row in paths))

    def test_split_uses_gamma_outcome_time_target_and_new_day_start(self):
        desk = self.desk('split_skipped_tracker', brake=1, freeze_day_drop_bps=25)
        req = self.req()
        desk.quote(req)
        self.flush(desk)
        desk.brake_mode = 'brake'
        desk.learn('one', False)
        self.assertEqual(desk.markups[SKIPPED_TRACKER], 14962.5)  # same-day floor
        self.assertEqual(self.records(desk, 'delta_b1_outcome')[0]['winTargetBps'], 2200)
        desk.now += DAY
        req = self.req('tomorrow')
        req['respondBy'] += DAY
        for option in req['options']:
            option['deadline'] += DAY
        desk.quote(req)
        self.assertEqual(desk.day_starts[SKIPPED_TRACKER], (1, 14962.5))
        desk.learn('tomorrow', False)
        self.assertEqual(desk.markups[SKIPPED_TRACKER], 14962.5 * .9975)
        self.assert_clean(desk)

    def test_arrival_note_dates_order_and_exception_context_remain_local(self):
        desk = self.desk('split_skipped_tracker')
        req = self.req(text='Ready tomorrow at 10:00')
        desk.now = 700  # parsing still anchors to original arrival
        req['respondBy'] = 750
        original = deepcopy(req)
        desk.quote(req)
        self.assertEqual(desk.note_facts(req).ready_at, DAY + 600)
        self.assertEqual(req, original)
        self.assertEqual(list(desk.outbox[-1]['prices']), ['next_day', 'within_3_days'])
        desk.learn('one', False)
        desk.now = 500
        with patch.object(desk, 'price_option', side_effect=RuntimeError('offline failure')):
            with self.assertRaisesRegex(RuntimeError, 'offline failure'):
                desk.quote(self.req('failed', full=True))
        self.assertIsNone(desk._delta_b1_menu)
        self.assertNotIn('failed', desk.delta_b1_pending)
        desk.eligible_options(self.req('inspect'), 10, 0)
        self.assertIsNone(desk._delta_b1_menu)

    def test_actual_pair_composition_booking_change_and_cancel_match_gamma(self):
        baseline = json.loads((Path(__file__).resolve().parents[1] / 'models/gamma.json').read_text())['settings']
        outcomes = []
        for mode in B1_MODES:
            desk = self.desk(mode, **baseline)
            for index, full in enumerate((False, True)):
                req = self.req(str(index), full=full, pickup='a' if index == 0 else 'b',
                               delivery='b' if index == 0 else 'c')
                desk.quote(req)
                self.flush(desk)
                self.event(desk, 'order_won', order=order_for(req))
            posts = [a for a in desk.outbox if a['type'] == 'post']
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(posts[0]['stops']), 4)
            self.flush(desk)
            pair_id = desk.leg_gigs['0'][0]
            self.event(desk, 'gig_booked', gigId=pair_id, driverId='d', feeCents=12000)
            changed = deepcopy(desk.orders['0'])
            changed['deadline'] += 30
            self.event(desk, 'order_changed', order=changed)  # intercepted by pairs
            self.assertEqual(desk.orders['0']['deadline'], changed['deadline'])
            self.event(desk, 'order_cancelled', orderId='0', gigs=[{'gigId': pair_id, 'outcome': 'continues'}])
            self.assertNotIn('0', desk.orders)
            self.assertEqual(desk.leg_gigs['1'][0], pair_id)
            self.assert_clean(desk)
            outcomes.append((posts, desk.booked, desk.leg_gigs, self.records(desk, 'gamma_pair'),
                             self.records(desk, 'gamma_pair_booked')))
        control = self.desk(factory=make_gamma_notes_pairs, **baseline)
        for index, full in enumerate((False, True)):
            req = self.req(str(index), full=full, pickup='a' if index == 0 else 'b',
                           delivery='b' if index == 0 else 'c')
            control.quote(req)
            self.flush(control)
            self.event(control, 'order_won', order=order_for(req))
        self.assertEqual(outcomes[0][0], [a for a in control.outbox if a['type'] == 'post'])
        self.assertTrue(all(outcome == outcomes[0] for outcome in outcomes))

    def test_selected_gamma_neutral_parity_and_b1_clock_coalescing(self):
        baseline = json.loads((Path(__file__).resolve().parents[1] / 'models/gamma.json').read_text())['settings']
        for pairs in (0, 1):
            for mode in B1_MODES:
                runs = []
                for fast in (False, True):
                    world, stream, desks = LossWorld(), io.StringIO(), []
                    for event in world.pending:
                        if event['kind'] != 'price_request':
                            continue
                        req = event['request']
                        for leg in req['legs']:
                            for place in ('pickup', 'delivery'):
                                leg[place].update(hours=None, window={'from': 0, 'to': 14 * DAY})
                        req['options'] = [dict(kind=kind, deadline=req['respondBy'] + slack,
                                               listPriceCents=25000)
                                          for kind, slack in (('same_day', 100), ('next_day', 2200))]
                    tape = deepcopy(world.pending)

                    def factory(*args):
                        desk = make_delta(*args, **{**baseline, 'pairs': pairs}, delta_b1=mode)
                        desks.append(desk)
                        return desk
                    with redirect_stdout(io.StringIO()):
                        score = play_model(world, 8, Journal(stream), factory, fast=fast)
                    desk = desks[0]
                    self.assert_clean(desk)
                    runs.append((world.sent, score, desk.markup, desk.markups, desk.delta_b1_counts))
                    if mode == 'off':
                        gamma_world, gamma_stream = LossWorld(), io.StringIO()
                        # Reuse only the untouched tape, never a live world.
                        gamma_world.pending = tape
                        with redirect_stdout(io.StringIO()):
                            gamma_score = play_model(gamma_world, 8, Journal(gamma_stream),
                                                     lambda *args: make_gamma_notes_pairs(*args, **{**baseline, 'pairs': pairs}),
                                                     fast=fast)
                        self.assertEqual((world.sent, score, stream.getvalue()),
                                         (gamma_world.sent, gamma_score, gamma_stream.getvalue()))
                self.assertEqual(*runs)

    def test_b1_modes_and_invalid_combinations_validate(self):
        for invalid in (True, False, 1, 0, None, '', 'split', [], B1_MODES[1:3]):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'delta_b1'):
                self.desk(invalid)
        invalid_settings = [dict(delta_note_fixes=1), dict(delta_rescue_windows=1), dict(place_table=1),
                            dict(dealer_table=1), dict(capacity_valve=1), dict(supply_scale=1), dict(town_caps=1),
                            dict(town_reserve_pending=1), dict(markup_scope='dealer'), dict(markup_scope='km'),
                            dict(learn_bps=400), dict(win_target_bps=3100), dict(fee_shape='review')]
        for mode in B1_MODES[1:]:
            for settings in invalid_settings:
                with self.subTest(mode=mode, settings=settings), self.assertRaisesRegex(ValueError, 'delta_b1'):
                    self.desk(mode, **settings)
        with self.assertRaises(TypeError):
            self.desk(delta_b1_discount_bps=9100)
        # Disabling B1 preserves all existing Delta/Gamma settings combinations.
        self.desk('off', delta_note_fixes=1, delta_rescue_windows=1, capacity_valve=1, learn_bps=400)


class DeltaModelConfigTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_early_delta_is_gamma_plus_the_two_repairs(self):
        from compare import load_model
        early = load_model(self.ROOT / 'models/delta-early.json').spec
        gamma = json.loads((self.ROOT / 'models/gamma.json').read_text())['settings']
        self.assertEqual(early['factory'], 'delta:make_delta')
        self.assertEqual(early['settings'],
                         {**gamma, 'delta_note_fixes': 1, 'delta_rescue_windows': 1})

    def test_selected_delta_adds_capacity_switches_and_volume_target(self):
        from compare import load_model
        delta = load_model(self.ROOT / 'models/delta.json').spec
        early = json.loads((self.ROOT / 'models/delta-early.json').read_text())['settings']
        self.assertEqual(delta['factory'], 'delta:make_delta')
        self.assertEqual(delta['settings'],
                         {**early, 'win_target_bps': 4200, 'delta_wide_windows': 1,
                          'delta_private_delivery_rescue': 1, 'delta_pairing': 'extended'})


if __name__ == '__main__':
    unittest.main()
