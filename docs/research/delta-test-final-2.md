# Delta: test final 2

**14 November 2026, 20:00 Helsinki (EET, UTC+2), 18:00 UTC.**
Team: **Guardians of the Moonlight** (`guardians-of-the-moonlight`).
Model: [Delta](../../models/delta.json), run through [`final.py`](../../final.py).

## Public standings

Retrieved **2026-11-14 18:40:38.493 UTC** from the public
[`/v1/leaderboard`](https://spread.bahnexpress.com/v1/leaderboard) event stream.
The [public leaderboard](https://spread.bahnexpress.com/leaderboard) script
`/chunk-25gvfzz1.js` opens `new EventSource("/v1/leaderboard")` and parses its
JSON messages for "The final"; this is separate from the practice-round feed.
The [saved public JSON snapshot](delta-test-final-2-public.json) retains the
complete message, source URL and retrieval time.

The feed reports `status: "ended"`, `startsAt: "2026-11-14T18:00:00.000Z"`,
and `now: 14280`, `endsAt: 14280`, identifying tonight's completed test final.
There are **75 ranked teams** among 234 listed teams: count only non-null
`rank` values, excluding unranked entries.

| Rank | Team | Gross margin | Orders won |
| ---: | --- | ---: | ---: |
| 1 | Juhus | €19,592.05 | 469 |
| 10 | Team Moonshot | €16,622.58 | 393 |
| 41 | bahn67 | €12,963.14 | 334 |
| **42** | **Guardians of the Moonlight** | **€12,816.67** | **256** |
| 43 | Bidcast | €12,694.24 | 351 |

Our exact public fields are `marginCents: 1281667`, `wonOrders: 256`,
`onTimeShare: 0.99609375` (**99.609375%**, published as **99.61%**),
`rank: 42`, `ranked: true`. Leader and tenth-place margins are respectively
`1959205` and `1662258` cents. These agree with the runner's reported
€12,816.67, 99.61% and 256 orders; there is no discrepancy at that precision.

The real screenshots show the original page, scrolled with no changed data,
hidden rows, cropping or annotations, at a 1280 × 1000 viewport:

- [Heading and leaders](../screenshots/test-final-2-leaders.png): captured **2026-11-14 18:41:23 UTC**.
- [Our row and neighbours](../screenshots/test-final-2-team.png): captured **2026-11-14 18:41:39 UTC**.

The page rounds margins to whole euros and on-time shares to one decimal:
our row shows **€12,817**, **99.6%**, **256 orders**, **rank 42**.

## Interrupted run

The runner observations supplied for this update record eight answers taking
1–2 seconds, then two connection drops during a server restart around Friday
of the simulated week: a read timeout and a name-resolution failure.
The runner rebuilt its desk on Saturday at **world minute 7849**, replaying
**18,342 history events**; it handled **19,014 events in total**.
A later trace audit found that the 1,171 events after the rebuild contained
no price requests, quotes, wins or losses, so the flat order count from
Saturday is not a quoting failure. Requests that arrived during the outage
(minutes 6871–7849) went unanswered; their number and margin are not measured.
See [the recovery work](final-rejoin-recovery.md).

These interruption details come from the supplied runner observations, not
the public standings feed. This update used only the public page, its script
and public JSON; no team key was used and no game was created, played or deleted.
