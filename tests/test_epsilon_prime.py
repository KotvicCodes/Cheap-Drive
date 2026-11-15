"""The pinned 24h95 candidate loads and rebuilds through the real live runner."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from capture import Journal
from compare import load_model
from final import play_live
from recovery import CheckpointStore, replay_history
from tests.test_gamma import GammaWorld, request
from tests.test_gamma_pairs import order_for


ROOT = Path(__file__).resolve().parents[1]


class CandidateLiveWorld:
    """In-memory stream and snapshot only; no client or world is created."""
    id = 'offline-epsilon-final'

    def __init__(self):
        self.now, self.actions, self.history, self.orders = 1300, [], [], []
        self.initial_map = GammaWorld().initial_map
        self.client = self
        requests = [request(f'completed-{n}') for n in range(20)]
        for req in requests:
            self.emit(500, 'price_request', request=req)
        for req in requests:
            order = order_for(req, deadline=1295)
            self.orders.append(order)
            self.emit(520, 'order_won', order=order)
        for n, order in enumerate(self.orders):
            at = 1295 if n < 18 else 1296
            self.emit(at, 'delivered', orderId=order['id'], leg=0)
            order['deliveredAt'] = [at]
            order['status'] = 'delivered'

    def emit(self, at, kind, **data):
        self.history.append(dict(seq=len(self.history), at=at, kind=kind, **deepcopy(data)))

    def map(self):
        return deepcopy(self.initial_map)

    def roster(self):
        return []

    def snapshot(self):
        return dict(worldId=self.id, now=self.now, endsAt=1340,
                    orders=deepcopy(self.orders), gigs=[], openRequests=[])

    def events(self, after=-1):
        return deepcopy([event for event in self.history if event['seq'] > after])

    def act(self, actions):
        self.actions.extend(deepcopy(actions))
        return [dict(ok=True, id=f'receipt-{n}') for n, _ in enumerate(actions)]

    def stream(self, after=-1, idle=None):
        req = request('future')
        req.update(arrivedAt=1310, respondBy=1325)
        for option in req['options']:
            option['deadline'] += 810
        for event in (dict(seq=60, at=1310, kind='price_request', request=req),
                      dict(seq=61, at=1340, kind='forecast', text='end of offline stream')):
            if event['seq'] > after:
                self.now = event['at']
                yield event

    def score(self):
        return dict(marginCents=0, revenueCents=0, wonOrders=20,
                    onTimeShare=.9, undeliveredShare=0, ranked=True)


class Reads:
    latest = 1300

    def drain(self, journal):
        pass


class EpsilonPrimeFinalTests(unittest.TestCase):
    def test_model_pins_the_exact_24h95_policy(self):
        model = load_model(ROOT / 'models/epsilon-prime.json')
        medium = json.loads((ROOT / 'models/epsilon-medium.json').read_text())
        self.assertEqual(model.spec['name'], 'Epsilon Prime')
        self.assertEqual(model.spec['factory'], 'delta:make_delta')
        self.assertEqual(model.spec['settings'], {
            **medium['settings'], 'epsilon_breaker': 1,
            'epsilon_breaker_on_time_bps': 9500,
            'epsilon_breaker_window_minutes': 1440,
            'epsilon_breaker_risk_orders': 0,
            'epsilon_breaker_restore_pairing': 0,
        })

    def test_live_runner_rebuilds_from_history_and_checkpoints_before_and_after_trip(self):
        model = load_model(ROOT / 'models/epsilon-prime.json')
        for mode in ('history_only', 'checkpoint_before_trip', 'checkpoint_after_trip'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                world, desks = CandidateLiveWorld(), []
                store = None
                if mode != 'history_only':
                    prior = model.factory(world, 8, 500, Journal(io.StringIO()))
                    history = world.history[:58] if mode == 'checkpoint_before_trip' else world.history
                    replay_history(prior, dict(gigs=[]), history)
                    self.assertEqual(prior.epsilon_breaker_active, mode == 'checkpoint_after_trip')
                    store = CheckpointStore(Path(directory) / 'checkpoint.json', world.id, model.spec)
                    store.save(prior, history[-1]['seq'])
                    store.pending.join()
                    self.assertIsNotNone(store.load())

                def factory(w, level, now, journal):
                    desk = model.factory(w, level, now, journal)
                    desks.append(desk)
                    return desk

                try:
                    play_live(world, 8, Journal(io.StringIO()), factory,
                              clock=lambda: world.now, reads=Reads(), checkpoint=store)
                finally:
                    if store:
                        store.close()
                desk = desks[0]
                self.assertTrue(desk.epsilon_breaker_active)
                self.assertEqual(desk.epsilon_breaker_at, 1296)
                self.assertEqual(len(desk.epsilon_breaker_outcomes), 20)
                self.assertEqual(sum(desk.epsilon_breaker_outcomes.values()), 18)
                self.assertEqual(len(desk.epsilon_breaker_resolved_at), 20)
                self.assertEqual(desk.win_target(), 4200)
                self.assertEqual(desk.settings.short_km, 45)
                self.assertEqual(desk.settings.short_bps, 9200)
                self.assertEqual(desk.settings.long_markup_bps, 10000)
                self.assertEqual(desk.settings.trade_ins, 0)
                self.assertEqual(desk.intake_settings.delta_relaxed_slack_minutes, 0)
                self.assertEqual(desk.intake_settings.delta_corridor_open_cap, 0)
                self.assertEqual(desk.driver_settings.pair_once, 0)
                self.assertEqual(desk.delta_pair_max_wait_minutes, 180)
                self.assertEqual([a['requestId'] for a in world.actions], ['future'])
