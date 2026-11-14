from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest

from alpha import AlphaDesk, AlphaSettings, quote_cents
from compare import load_model
from demo import DemoWorld, sample_request
from dispatch import Journal, JournalDesk, play_model


ROOT = Path(__file__).resolve().parents[1]


class MarketWorld(DemoWorld):
    """Scripted execution with explicit public geography; no simulated market."""
    def __init__(self):
        super().__init__()
        self.client = self

    def map(self):
        places = ['demo-home', 'demo-helsinki', 'demo-tampere']
        distance = {('demo-home', 'demo-helsinki'): (30, 30),
                    ('demo-helsinki', 'demo-tampere'): (200, 180),
                    ('demo-home', 'demo-tampere'): (230, 210)}
        roads = []
        for start in places:
            for end in places:
                km, minutes = (0, 0) if start == end else distance.get((start, end), distance.get((end, start)))
                roads.append({'from': start, 'to': end, 'km': km, 'minutes': minutes})
        return {'places': [], 'roads': roads}

    def roster(self):
        return [{'id': f'driver-{i}', 'homePlaceId': 'demo-home', 'rating': 4.9,
                 'licence': 'manual', 'completedGigs': 100, 'drops': 0} for i in range(3)]


class AlphaTests(unittest.TestCase):
    def setUp(self):
        self.trace = io.StringIO()
        self.desk = AlphaDesk(MarketWorld(), 8, 540, Journal(self.trace))

    def quote(self, identity, dealer='demo-dealer', **changes):
        request = sample_request()
        request.update(id=identity, dealerId=dealer, **changes)
        self.desk.quote(request)
        return request

    def lose(self, request):
        self.desk.handle({'seq': 1, 'at': 555, 'kind': 'order_lost', 'requestId': request['id']})

    def win(self, request):
        quote = next(action for action in reversed(self.desk.outbox)
                     if action['type'] == 'quote' and action['requestId'] == request['id'])
        order = {'id': request['id'], 'dealerId': request['dealerId'], 'option': 'same_day',
                 'priceCents': quote['prices']['same_day'], 'deadline': 1200,
                 'legs': deepcopy(request['legs']), 'status': 'waiting',
                 'deliveredAt': [None] * len(request['legs']), 'lastPickupAt': 1080}
        self.desk.handle({'seq': 2, 'at': 555, 'kind': 'order_won', 'order': order})

    def test_formula_matches_discussed_example_and_rounds_only_final_price(self):
        settings = AlphaSettings()
        price, cost = quote_cents(10_000, 200, 30, 3, 2500, settings)
        self.assertEqual((price, cost), (14_625, 10_900))
        self.assertEqual(quote_cents(10_000, 200, 30, 3, 2800, settings)[0], 14_952)
        self.assertEqual(quote_cents(10_000, 200, 30, 3, 2200, settings)[0], 14_298)
        self.assertEqual(quote_cents(10_001, 0, 0, 2, 2500, settings)[0], 13_835)

    def test_distance_floor_deadhead_scarcity_and_minimum_margin_affect_price(self):
        settings = AlphaSettings()
        baseline = quote_cents(10_000, 200, 30, 3, 2500, settings)[0]
        for changes in ((10_000, 400, 30, 3), (10_000, 200, 100, 3), (10_000, 200, 30, 0)):
            self.assertGreater(quote_cents(*changes, 2500, settings)[0], baseline)
        self.assertEqual(quote_cents(1000, 0, 0, 3, 1500, settings)[0], 4000)

    def test_feedback_is_per_dealer_and_consumed_once(self):
        request = self.quote('one')
        self.win(request)
        self.win(request)
        self.assertEqual(self.desk.dealer_margins['demo-dealer'], 2800)
        second = self.quote('two', dealer='another-dealer')
        self.lose(second)
        self.lose(second)
        self.assertEqual(self.desk.dealer_margins, {'demo-dealer': 2800, 'another-dealer': 2200})
        self.lose(self.quote('three'))
        self.assertEqual(self.desk.dealer_margins['demo-dealer'], 2500)

    def test_feedback_respects_bounds_and_ignores_rejected_and_unknown_quotes(self):
        self.desk = AlphaDesk(MarketWorld(), 8, 540, Journal(self.trace),
                              AlphaSettings(min_margin_bps=2400, max_margin_bps=2600))
        self.lose(self.quote('one'))
        self.assertEqual(self.desk.dealer_margins['demo-dealer'], 2400)
        self.win(self.quote('two'))
        self.assertEqual(self.desk.dealer_margins['demo-dealer'], 2600)
        request = self.quote('rejected')
        self.desk.read_results([self.desk.outbox[-1]], [{'ok': False, 'reason': 'Too late'}])
        self.lose(request)
        self.lose({'id': 'unknown'})
        self.assertEqual(self.desk.dealer_margins['demo-dealer'], 2600)
        self.assertNotIn('rejected', self.desk.reservations)

    def test_reservations_prevent_burst_quotes_counting_same_driver(self):
        for index in range(3):
            self.quote(str(index))
        self.assertEqual(len(set(self.desk.reservations.values())), 3)
        self.quote('declined')
        self.assertGreaterEqual(self.desk.outbox[-1]['prices']['same_day'], 1_000_000)
        self.assertNotIn('declined', self.desk.pending_quotes)
        self.lose({'id': 'declined'})
        self.assertEqual(self.desk.dealer_margins, {})
        self.lose({'id': '0'})
        self.quote('capacity-released')
        self.assertIn('capacity-released', self.desk.reservations)

    def test_booking_and_final_delivery_update_busy_driver_and_known_position(self):
        request = self.quote('one')
        self.win(request)
        self.desk.send()
        gig_id = next(iter(self.desk.posts))
        self.desk.handle({'seq': 3, 'at': 560, 'kind': 'gig_booked', 'gigId': gig_id,
                          'driverId': 'driver-0', 'feeCents': 12000})
        self.assertNotIn('one', self.desk.reservations)
        self.assertIn('driver-0', self.desk.gig_drivers.values())
        self.desk.handle({'seq': 4, 'at': 700, 'kind': 'delivered', 'gigId': gig_id,
                          'orderId': 'one', 'leg': 0, 'placeId': 'demo-tampere'})
        self.assertNotIn('driver-0', self.desk.gig_drivers.values())
        self.assertEqual(self.desk.positions['driver-0'], ('demo-tampere', 700))
        self.desk.now = 700
        candidates = self.desk.candidates(sample_request(), sample_request()['options'][0])
        self.assertEqual(dict((driver, km) for km, driver in candidates)['driver-0'], 200)
        self.desk.now = 821
        candidates = self.desk.candidates(sample_request(), sample_request()['options'][0])
        self.assertEqual(dict((driver, km) for km, driver in candidates)['driver-0'], 30)

    def test_premium_eligibility_and_windows_gate_quotes(self):
        for driver in self.desk.drivers.values():
            driver['rating'] = 4.7
        request = sample_request()
        request['legs'][0]['car']['premium'] = True
        self.quote('premium', legs=request['legs'])
        self.assertNotIn('premium', self.desk.reservations)
        self.quote('impossible', options=[{'kind': 'same_day', 'deadline': 600, 'listPriceCents': 25000}])
        self.assertNotIn('impossible', self.desk.reservations)

    def test_multi_option_quote_reserves_only_one_driver_and_route_counts_trade_in(self):
        options = sample_request()['options'] + [{'kind': 'next_day', 'deadline': 2640, 'listPriceCents': 30000}]
        self.quote('one', options=options)
        self.assertEqual(set(self.desk.outbox[-1]['prices']), {'same_day', 'next_day'})
        self.assertEqual(len(self.desk.reservations), 1)
        request = sample_request()
        request['legs'].append(deepcopy(request['legs'][0]))
        # H->T, T->H repositioning, H->T: all driving between stops counts.
        self.assertEqual(self.desk.route_distance(request), (600, 540))

    def test_multi_option_reservation_fits_every_quoted_option(self):
        options = sample_request()['options'] + [{'kind': 'next_day', 'deadline': 2640, 'listPriceCents': 30000}]
        lists = {'same_day': [(30, 'driver-0')], 'next_day': [(10, 'driver-1'), (30, 'driver-0')]}
        self.desk.candidates = lambda request, option: lists[option['kind']]
        self.quote('shared', options=options)
        self.assertEqual(self.desk.reservations['shared'], 'driver-0')
        lists['next_day'] = [(5, 'driver-2'), (10, 'driver-1')]
        self.quote('disjoint', options=options)
        self.assertEqual(self.desk.reservations['disjoint'], 'driver-0')

    def test_booking_by_another_reserved_driver_moves_that_reservation(self):
        first = self.quote('first')
        self.win(first)
        self.desk.send()  # the demo world knows one request, so quote the second afterwards
        self.quote('second')
        estimated, displaced = self.desk.reservations['first'], self.desk.reservations['second']
        self.assertNotEqual(estimated, displaced)
        gig_id = next(iter(self.desk.posts))
        self.desk.handle({'seq': 3, 'at': 560, 'kind': 'gig_booked', 'gigId': gig_id,
                          'driverId': displaced, 'feeCents': 12000})
        self.assertNotIn('first', self.desk.reservations)
        self.assertEqual(self.desk.reservations['second'], estimated)
        busy = set(self.desk.gig_drivers.values()) | set(self.desk.reservations.values())
        self.assertEqual(busy, {estimated, displaced})

    def test_reassigned_reservation_uses_only_a_driver_feasible_for_that_quote(self):
        first = self.quote('first')
        self.win(first)
        self.desk.send()
        self.quote('second')
        estimated, displaced = self.desk.reservations['first'], self.desk.reservations['second']
        original = self.desk.candidates
        self.desk.candidates = lambda request, option: [c for c in original(request, option) if c[1] != estimated]
        gig_id = next(iter(self.desk.posts))
        self.desk.handle({'seq': 3, 'at': 560, 'kind': 'gig_booked', 'gigId': gig_id,
                          'driverId': displaced, 'feeCents': 12000})
        self.assertNotIn(self.desk.reservations['second'], {estimated, displaced})
        self.desk.candidates = lambda request, option: []
        self.desk.reservations['third'] = 'driver-9'
        self.desk.requests['third'] = sample_request()
        self.desk.quoted_options['third'] = {'same_day'}
        self.desk.gig_drivers.clear()
        self.desk.handle({'seq': 4, 'at': 561, 'kind': 'gig_booked', 'gigId': gig_id,
                          'driverId': 'driver-9', 'feeCents': 12000})
        self.assertNotIn('third', self.desk.reservations)

    def test_reestimate_ignores_unquoted_options_and_keeps_feasible_ones(self):
        options = sample_request()['options'] + [{'kind': 'next_day', 'deadline': 2640, 'listPriceCents': 30000}]
        self.quote('two-options', options=options)
        self.desk.quoted_options['two-options'] = {'next_day'}
        self.desk.reservations['two-options'] = 'driver-0'
        lists = {'same_day': [(1, 'driver-1')], 'next_day': [(5, 'driver-2')]}
        self.desk.candidates = lambda request, option: lists[option['kind']]
        self.desk.reserve_again('two-options')
        self.assertEqual(self.desk.reservations['two-options'], 'driver-2')
        self.desk.quoted_options['two-options'] = {'same_day', 'next_day'}
        lists['same_day'] = []
        self.desk.reserve_again('two-options')
        self.assertEqual(self.desk.reservations['two-options'], 'driver-2')

    def test_booking_of_unreserved_order_releases_the_driver_it_used(self):
        declined = self.quote('declined')
        self.desk.reservations.pop('declined')  # e.g. a high-price decline that still won
        self.win(declined)
        self.desk.send()
        self.quote('other')
        taken = self.desk.reservations['other']
        gig_id = next(iter(self.desk.posts))
        self.desk.handle({'seq': 3, 'at': 560, 'kind': 'gig_booked', 'gigId': gig_id,
                          'driverId': taken, 'feeCents': 12000})
        self.assertNotEqual(self.desk.reservations.get('other'), taken)

    def test_expired_and_duplicate_requests_do_not_queue_quotes(self):
        request = self.quote('one')
        self.desk.quote(request)
        self.assertEqual(len(self.desk.outbox), 1)
        self.desk.now = request['respondBy']
        self.quote('expired')
        self.assertEqual(len(self.desk.outbox), 1)

    def test_low_levels_preserve_starter_quote_and_driver_fee_schedules(self):
        for level in (1, 2, 3):
            self.desk = AlphaDesk(MarketWorld(), level, 540, Journal(self.trace))
            request = self.quote(f'level-{level}')
            self.assertEqual(self.desk.outbox[-1]['prices'], {'same_day': 25000})
            self.win(request)
            self.assertEqual(self.desk.dealer_margins, {})
            starter = JournalDesk(None, level, 540, Journal(io.StringIO()))
            starter.requests[request['id']] = request
            order = self.desk.orders[request['id']]
            self.assertEqual(self.desk.fees_for(order, 1), starter.fees_for(order, 1))
            self.desk.urgent.add(request['id'])
            starter.urgent.add(request['id'])
            self.assertEqual(self.desk.fees_for(order, 1), starter.fees_for(order, 1))

    def test_alpha_config_runs_full_offline_flow_and_records_decisions(self):
        model = load_model(ROOT / 'models' / 'alpha.json')
        with redirect_stdout(io.StringIO()):
            score = play_model(MarketWorld(), 8, Journal(self.trace), model.factory)
        self.assertTrue(score['ranked'])
        self.assertGreater(score['marginCents'], 0)
        records = [json.loads(line) for line in self.trace.getvalue().splitlines()]
        self.assertTrue(any(record['type'] == 'alpha_quote' for record in records))
        self.assertTrue(any(record['type'] == 'alpha_feedback' for record in records))

    def test_invalid_settings_fail_explicitly(self):
        for changes in ({'initial_margin_bps': 100}, {'feedback_step_bps': 0},
                        {'max_margin_bps': 1000}, {'nearby_km': 0},
                        {'min_margin_cents': -1}, {'feedback_step_bps': True},
                        {'distance_cents_per_km': 0.45}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                AlphaSettings(**changes)


if __name__ == '__main__':
    unittest.main()
