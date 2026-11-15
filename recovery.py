"""Offline model recovery. History never calls handle(), post(), send() or world.act().

Only reconciliation may act on the current snapshot. No SDK state is pickled;
checkpoints are versioned JSON, tied to a world and the selected model spec.
"""
from __future__ import annotations

from collections import Counter, deque
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
import gzip
import json
import logging
import math
import os
from pathlib import Path
import queue
import threading

from spread.starter import DAY, undelivered

LOG = logging.getLogger("cheap-drive.recovery")
VERSION = 1
SETS = ("booked", "urgent", "pending", "brake_warned", "brake_late", "town_won_ids",
        "_split_orders", "_failed_orders", "_picked", "_started", "_skip_logged")
DICTS = ("requests", "orders", "leg_gigs", "posts", "trust", "dealers", "markups",
         "quote_trackers", "day_starts", "brake_last_held", "near30", "town_pending",
         "first_posted", "delta_b1_pending", "delta_lane_counts", "delta_b1_counts")
SCALARS = ("markup", "brake_mode", "supply_roster_size", "now")
DEQUES = ("brake_warnings", "brake_drops")


def model_state(desk):
    """Copy only data, after a successful send; no clients, secrets or pending actions."""
    state = {k: deepcopy(getattr(desk, k)) for k in (*DICTS, *SCALARS) if hasattr(desk, k)}
    state.update({k: sorted(getattr(desk, k)) for k in SETS if hasattr(desk, k)})
    state.update({k: list(getattr(desk, k)) for k in DEQUES if hasattr(desk, k)})
    state["town_wins"] = deepcopy(desk.town_wins)
    state["recovery_quotes"] = deepcopy(desk.recovery_quotes)
    if hasattr(desk, "_pairs"):
        state["_pairs"] = {k: asdict(p) for k, p in desk._pairs.items()}
        if desk.driver_settings.pair_retry_limit:
            state["_failed_pairs"] = sorted(sorted(pair) for pair in desk._failed_pairs)
            state["_pair_failures"] = dict(desk._pair_failures)
    return state


def restore_state(desk, state):
    desk.recovery_quotes = deepcopy(state.get("recovery_quotes", {}))
    for name in (*DICTS, *SCALARS):
        if name in state:
            setattr(desk, name, deepcopy(state[name]))
    for name in SETS:
        if name in state:
            setattr(desk, name, set(state[name]))
    for name in DEQUES:
        if name in state:
            setattr(desk, name, deque(state[name]))
    desk.leg_gigs = {identity: {int(k): v for k, v in links.items()}
                     for identity, links in desk.leg_gigs.items()}
    desk.day_starts = {k: tuple(v) for k, v in desk.day_starts.items()}
    desk.town_pending = {k: tuple(v) for k, v in desk.town_pending.items()}
    desk.town_wins = {int(k): Counter(v) for k, v in state["town_wins"].items()}
    if hasattr(desk, "delta_lane_counts"):
        desk.delta_lane_counts = Counter(desk.delta_lane_counts)
    if hasattr(desk, "delta_b1_counts"):
        desk.delta_b1_counts = {k: Counter(v) for k, v in desk.delta_b1_counts.items()}
    if hasattr(desk, "_pairs"):
        from models.gamma_pairs import _Pair
        desk._pairs = {k: _Pair(**{**v, "orders": tuple(v["orders"])})
                       for k, v in state.get("_pairs", {}).items()}
        desk._pending_pairs.clear()
        if desk.driver_settings.pair_retry_limit:
            desk._failed_pairs = {frozenset(pair) for pair in state.get("_failed_pairs", [])}
            desk._pair_failures = Counter(state.get("_pair_failures", {}))


class CheckpointStore:
    """One coalescing writer: disk latency and fsync never hold up a quote.

    A stable world-specific filename beside the traces survives a fresh process.
    Atomic replacement leaves the previous complete checkpoint on SIGKILL.
    """
    def __init__(self, path, world_id, model_spec):
        self.path, self.world_id = Path(path), world_id
        self.model_spec = model_spec
        self.pending = queue.Queue(maxsize=1)
        self.error = None
        self.worker = threading.Thread(target=self._write, daemon=True, name="final-checkpoint")
        self.worker.start()

    def load(self):
        try:
            value = json.loads(self.path.read_text())
            if (value["version"] != VERSION or value["worldId"] != self.world_id
                    or value["model"] != self.model_spec or type(value["lastSeq"]) is not int
                    or not isinstance(value["state"], dict)
                    or not all(k in value["state"] for k in (*DICTS[:11], *SCALARS, *DEQUES,
                                                             "town_wins", "pending", "booked", "urgent"))):
                return None
            state = value["state"]
            if (value["lastSeq"] < -1 or type(state["now"]) is not int or state["now"] < 0
                    or any(not isinstance(state[k], dict) for k in DICTS if k in state)
                    or any(not isinstance(state[k], list) for k in (*SETS, *DEQUES) if k in state)):
                return None
            return value
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def save(self, desk, last_seq):
        value = dict(version=VERSION, worldId=self.world_id, model=self.model_spec,
                     lastSeq=last_seq, state=model_state(desk))
        try:
            self.pending.get_nowait()
            self.pending.task_done()
        except queue.Empty:
            pass
        self.pending.put_nowait(value)

    def quote_receipts(self):
        """Recover the few seconds after a checkpoint from our durable trace.

        SIGKILL may leave a gzip member without its footer; retain its complete
        JSON lines. Ignore other worlds/models and tolerate an incomplete tail.
        """
        receipts = {}
        for path in sorted(self.path.parent.glob(f"*-{self.world_id}.jsonl.gz")):
            quotes, intents = {}, {}
            try:
                with gzip.open(path, "rt", encoding="utf-8") as stream:
                    run = json.loads(next(stream))
                    if run.get("worldId") != self.world_id or run.get("model") != self.model_spec:
                        continue
                    for line in stream:
                        row = json.loads(line)
                        kind = row.get("type")
                        if kind in ("beta_quote", "beta_decline"):
                            quotes[row["requestId"]] = dict(at=row["at"], competitive=kind == "beta_quote",
                                                            tracker=row.get("tracker", "global"))
                        elif kind == "action_intent":
                            intents[row["batchId"]] = row["actions"]
                        elif kind == "act_result":
                            # Compatibility with traces from the previous final
                            # runner: it already persisted both sides of a call.
                            for action, result in zip(intents.pop(row["batchId"], []), row["results"]):
                                identity = action.get("requestId")
                                if action["type"] == "quote" and identity in quotes:
                                    receipts[identity] = {**quotes[identity], "ok": result["ok"]}
                        elif kind == "model_quote_result":
                            receipts[row["requestId"]] = {k: row[k] for k in ("at", "ok", "competitive", "tracker")}
            except (OSError, EOFError, ValueError, KeyError, StopIteration):
                continue
        return receipts

    def _write(self):
        while True:
            value = self.pending.get()
            try:
                if value is None:
                    return
                temporary = self.path.with_suffix(self.path.suffix + ".tmp")
                with temporary.open("w") as stream:
                    json.dump(value, stream, allow_nan=False, separators=(",", ":"))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            except (OSError, ValueError, TypeError) as error:
                self.error = type(error).__name__
                LOG.warning("Checkpoint write failed (%s); history replay remains available", self.error)
            finally:
                self.pending.task_done()

    def close(self):
        self.pending.join()
        self.pending.put(None)
        self.worker.join(timeout=1)


class _SilentJournal:
    def record(self, *args, **kwargs):
        pass


@contextmanager
def _bookkeeping(desk):
    journal = desk.journal
    desk.journal = _SilentJournal()
    if hasattr(desk, "_busy"):
        desk._busy += 1  # quote's outbox access must not run live pair timers
    try:
        yield
    finally:
        desk.outbox = []
        desk.journal = journal
        if hasattr(desk, "_busy"):
            desk._busy -= 1


def _detach(desk, gig_id):
    for links in desk.leg_gigs.values():
        for leg in [leg for leg, gig in links.items() if gig == gig_id]:
            links.pop(leg)
    desk.booked.discard(gig_id)


def _post_action(gig):
    return {"type": "post", **{k: deepcopy(gig[k]) for k in ("stops", "audience", "schedule")}}


def replay_history(desk, snapshot, history, *, after=-1):
    """Replay feedback in event order with the real pricing/learner hooks.

    Server history omits quote receipts and our withdrawals/timer decisions.
    With no checkpoint, assume the normal quote was accepted. The saved public
    gig posting times restore capacity/link bookkeeping as far as history can.
    In particular, final snapshot statuses must NOT leak into past quote targets.
    """
    # Preserve the snapshot's creation order for posts sharing one minute.
    gigs = sorted((g for g in snapshot["gigs"] if g["id"] not in desk.posts),
                  key=lambda g: g["postedAt"])
    if after >= 0:
        gigs = [g for g in gigs if g["postedAt"] >= desk.now]
    waiting = list(gigs)
    first = {}
    for gig in snapshot["gigs"]:
        for stop in gig["stops"]:
            first[stop["orderId"]] = min(first.get(stop["orderId"], gig["postedAt"]), gig["postedAt"])

    def carry_posts(at):
        for gig in waiting[:]:
            if gig["postedAt"] > at:
                break
            members = {s["orderId"] for s in gig["stops"]}
            if not members <= desk.orders.keys():
                continue
            desk.carry(_post_action(gig), gig["id"])
            waiting.remove(gig)

    if after < 0:
        desk.now = 0
    receipts = {**desk.recovery_quotes, **getattr(desk.world, "recovery_quote_receipts", {})}
    with _bookkeeping(desk):
        for source in history:
            if source["seq"] <= after:
                continue
            event = deepcopy(source)  # delivered() must never mutate the caller's history
            desk.now = max(desk.now, event["at"])
            carry_posts(desk.now)
            kind, identity, gig_id = event["kind"], event.get("orderId"), event.get("gigId")
            # Reuse the live pre-handler bookkeeping and Beta's exact learning
            # order (before win/cancellation changes the capacity books).
            pair_identity = event["order"]["id"] if kind == "order_changed" else identity
            pair_gig = gig_id or desk.leg_gigs.get(pair_identity, {}).get(0)
            action = desk.posts.get(pair_gig, {})
            members = {s["orderId"] for s in action.get("stops", [])}
            if hasattr(desk, "_pairs") and pair_gig in desk._pairs:
                pair = desk._pairs[pair_gig]
                if pair.active or not desk.driver_settings.pair_cancel_cleanup:
                    members.update(pair.orders)
            is_pair = bool(getattr(getattr(desk, "driver_settings", None), "pairs", 0) and len(members) > 1)
            intercepted = is_pair and (kind in ("gig_dropped", "no_show", "gig_expired", "order_changed")
                                      or kind == "deadline_close" and pair_gig in desk.booked)
            # DriverSideMixin returns before Gamma/Beta for these pair events.
            # Counting a pair drop as a single-gig brake signal changes pricing.
            if not intercepted:
                desk.observe_history(event)
                desk.observe_feedback(event)
            if is_pair and (kind in ("gig_dropped", "no_show", "gig_expired")
                            or kind == "order_changed" and pair_gig not in desk.booked):
                desk._split_orders.update(members)
                if desk.driver_settings.pair_retry_limit:
                    desk._remember_pair_failure(members)
            if kind == "price_request":
                receipt = receipts.get(event["request"]["id"])
                if receipt:
                    desk.now = max(desk.now, receipt["at"])
                desk.quote(event["request"])
                if receipt:
                    identity = event["request"]["id"]
                    # Public gig history can miss a rejected/withdrawn post and
                    # hence an admission decision. Local evidence wins.
                    if receipt["ok"] and receipt["competitive"]:
                        desk.pending.add(identity)
                        desk.quote_trackers[identity] = receipt["tracker"]
                        tracker = receipt["tracker"]
                        if desk.day_starts.get(tracker, (-1, 0))[0] != desk.now // DAY:
                            desk.day_starts[tracker] = (desk.now // DAY, desk.tracker_markup(tracker))
                    else:
                        desk.pending.discard(identity)
                        desk.quote_trackers.pop(identity, None)
                        desk.town_pending.pop(identity, None)
                    desk.recovery_quotes[identity] = deepcopy(receipt)
                desk.outbox = []  # never submit a past quote
            elif kind == "order_won":
                order = event["order"]
                desk.orders[order["id"]] = order
                if hasattr(desk, "first_posted"):
                    # If the first rejected post left no public gig, the win
                    # minute errs towards an older/higher fee, never a new ramp.
                    desk.first_posted.setdefault(order["id"], min(desk.now, first.get(order["id"], desk.now)))
            elif kind == "order_changed":
                if event["order"]["id"] in desk.orders:
                    desk.orders[event["order"]["id"]] = event["order"]
            elif kind == "order_cancelled":
                desk.orders.pop(identity, None)
                desk.leg_gigs.pop(identity, None)
                for gig in event.get("gigs", []):
                    if gig["outcome"] in ("withdrawn", "released"):
                        _detach(desk, gig["gigId"])
            elif kind == "deadline_close":
                desk.urgent.add(identity)
            elif kind in ("gig_booked", "gig_started"):
                desk.booked.add(gig_id)
            elif kind in ("gig_dropped", "no_show"):
                desk.booked.discard(gig_id)
            elif kind == "gig_expired":
                _detach(desk, gig_id)
            elif kind == "visit_failed":
                desk.leg_gigs.get(identity, {}).pop(event["leg"], None)
            elif kind == "delivered":
                desk.delivered(identity, event["leg"], event["at"])
            if hasattr(desk, "_picked"):
                if kind == "picked_up":
                    desk._picked.add(identity)
                elif kind == "visit_failed":
                    desk._failed_orders.add(identity)
                elif kind == "gig_started":
                    desk._started.add(gig_id)
                elif kind in ("gig_dropped", "no_show"):
                    desk._started.discard(gig_id)
            carry_posts(desk.now)


def _restore_pairs(desk, snapshot):
    if not hasattr(desk, "_pairs") or not desk.driver_settings.pairs:
        return []
    from models.gamma_pairs import _Pair
    uncertain = []
    active_ids = {g["id"] for g in snapshot["gigs"] if g["status"] in ("open", "booked", "working")}
    for pair in desk._pairs.values():
        if pair.gig_id not in active_ids:
            pair.active = False
    for gig in snapshot["gigs"]:
        members = tuple(dict.fromkeys(s["orderId"] for s in gig["stops"]))
        if len(members) < 2:
            continue
        if gig["id"] not in active_ids:
            # Public history cannot distinguish a timer split from another
            # withdrawal. Conservatively exclude former members from re-pairing.
            desk._split_orders.update(members)
            if desk.driver_settings.pair_retry_limit:
                # A public withdrawn gig conservatively consumes one attempt.
                # A checkpoint or history event may already have counted it.
                # Completed pairs do not limit still-actionable orders.
                if any(m in desk.orders and desk.orders[m]["status"] not in ("cancelled", "delivered")
                       for m in members):
                    desk._remember_pair_failure(members)
            continue
        pair = desk._pairs.get(gig["id"])
        action = _post_action(gig)
        if pair and pair.active and pair.orders == members and pair.action["stops"] == action["stops"]:
            pair.action = action
            continue
        pair = None
        now = desk.now
        # A plan is safe only if recreating it at its ORIGINAL posting minute
        # produces the same stops and audience, including all note restrictions.
        if (len(members) == 2 or len(members) == 3 and desk.driver_settings.pair_chain3) and all(
                m in desk.orders and m in desk.requests for m in members):
            desk.now = gig["postedAt"]
            try:
                with _bookkeeping(desk):
                    orders = [desk.orders[m] for m in members]
                    pair, _ = desk._plan(*orders) if len(members) == 2 else desk._plan_chain(orders)
            except Exception:
                pair = None
            finally:
                desk.now = now
            if pair and (pair.action["stops"] != action["stops"] or pair.action["audience"] != action["audience"]):
                pair = None
        if pair is None:
            # Keep a protective pair record even after a racing booking. A drop,
            # cancellation or expiry must still rescue the surviving member.
            typical = sum(desk.requests[m]["referenceFeeCents"] for m in members if m in desk.requests)
            pair = _Pair(members, action, 0, 0, now, gig["postedAt"], gig["postedAt"], typical, gig["postedAt"])
            uncertain.append(pair)
        pair.action, pair.gig_id = action, gig["id"]
        desk._pairs[gig["id"]] = pair
    return uncertain


def rejoin_model(desk, snapshot, history):
    """Reconstruct the model, then reconcile ONLY the currently actionable work."""
    checkpoint = getattr(desk.world, "recovery_checkpoint", None)
    after = -1
    if checkpoint:
        initial = model_state(desk)
        try:
            seq = checkpoint["lastSeq"]
            if (checkpoint["worldId"] == snapshot.get("worldId")
                    and checkpoint["state"]["now"] <= snapshot["now"]
                    and (seq == -1 or any(e["seq"] == seq for e in history))):
                restore_state(desk, checkpoint["state"])
                if not math.isfinite(desk.markup) or not desk.settings.markup_min_bps <= desk.markup <= desk.settings.markup_max_bps:
                    raise ValueError("invalid checkpoint markup")
                after = seq
        except (KeyError, TypeError, ValueError, AttributeError):
            restore_state(desk, initial)
            desk.journal.record("checkpoint_ignored", reason="invalid state")
    replay_history(desk, snapshot, history, after=after)
    desk.now = snapshot["now"]
    desk.world.now = desk.now
    replayed_orders = desk.orders
    cancelled = {e["orderId"] for e in history if e["kind"] == "order_cancelled"}
    desk.orders = {o["id"]: deepcopy(o) for o in snapshot["orders"]
                   if o["id"] in desk.requests and o["status"] != "cancelled" and o["id"] not in cancelled}
    # Snapshot has no sequence watermark. Events fetched just afterwards can
    # share its minute. Their cancellation/delivery/change is already true and
    # must not be undone by a slightly older snapshot of that same minute.
    for event in history:
        if event["at"] < snapshot["now"]:
            continue
        if event["kind"] in ("order_won", "order_changed"):
            identity = event["order"]["id"]
            if identity not in cancelled:
                desk.orders[identity] = deepcopy(replayed_orders[identity])
        elif event["kind"] == "delivered" and event["orderId"] in desk.orders:
            desk.orders[event["orderId"]]["deliveredAt"][event["leg"]] = event["at"]
    current_gigs = {g["id"]: deepcopy(g) for g in snapshot["gigs"]}
    for event in history:
        if event["at"] < snapshot["now"]:
            continue
        kind, gig_id = event["kind"], event.get("gigId")
        if gig_id in current_gigs:
            gig = current_gigs[gig_id]
            if kind in ("gig_booked", "gig_started", "gig_dropped", "no_show", "gig_expired"):
                gig["status"] = {"gig_booked": "booked", "gig_started": "working", "gig_dropped": "open",
                                 "no_show": "open", "gig_expired": "withdrawn"}[kind]
            elif kind == "visit_failed":
                gig["stops"] = [s for s in gig["stops"]
                                if (s["orderId"], s["leg"]) != (event["orderId"], event["leg"])]
                if not gig["stops"]:
                    gig["status"] = "withdrawn"
        elif kind == "order_cancelled":
            for outcome in event.get("gigs", []):
                gig = current_gigs.get(outcome["gigId"])
                if gig and outcome["outcome"] in ("withdrawn", "released"):
                    gig["status"] = "withdrawn"
    snapshot = {**snapshot, "gigs": list(current_gigs.values())}
    desk.leg_gigs = {}
    desk.posts = {}
    desk.booked = {g["id"] for g in snapshot["gigs"] if g["status"] in ("booked", "working", "done")}
    for gig in snapshot["gigs"]:
        if hasattr(desk, "first_posted"):
            for stop in gig["stops"]:
                identity = stop["orderId"]
                desk.first_posted[identity] = min(desk.first_posted.get(identity, gig["postedAt"]), gig["postedAt"])
        if gig["status"] not in ("open", "booked", "working"):
            continue
        action = _post_action(gig)
        desk.posts[gig["id"]] = action
        for stop in action["stops"]:
            order = desk.orders.get(stop["orderId"])
            if order and stop["leg"] in undelivered(order):
                desk.leg_gigs.setdefault(order["id"], {})[stop["leg"]] = gig["id"]
        if hasattr(desk, "_started") and gig["status"] == "working":
            desk._started.add(gig["id"])
    # Prepare pair state before any outbox read can poll a timer. Plan building
    # is bookkeeping-only and runs before queuing current quotes.
    if hasattr(desk, "_busy"):
        desk._busy += 1
    try:
        uncertain = _restore_pairs(desk, snapshot)
        settled = {e["requestId"] for e in history if e["kind"] == "order_lost"} | {
            e["order"]["id"] for e in history if e["kind"] == "order_won"}
        open_requests = {r["id"]: r for r in snapshot["openRequests"]}
        open_requests.update({e["request"]["id"]: e["request"] for e in history
                              if e["kind"] == "price_request" and e["at"] >= snapshot["now"]})
        for identity, request in open_requests.items():
            if identity in settled:
                continue
            identity = request["id"]
            if desk.now >= request["respondBy"]:
                # A snapshot can straddle the decision boundary. Preserve an
                # earlier accepted quote's pending feedback even though a new
                # quote can no longer be sent.
                desk.requests.setdefault(identity, deepcopy(request))
                continue
            desk.requests.pop(identity, None)  # known request != answered after rejoin
            desk.pending.discard(identity)
            desk.quote_trackers.pop(identity, None)
            desk.town_pending.pop(identity, None)
            desk.quote(deepcopy(request))
        # Give the few-second quote windows priority over withdrawal round trips.
        needs_withdrawal = uncertain or (hasattr(desk, "_pairs") and
                                        any(set(p.orders) & desk.urgent for p in desk._live_pairs()))
        if hasattr(desk, "next_pair_wake"):
            wake = desk.next_pair_wake()
            needs_withdrawal = needs_withdrawal or (wake is not None and wake <= desk.now)
        if desk.outbox and needs_withdrawal:
            desk.send()
        for pair in uncertain:
            desk._safe_split_pair(pair, "rejoin_unknown")
        if hasattr(desk, "_pairs"):
            for pair in list(desk._live_pairs()):
                if set(pair.orders) & desk.urgent:
                    desk._safe_split_pair(pair, "rejoin_urgent")
        # Warnings missed while offline must affect EXISTING open gigs too.
        paired = {m for p in desk._live_pairs() for m in p.orders} if hasattr(desk, "_pairs") else set()
        for identity in sorted(desk.urgent & desk.orders.keys() - paired):
            desk.raise_fees(identity)
        failures = {(e["orderId"], e["leg"]): e for e in history if e["kind"] == "visit_failed"}
        for identity, order in desk.orders.items():
            missing = [leg for leg in undelivered(order) if leg not in desk.leg_gigs.get(identity, {})]
            for leg in missing[:]:
                failure = failures.get((identity, leg))
                if failure:
                    desk.retry(identity, leg, failure["reason"])
                    missing.remove(leg)
            if missing and order["status"] == "waiting":
                queued_legs = {s["leg"] for a in desk.outbox if a["type"] == "post"
                               for s in a["stops"] if s["orderId"] == identity}
                missing = [leg for leg in missing if leg not in queued_legs]
                if missing:
                    desk.post(order, missing)
    finally:
        if hasattr(desk, "_busy"):
            desk._busy -= 1
    desk.journal.record("model_rejoin", at=desk.now, checkpointSeq=after,
                        replayedEvents=sum(e["seq"] > after for e in history), markupBps=desk.markup,
                        pending=len(desk.pending), openOrders=len(desk.orders),
                        pairs=len(desk._live_pairs()) if hasattr(desk, "_pairs") else 0)
