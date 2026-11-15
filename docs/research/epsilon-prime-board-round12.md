# Epsilon Prime: round 12 leaderboard runs

All five official level-8 ranking runs are public in round **12, “Sunday
06:00” (Helsinki, 15 November 2026)**. Team: **Guardians of the Moonlight**
(`guardians-of-the-moonlight`). Our result is **34 of 51 ranked teams**,
**€69,640.20**, **97.25% on time**, **1,779 orders won**, all five qualified.

## Public standings

Retrieved **2026-11-15 07:55:28.783 UTC** from the public
[`/v1/leaderboards/practice?level=8`](https://spread.bahnexpress.com/v1/leaderboards/practice?level=8)
endpoint through [the public leaderboard](https://spread.bahnexpress.com/leaderboard).
The [complete frozen JSON](round12-board-public.json) includes `current`
(round 12) and `previous` (closed round 11). Round 12 is the newest round
provided by this feed; no round newer than 12 appears in this retrieval.
It started at `2026-11-15T04:00:17.083Z` (**06:00:17 Helsinki**).

There are **51 non-null ranks**, excluding House and unqualified entries.
The page separately displays **65 of 67 teams complete**; completion is not
the ranked-team count. The feed lists 240 teams, including teams with no runs.
The feed still calls round 12 `current` and provides **no explicit round-closed
flag or closing timestamp**. These are the latest public standings at retrieval,
not an independently verified immutable closing position.

| Epsilon Prime run | Gross margin | On time | Orders won | Ranked |
| --- | ---: | ---: | ---: | :---: |
| 1 | €11,066.13 | 98.18% | 330 | Yes |
| 2 | €12,497.55 | 98.21% | 336 | Yes |
| 3 | €14,397.90 | 97.23% | 361 | Yes |
| 4 | €11,617.79 | 94.00% | 350 | Yes |
| 5 | €20,060.83 | 98.51% | 402 | Yes |
| **Total** | **€69,640.20** | **97.25%** | **1779** | **5 / 5** |

The exact aggregate on-time share is `0.9724564362001125`, not the mean of
rounded weekly percentages. The sum of exact-cent run margins is `6964020`.
The lowest weekly on-time share is 94.00%, above the 90% qualification floor.

Leader **Juhus**: **€98,178.92**, **€28,538.72 ahead of us**.
Tenth place **Elysa's Secret**: **€77,833.16**, **€8,192.96 ahead**.
Organisers' **House best**: **€58,697.43**, **€10,942.77 behind us**, with no rank.

| Public rank | Team | Gross margin |
| --- | --- | ---: |
| 1 | Juhus | €98,178.92 |
| 2 | Seekers | €87,241.12 |
| 3 | Progresful | €86,394.08 |
| 4 | MathNet1 | €85,567.76 |
| 5 | bobbing-wombat | €83,705.04 |
| 6 | source-exp | €82,771.11 |
| 7 | blib_blib | €81,773.06 |
| 8 | pelaaja juhlii | €79,842.00 |
| 9 | Team Moonshot | €79,577.68 |
| 10 | Elysa's Secret | €77,833.16 |
| 32 | pfjfjfjfj | €70,804.83 |
| 33 | monkey | €70,324.76 |
| **34** | **Guardians of the Moonlight** | **€69,640.20** |
| 35 | car | €69,541.75 |
| 36 | Halal Team | €69,092.27 |
| — | House best | €58,697.43 |

The run chart compares the same numbered secret weeks:

| Run | Epsilon Prime | Juhus |
| --- | ---: | ---: |
| 1 | €11,066.13 | €15,133.31 |
| 2 | €12,497.55 | €16,414.25 |
| 3 | €14,397.90 | €21,531.02 |
| 4 | €11,617.79 | €17,737.79 |
| 5 | €20,060.83 | €27,362.55 |
| **Total** | **€69,640.20** | **€98,178.92** |

## Model and local provenance

All five runs used **[Epsilon Prime](../../models/epsilon-prime.json)**,
`win_target_bps: 4300`, `premium_min_slack_minutes: 1440`, and the 95% / 1440-minute
breaker with risk orders and pairing restoration both zero. The full settings
match [the final's saved configuration](final-board.md#model-and-local-provenance).
Every inspected run header has the same name and settings, using the compatible
`delta:make_delta` factory alias. Provenance is in the sibling worktree
`final-prime/runs/board/` (git-ignored):

| Run | World ID | Completed trace filename |
| --- | --- | --- |
| 1 | `wfe6065218fe74ac59c1e` | `20261115T061652713009Z-resume-wfe6065218fe74ac59c1e.jsonl.gz` |
| 2 | `w52c66a37c4d1b74c57f4` | `20261115T062011Z-level8-w52c66a37c4d1b74c57f4.jsonl.gz` |
| 3 | `wf9a13786ff82c034355d` | `20261115T062304Z-level8-wf9a13786ff82c034355d.jsonl.gz` |
| 4 | `wd837237b08c5211e24c4` | `20261115T062554Z-level8-wd837237b08c5211e24c4.jsonl.gz` |
| 5 | `w06d2acc243c40c384159` | `20261115T062903Z-level8-w06d2acc243c40c384159.jsonl.gz` |

All five completed `run_end` score records match the public per-run margin,
on-time share, order count and qualification exactly. Run 1's earlier
`20261115T061425Z-level8-wfe6065218fe74ac59c1e.jsonl.gz` is a truncated gzip
after an interruption; its model header is readable and agrees. The resumed
trace, `prime-4300-ranking-20261115.result.json`, and launch log preserve the
completed run-1 result. The five matching result tuples establish the local
run-to-public-row correspondence; no authenticated world-list request was used.
The actual runtime source revision is **unverified**; inspected sibling HEAD
is `6c1822e97409b9d6fcc6b07e05a7c34dcce21932`, but headers do not stamp a commit.

## Evidence and caveats

- [Round totals](../screenshots/round12-totals.svg): top ten, our two neighbours on either side and House best; exact cents, our team highlighted.
- [Five runs versus Juhus](../screenshots/round12-runs.svg): same numbered weeks, exact cents and zero-based bars.
- [Real public-page leaders](../screenshots/leaderboard-round12.png): round label and selected level 8; captured **2026-11-15 07:58:45 UTC**.
- [Our public-page row](../screenshots/leaderboard-round12-team.png): rank 34 and neighbours; captured **2026-11-15 07:57:18 UTC**.

PNGs are unaltered captures of the public page at a **1280 × 1000 CSS-pixel
viewport** (**2560 × 2000 image pixels**). Only scrolling was used; no changed
data, hidden rows, cropping or annotation. The page rounds our total to
**€69,640** and on time to **97.2%**; charts retain exact cents. Feed and
screenshots have separate capture times and the board can update between them.
Different rounds and the final use different secret weeks; their totals are
not a paired model comparison.

[Offline reproduction of all three new SVGs](final-board.md#rebuild-the-charts-offline)
uses the established round-9/round-11 style and the frozen public snapshots.
This documentation task used public GETs and read-only local inspection only;
it created no worlds or runs and did not touch any running process.
