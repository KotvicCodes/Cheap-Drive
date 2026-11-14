# Gamma: round 7 leaderboard runs

All five official level-8 ranking runs completed on 14 November 2026 in
round 7, **Saturday 15:00 Helsinki (13:00 UTC)**. The round opened at
`2026-11-14T13:00:17.090Z` and remains open until 18:00 Helsinki.

Team: **Guardians of the Moonlight** (`guardians-of-the-moonlight`).
Model: unchanged [Gamma](../../models/gamma.json), factory
`gamma_notes:make_gamma_notes_pairs`, source revision `0eb4e3e`.

```bash
python scripts/board.py models/gamma.json --runs 5 --fast
```

The official client created one ranking world at a time and finished it before
starting the next. All five traces, final scores and end snapshots remain
private in git-ignored `runs/board/`. No ranking world was deleted or retried.

## Completed runs

| Run | Gross margin | On time | Orders won | Ranked |
| --- | ---: | ---: | ---: | :---: |
| 1 | €14,924.75 | 97.52% | 282 | Yes |
| 2 | €13,563.36 | 99.22% | 255 | Yes |
| 3 | €9,385.40 | 91.35% | 289 | Yes |
| 4 | €12,867.62 | 97.87% | 282 | Yes |
| 5 | €16,139.35 | 98.18% | 275 | Yes |
| **Total** | **€66,880.48** | **96.75%** | **1383** | **5 / 5** |

The total on-time figure is the official leaderboard's aggregate; qualification
is checked separately for every week. Every run exceeded the required 90%.

## Standings snapshot

Retrieved **2026-11-14 15:05:59 UTC** from the public
[`/v1/leaderboards/practice?level=8`](https://spread.bahnexpress.com/v1/leaderboards/practice?level=8)
endpoint, with the page at [the public leaderboard](https://spread.bahnexpress.com/leaderboard).

- Our rank: **32 of 45 ranked teams**, €66,880.48.
- Leader: **source-exp**, €92,830.32.
- Tenth place: **razors**, €82,653.03.
- Gap to tenth: **€15,772.55**.
- Organisers' House best: **€64,249.30**; house teams do not receive a public rank.

This is a snapshot of an open round, not the final round position. Charts use
exact cents; the original public-page screenshots show rounded whole euros.
Screenshots were captured at 15:07 UTC (17:07 Helsinki) on 14 November 2026.
The previous Beta round used different weeks and is not a paired Gamma comparison.

## Evidence

- [Round totals](../screenshots/round7-totals.svg): top ten, our neighbours and House best.
- [Five runs versus the leader](../screenshots/round7-runs.svg): same numbered secret weeks, zero-based bars.
- [Public-page leaders](../screenshots/leaderboard-round7.png).
- [Our public-page row](../screenshots/leaderboard-round7-team.png).
