"""Offline, scripted SDK contracts; these tests never construct a network client."""
from copy import deepcopy
import io
import json
import unittest
from unittest.mock import patch

from beta import BetaDesk
from demo import sample_request
from dispatch import Journal, handle_batch, play_model
from gamma import GammaCoreDesk
from gamma_pairs import DriverSideSettings, make_gamma_pairs, make_pairs_beta
from spread.starter import retry_from, steep
from tests.test_alpha import MarketWorld


def order_for(request, deadline=6000):
    order = dict(id=request['id'], dealerId=request['dealerId'], option='same_day',
                 priceCents=30000, deadline=deadline, legs=deepcopy(request['legs']),
                 status='waiting', deliveredAt=[None] * len(request['legs']), lastPickupAt=deadline - 180)
    for leg in order['legs']:
        for kind in ('pickup', 'delivery'):
            leg[kind]['window'] = {'from': 480, 'to': deadline}
    return order


def new_desk(factory=make_pairs_beta, now=600, **settings):
    stream = io.StringIO()
    return factory(MarketWorld(), 8, now, Journal(stream), **settings), stream


def seed(desk, identity='one', deadline=6000):
    request = sample_request()
    request['id'] = identity
    desk.requests[identity] = request
    return order_for(request, deadline)


class ReviewTests(unittest.TestCase):
    def test_defaults_equivalent_for_both_factories_through_scripted_events(self):
        for factory, base_type in ((make_pairs_beta, BetaDesk), (make_gamma_pairs, GammaCoreDesk)):
            with self.subTest(factory=factory.__name__):
                actual, _ = new_desk(factory)
                base = base_type(MarketWorld(), 8, 600, Journal(io.StringIO()))
                request = sample_request()
                request.update(arrivedAt=400, respondBy=700)
                order = order_for(request)
                events = [dict(kind='price_request', request=request), dict(kind='order_won', order=order),
                          dict(kind='gig_booked', gigId='g', driverId='d', feeCents=9600),
                          dict(kind='gig_dropped', gigId='g', driverId='d'),
                          dict(kind='no_show', gigId='g', driverId='d'),
                          dict(kind='gig_expired', gigId='g'),
                          dict(kind='deadline_close', orderId=request['id'], lastPickupAt=5820),
                          dict(kind='visit_failed', gigId='g', orderId=request['id'], leg=0, reason='no_plates'),
                          dict(kind='delivered', gigId='g', orderId=request['id'], leg=0),
                          dict(kind='order_cancelled', orderId=request['id'], gigs=[])]
                for index, event in enumerate(events):
                    for desk in (actual, base):
                        desk.now = 600 + index * 10
                        desk.handle(dict(seq=index, at=desk.now, **deepcopy(event)))
                    self.assertEqual(actual.outbox, base.outbox)
                    if index == 1:
                        for desk in (actual, base):
                            actions, desk.outbox = desk.outbox, []
                            results = [dict(ok=True, id='g' if a['type'] == 'post' else request['id']) for a in actions]
                            desk.read_results(actions, results)
                self.assertEqual(actual.leg_gigs, base.leg_gigs)
                self.assertEqual(actual.booked, base.booked)

    def test_review_at_posting_ages_and_repost_continuity(self):
        desk, _ = new_desk(fee_shape='review', review_skip_night=0)
        order = seed(desk, deadline=3000)
        desk.post(order, [0])
        self.assertEqual(desk.outbox.pop()['schedule'],
                         [{'at': 600, 'feeCents': 9600}, {'at': 960, 'feeCents': 13200},
                          {'at': 2460, 'feeCents': 18000}])
        for now, expected in ((959, 9600), (960, 13200), (2459, 13200), (2460, 18000), (2900, 18000)):
            desk.now = now
            desk.post(order, [0])
            self.assertEqual(desk.outbox.pop()['schedule'][0], {'at': now, 'feeCents': expected})
        self.assertEqual(desk.first_posted['one'], 600)

    def test_expiry_keeps_age(self):
        desk, _ = new_desk(fee_shape='review', review_skip_night=0)
        order = seed(desk)
        desk.orders['one'] = order
        desk.post(order, [0])
        action = desk.outbox.pop()
        desk.read_results([action], [{'ok': True, 'id': 'g'}])
        desk.now = 1100
        desk.handle({'seq': 1, 'at': 1100, 'kind': 'gig_expired', 'gigId': 'g'})
        self.assertEqual(desk.outbox[-1]['schedule'][0]['feeCents'], 13200)

    def test_warning_floor_urgent_and_level_one_unchanged(self):
        desk, _ = new_desk(fee_shape='review', cap_before_last_pickup_minutes=20, review_skip_night=0)
        order = seed(desk, deadline=3000)
        self.assertEqual(desk.fees_for(order, 1)[-1]['at'], order['lastPickupAt'] - 180)
        desk.urgent.add('one')
        self.assertEqual(desk.fees_for(order, 1), steep(desk.now, 12000, 8))
        desk.urgent.clear()
        desk.level = 1
        self.assertEqual(desk.fees_for(order, 1), steep(desk.now, 12000, 1))

    def test_night_skip_and_monotone_with_cap_before_review(self):
        for first, reviewed in ((1100, 1860), (1200, 1860), (600, 960)):
            desk, _ = new_desk(now=first, fee_shape='review')
            order = seed(desk)
            self.assertEqual(desk.fees_for(order, 1)[1]['at'], reviewed)
        desk, _ = new_desk(fee_shape='review', review_after_minutes=5000, review_skip_night=0)
        order = seed(desk, deadline=1600)
        self.assertEqual(desk.fees_for(order, 1),
                         [{'at': 600, 'feeCents': 9600}, {'at': 1060, 'feeCents': 18000}])

    def test_gamma_opening_and_cap_are_respected(self):
        desk, _ = new_desk(make_gamma_pairs, fee_shape='review', max_km=100, long_max_km=300,
                           long_opening_fee_bps=13000, fee_cap_bps=14000)
        order = seed(desk)
        self.assertEqual([s['feeCents'] for s in desk.fees_for(order, 1)], [15600, 16800])

    def test_settings_validation_and_factory_keyword_split(self):
        for settings in ({'fee_shape': 'bad'}, {'pairs': True}, {'pairs': 2}, {'review_after_minutes': -1},
                         {'pair_max_drive_minutes': 721}, {'pair_split_minutes': 0}, {'pair_fee_bps': 0}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                DriverSideSettings(**settings)
        for factory in (make_pairs_beta, make_gamma_pairs):
            with self.assertRaises(TypeError):
                new_desk(factory, unknown=1)
            desk, _ = new_desk(factory, opening_fee_bps=9000, fee_shape='review')
            self.assertEqual(desk.settings.opening_fee_bps, 9000)
            self.assertEqual(desk.driver_settings.fee_shape, 'review')
        # Unused pair knobs cannot reject an otherwise valid Gamma fee cap.
        desk, _ = new_desk(make_gamma_pairs, opening_fee_bps=5000, long_opening_fee_bps=5000, fee_cap_bps=7000)
        self.assertEqual(desk.settings.fee_cap_bps, 7000)


class PairWorld:
    """A local action recorder, deliberately containing no Spread client."""
    id = 'offline-pairs'

    def __init__(self):
        places = ['a', 'b', 'c', 'd']
        self.initial_map = {'places': [], 'roads': [
            {'from': a, 'to': b, 'km': 0 if a == b else 10, 'minutes': 0 if a == b else 30}
            for a in places for b in places]}
        self.actions, self.serial, self.fail_withdraw, self.fail_post = [], 0, False, False
        self.now = 600
        self.initial_roster = [{'id': 'd', 'licence': 'manual', 'rating': 4.9, 'completedGigs': 80}]

    def act(self, actions):
        results = []
        for action in actions:
            self.actions.append(deepcopy(action))
            self.serial += 1
            if action['type'] == 'withdraw' and self.fail_withdraw:
                results.append({'ok': False, 'reason': 'Gig is booked'})
            elif action['type'] == 'post' and self.fail_post:
                results.append({'ok': False, 'reason': 'Rejected four-stop gig'})
            else:
                results.append({'ok': True, 'id': f'g{self.serial}'})
        return results

    def advance(self, *, actions=(), until=(), max=10000):
        results = self.act(actions)
        self.now = max
        return {'now': max, 'events': [], 'results': results}


def pair_order(desk, identity, pickup='a', delivery='b', *, deadline=3000, private=False):
    request = sample_request()
    request.update(id=identity, arrivedAt=400, respondBy=500)
    for kind, place in (('pickup', pickup), ('delivery', delivery)):
        request['legs'][0][kind].update(placeId=place, privateAddress=private,
                                       window={'from': 480, 'to': deadline}, hours=None)
    desk.requests[identity] = request
    return order_for(request, deadline)


class PairTests(unittest.TestCase):
    def desk(self, **settings):
        self.world, self.stream = PairWorld(), io.StringIO()
        self.desk_ = make_pairs_beta(self.world, 8, 600, Journal(self.stream), pairs=1, **settings)
        return self.desk_

    def event(self, desk, kind, **values):
        desk.handle({'seq': 1, 'at': desk.now, 'kind': kind, **values})

    def win(self, desk, order):
        self.event(desk, 'order_won', order=order)

    def flush(self, desk):
        actions, desk.outbox = desk.outbox, []
        desk.read_results(actions, self.world.act(actions))
        return actions

    def paired(self, **settings):
        desk = self.desk(**settings)
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c')
        self.win(desk, one)
        self.win(desk, two)
        self.assertEqual(len(desk.outbox), 1)
        self.assertEqual(len(desk.outbox[0]['stops']), 4)
        self.flush(desk)
        gig = desk.leg_gigs['one'][0]
        self.assertEqual(desk.leg_gigs['two'][0], gig)
        return desk, one, two, gig

    def records(self, kind):
        return [row for row in map(json.loads, self.stream.getvalue().splitlines()) if row.get('type') == kind]

    def assert_singles(self, desk):
        singles = [a for a in desk.outbox if a['type'] == 'post']
        self.assertEqual(len(singles), 2)
        self.assertEqual({a['stops'][0]['orderId'] for a in singles}, {'one', 'two'})
        self.assertTrue(all(len(a['stops']) == 2 for a in singles))

    def test_pair_fee_stops_road_metrics_and_booking_journal(self):
        desk, one, two, gig = self.paired()
        action = desk.posts[gig]
        self.assertEqual([(s['orderId'], s['kind']) for s in action['stops']],
                         [('one', 'pickup'), ('one', 'delivery'), ('two', 'pickup'), ('two', 'delivery')])
        self.assertEqual(action['schedule'][0]['feeCents'], 19200)
        self.assertEqual(action['schedule'][-1]['feeCents'], 36000)
        self.assertEqual(self.records('gamma_pair')[0]['transferKm'], 0)
        self.assertEqual(self.records('gamma_pair')[0]['driveMinutes'], 60)
        self.assertEqual(self.records('gamma_pair')[0]['typicalFeeCents'], 24000)
        desk.now = 620
        self.event(desk, 'gig_booked', gigId=gig, driverId='d', feeCents=19200)
        self.assertEqual(desk.gigs_of('one'), [gig])
        self.assertEqual(desk.gigs_of('two'), [gig])
        self.assertIn(gig, desk.booked)
        booking = self.records('gamma_pair_booked')[0]
        self.assertEqual(booking['feeRatio'], 0.8)
        self.assertEqual(booking['minutesSincePosted'], 20)

    def test_feasibility_tries_both_orientations_then_transfer_then_finish(self):
        desk = self.desk()
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c')
        plan, reason = desk._plan(one, two)
        self.assertIsNone(reason)
        self.assertEqual(plan.orders, ('one', 'two'))
        # Only the reverse sequence can meet one's early pickup window.
        one['legs'][0]['pickup']['window']['to'] = 790
        self.assertIsNotNone(desk._plan(one, two)[0])
        self.assertEqual(desk._plan(two, one)[1], 'windows')
        self.win(desk, one)
        self.win(desk, two)
        self.assertEqual([s['orderId'] for s in desk.outbox[0]['stops']], ['one', 'one', 'two', 'two'])

    def test_transfer_drive_hard_cap_and_each_window(self):
        desk = self.desk()
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'c', 'd')
        desk.roads['b', 'c']['km'] = 31
        self.assertEqual(desk._plan(one, two)[1], 'transfer_too_far')
        desk.roads['b', 'c']['km'] = 10
        desk.roads['b', 'c']['minutes'] = 260
        self.assertEqual(desk._plan(one, two)[1], 'drive_too_long')
        desk.roads['b', 'c']['minutes'] = 30
        for index in range(4):
            orders = deepcopy([one, two])
            orders[index // 2]['legs'][0]['pickup' if index % 2 == 0 else 'delivery']['window']['to'] = 700
            with self.subTest(stop=index):
                self.assertEqual(desk._plan(*orders)[1], 'windows')
        with self.assertRaises(ValueError):
            self.desk(pair_max_drive_minutes=721)

    def test_ready_times_opening_closing_weekends_and_private_slots(self):
        desk = self.desk()
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c', private=True)
        one['legs'][0]['pickup']['window']['from'] = 900
        plan, _ = desk._plan(one, two)
        self.assertEqual(plan.finish, 960)
        hours = dict(opens=1000, closes=1100, weekdays=[0, 1, 2, 3, 4], saturday=None)
        one['legs'][0]['pickup']['hours'] = hours
        self.assertEqual(desk._plan(one, two)[0].finish, 1060)
        one['legs'][0]['delivery']['hours'] = dict(hours, opens=800, closes=900)
        two['legs'][0]['pickup']['window']['to'] = 1200
        self.assertEqual(desk._plan(one, two)[1], 'windows')
        one['legs'][0]['delivery']['hours'] = None
        one['legs'][0]['pickup']['hours'] = dict(hours, weekdays=[1])
        self.assertEqual(desk._plan(one, two)[1], 'windows')
        # Saturday hours differ; Sunday must wait until Monday.
        one['legs'][0]['pickup']['hours'] = dict(hours, saturday={'opens': 600, 'closes': 800})
        for order in (one, two):
            order['deadline'] = 8 * 1440
            order['lastPickupAt'] = 8 * 1440 - 180
            for kind in ('pickup', 'delivery'):
                order['legs'][0][kind]['window'] = {'from': 0, 'to': 8 * 1440}
        desk.now = 5 * 1440 + 300
        self.assertEqual(desk._plan(one, two)[0].finish, 5 * 1440 + 660)
        desk.now = 6 * 1440 + 300
        self.assertEqual(desk._plan(one, two)[0].finish, 7 * 1440 + 1060)

    def test_spare_allowance_plates_charging_notes_and_combined_audience(self):
        desk = self.desk()
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c')
        baseline = desk._plan(one, two)[0]
        one['legs'][0]['car'].update(electric=True, chargePercent=20, premium=True)
        desk.requests['two']['note'] = {'text': 'manual car without plates', 'language': 'en'}
        plan = desk._plan(one, two)[0]
        self.assertEqual(plan.finish, baseline.finish + 70)
        self.assertEqual(plan.drive_minutes, baseline.drive_minutes)
        self.assertTrue(plan.action['stops'][0]['withCharging'])
        self.assertTrue(plan.action['stops'][2]['withPlates'])
        self.assertEqual(plan.action['audience'], {'experienced': True, 'manualLicence': True})
        self.world.initial_roster = [dict(self.world.initial_roster[0], licence='automatic_only')]
        self.assertEqual(desk._plan(one, two)[1], 'audience')
        self.world.initial_roster = None  # no fetched roster: union remains a valid audience
        two['deadline'] = plan.finish + 59
        self.assertEqual(desk._plan(one, two)[1], 'windows')

    def test_candidates_exclude_booked_picked_urgent_tradeins_failures_and_split(self):
        for excluded in ('booked', 'picked', 'urgent', 'tradein', 'failed', 'split'):
            with self.subTest(excluded=excluded):
                desk = self.desk()
                one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c')
                self.win(desk, one)
                if excluded == 'tradein':
                    one['legs'] *= 2
                    one['deliveredAt'] *= 2
                elif excluded == 'booked':
                    self.flush(desk)
                    desk.booked.add(desk.gigs_of('one')[0])
                elif excluded == 'picked':
                    desk._picked.add('one')
                elif excluded == 'urgent':
                    desk.urgent.add('one')
                elif excluded == 'failed':
                    desk._failed_orders.add('one')
                elif excluded == 'split':
                    desk._split_orders.add('one')
                self.win(desk, two)
                self.assertFalse(any(len(a['stops']) == 4 for a in desk.outbox if a['type'] == 'post'))

    def test_waiting_withdraw_is_before_pair_and_with_waiting_off_only_queued(self):
        desk = self.desk()
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c')
        self.win(desk, one)
        self.flush(desk)
        old = desk.gigs_of('one')[0]
        self.win(desk, two)
        self.assertEqual(self.world.actions[-1], {'type': 'withdraw', 'gigId': old})
        self.assertEqual(desk.gigs_of('one'), [])
        self.flush(desk)
        self.assertEqual([a['type'] for a in self.world.actions], ['post', 'withdraw', 'post'])
        self.assertTrue(self.records('gamma_pair')[0]['waitingWithdrawn'])
        desk = self.desk(pair_with_waiting=0)
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c')
        self.win(desk, one)
        self.flush(desk)
        self.win(desk, two)
        self.assertEqual(len(desk.outbox[0]['stops']), 2)
        self.assertNotIn('withdraw', [a['type'] for a in self.world.actions])
        self.paired(pair_with_waiting=0)

    def test_time_split_age_continuity_and_pair_once(self):
        desk, one, two, gig = self.paired(fee_shape='review', review_after_minutes=30, review_skip_night=0)
        desk.now = 659
        self.assertEqual(desk.outbox, [])
        desk.now = 660
        self.assert_singles(desk)
        self.assertEqual(self.world.actions[-1], {'type': 'withdraw', 'gigId': gig})
        self.assertEqual([a['schedule'][0]['feeCents'] for a in desk.outbox], [13200, 13200])
        self.assertEqual(self.records('gamma_pair_split')[0]['reason'], 'time')
        self.flush(desk)
        third = pair_order(desk, 'third', 'b', 'c')
        self.win(desk, third)
        self.assertEqual(len(desk.outbox[0]['stops']), 2)

    def test_exact_idle_timer_caps_advance_without_any_event(self):
        desk, one, two, gig = self.paired()
        self.assertEqual(desk.next_pair_wake(), 660)
        step = self.world.advance(until=['price_request'], max=2000, actions=[])
        self.assertEqual(step['now'], 660)
        handle_batch(desk, step['events'], step['now'])
        self.assert_singles(desk)

    def test_warning_splits_queued_and_accepted_pairs_and_uses_rescue(self):
        for queued in (False, True):
            with self.subTest(queued=queued):
                desk = self.desk()
                one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c')
                self.win(desk, one)
                self.win(desk, two)
                if not queued:
                    self.flush(desk)
                self.event(desk, 'deadline_close', orderId='two', lastPickupAt=2820)
                actions = [a for a in self.world.actions + desk.outbox if a['type'] == 'post' and len(a['stops']) == 2]
                self.assertEqual({a['stops'][0]['orderId'] for a in actions}, {'one', 'two'})
                self.assertEqual(next(a for a in actions if a['stops'][0]['orderId'] == 'two')['schedule'], steep(600, 12000, 8))
                self.assertIn('two', desk.urgent)
                self.assertEqual(self.records('gamma_pair_split')[0]['reason'], 'deadline_close')

    def test_drop_no_show_expiry_reopen_both_and_old_events_are_harmless(self):
        for kind in ('gig_dropped', 'no_show', 'gig_expired'):
            with self.subTest(kind=kind):
                desk, one, two, gig = self.paired()
                if kind != 'gig_expired':
                    self.event(desk, 'gig_booked', gigId=gig, driverId='d', feeCents=19200)
                self.event(desk, kind, gigId=gig, driverId='d')
                self.assert_singles(desk)
                self.assertNotIn(gig, desk.booked)
                self.flush(desk)
                self.assertNotEqual(desk.gigs_of('one'), desk.gigs_of('two'))
                before = deepcopy(desk.leg_gigs)
                self.event(desk, 'gig_expired', gigId=gig)
                self.assertEqual(desk.leg_gigs, before)
                self.assertEqual(desk.outbox, [])

    def test_started_picked_delivered_books_and_no_timer_release(self):
        desk, one, two, gig = self.paired()
        self.event(desk, 'gig_booked', gigId=gig, driverId='d', feeCents=19200)
        self.event(desk, 'gig_started', gigId=gig, driverId='d')
        self.event(desk, 'picked_up', gigId=gig, orderId='one', leg=0)
        desk.now = 800
        self.assertEqual(desk.outbox, [])
        self.assertIsNone(desk.next_pair_wake())
        self.event(desk, 'delivered', gigId=gig, orderId='one', leg=0)
        self.assertEqual(desk.gigs_of('one'), [])
        self.assertEqual(desk.gigs_of('two'), [gig])
        self.assertEqual(one['deliveredAt'], [800])
        self.event(desk, 'picked_up', gigId=gig, orderId='two', leg=0)
        self.event(desk, 'delivered', gigId=gig, orderId='two', leg=0)
        self.assertEqual(desk.gigs_of('two'), [])
        self.assertEqual(two['deliveredAt'], [800])
        self.assertFalse(any(a['type'] in ('withdraw', 'release') for a in self.world.actions))

    def test_failed_visit_retries_only_failed_car_with_base_retry_flags(self):
        for failed in ('one', 'two'):
            for reason in ('not_ready', 'closed', 'licence', 'no_plates'):
                with self.subTest(failed=failed, reason=reason):
                    desk, one, two, gig = self.paired()
                    other = 'two' if failed == 'one' else 'one'
                    self.event(desk, 'gig_started', gigId=gig, driverId='d')
                    self.event(desk, 'visit_failed', gigId=gig, orderId=failed, leg=0, reason=reason)
                    self.assertEqual(desk.gigs_of(other), [gig])
                    self.assertEqual(desk.gigs_of(failed), [])
                    retry = desk.outbox[0]
                    self.assertEqual({s['orderId'] for s in retry['stops']}, {failed})
                    if reason in ('not_ready', 'closed'):
                        self.assertEqual(retry['stops'][0]['window']['from'],
                                         retry_from(desk.orders[failed], desk.requests[failed], 0, 600))
                    elif reason == 'licence':
                        self.assertTrue(retry['audience']['manualLicence'])
                    else:
                        self.assertTrue(retry['stops'][0]['withPlates'])
                    self.flush(desk)
                    self.assertNotEqual(desk.gigs_of(failed), [gig])
                    self.event(desk, 'delivered', gigId=gig, orderId=other, leg=0)
                    self.assertEqual(desk.gigs_of(other), [])
                    self.assertTrue(desk.gigs_of(failed))

    def test_cancel_either_order_unbooked_and_all_server_outcomes(self):
        for identity in ('one', 'two'):
            for outcome in ('withdrawn', 'released', 'shortened', 'continues'):
                with self.subTest(identity=identity, outcome=outcome):
                    desk, one, two, gig = self.paired()
                    other = 'two' if identity == 'one' else 'one'
                    if outcome != 'withdrawn':
                        self.event(desk, 'gig_booked', gigId=gig, driverId='d', feeCents=19200)
                    if outcome == 'continues':
                        self.event(desk, 'gig_started', gigId=gig, driverId='d')
                    self.event(desk, 'order_cancelled', orderId=identity, gigs=[{'gigId': gig, 'outcome': outcome}])
                    self.assertNotIn(identity, desk.orders)
                    self.assertNotIn(identity, desk.leg_gigs)
                    if outcome in ('withdrawn', 'released'):
                        self.assertEqual(len(desk.outbox), 1)
                        self.assertEqual(desk.outbox[0]['stops'][0]['orderId'], other)
                        self.flush(desk)
                        self.assertNotEqual(desk.gigs_of(other), [gig])
                    else:
                        self.assertEqual(desk.outbox, [])
                        self.assertEqual(desk.gigs_of(other), [gig])
                    self.assertFalse(any(a['type'] == 'release' for a in self.world.actions))

    def test_change_either_order_unbooked_splits_booked_continues(self):
        for identity in ('one', 'two'):
            for booked in (False, True):
                with self.subTest(identity=identity, booked=booked):
                    desk, one, two, gig = self.paired()
                    if booked:
                        self.event(desk, 'gig_booked', gigId=gig, driverId='d', feeCents=19200)
                    changed = deepcopy(desk.orders[identity])
                    changed['legs'][0]['delivery']['placeId'] = 'd'
                    self.event(desk, 'order_changed', order=changed, message={'text': 'change', 'language': 'en'})
                    self.assertEqual(desk.orders[identity], changed)
                    if booked:
                        self.assertEqual(desk.outbox, [])
                        self.assertEqual(desk.gigs_of('one'), [gig])
                        self.assertEqual(desk.gigs_of('two'), [gig])
                    else:
                        self.assert_singles(desk)
                        self.flush(desk)
                        self.assertNotEqual(desk.gigs_of('one'), desk.gigs_of('two'))

    def test_many_events_in_batch_bookings_precede_timer(self):
        desk = self.desk()
        orders = [pair_order(desk, str(i), 'a' if i % 2 == 0 else 'b', 'b' if i % 2 == 0 else 'c')
                  for i in range(5)]
        handle_batch(desk, [dict(seq=i, at=600, kind='order_won', order=o) for i, o in enumerate(orders)], 600)
        self.assertEqual(sorted(len(a['stops']) for a in desk.outbox), [2, 4, 4])
        self.flush(desk)
        gig = desk.gigs_of('0')[0]
        handle_batch(desk, [dict(seq=10, at=620, kind='gig_booked', gigId=gig, driverId='d', feeCents=19200),
                            dict(seq=11, at=630, kind='gig_started', gigId=gig, driverId='d')], 660)
        self.assertIn(gig, desk.booked)
        self.assertEqual(desk.gigs_of('0'), [gig])
        self.assertTrue(all(a.get('gigId') != gig for a in self.world.actions if a['type'] == 'withdraw'))
        self.assertEqual(type(desk).__dict__['passive_wake_events'], frozenset())

    def test_pairing_exceptions_and_rejected_pair_post_fall_back_to_singles(self):
        desk = self.desk()
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c')
        self.win(desk, one)
        with patch.object(desk, '_plan', side_effect=RuntimeError('bad map')):
            self.win(desk, two)
        self.assert_singles(desk)
        self.assertEqual(self.records('gamma_pair_error')[0]['phase'], 'pairing')
        desk = self.desk()
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c')
        self.win(desk, one)
        self.win(desk, two)
        self.world.fail_post = True
        self.flush(desk)
        self.assert_singles(desk)
        self.assertEqual(self.records('gamma_pair_error')[0]['phase'], 'post')
        self.world.fail_post = False
        self.flush(desk)
        self.assertTrue(desk.gigs_of('one'))
        self.assertTrue(desk.gigs_of('two'))

    def test_rejected_withdraw_keeps_old_gig_and_posts_only_new_car(self):
        desk = self.desk()
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c')
        self.win(desk, one)
        self.flush(desk)
        old = desk.gigs_of('one')[0]
        self.world.fail_withdraw = True
        self.win(desk, two)
        self.assertEqual(desk.gigs_of('one'), [old])
        self.assertEqual(len(desk.outbox), 1)
        self.assertEqual(desk.outbox[0]['stops'][0]['orderId'], 'two')
        self.assertEqual(self.records('gamma_pair_error')[0]['phase'], 'withdraw')
        desk, one, two, gig = self.paired()
        self.world.fail_withdraw = True
        desk.now = 660
        self.assertEqual(desk.outbox, [])
        self.assertEqual(desk.gigs_of('one'), [gig])
        self.assertEqual(desk.gigs_of('two'), [gig])
        self.assertEqual(desk.next_pair_wake(), 720)

    def test_skip_counts_are_once_per_won_order(self):
        desk = self.desk(pair_transfer_km=0)
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'c', 'd')
        self.win(desk, one)
        self.win(desk, two)
        self.flush(desk)
        for _ in range(3):
            self.event(desk, 'gig_dropped', gigId=desk.gigs_of('two')[0], driverId='d')
        records = self.records('gamma_pair_skip')
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]['counts'], {'no_partner': 1})
        self.assertEqual(records[1]['counts'], {'transfer_too_far': 2})

    def test_reopened_single_drop_and_expiry_find_waiting_partner(self):
        for kind in ('gig_dropped', 'no_show', 'gig_expired'):
            with self.subTest(kind=kind):
                desk = self.desk()
                one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c')
                self.win(desk, one)
                self.flush(desk)
                old = desk.gigs_of('one')[0]
                self.event(desk, 'gig_booked', gigId=old, driverId='d', feeCents=9600)
                self.win(desk, two)
                self.flush(desk)
                self.event(desk, kind, gigId=old, driverId='d')
                self.assertEqual(len(desk.outbox), 1)
                self.assertEqual(len(desk.outbox[0]['stops']), 4)
                self.flush(desk)
                self.assertEqual(desk.gigs_of('one'), desk.gigs_of('two'))
                self.assertNotEqual(desk.gigs_of('one'), [old])

    def test_windows_can_split_before_the_time_limit(self):
        desk = self.desk(pair_split_minutes=300, pair_spare_minutes=60)
        one, two = pair_order(desk, 'one', deadline=1050), pair_order(desk, 'two', 'b', 'c', deadline=1050)
        self.win(desk, one)
        self.win(desk, two)
        self.flush(desk)
        wake = desk.next_pair_wake()
        self.assertLess(wake, 900)
        desk.now = wake
        self.assert_singles(desk)
        self.assertEqual(self.records('gamma_pair_split')[0]['reason'], 'windows')

    def test_gamma_pairs_uses_gamma_steps_cap_and_pair_deadline(self):
        desk = self.desk()
        desk = make_gamma_pairs(self.world, 8, 600, Journal(self.stream), pairs=1, fee_steps=3, fee_cap_bps=16000)
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c', deadline=2000)
        self.win(desk, one)
        self.win(desk, two)
        pair = next(iter(desk._pending_pairs.values()))
        schedule = desk.outbox[0]['schedule']
        self.assertEqual(len(schedule), 3)
        self.assertEqual([s['feeCents'] for s in schedule], [19200, 28800, 38400])
        self.assertLessEqual(abs(schedule[-1]['at'] - (pair.last_start - 180)), 1)
        self.assertLess(pair.last_start, one['lastPickupAt'])
        self.assertLessEqual(pair.last_start + 60, two['deadline'])

    def test_review_pair_uses_sum_and_earlier_recomputed_pickup(self):
        desk = self.desk(fee_shape='review', review_skip_night=0)
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c', deadline=2000)
        self.win(desk, one)
        self.win(desk, two)
        pair = next(iter(desk._pending_pairs.values()))
        schedule = pair.action['schedule']
        self.assertEqual(schedule[0], {'at': 600, 'feeCents': 19200})
        self.assertEqual(schedule[1], {'at': 960, 'feeCents': 26400})
        self.assertEqual(schedule[-1], {'at': pair.last_start - 360, 'feeCents': 36000})

    def test_ramp_split_keeps_first_posting_age_and_once_can_be_disabled(self):
        desk, one, two, gig = self.paired(pair_split_minutes=400, pair_once=0)
        initial = desk._ramp_schedule(12000, 8000, 600, one['lastPickupAt'])
        desk.now = 1000
        self.assert_singles(desk)
        current = max((s for s in initial if s['at'] <= 1000), key=lambda s: s['at'])
        self.assertEqual(desk.outbox[0]['schedule'][0]['feeCents'], current['feeCents'])
        self.flush(desk)
        self.event(desk, 'gig_dropped', gigId=desk.gigs_of('one')[0], driverId='d')
        self.assertEqual(len(desk.outbox[0]['stops']), 4)

    def test_split_exception_is_journaled_without_stopping_event_handler(self):
        desk, one, two, gig = self.paired()
        with patch.object(self.world, 'act', side_effect=RuntimeError('offline rejection')):
            self.event(desk, 'gig_dropped', gigId=gig, driverId='d')
        self.assertEqual(self.records('gamma_pair_error')[0]['phase'], 'split')
        self.assertEqual(desk.gigs_of('one'), [gig])
        self.assertEqual(desk.gigs_of('two'), [gig])
        desk.now = 720
        self.assert_singles(desk)

    def test_rejected_single_change_withdraw_preserves_existing_books(self):
        desk = self.desk()
        one = pair_order(desk, 'one')
        self.win(desk, one)
        self.flush(desk)
        old = desk.gigs_of('one')[0]
        self.world.fail_withdraw = True
        changed = deepcopy(one)
        changed['legs'][0]['delivery']['placeId'] = 'd'
        self.event(desk, 'order_changed', order=changed, message=None)
        self.assertEqual(desk.gigs_of('one'), [old])
        self.assertEqual(desk.outbox, [])

    def test_partial_withdraw_rejection_restores_only_the_withdrawn_car(self):
        for reject_current in (False, True):
            with self.subTest(reject_current=reject_current):
                desk = self.desk()
                one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'b', 'c')
                self.win(desk, one)
                self.flush(desk)
                old_one = desk.gigs_of('one')[0]
                self.event(desk, 'gig_booked', gigId=old_one, driverId='d', feeCents=9600)
                self.win(desk, two)
                self.flush(desk)
                old_two = desk.gigs_of('two')[0]
                refused = old_one if reject_current else old_two
                accepted = old_two if reject_current else old_one
                act = self.world.act

                def partial(actions):
                    if all(a['type'] == 'withdraw' for a in actions):
                        self.world.actions.extend(deepcopy(actions))
                        return [dict(ok=False, reason='Gig is booked') if a['gigId'] == refused
                                else dict(ok=True, id=a['gigId']) for a in actions]
                    return act(actions)

                with patch.object(self.world, 'act', side_effect=partial):
                    self.event(desk, 'gig_dropped', gigId=old_one, driverId='d')
                posts = [a for a in desk.outbox if a['type'] == 'post']
                self.assertEqual(len(posts), 1)
                restored = 'two' if reject_current else 'one'
                retained = 'one' if reject_current else 'two'
                self.assertEqual(posts[0]['stops'][0]['orderId'], restored)
                self.assertEqual(desk.gigs_of(retained), [refused])
                self.assertEqual(desk.gigs_of(restored), [])
                self.flush(desk)
                self.assertNotEqual(desk.gigs_of(restored), [accepted])

    def test_driver_fee_ledger_does_not_invent_order_attribution(self):
        desk, one, two, gig = self.paired()
        self.event(desk, 'ledger', line=dict(at=600, kind='driver_fee', cents=-19200,
                                            orderId=None, gigId=gig, detail='shared gig'))
        self.assertEqual(desk.trust, {})
        for identity in ('one', 'two'):
            self.event(desk, 'ledger', line=dict(at=600, kind='revenue', cents=30000,
                                                orderId=identity, gigId=None, detail='order revenue'))
        self.assertEqual(desk.trust['demo-dealer'], 2)

    def test_transfer_tie_selects_earliest_finish(self):
        desk = self.desk()
        one, two = pair_order(desk, 'one'), pair_order(desk, 'two', 'c', 'd')
        one['legs'][0]['pickup']['window']['from'] = 1000
        early = desk._plan(two, one)[0]
        late = desk._plan(one, two)[0]
        self.assertEqual(early.transfer_km, late.transfer_km)
        self.assertLess(early.finish, late.finish)
        self.win(desk, one)
        self.win(desk, two)
        self.assertEqual(desk.outbox[0]['stops'][0]['orderId'], 'two')

    def test_idle_timer_in_real_dispatch_loop_for_both_factories_and_fast_modes(self):
        class Week(PairWorld):
            def __init__(self):
                super().__init__()
                self.client, self.requests, self.timed_actions = self, {}, []
                one, two = pair_order(self, 'one'), pair_order(self, 'two', 'b', 'c')
                for request in self.requests.values():
                    request['respondBy'] = 550
                self.events = [dict(seq=i, at=500, kind='price_request', request=r)
                               for i, r in enumerate(self.requests.values())]
                self.events += [dict(seq=i + 2, at=600, kind='order_won', order=o)
                                for i, o in enumerate((one, two))]
                self.now = 400

            def map(self):
                return self.initial_map

            def roster(self):
                return self.initial_roster

            def snapshot(self):
                return dict(now=self.now, endsAt=900, orders=[], gigs=[], openRequests=[], driverPositions=[], score=self.score())

            def score(self):
                return dict(marginCents=0, revenueCents=0, marginShare=0, wonOrders=2,
                            onTimeShare=0, undeliveredShare=1, ranked=False)

            def act(self, actions):
                self.timed_actions.extend((self.now, deepcopy(a)) for a in actions)
                return super().act(actions)

            def advance(self, *, actions=(), until=(), max=10000):
                results = self.act(actions)
                self.now = min([max, *(e['at'] for e in self.events if e['kind'] in until)])
                events = [e for e in self.events if e['at'] <= self.now]
                self.events = [e for e in self.events if e['at'] > self.now]
                return dict(now=self.now, events=events, results=results)

        for factory in (make_pairs_beta, make_gamma_pairs):
            for fast in (False, True):
                with self.subTest(factory=factory.__name__, fast=fast):
                    world, trace = Week(), io.StringIO()
                    play_model(world, 8, Journal(trace), lambda w, l, n, j: factory(w, l, n, j, pairs=1), fast=fast)
                    posts = [(at, a) for at, a in world.timed_actions if a['type'] == 'post']
                    self.assertEqual([(at, len(a['stops'])) for at, a in posts], [(600, 4), (660, 2), (660, 2)])
                    self.assertEqual([at for at, a in world.timed_actions if a['type'] == 'withdraw'], [660])


if __name__ == '__main__':
    unittest.main()
