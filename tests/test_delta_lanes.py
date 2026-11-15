"""Offline B2 contracts; scripted receipts/outcomes do not measure economics."""
from copy import deepcopy
from fractions import Fraction
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from models.delta import make_delta
from models.delta_b1 import B1_MODES
from models.delta_lanes import HUBS, LANE_MODES, REMOTE_DESTINATIONS
from dispatch import Journal
from models.gamma import PLACE_IDS
from models.gamma_notes import make_gamma_notes_pairs
from spread.starter import DAY, Retry
from tests.test_gamma import request
from tests.test_gamma_pairs import PairWorld
from tests.test_notes import order_for


BASELINE = json.loads((Path(__file__).resolve().parents[1] / 'models/gamma.json').read_text())['settings']


class LaneWorld(PairWorld):
    """In-memory map and action receipts; no client or market simulation."""
    def __init__(self):
        super().__init__()
        self.initial_map = {'places': [{'id': place} for place in PLACE_IDS], 'roads': [
            {'from': origin, 'to': destination, 'km': 0 if origin == destination else 10,
             'minutes': 0 if origin == destination else 30}
            for origin in PLACE_IDS for destination in PLACE_IDS]}


class DeltaLaneTests(unittest.TestCase):
    def desk(self, mode='off', *, factory=make_delta, level=8, **settings):
        stream = io.StringIO()
        switches = {'delta_lanes': mode} if factory is make_delta else {}
        desk = factory(LaneWorld(), level, 500, Journal(stream),
                       **{**BASELINE, **settings, **switches})
        desk.trace = stream
        return desk

    def req(self, identity='one', pickup='tampere', delivery='vantaa'):
        return request(identity, slacks=(900, 1800, 3000), pickup=pickup, delivery=delivery)

    def offer(self, desk, req=None, km=120):
        req = self.req() if req is None else req
        if len(req['legs']) == 1:
            road = (req['legs'][0]['pickup']['placeId'], req['legs'][0]['delivery']['placeId'])
            desk.roads[road]['km'] = km
        desk.quote(req)
        return desk._outbox[-1]['prices']

    def records(self, desk, kind='delta_lane_quote'):
        return [row for row in map(json.loads, desk.trace.getvalue().splitlines()) if row['type'] == kind]

    def event(self, desk, kind, **data):
        desk.handle(dict(seq=1, at=desk.now, kind=kind, **data))

    def flush(self, desk):
        actions, desk.outbox = desk.outbox, []
        desk.read_results(actions, desk.world.act(actions))
        return actions

    def test_exact_five_hubs_without_eight_town_origin_expansion(self):
        exact = {'vantaa', 'helsinki', 'espoo', 'hyvinkaa', 'porvoo'}
        self.assertEqual(HUBS, exact)
        desk = self.desk('inbound_9100')
        for origin in PLACE_IDS:
            for destination in exact:
                with self.subTest(origin=origin, destination=destination):
                    req = self.req(pickup=origin, delivery=destination)
                    self.assertEqual(desk.lane_factor_bps(req, 120), 10000 if origin in exact else 9100)
        for origin in ('tampere', 'lempaala', 'raisio'):
            req = self.req(origin, pickup=origin)
            self.offer(desk, req)
            row = self.records(desk)[-1]
            self.assertEqual(row['cohort'], 'inbound')
            self.assertEqual(row['diagnosticGroup'], 'inbound_retrospective_excluded')
            self.assertTrue(row['retrospectiveExcludedOrigin'])
            self.assertEqual(row['laneFactorBps'], 9100)

    def test_outbound_exact_destinations_without_origin_restriction(self):
        remote = {'savonlinna', 'kajaani', 'kotka', 'ylivieska', 'kokkola', 'seinajoki',
                  'mikkeli', 'rovaniemi', 'vaasa', 'lappeenranta', 'kouvola', 'pori'}
        self.assertEqual(REMOTE_DESTINATIONS, remote)
        desk = self.desk('outbound_10600')
        for destination in PLACE_IDS:
            for origin in ('helsinki', 'tampere', 'lempaala', 'raisio', 'oulu', 'pori'):
                with self.subTest(origin=origin, destination=destination):
                    self.assertEqual(desk.lane_factor_bps(self.req(pickup=origin, delivery=destination), 100),
                                     10600 if destination in remote else 10000)

    def test_thresholds_at_59_60_and_99_100_use_gamma_distance(self):
        cases = [('tampere', 'vantaa', 59, 10000), ('tampere', 'vantaa', 60, 9100),
                 ('oulu', 'pori', 99, 10000), ('oulu', 'pori', 100, 10400)]
        for origin, destination, km, expected in cases:
            with self.subTest(km=km, destination=destination):
                desk = self.desk('inbound_9100_outbound_10400')
                self.offer(desk, self.req(pickup=origin, delivery=destination), km)
                row = self.records(desk)[0]
                self.assertEqual((row['routeKm'], row['laneFactorBps']), (km, expected))
                self.assertEqual(self.records(desk, 'beta_quote')[0]['routeKm'], km)

    def test_five_treatments_apply_both_arms_independently(self):
        expected = {'off': (10000, 10000), 'inbound_9100': (9100, 10000),
                    'outbound_10400': (10000, 10400), 'outbound_10600': (10000, 10600),
                    'inbound_9100_outbound_10400': (9100, 10400),
                    'inbound_9100_outbound_10600': (9100, 10600)}
        self.assertEqual(set(LANE_MODES), set(expected))
        for mode, factors in expected.items():
            for (origin, destination), factor in zip((('turku', 'vantaa'), ('oulu', 'pori')), factors):
                with self.subTest(mode=mode, origin=origin):
                    desk, control = self.desk(mode), self.desk(factory=make_gamma_notes_pairs)
                    req = self.req(pickup=origin, delivery=destination)
                    prices, unchanged = self.offer(desk, req), self.offer(control, deepcopy(req))
                    self.assertEqual(prices.keys(), unchanged.keys())
                    for option in req['options']:
                        exact = Fraction(option['listPriceCents'] * 15000 * factor, 10000 ** 2)
                        self.assertEqual(prices[option['kind']], -(-exact.numerator // exact.denominator))

    def test_every_option_kind_and_multi_option_menu_get_one_factor(self):
        for selection in ((0,), (1,), (2,), (0, 1), (1, 2), (2, 0, 1)):
            for destination, factor in (('vantaa', 9100), ('pori', 10600)):
                with self.subTest(selection=selection, destination=destination):
                    desk = self.desk('inbound_9100_outbound_10600')
                    req = self.req(delivery=destination)
                    req['options'] = [req['options'][index] for index in selection]
                    original = deepcopy(req)
                    prices = self.offer(desk, req)
                    self.assertEqual(list(prices), [o['kind'] for o in req['options']])
                    self.assertEqual(req, original)
                    base = self.records(desk, 'beta_quote')[0]
                    self.assertTrue(all(f['deltaLaneBps'] == factor for f in base['optionFactors'].values()))
                    self.assertEqual(base['prices'], self.records(desk)[0]['prices'])
                    self.assertEqual(base['prices'], prices)

    def test_gamma_route_sum_and_first_pickup_final_delivery_for_multileg(self):
        for kms, expected in (((29, 30), 10000), ((30, 30), 9100)):
            desk = self.desk('inbound_9100', trade_ins=1)
            req = self.req(pickup='tampere', delivery='oulu')
            req['legs'].append(deepcopy(self.req(pickup='oulu', delivery='vantaa')['legs'][0]))
            for leg, km in zip(req['legs'], kms):
                desk.roads[leg['pickup']['placeId'], leg['delivery']['placeId']]['km'] = km
            # A direct first-to-last road must not determine the cohort distance.
            desk.roads['tampere', 'vantaa']['km'] = 1000
            self.offer(desk, req)
            row = self.records(desk)[0]
            self.assertEqual((row['routeKm'], row['laneFactorBps']), (sum(kms), expected))
            self.assertEqual((row['pickupPlaceId'], row['deliveryPlaceId']), ('tampere', 'vantaa'))
        desk = self.desk('inbound_9100_outbound_10600', trade_ins=1)
        req = self.req(pickup='helsinki', delivery='vantaa')
        req['legs'].append(deepcopy(self.req(pickup='tampere', delivery='pori')['legs'][0]))
        for leg in req['legs']:
            desk.roads[leg['pickup']['placeId'], leg['delivery']['placeId']]['km'] = 50
        self.offer(desk, req)
        self.assertEqual(self.records(desk)[0]['laneFactorBps'], 10600)

    def test_exact_final_ceiling_with_markup_trust_option_and_long_factors(self):
        for mode, factor, destination in (('inbound_9100', 9100, 'vantaa'),
                                          ('outbound_10400', 10400, 'pori'),
                                          ('outbound_10600', 10600, 'pori')):
            desk = self.desk(mode, max_km=100, long_max_km=700, long_markup_bps=10301,
                             next_day_bps=9801, within_3_days_bps=10003)
            desk.markup = 15001.9
            desk.trust['D01'] = 7
            req = self.req(delivery=destination)
            req['options'][1]['listPriceCents'] = 20001
            prices = self.offer(desk, req)
            self.assertNotIn('same_day', prices)  # unchanged Gamma long-route guard
            for option in req['options'][1:]:
                exact = (Fraction(option['listPriceCents'] * 15001 * 10700, 10000 ** 2)
                         * Fraction(10301, 10000) * Fraction(factor, 10000)
                         * Fraction(getattr(desk.settings, option['kind'] + '_bps'), 10000))
                self.assertEqual(prices[option['kind']], -(-exact.numerator // exact.denominator))
        # A staged cent ceiling would charge 2 cents; exact composition charges 1.
        desk = self.desk('inbound_9100', start_markup_bps=10001, markup_min_bps=1)
        req = self.req()
        req['options'] = [{**req['options'][1], 'listPriceCents': 1}]
        self.assertEqual(self.offer(desk, req), {'next_day': 1})

    def test_no_new_short_discount_and_existing_gamma_short_factor_survives(self):
        for mode in LANE_MODES:
            for km in (0, 44, 45, 59):
                for destination in ('vantaa', 'pori'):
                    desk, control = self.desk(mode), self.desk(factory=make_gamma_notes_pairs)
                    req = self.req(delivery=destination)
                    self.assertEqual(self.offer(desk, req, km), self.offer(control, deepcopy(req), km))
                    row = self.records(desk, 'beta_quote')[0]
                    for factors in row['optionFactors'].values():
                        self.assertEqual(factors['shortBps'], 9200 if km < 45 else 10000)
                        if mode != 'off':
                            self.assertGreaterEqual(factors['deltaLaneBps'], 10000)
        # Even a selected Gamma short band extending past 60 remains composed.
        desk = self.desk('inbound_9100', short_km=70)
        self.offer(desk, km=60)
        factors = self.records(desk, 'beta_quote')[0]['optionFactors']['same_day']
        self.assertEqual((factors['shortBps'], factors['deltaLaneBps']), (9200, 9100))

    def test_eligibility_and_selected_menu_match_gamma(self):
        cases = [({'premium_min_slack_minutes': 1800}, 'premium'),
                 ({'same_day_min_slack_minutes': 1800}, None),
                 ({'trust_guard': 1}, 'trust'), ({'quote_options': 'no_same_day'}, None),
                 ({'quote_options': 'cheapest_only'}, None), ({'quote_options': 'slowest_only'}, None),
                 ({'max_km': 100, 'long_max_km': 700}, None), ({'brake': 1}, 'brake'),
                 ({}, 'readiness')]
        for settings, guard in cases:
            desks = [self.desk('inbound_9100', **settings), self.desk(factory=make_gamma_notes_pairs, **settings)]
            req = self.req()
            req['options'][0]['deadline'] = 1000
            if guard == 'premium':
                req['legs'][0]['car']['premium'] = True
            if guard == 'readiness':
                req['note'] = {'text': 'Ready tomorrow at 10:00', 'language': 'en'}
            for desk in desks:
                if guard == 'trust':
                    desk.trust['D01'] = 10
                if guard == 'brake':
                    desk.brake_warnings.extend([desk.now] * desk.settings.brake_hard_warnings)
                self.offer(desk, deepcopy(req))
            self.assertEqual(desks[0]._outbox[-1]['prices'].keys(), desks[1]._outbox[-1]['prices'].keys())
            self.assertEqual(desks[0].pending, desks[1].pending)

    def test_declines_low_levels_duplicates_expiry_and_exceptions_have_no_lane_record(self):
        for decline in ('route', 'time', 'trade_in', 'premium'):
            desk, req = self.desk('inbound_9100'), self.req()
            km = 120
            if decline == 'route':
                km = 701
            elif decline == 'time':
                for option in req['options']:
                    option['deadline'] = 600
            elif decline == 'trade_in':
                req['legs'] *= 2
            else:
                req['legs'][0]['car']['premium'] = True
                req['options'] = [{**req['options'][0], 'deadline': 1100}]
            control = self.desk(factory=make_gamma_notes_pairs)
            self.assertEqual(self.offer(desk, req, km), self.offer(control, deepcopy(req), km))
            self.assertFalse(self.records(desk))
            self.assertFalse(desk.delta_lane_counts)
        for level in (1, 2, 3):
            desk, control = self.desk('inbound_9100', level=level), self.desk(factory=make_gamma_notes_pairs, level=level)
            self.assertEqual(self.offer(desk), self.offer(control))
            self.assertFalse(self.records(desk))
        desk, req = self.desk('inbound_9100'), self.req()
        desk.now = req['respondBy']
        desk.quote(req)
        self.assertEqual(desk._outbox, [])
        desk.now = 500
        self.offer(desk, req)
        desk.quote(req)
        self.assertEqual(len(self.records(desk)), 1)
        with patch.object(desk, 'price_option', side_effect=RuntimeError('offline failure')):
            with self.assertRaisesRegex(RuntimeError, 'offline failure'):
                self.offer(desk, self.req('failed'))
        self.assertEqual(len(self.records(desk)), 1)
        self.assertNotIn('failed', desk.pending)

    def test_learner_and_outcome_handling_are_gamma_for_every_arm(self):
        for mode in LANE_MODES:
            desks = [self.desk(mode), self.desk(factory=make_gamma_notes_pairs)]
            for index, won in enumerate((False, True, False, True)):
                for desk in desks:
                    req = self.req(str(index), delivery='vantaa' if index % 2 else 'pori')
                    self.offer(desk, req)
                    self.flush(desk)
                    if won:
                        self.event(desk, 'order_won', order=order_for(req))
                        self.event(desk, 'ledger', line={'kind': 'revenue', 'orderId': req['id'], 'cents': 30000})
                    else:
                        self.event(desk, 'order_lost', requestId=req['id'])
                for name in ('markup', 'markups', 'pending', 'quote_trackers', 'day_starts', 'trust', 'dealers'):
                    self.assertEqual(getattr(desks[0], name), getattr(desks[1], name))
                self.assertEqual(desks[0].delta_b1_pending, {})

    def test_rejected_receipt_uses_gamma_cleanup_without_learning(self):
        for mode in LANE_MODES:
            desks = [self.desk(mode), self.desk(factory=make_gamma_notes_pairs)]
            for desk in desks:
                self.offer(desk)
                with self.assertLogs('cheap-drive', level='WARNING'):
                    desk.read_results([desk._outbox[-1]], [{'ok': False, 'reason': 'offline rejection'}])
                desk.learn('one', False)
            for name in ('markup', 'pending', 'quote_trackers', 'town_pending'):
                self.assertEqual(getattr(desks[0], name), getattr(desks[1], name))
            self.assertEqual(desks[0].markup, 15000)

    def test_default_off_exact_quote_and_journal_parity_for_selected_gamma(self):
        for pairs in (0, 1):
            for mode in (None, 'off'):
                control = self.desk(factory=make_gamma_notes_pairs, pairs=pairs)
                desk = self.desk(pairs=pairs) if mode == 'off' else make_delta(
                    LaneWorld(), 8, 500, Journal(io.StringIO()), **{**BASELINE, 'pairs': pairs})
                req = self.req()
                for current in (desk, control):
                    self.offer(current, deepcopy(req))
                self.assertEqual(desk._outbox, control._outbox)
                self.assertEqual(desk.journal.output.getvalue(), control.journal.output.getvalue())
                self.assertFalse(desk.delta_lane_counts)

    def test_pair_posts_booking_change_cancel_and_fees_preserve_selected_gamma(self):
        runs = []
        for mode in (*LANE_MODES, None):
            desk = self.desk(mode) if mode is not None else self.desk(factory=make_gamma_notes_pairs)
            for index, origin, destination in ((0, 'tampere', 'vantaa'), (1, 'vantaa', 'pori')):
                req = self.req(str(index), origin, destination)
                self.offer(desk, req)
                self.flush(desk)
                order = order_for(req)
                self.event(desk, 'order_won', order=order)
            posts = deepcopy([a for a in desk._outbox if a['type'] == 'post'])
            self.assertEqual(len(posts), 1)
            self.assertEqual(len(posts[0]['stops']), 4)
            self.flush(desk)
            gig = desk.leg_gigs['0'][0]
            self.event(desk, 'gig_booked', gigId=gig, driverId='driver', feeCents=12000)
            changed = deepcopy(desk.orders['0'])
            changed['deadline'] += 30
            self.event(desk, 'order_changed', order=changed)
            self.event(desk, 'order_cancelled', orderId='0', gigs=[{'gigId': gig, 'outcome': 'continues'}])
            runs.append((posts, desk._outbox, desk.booked, desk.leg_gigs,
                         self.records(desk, 'gamma_pair'), self.records(desk, 'gamma_pair_booked')))
        self.assertTrue(all(run == runs[-1] for run in runs))
        # Segment floors, urgent fees, and plate/charging retry flags remain Gamma's.
        for km, premium in ((44, False), (120, True)):
            desks = [self.desk('inbound_9100'), self.desk(factory=make_gamma_notes_pairs)]
            fees = []
            for desk in desks:
                req = self.req()
                req['legs'][0]['car']['premium'] = premium
                req['legs'][0]['car'].update(electric=True, chargePercent=10)
                self.offer(desk, req, km)
                order = order_for(req)
                ordinary = desk.fees_for(order, 1)
                desk.urgent.add('one')
                fees.append((ordinary, desk.fees_for(order, 1)))
                desk.urgent.clear()
                desk.post(order, [0], Retry(plates=True))
                pickup = desk._outbox[-1]['stops'][0]
                self.assertTrue(pickup['withPlates'])
                self.assertTrue(pickup['withCharging'])
            self.assertEqual(*fees)
            self.assertEqual(desks[0]._outbox[-1], desks[1]._outbox[-1])

    def test_active_arms_leave_noncohort_quotes_neutral_with_pairs_on_and_off(self):
        for mode in LANE_MODES:
            for pairs in (0, 1):
                for origin, destination in (('helsinki', 'vantaa'), ('oulu', 'tampere'),
                                            ('tampere', 'lempaala'), ('raisio', 'turku')):
                    with self.subTest(mode=mode, pairs=pairs, lane=(origin, destination)):
                        desks = [self.desk(mode, pairs=pairs),
                                 self.desk(factory=make_gamma_notes_pairs, pairs=pairs)]
                        for desk in desks:
                            self.offer(desk, self.req(pickup=origin, delivery=destination))
                        self.assertEqual(desks[0]._outbox, desks[1]._outbox)
                        self.assertEqual(desks[0].quote_trackers, desks[1].quote_trackers)

    def test_diagnostics_are_quote_counts_with_matching_prices_and_no_raw_notes(self):
        desk = self.desk('inbound_9100_outbound_10400')
        for index, origin, destination in ((0, 'turku', 'vantaa'), (1, 'tampere', 'vantaa'),
                                            (2, 'oulu', 'pori'), (3, 'helsinki', 'espoo')):
            req = self.req(str(index), origin, destination)
            req['note'] = {'text': 'Private reference XYZ_76342', 'language': 'en'}
            prices = self.offer(desk, req)
            row = self.records(desk)[-1]
            self.assertEqual(row['prices'], prices)
            self.assertEqual(row['optionKeys'], list(prices))
            self.assertNotIn('XYZ_76342', json.dumps(row))
        self.assertEqual(dict(desk.delta_lane_counts),
                         {'inbound': 1, 'inbound_retrospective_excluded': 1, 'outbound': 1, 'other': 1})

    def test_invalid_modes_and_unqualified_combinations_fail_at_factory(self):
        for mode in (True, False, None, 0, 9100, '', 'inbound', [], {}, ['inbound_9100', 'outbound_10400']):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'delta_lanes'):
                self.desk(mode)
        invalid = [dict(delta_note_fixes=1), dict(delta_rescue_windows=1), dict(dealer_table=1),
                   dict(place_table=1), dict(capacity_valve=1), dict(supply_scale=1), dict(town_caps=1),
                   dict(town_reserve_pending=1), dict(markup_scope='dealer'), dict(markup_scope='km'),
                   dict(learn_bps=201), dict(win_target_bps=3100), dict(trust_bps_per_order=50),
                   dict(fee_shape='review')]
        for mode in tuple(LANE_MODES)[1:]:
            for settings in (*invalid, *(dict(delta_b1=b1) for b1 in B1_MODES[1:])):
                with self.subTest(mode=mode, settings=settings), self.assertRaisesRegex(ValueError, 'delta_lanes'):
                    self.desk(mode, **settings)
        with self.assertRaises(TypeError):
            self.desk(delta_lane_bps=9100)
        # Off preserves existing supported combinations, including active B1.
        for settings in invalid:
            self.desk('off', **settings)
        for b1 in B1_MODES:
            self.desk('off', delta_b1=b1)


if __name__ == '__main__':
    unittest.main()
