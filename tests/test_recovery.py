"""Synthetic, credential-free recovery contracts. No private trace/reveal data."""
from collections import Counter, deque
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from capture import Journal
from models.delta import make_delta
from models.gamma import make_gamma
from recovery import CheckpointStore, model_state, replay_history
from spread.starter import steep
from tests.test_gamma import GammaWorld, request as gamma_request
from tests.test_gamma_pairs import PairWorld, order_for
from demo import sample_request


class World(PairWorld):
    """Only action receipts and public snapshot bookkeeping, all in memory."""
    def __init__(self):
        super().__init__()
        self.gigs = {}
        self.now = 600
        self.recovery_checkpoint = None

    def act(self, actions):
        results = super().act(actions)
        for action, result in zip(actions, results):
            if not result['ok']:
                continue
            if action['type'] == 'post':
                self.gigs[result['id']] = dict(id=result['id'], postedAt=self.now, status='open',
                                               **{k: deepcopy(action[k]) for k in ('stops', 'schedule', 'audience')})
            elif action['type'] == 'withdraw':
                self.gigs[action['gigId']]['status'] = 'withdrawn'
            elif action['type'] == 'reprice':
                self.gigs[action['gigId']]['schedule'] = deepcopy(action['schedule'])
        return results


def request(identity='one', pickup='a', delivery='b', at=600, deadline=6000):
    req = sample_request()
    req.update(id=identity, dealerId='D01', arrivedAt=at, respondBy=at + 15)
    req['options'] = [dict(kind='same_day', deadline=deadline, listPriceCents=20000)]
    for kind, place in (('pickup', pickup), ('delivery', delivery)):
        req['legs'][0][kind].update(placeId=place, hours=None, privateAddress=False,
                                   window={'from': 480, 'to': deadline})
    return req


def new_desk(world=None, now=600, factory=make_delta, **settings):
    world = world or World()
    return factory(world, 8, now, Journal(io.StringIO()), **settings)


def emit(desk, history, at, kind, **data):
    event = dict(seq=len(history), at=at, kind=kind, **deepcopy(data))
    history.append(deepcopy(event))
    desk.now = desk.world.now = at
    if kind in ('gig_booked', 'gig_started', 'gig_dropped', 'no_show', 'gig_expired'):
        status = {'gig_booked': 'booked', 'gig_started': 'working', 'gig_dropped': 'open',
                  'no_show': 'open', 'gig_expired': 'withdrawn'}[kind]
        desk.world.gigs[data['gigId']]['status'] = status
    desk.handle(event)
    desk.send()
    return event


def snapshot(desk, at=None, open_requests=()):
    return dict(worldId=desk.world.id, now=desk.now if at is None else at, endsAt=14280,
                orders=deepcopy(list(desk.orders.values())), gigs=deepcopy(list(desk.world.gigs.values())),
                openRequests=deepcopy(list(open_requests)))


def paired(**settings):
    desk, history = new_desk(pairs=1, **settings), []
    one, two = request(), request('two', 'b', 'c', at=601)
    emit(desk, history, 600, 'price_request', request=one)
    emit(desk, history, 601, 'price_request', request=two)
    emit(desk, history, 620, 'order_won', order=order_for(one))
    emit(desk, history, 625, 'order_won', order=order_for(two))
    return desk, history, desk.leg_gigs['one'][0]


def rebuild(original, history, snap=None, **settings):
    world = World()
    world.gigs = deepcopy(original.world.gigs)
    world.serial = original.world.serial
    snap = snap or snapshot(original)
    world.now = snap['now']
    desk = new_desk(world, snap['now'], **settings)
    desk.rejoin(snap, history)
    desk.send()
    return desk


class RecoveryTests(unittest.TestCase):
    def test_known_open_request_is_quoted_once_through_normal_pricing(self):
        desk, history = new_desk(), []
        req = request()
        emit(desk, history, 600, 'price_request', request=req)
        expected = desk.world.actions[-1]['prices']
        resumed = rebuild(desk, history, snapshot(desk, at=605, open_requests=[req]))
        quotes = [a for a in resumed.world.actions if a['type'] == 'quote']
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0]['prices'], expected)
        self.assertEqual(resumed.pending, {'one'})
        resumed.handle(dict(seq=1, at=605, kind='price_request', request=req))
        self.assertFalse(resumed.outbox)

    def test_expired_open_request_is_not_quoted(self):
        desk = new_desk()
        resumed = rebuild(desk, [], snapshot(desk, at=620, open_requests=[request()]))
        self.assertEqual(resumed.world.actions, [])

    def test_replay_has_no_actions_and_does_not_mutate_history(self):
        original, history, _ = paired()
        saved = deepcopy(history)
        desk = new_desk(pairs=1)
        desk.world.act = lambda actions: self.fail('history replay emitted actions')
        replay_history(desk, snapshot(original), history)
        self.assertEqual(history, saved)
        self.assertEqual(desk._outbox, [])
        self.assertEqual(desk.journal.output.getvalue(), '')
        self.assertEqual(desk.markup, original.markup)

    def test_learner_trackers_day_starts_and_trust_match_live(self):
        for scope in ('global', 'dealer', 'km'):
            with self.subTest(scope=scope):
                world = GammaWorld()
                desk = make_gamma(world, 8, 500, Journal(io.StringIO()), markup_scope=scope,
                                  freeze_day_drop_bps=100)
                history = []
                for index, at in enumerate((500, 700, 2000, 2400, 3500)):
                    req = gamma_request(str(index), dealer='D01' if index % 2 else 'D05')
                    req.update(arrivedAt=at, respondBy=at + 15)
                    req['options'][0]['deadline'] = at + 1800
                    for kind, data in (('price_request', {'request': req}),
                                       ('order_lost', {'requestId': req['id']})):
                        event = dict(seq=len(history), at=at, kind=kind, **data)
                        history.append(deepcopy(event))
                        desk.now = at
                        desk.handle(deepcopy(event))
                        desk.outbox = []
                # Dealer mappings and revenue/refund trust do not need a live post.
                req = gamma_request('won')
                req.update(arrivedAt=3501, respondBy=3516)
                req['options'][0]['deadline'] = 6000
                for at, kind, data in ((3501, 'price_request', {'request': req}),
                                       (3520, 'order_won', {'order': order_for(req)}),
                                       (3600, 'ledger', {'line': {'kind': 'revenue', 'orderId': 'won'}}),
                                       (3601, 'ledger', {'line': {'kind': 'late_refund', 'orderId': 'won'}})):
                    event = dict(seq=len(history), at=at, kind=kind, **data)
                    history.append(deepcopy(event)); desk.now = at
                    desk.handle(deepcopy(event)); desk.outbox = []
                recovered = make_gamma(GammaWorld(), 8, 3601, Journal(io.StringIO()),
                                       markup_scope=scope, freeze_day_drop_bps=100)
                replay_history(recovered, dict(gigs=[]), history)
                for key in ('markup', 'markups', 'day_starts', 'quote_trackers', 'pending', 'dealers', 'trust'):
                    self.assertEqual(getattr(recovered, key), getattr(desk, key), key)

    def test_declines_do_not_train_the_replayed_learner(self):
        desk, history = new_desk(max_km=1), []
        emit(desk, history, 600, 'price_request', request=request())
        emit(desk, history, 620, 'order_lost', requestId='one')
        resumed = rebuild(desk, history, max_km=1)
        self.assertEqual(resumed.markup, 15000)
        self.assertFalse(resumed.pending)

    def test_restored_pair_keeps_membership_and_original_split_timer(self):
        desk, history, gig = paired()
        resumed = rebuild(desk, history, snapshot(desk, at=650), pairs=1)
        self.assertEqual(resumed.leg_gigs, desk.leg_gigs)
        self.assertEqual(resumed._pairs[gig].orders, desk._pairs[gig].orders)
        self.assertEqual(resumed._pairs[gig].posted_at, 625)
        self.assertEqual(resumed._pairs[gig].latest_safe, desk._pairs[gig].latest_safe)
        self.assertEqual(resumed.next_pair_wake(), 685)
        self.assertEqual(resumed.world.actions, [])
        resumed.now = resumed.world.now = 685
        resumed.send()
        self.assertFalse(resumed._pairs[gig].active)
        self.assertNotEqual(resumed.leg_gigs['one'][0], resumed.leg_gigs['two'][0])

    def test_restored_pair_cancellation_rescues_partner(self):
        desk, history, gig = paired()
        resumed = rebuild(desk, history, pairs=1)
        resumed.world.gigs[gig]['status'] = 'withdrawn'
        emit(resumed, history, 630, 'order_cancelled', orderId='one',
             gigs=[dict(gigId=gig, outcome='withdrawn')])
        self.assertNotIn('one', resumed.orders)
        self.assertNotEqual(resumed.leg_gigs['two'][0], gig)
        self.assertEqual(resumed.world.gigs[resumed.leg_gigs['two'][0]]['status'], 'open')

    def test_restored_pair_drop_and_expiry_rescue_both_members(self):
        for kind in ('gig_dropped', 'gig_expired', 'no_show'):
            with self.subTest(kind=kind):
                desk, history, gig = paired()
                resumed = rebuild(desk, history, pairs=1)
                emit(resumed, history, 630, kind, gigId=gig)
                self.assertFalse(resumed._pairs[gig].active)
                self.assertEqual(set(resumed.leg_gigs), {'one', 'two'})
                self.assertNotEqual(resumed.leg_gigs['one'][0], resumed.leg_gigs['two'][0])

    def test_unreconstructable_pair_is_withdrawn_and_posted_singly(self):
        desk, history, gig = paired()
        snap = snapshot(desk)
        # Public stop no longer matches a safely reproducible two-car plan.
        snap['gigs'][-1]['stops'][0]['window']['to'] -= 1
        resumed = rebuild(desk, history, snap, pairs=1)
        self.assertFalse(resumed._pairs[gig].active)
        self.assertNotEqual(resumed.leg_gigs['one'][0], resumed.leg_gigs['two'][0])
        self.assertEqual(resumed._split_orders, {'one', 'two'})

    def test_uncertain_pair_racing_booking_keeps_links_until_withdrawal_succeeds(self):
        desk, history, gig = paired()
        snap = snapshot(desk)
        snap['gigs'][-1]['stops'][0]['window']['to'] -= 1
        world = World(); world.gigs = deepcopy(desk.world.gigs); world.fail_withdraw = True
        resumed = new_desk(world, pairs=1)
        resumed.rejoin(snap, history)
        self.assertTrue(resumed._pairs[gig].active)
        self.assertEqual(resumed.gigs_of('two'), [gig])
        self.assertFalse(any(a['type'] == 'post' for a in world.actions))
        self.assertEqual(resumed._pairs[gig].retry_at, snap['now'] + 60)

    def test_warning_during_outage_reprices_existing_open_single(self):
        desk, history = new_desk(), []
        req = request()
        emit(desk, history, 600, 'price_request', request=req)
        emit(desk, history, 620, 'order_won', order=order_for(req))
        gig = desk.leg_gigs['one'][0]
        history.append(dict(seq=len(history), at=630, kind='deadline_close', orderId='one'))
        resumed = rebuild(desk, history, snapshot(desk, at=650))
        reprices = [a for a in resumed.world.actions if a['type'] == 'reprice']
        self.assertEqual(reprices, [dict(type='reprice', gigId=gig,
                                        schedule=steep(650, req['referenceFeeCents'], 8))])

    def test_warning_does_not_reprice_booked_gig(self):
        desk, history = new_desk(), []
        req = request()
        emit(desk, history, 600, 'price_request', request=req)
        emit(desk, history, 620, 'order_won', order=order_for(req))
        gig = desk.leg_gigs['one'][0]
        emit(desk, history, 625, 'gig_booked', gigId=gig, feeCents=10000)
        history.append(dict(seq=len(history), at=630, kind='deadline_close', orderId='one'))
        resumed = rebuild(desk, history, snapshot(desk, at=650))
        self.assertEqual(resumed.world.actions, [])

    def test_warning_for_restored_pair_splits_before_applying_single_car_fees(self):
        desk, history, gig = paired()
        history.append(dict(seq=len(history), at=630, kind='deadline_close', orderId='one'))
        resumed = rebuild(desk, history, snapshot(desk, at=650), pairs=1)
        self.assertFalse(resumed._pairs[gig].active)
        singles = [a for a in resumed.world.actions if a['type'] == 'post']
        self.assertEqual(len(singles), 2)
        one = next(a for a in singles if a['stops'][0]['orderId'] == 'one')
        self.assertEqual(one['schedule'], steep(650, desk.requests['one']['referenceFeeCents'], 8))
        self.assertFalse(any(a['type'] == 'reprice' and a['gigId'] == gig for a in resumed.world.actions))

    def test_first_posted_age_survives_rejoin_and_expiry(self):
        desk, history = new_desk(fee_shape='review', review_skip_night=0), []
        req = request()
        emit(desk, history, 600, 'price_request', request=req)
        emit(desk, history, 620, 'order_won', order=order_for(req))
        gig = desk.leg_gigs['one'][0]
        resumed = rebuild(desk, history, snapshot(desk, at=1100), fee_shape='review', review_skip_night=0)
        emit(resumed, history, 1100, 'gig_expired', gigId=gig)
        self.assertEqual(resumed.first_posted['one'], 620)
        posts = [a for a in resumed.world.actions if a['type'] == 'post']
        self.assertEqual(posts[-1]['schedule'][0]['feeCents'], 13200)

    def test_missed_failed_visit_restores_restrictions_and_does_not_duplicate_current_gig(self):
        desk, history = new_desk(), []
        req = request()
        emit(desk, history, 600, 'price_request', request=req)
        emit(desk, history, 620, 'order_won', order=order_for(req))
        gig = desk.leg_gigs['one'][0]
        history.append(dict(seq=len(history), at=630, kind='visit_failed', orderId='one', leg=0,
                            gigId=gig, reason='no_plates'))
        snap = snapshot(desk, at=640)
        snap['gigs'][0]['status'] = 'withdrawn'
        resumed = rebuild(desk, history, snap)
        posts = [a for a in resumed.world.actions if a['type'] == 'post']
        self.assertEqual(len(posts), 1)
        self.assertTrue(posts[0]['stops'][0]['withPlates'])
        again = rebuild(resumed, history, snapshot(resumed, at=645))
        self.assertFalse(again.world.actions)


class CheckpointTests(unittest.TestCase):
    def test_roundtrip_and_tail_replay_preserve_exact_private_state(self):
        original, history, gig = paired()
        original._split_orders.add('private-failed-pair')
        original.day_starts['global'] = (0, original.markup)
        original.brake_warnings = deque([600])
        original.town_wins = {0: Counter(a=2)}
        original.town_pending = {'pending': (1, 'a')}
        original.now = 630
        with tempfile.TemporaryDirectory() as directory:
            store = CheckpointStore(Path(directory) / 'checkpoint.json', original.world.id, {'name': 'Delta'})
            try:
                store.save(original, history[-1]['seq'])
                store.pending.join()
                loaded = store.load()
                self.assertIsNotNone(loaded)
                req = request('lost', at=635)
                emit(original, history, 635, 'price_request', request=req)
                emit(original, history, 655, 'order_lost', requestId='lost')
                world = World(); world.gigs = deepcopy(original.world.gigs)
                world.recovery_checkpoint = loaded
                resumed = new_desk(world, now=655, pairs=1)
                resumed.rejoin(snapshot(original), history)
                for key in ('markup', 'markups', 'day_starts', 'trust', 'dealers', 'pending',
                            'leg_gigs', 'first_posted', '_split_orders', 'town_wins', 'town_pending'):
                    self.assertEqual(getattr(resumed, key), getattr(original, key), key)
                self.assertEqual(resumed._pairs[gig], original._pairs[gig])
            finally:
                store.close()

    def test_corrupt_wrong_world_or_changed_model_checkpoint_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'checkpoint.json'
            store = CheckpointStore(path, 'world', {'name': 'Delta'})
            try:
                self.assertIsNone(store.load())
                path.write_text('{broken')
                self.assertIsNone(store.load())
                desk = new_desk()
                store.save(desk, -1); store.pending.join()
                data = json.loads(path.read_text())
                data['worldId'] = 'another-world'; path.write_text(json.dumps(data))
                self.assertIsNone(store.load())
                data['worldId'] = 'world'; data['model'] = {'name': 'Gamma'}
                path.write_text(json.dumps(data))
                self.assertIsNone(store.load())
            finally:
                store.close()

    def test_synthetic_half_week_rebuild_matches_continuous_desk(self):
        """Build a small practice-format history; no external/private fixture needed."""
        original, history = new_desk(pairs=1), []
        for day in range(3):
            at = day * 1440 + 600
            req = request(f'day-{day}', at=at, deadline=at + 1000)
            emit(original, history, at, 'price_request', request=req)
            emit(original, history, at + 20, 'order_lost', requestId=req['id'])
        at = 3 * 1440 + 600
        one, two = request(at=at, deadline=at + 1500), request('two', 'b', 'c', at=at + 1, deadline=at + 1500)
        emit(original, history, at, 'price_request', request=one)
        emit(original, history, at + 1, 'price_request', request=two)
        emit(original, history, at + 20, 'order_won', order=order_for(one, at + 1500))
        emit(original, history, at + 25, 'order_won', order=order_for(two, at + 1500))
        resumed = rebuild(original, history, snapshot(original, at=at + 30), pairs=1)
        for key in ('markup', 'markups', 'day_starts', 'pending', 'orders', 'leg_gigs', 'first_posted',
                    'dealers', 'trust', '_split_orders', '_failed_orders', '_picked', '_started'):
            self.assertEqual(getattr(resumed, key), getattr(original, key), key)
        for gig, pair in original._pairs.items():
            rebuilt = resumed._pairs[gig]
            for key in ('orders', 'posted_at', 'latest_safe', 'last_start', 'active', 'typical'):
                self.assertEqual(getattr(rebuilt, key), getattr(pair, key), key)
        self.assertEqual(resumed.next_pair_wake(), original.next_pair_wake())
        # The next market feedback also produces the same learned markup.
        for desk in (original, resumed):
            desk.now = at + 35
            desk.quote(request('tail', at=at + 35, deadline=at + 2000))
            desk.now = at + 55
            desk.handle(dict(seq=99, at=at + 55, kind='order_lost', requestId='tail'))
        self.assertEqual(resumed.markup, original.markup)


class ReceiptAndBoundaryTests(unittest.TestCase):
    def test_intercepted_pair_events_do_not_become_new_brake_signals_on_replay(self):
        desk, history, gig = paired(brake=1)
        emit(desk, history, 630, 'gig_booked', gigId=gig, feeCents=17280)
        emit(desk, history, 635, 'deadline_close', orderId='one')
        self.assertFalse(desk.brake_warned)  # booked pair handler intercepts the warning
        resumed = rebuild(desk, history, pairs=1, brake=1)
        self.assertEqual(resumed.brake_warned, desk.brake_warned)
        emit(desk, history, 640, 'gig_dropped', gigId=gig)
        self.assertFalse(desk.brake_drops)  # pair drop is intercepted before Gamma
        resumed = rebuild(desk, history, pairs=1, brake=1)
        self.assertEqual(resumed.brake_drops, desk.brake_drops)

    def test_expired_open_request_keeps_feedback_from_an_earlier_accepted_quote(self):
        desk, history = new_desk(), []
        req = request()
        emit(desk, history, 600, 'price_request', request=req)
        resumed = rebuild(desk, history, snapshot(desk, at=620, open_requests=[req]))
        self.assertFalse(resumed.world.actions)
        self.assertEqual(resumed.pending, {'one'})
        resumed.handle(dict(seq=1, at=621, kind='order_lost', requestId='one'))
        self.assertEqual(resumed.markup, 15000 * .994)

    def test_rejected_quote_receipt_prevents_false_loss_training_after_restart(self):
        desk, history = new_desk(), []
        req = request()
        event = dict(seq=0, at=600, kind='price_request', request=req)
        history.append(deepcopy(event)); desk.handle(event)
        actions, desk.outbox = desk.outbox, []
        desk.read_results(actions, [dict(ok=False, reason='Request is not open')])
        emit(desk, history, 620, 'order_lost', requestId='one')
        world = World(); world.recovery_quote_receipts = deepcopy(desk.recovery_quotes)
        resumed = new_desk(world, now=620)
        resumed.rejoin(snapshot(desk), history)
        self.assertEqual(resumed.markup, desk.markup)
        self.assertEqual(resumed.markup, 15000)
        self.assertFalse(resumed.pending)

    def test_receipts_survive_truncated_gzip_and_support_previous_runner_traces(self):
        import gzip
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            spec = {'name': 'Delta'}
            trace = path / '20261114-final-world.jsonl.gz'
            rows = [dict(type='run', worldId='world', model=spec),
                    dict(type='beta_quote', at=600, requestId='r1', tracker='global'),
                    dict(type='action_intent', batchId=1, actions=[dict(type='quote', requestId='r1')]),
                    dict(type='act_result', batchId=1, results=[dict(ok=False)]),
                    dict(type='model_quote_result', requestId='r2', at=601, ok=True,
                         competitive=True, tracker='global')]
            with gzip.open(trace, 'wt') as stream:
                for row in rows:
                    stream.write(json.dumps(row) + '\n')
                    stream.flush()
            trace.write_bytes(trace.read_bytes()[:-8])  # simulate SIGKILL before gzip footer
            store = CheckpointStore(path / 'world-checkpoint.json', 'world', spec)
            try:
                receipts = store.quote_receipts()
                self.assertEqual(set(receipts), {'r1', 'r2'})
                self.assertFalse(receipts['r1']['ok'])
                self.assertTrue(receipts['r2']['competitive'])
            finally:
                store.close()

    def test_checkpoint_with_invalid_state_falls_back_without_partial_restore(self):
        desk, history, _ = paired()
        state = model_state(desk)
        state['markup'] = 'broken'
        state['trust'] = {'wrong': 99}
        world = World(); world.gigs = deepcopy(desk.world.gigs)
        world.recovery_checkpoint = dict(worldId=world.id, lastSeq=history[-1]['seq'], state=state)
        resumed = new_desk(world, pairs=1)
        resumed.rejoin(snapshot(desk), history)
        self.assertEqual(resumed.markup, desk.markup)
        self.assertNotIn('wrong', resumed.trust)

    def test_delivery_arriving_at_snapshot_minute_is_not_undone(self):
        desk, history = new_desk(), []
        req = request()
        emit(desk, history, 600, 'price_request', request=req)
        emit(desk, history, 620, 'order_won', order=order_for(req))
        snap = snapshot(desk, at=630)
        history.append(dict(seq=len(history), at=630, kind='delivered', orderId='one', leg=0,
                            gigId=desk.leg_gigs['one'][0]))
        resumed = rebuild(desk, history, snap)
        self.assertEqual(resumed.orders['one']['deliveredAt'], [630])
        self.assertFalse(resumed.leg_gigs)
        self.assertFalse(resumed.world.actions)

    def test_snapshot_request_settled_at_same_minute_is_not_quoted_again(self):
        desk, history = new_desk(), []
        req = request()
        emit(desk, history, 600, 'price_request', request=req)
        snap = snapshot(desk, at=605, open_requests=[req])
        history.append(dict(seq=len(history), at=605, kind='order_lost', requestId='one'))
        resumed = rebuild(desk, history, snap)
        self.assertFalse(resumed.world.actions)
        self.assertFalse(resumed.pending)

    def test_same_minute_pair_cancellation_does_not_leave_a_withdrawn_partner_link(self):
        desk, history, gig = paired()
        snap = snapshot(desk, at=630)
        history.append(dict(seq=len(history), at=630, kind='order_cancelled', orderId='one',
                            gigs=[dict(gigId=gig, outcome='withdrawn')]))
        resumed = rebuild(desk, history, snap, pairs=1)
        self.assertNotIn('one', resumed.orders)
        self.assertNotEqual(resumed.leg_gigs['two'][0], gig)

    def test_open_quote_is_sent_before_overdue_pair_withdrawal(self):
        desk, history, _ = paired()
        req = request('open', at=680)
        history.append(dict(seq=len(history), at=680, kind='price_request', request=req))
        resumed = rebuild(desk, history, snapshot(desk, at=690, open_requests=[req]), pairs=1)
        self.assertEqual(resumed.world.actions[0]['type'], 'quote')
        self.assertEqual(resumed.world.actions[0]['requestId'], 'open')
        self.assertIn('withdraw', [a['type'] for a in resumed.world.actions])
