from copy import deepcopy
import io
import json
from pathlib import Path
import unittest

from models.beta import MARKUP_MAX, MARKUP_MIN, MIN_SLACK, START_MARKUP, BetaDesk, BetaSettings
from compare import load_model
from demo import sample_request
from dispatch import Journal, JournalDesk, play_model
from tests.test_alpha import MarketWorld


ROOT = Path(__file__).resolve().parents[1]


def roomy_request():
    """The demo request, asked early enough that a driver has more than the 8-hour minimum."""
    request = sample_request()
    request.update(arrivedAt=500, respondBy=515)
    return request


class BetaTests(unittest.TestCase):
    def setUp(self):
        self.trace = io.StringIO()
        self.desk = BetaDesk(MarketWorld(), 8, 500, Journal(self.trace))

    def quote(self, identity, dealer='demo-dealer', **changes):
        request = roomy_request()
        request.update(id=identity, dealerId=dealer, **changes)
        self.desk.quote(request)
        return request

    def prices(self, request):
        return next(action for action in reversed(self.desk.outbox)
                    if action['type'] == 'quote' and action['requestId'] == request['id'])['prices']

    def lose(self, request):
        self.desk.handle({'seq': 1, 'at': 555, 'kind': 'order_lost', 'requestId': request['id']})

    def win(self, request, last_pickup=1080):
        order = {'id': request['id'], 'dealerId': request['dealerId'], 'option': 'same_day',
                 'priceCents': self.prices(request)['same_day'], 'deadline': 1200,
                 'legs': deepcopy(request['legs']), 'status': 'waiting',
                 'deliveredAt': [None] * len(request['legs']), 'lastPickupAt': last_pickup}
        self.desk.handle({'seq': 2, 'at': 555, 'kind': 'order_won', 'order': order})
        return order

    def ledger(self, request, kind, cents):
        self.desk.handle({'seq': 3, 'at': 700, 'kind': 'ledger',
                          'line': {'at': 700, 'kind': kind, 'cents': cents, 'orderId': request['id'],
                                   'gigId': None, 'detail': ''}})

    def test_each_option_is_priced_from_its_own_list_price(self):
        options = [{'kind': 'same_day', 'deadline': 1200, 'listPriceCents': 25_000},
                   {'kind': 'next_day', 'deadline': 2640, 'listPriceCents': 20_001}]
        request = self.quote('one', options=options)
        # 1.5 x list, rounded up to a whole cent.
        self.assertEqual(self.prices(request), {'same_day': 37_500, 'next_day': 30_002})

    def test_markup_follows_wins_and_losses_towards_the_target_share(self):
        target = self.desk.settings.win_target_bps / 10_000
        self.win(self.quote('won'))
        self.assertAlmostEqual(self.desk.markup, START_MARKUP * (1 + 0.02 * (1 - target)))
        raised = self.desk.markup
        self.lose(self.quote('lost'))
        self.assertAlmostEqual(self.desk.markup, raised * (1 - 0.02 * target))
        # At the target share the expected step is zero: 30 wins and 70 losses cancel to first order.
        self.assertAlmostEqual((1 - target) * target - target * (1 - target), 0)

    def test_markup_stays_inside_its_bounds_and_learns_once_per_quote(self):
        for index in range(60):
            self.lose(self.quote(f'lost-{index}'))
        self.assertEqual(self.desk.markup, MARKUP_MIN)
        request = self.quote('twice')
        self.lose(request)
        self.lose(request)  # a replayed event teaches nothing
        self.assertEqual(self.desk.markup, MARKUP_MIN)
        for index in range(60):
            self.win(self.quote(f'won-{index}'))
        self.assertEqual(self.desk.markup, MARKUP_MAX)

    def test_trust_counts_on_time_orders_and_halves_after_a_late_one(self):
        desk = self.desk
        for index in range(5):
            request = self.quote(f'on-time-{index}')
            self.win(request)
            self.ledger(request, 'revenue', 30_000)
        self.assertEqual(desk.trust['demo-dealer'], 5)
        late = self.quote('late')
        self.win(late)
        self.ledger(late, 'revenue', 30_000)
        self.ledger(late, 'late_refund', -3_000)
        self.assertEqual(desk.trust['demo-dealer'], 2)  # 5 on time, halved
        self.assertNotIn('other-dealer', desk.trust)

    def test_trust_raises_the_price_one_percent_per_order_up_to_25(self):
        desk = self.desk
        desk.trust['trusted'] = 10
        desk.markup = 15_000.0
        self.assertEqual(self.prices(self.quote('trusted-one', dealer='trusted'))['same_day'], 41_250)
        self.assertEqual(self.prices(self.quote('new-one', dealer='new'))['same_day'], 37_500)
        request = self.quote('cap', dealer='loyal')
        self.win(request)
        desk.trust['loyal'] = 25
        self.ledger(request, 'revenue', 30_000)
        self.assertEqual(desk.trust['loyal'], 25)

    def test_declines_long_routes_trade_ins_and_options_without_time_for_a_driver(self):
        desk = self.desk
        long_route = BetaDesk(MarketWorld(), 8, 500, Journal(io.StringIO()), BetaSettings(max_km=150))
        request = sample_request()
        request.update(arrivedAt=500, respondBy=515)
        long_route.quote(request)  # the demo route is 200 km
        self.assertEqual(long_route.outbox[-1]['prices'], {'same_day': 250_000})
        self.assertEqual(long_route.pending, set())
        trade_in = self.quote('trade-in', legs=sample_request()['legs'] * 2)
        self.assertEqual(self.prices(trade_in), {'same_day': 250_000})
        # Same-day at 20:00 with a 3-hour drive, decided at 09:15: 7.75 hours, under the 8-hour minimum.
        options = [{'kind': 'same_day', 'deadline': 1200, 'listPriceCents': 25_000},
                   {'kind': 'next_day', 'deadline': 2640, 'listPriceCents': 20_000}]
        self.assertEqual(desk.slack(sample_request(), options[0]), 1200 - 180 - 555)
        self.assertLess(desk.slack(sample_request(), options[0]), MIN_SLACK)
        later = sample_request()
        for stop in ('pickup', 'delivery'):
            later['legs'][0][stop]['window']['to'] = 2640
        self.assertEqual(set(self.prices(self.quote('later', options=options, legs=later['legs'],
                                                    arrivedAt=540, respondBy=555))), {'next_day'})
        tight = self.quote('tight', options=options[:1], arrivedAt=700, respondBy=715)
        self.assertEqual(self.prices(tight), {'same_day': 250_000})
        self.assertNotIn('tight', desk.pending)
        self.lose(tight)  # a decline is not market evidence
        self.assertEqual(desk.markup, START_MARKUP)

    def test_slack_respects_site_closing_times_and_ready_times(self):
        request = sample_request()
        option = {'kind': 'next_day', 'deadline': 2640, 'listPriceCents': 20_000}
        request['legs'][0]['pickup']['window'] = {'from': 540, 'to': 2640}
        request['legs'][0]['delivery']['window'] = {'from': 540, 'to': 2640}
        request['legs'][0]['pickup']['hours']['closes'] = 900  # pickup site shuts at 15:00
        # Deliver by 20:00 next day -> leave by 17:00, but the yard closes at 15:00 that day.
        self.assertEqual(self.desk.slack(request, option), 1440 + 900 - 555)
        request['legs'][0]['pickup']['window']['from'] = 2600  # ready too late for the drive
        self.assertEqual(self.desk.slack(request, option), -1)

    def test_fee_opens_below_the_typical_fee_and_reaches_the_cap_at_the_deadline_warning(self):
        desk = self.desk
        request = self.quote('fees')
        desk.now = 555
        order = {'id': 'fees', 'legs': request['legs'], 'lastPickupAt': 555 + 180 + 7 * 240}
        schedule = desk.fees_for(order, 1)
        self.assertEqual([step['feeCents'] for step in schedule],
                         [9_600, 10_800, 12_000, 13_200, 14_400, 15_600, 16_800, 18_000])
        self.assertEqual([step['at'] for step in schedule], [555 + 240 * k for k in range(8)])
        self.assertEqual(schedule[-1]['at'], order['lastPickupAt'] - 180)
        # With little time left the steps are never closer than an hour.
        order['lastPickupAt'] = 600
        self.assertEqual([step['at'] for step in desk.fees_for(order, 1)], [555 + 60 * k for k in range(8)])
        # After the deadline warning the starter's steep rescue fees apply.
        desk.urgent.add('fees')
        self.assertEqual(desk.fees_for(order, 1)[0]['feeCents'], 18_000)

    def test_notes_about_plates_and_manual_gearboxes_change_the_post(self):
        cases = {'Kilvet puuttuu, tuo siirtokilvet': (True, False), 'Inga skyltar på bilen': (True, False),
                 'Car has no plates, bring trade plates': (True, False), 'Ei rekkareita, koekilvet tarvitaan': (True, False),
                 'Huom manuaali': (False, True), 'käsivaihteinen': (False, True),
                 'Manual transmission, no automatic': (False, True), 'Kesärenkaat takakontissa': (False, False)}
        for index, (text, (plates, manual)) in enumerate(cases.items()):
            desk = BetaDesk(MarketWorld(), 8, 500, Journal(io.StringIO()))
            request = sample_request()
            request.update(id=f'note-{index}', note={'text': text, 'language': 'fi'}, arrivedAt=500, respondBy=515)
            desk.quote(request)
            order = {'id': request['id'], 'dealerId': 'demo-dealer', 'option': 'same_day', 'priceCents': 37_500,
                     'deadline': 1200, 'legs': deepcopy(request['legs']), 'status': 'waiting',
                     'deliveredAt': [None], 'lastPickupAt': 1020}
            desk.handle({'seq': 2, 'at': 555, 'kind': 'order_won', 'order': order})
            post = next(action for action in desk.outbox if action['type'] == 'post')
            self.assertEqual((post['stops'][0]['withPlates'], post['audience']['manualLicence']), (plates, manual), text)

    def test_low_levels_keep_starter_quotes(self):
        desk = BetaDesk(MarketWorld(), 3, 540, Journal(io.StringIO()))
        desk.quote(sample_request())  # even a tight request: below level 4 every quote wins at list
        self.assertEqual(desk.outbox[-1]['prices'], {'same_day': 25_000})

    def test_lost_quotes_are_declared_bookkeeping_for_fast_practice(self):
        self.assertEqual(BetaDesk.__dict__['passive_wake_events'], JournalDesk.passive_wake_events)
        self.lose(self.quote('quiet'))
        self.assertEqual([action['type'] for action in self.desk.outbox], ['quote'])

    def test_beta_config_runs_full_offline_flow_fast_and_full(self):
        model = load_model(ROOT / 'models' / 'beta.json')
        self.assertEqual(set(model.spec['settings']), {'win_target_bps', 'opening_fee_bps', 'max_km'})
        for fast in (False, True):
            trace = io.StringIO()
            world = MarketWorld()
            # The scripted request is decided at 09:15; a 19:00 pickup close leaves the driver time.
            scripted = world.pending[0]['request']
            scripted['options'][0]['deadline'] = 1380
            for stop in ('pickup', 'delivery'):
                scripted['legs'][0][stop]['window']['to'] = 1380
                scripted['legs'][0][stop]['hours']['closes'] = 1380
            score = play_model(world, 8, Journal(trace), model.factory, fast=fast)
            self.assertEqual(score['wonOrders'], 1)
            self.assertEqual(score['revenueCents'], 37_500)
            records = [json.loads(line) for line in trace.getvalue().splitlines()]
            self.assertIn('beta_quote', [record['type'] for record in records])
            posts = [action for record in records if record['type'] == 'action_intent'
                     for action in record['actions'] if action['type'] == 'post']
            self.assertEqual(posts[0]['schedule'][0]['feeCents'], 9_600)  # 0.8 x the typical fee

    def test_invalid_settings_fail_explicitly(self):
        for changes in ({'win_target_bps': 0}, {'win_target_bps': 10_000}, {'opening_fee_bps': 0},
                        {'opening_fee_bps': 20_000}, {'max_km': -1}, {'max_km': 1.5}, {'win_target_bps': True}):
            with self.assertRaises(ValueError, msg=changes):
                BetaSettings(**changes)


if __name__ == '__main__':
    unittest.main()
