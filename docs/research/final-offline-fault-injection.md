# Final runner offline fault injection, 15 November 2026

Base: `0b537090727d6e520588ac0f8c7cc414c0e86084`. Combined candidate includes
hardening A `50e4542c35930533201397d0091d6aafa4cfb825` plus hardening B.
All worlds, HTTP connections, WebSocket sockets and action responses in this
audit are fakes. No Spread world was created or advanced; no existing process
was touched. SIGKILL targeted only the audit's own spawned children.

The tests use the actual Epsilon Prime configuration, actual live runner,
actual SDK validation/rate buckets/429 loop, and actual gzip journals and JSON
checkpoints. The fake world begins with a historical 18/20 on-time outcome,
which latches `epsilon_breaker` at world minute 1296. This tests restoration of
the breaker policy as well as its stored flag. HTTP latency and world time are
simulated; the journal fsync experiment actually sleeps for ten seconds.

## Results

PASS means the stated bounded scenario passed, not a guarantee for arbitrarily
long outages. A test that documents a limitation can pass its assertions while
the stronger operational requirement below remains FAIL.

| Injected fault | Result | Evidence and practical limit |
| --- | --- | --- |
| Stream disconnect mid-burst | PASS for disconnect; FAIL for silent black hole | Actual SDK reconnect resumes `after=64` after five events, deliberately replaying the boundary event. All 12 requests get one quote before minute 1325. Runner-level `Unreachable` also rebuilds with 12/12 unique attempts (zero retry delay for that bounded probe). A fake black-holed SDK socket yields 305 consecutive idle `None` values and never reconnects despite `QUIET_LIMIT=300`. |
| HTTP 5xx / 429 / timeout in `act()` | PASS for recovery; FAIL for deadline guarantee | HTTP 409/500/501/502/503/504/507 and SDK-mapped timeout recover by rebuilding; one SDK 429 retries once and yields 12 unique accepted quotes. The actual SDK timeout path advances simulated time by 20 seconds; after the runner's normal three-second backoff, the expired request is skipped and a fresh request is accepted. Even a single 500 plus three-second backoff can exhaust a 15-minute window at 5 world minutes/s. A tape of 100 429s occupies the SDK call for 10.04 simulated seconds, sends the old quote late, and then quotes a fresh request. The SDK loop has no retry/deadline bound. |
| One rejected action in a batch | PASS | One of four initial open-request quotes is refused; the other three receipts remain accepted, and the refused request leaves pending feedback. A's separate 55-quote test crosses the 50-action boundary, refuses the first quote, and retains the other 54 receipts plus post bookkeeping. |
| 40+ price requests in one minute | PASS within tested budget | 64 requests born at minute 1310, all due at 1325; 40 ms simulated HTTP latency/call and a conservative 20-token capacity/refill of 20 actions/s. All 64 quotes arrive strictly before the deadline; last receipt minute 1322.8 (2.56 simulated seconds). This does not establish safety for higher HTTP latency or concurrent blocking post/withdraw calls. |
| SIGKILL and restart | FAIL strict zero-duplicate requirement; PASS obligations and breaker | 15 real child kills: three seeded random request positions at each of five boundaries (flushed intent, before server commit, after server commit, flushed action result, flushed model receipt). Every trial restores all 12 accepted request IDs, an outstanding delivery obligation and its gig link, and the breaker latch at 1296. The three kills after server commit but before receipt cause one duplicate wire attempt each; all other boundaries have zero duplicates. This fake server rejects the repeated request, so no second accepted quote is counted. Real replacement/rejection semantics do not remove the duplicate wire attempt or resolve an uncertain write atomically. |
| Corrupt/truncated checkpoint or journal | PASS for fallback; lost receipt contents remain unrecoverable | Truncated JSON, invalid JSON and non-object checkpoint root all fall back; a gzip footer truncated by eight bytes retains four complete receipts and avoids re-quoting them. Invalid DEFLATE and non-object journal rows no longer crash recovery (A fix); other readable traces still supply receipts. Invalid checkpoint markup cannot leave the breaker policy applied after fallback (A fix). No claim of exact learner restoration when the only receipt copy is destroyed. |
| Slow fsync / ENOSPC | PASS slow fsync; FAIL continuous operation on ENOSPC | Actual ten-second journal fsync runs in the background while all 64 quotes complete; consumer elapsed time is asserted below one real second. Shutdown waits for pending fsync, outside quote windows. ENOSPC on the intent write raises before any server action; after storage returns, restart quotes all four open requests and restores the breaker. Continuing to quote while the journal is full is deliberately unsupported. |
| Final appears while waiting / already running | PASS | An absent-final 404 followed by an announced final is discovered after the normal five-second poll. Starting at minute 1310 with open requests rebuilds immediately. Both paths quote four of four requests and reconstruct the breaker from history. Transient HTTP errors during waiting also recover. |
| WebSocket upgrade HTTP 409 / 429 / 500 | PASS after B fix | Actual SDK HTTP-upgrade parsing uses fake sockets. Each status rebuilds the runner, closes the failed fake socket, and subsequently accepts all four quotes. Previously the plain `SpreadError` escaped the retry loop. |

## Changes kept small

- A: live quotes drain before pair timer withdrawals/posts; corrupt gzip and
  malformed rows fall back; markup is validated before a checkpoint can apply
  breaker settings.
- B: rebuild on transient HTTP 409/429/5xx as well as `Unreachable`, including
  the final discovery loop. HTTP 400/401/403/404/422 remain fatal during play.
- B: microseconds in trace filenames keep same-second restarts in separate
  gzip files instead of appending behind a killed, incomplete gzip member.
- No model files or pricing/admission settings changed.

## Reproduction

Run with the supplied interpreter (pytest was installed externally by A):

```sh
PYTHONPATH=/tmp/cheap-drive-final-audit-pytest \
  /home/agent/.t3/worktrees/Cheap-Drive/t3-034ebca2-70a3ee396c687b47/.venv/bin/python \
  -m pytest -q
```

Targeted tests are in `tests/test_final_faults.py`,
`tests/test_final_hardening.py` and `tests/test_final_output.py`. The full suite
includes the earlier replay, capture, recovery and model-equivalence tests.
Combined-suite result at 05:32 UTC: **563 passed, 1,915 subtests passed**, six
existing `models/gamma_notes.py` deprecation warnings, in **24.43 seconds**.

## Remaining operational needs

Monitor actual event consumption, not merely process existence or a growing
journal. On a black-holed stream, idle ticks can keep writing checkpoints and
background clock reads can keep working. A supervisor or operator needs a
separate liveness signal and may need to restart the process. No untested SDK
monkeypatch or automatic forced-rejoin policy was added immediately before the
final. Keep storage available, avoid parallel key use that sustains rate limits,
and do not interpret restart recovery as an exactly-once write guarantee.
