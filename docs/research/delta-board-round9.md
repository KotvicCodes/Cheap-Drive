# Delta: round 9 leaderboard runs

All five official level-8 ranking runs are present and ranked on the public
leaderboard in round **9, Saturday 21:00 Helsinki** (14 November 2026).
The public endpoint confirms the round opened at `2026-11-14T19:00:17.085Z`.
Team: **Guardians of the Moonlight** (`guardians-of-the-moonlight`).

The runs used the settings now in `models/delta.json`: Early Delta plus the
dispatch fixes `delta_wide_windows` and `delta_private_delivery_rescue`, wider
pairing (`delta_pairing="extended"`) and a 42% win target
(`win_target_bps=4200`), from code at
[`589daf7ad8b17d6c2402bb45f7cab7856cd777b9`](https://github.com/KotvicCodes/Cheap-Drive/commit/589daf7ad8b17d6c2402bb45f7cab7856cd777b9).
At the time of the runs it was called "the Epsilon candidate" and had no
committed model file; it was then named Delta. The public feed verifies results and
qualification, not which code or settings produced them; candidate provenance
comes from the ranking-run handoff.

## Completed runs

| Delta run | Gross margin | On time | Orders won | Ranked |
| --- | ---: | ---: | ---: | :---: |
| 1 | €13,767.61 | 97.99% | 348 | Yes |
| 2 | €16,382.65 | 93.58% | 374 | Yes |
| 3 | €13,906.72 | 95.47% | 353 | Yes |
| 4 | €18,057.50 | 98.40% | 374 | Yes |
| 5 | €13,649.07 | 98.28% | 349 | Yes |
| **Total** | **€75,763.55** | **96.72%** | **1798** | **5 / 5** |

All figures above come from the public feed, with margins retained to exact
cents and on-time shares rounded to two decimal places. The total on-time share
is the official board aggregate (`0.9671857619577308`), not an average of the
rounded weekly percentages. Qualification is checked separately for every week;
all five exceeded the required 90%, with the lowest at 93.58% in run 2.

## Standings snapshot

Retrieved **2026-11-14 21:34:23 UTC** (`2026-11-14T21:34:23.095Z`) from the public
[`/v1/leaderboards/practice?level=8`](https://spread.bahnexpress.com/v1/leaderboards/practice?level=8)
endpoint, with the page at [the public leaderboard](https://spread.bahnexpress.com/leaderboard).

Our rank: **31 of 52 ranked teams**, **€75,763.55**, **96.72% on time**.
The count includes only teams with a non-null public rank, excluding house teams
and teams that did not qualify. The page's separate completion counter showed
65 of 71 teams complete; completion is not the same as qualification.

Leader **Juhus**: **€105,424.26**; tenth place:
**pelaaja juhlii**, **€84,856.64** (we are **€9,093.09 behind**).
Organisers' **House best**: **€66,135.59**.
House teams have no public rank and are excluded from the ranked-team count.

| Public rank | Team | Gross margin |
| --- | --- | ---: |
| 1 | Juhus | €105,424.26 |
| 2 | MathNet1 | €96,849.68 |
| 3 | source-exp | €94,298.50 |
| 4 | No Empty Miles | €92,266.71 |
| 5 | Team Moonshot | €89,316.90 |
| 6 | eth | €88,728.89 |
| 7 | akanegakirru | €86,729.61 |
| 8 | ppo | €86,560.08 |
| 9 | klmisbest | €86,201.40 |
| 10 | pelaaja juhlii | €84,856.64 |
| 29 | The Delusionals | €77,245.49 |
| 30 | katalyst | €76,169.01 |
| **31** | **Guardians of the Moonlight** | **€75,763.55** |
| 32 | Test-Team1114 | €73,056.42 |
| 33 | monkey | €72,169.05 |
| — | House best | €66,135.59 |

The run chart compares the same numbered secret weeks within round 9:

| Run | Delta | Juhus |
| --- | ---: | ---: |
| 1 | €13,767.61 | €19,096.44 |
| 2 | €16,382.65 | €23,791.88 |
| 3 | €13,906.72 | €20,731.31 |
| 4 | €18,057.50 | €24,529.27 |
| 5 | €13,649.07 | €17,275.36 |
| **Total** | **€75,763.55** | **€105,424.26** |

**The round was still open at retrieval and at both screenshot captures, until
22:00 UTC (00:00 Helsinki on 15 November).** This is a snapshot, not a final
round position. The board can update between retrieval and screenshots.
The original page rounds margins to whole euros and on-time shares to one
decimal place; our row displays €75,764 and 96.7%.

## Previous rounds

The README retains the dated Early Delta round-8 snapshot: **37th of 58**,
**€55,639.62**, **96.96% on time**, retrieved **2026-11-14 17:53:55 UTC**.
That was an open-round snapshot, not its final position. For completeness,
the round-9 response's previous-round data now records Early Delta's closed round 8
as **44th of 67 ranked teams**, with the same total and on-time share.
[Original round-8 snapshot and evidence](delta-board-round8.md).

Gamma's closed round 7 was **41st of 62**, **€66,880.48**, **96.75% on time**,
all five qualified (retrieved 2026-11-14 17:53:55 UTC).
[Earlier round-7 snapshot](gamma-board-round7.md).
The three rounds used different secret weeks, so their totals are not a paired
comparison of the models; the paired practice evidence is in
[Delta results](delta-results.md).

## Evidence and reproduction

- [Round totals](../screenshots/round9-totals.svg): top ten, ranks 29–33 and House best.
- [Five runs versus Juhus](../screenshots/round9-runs.svg): same numbered secret weeks within this round, zero-based bars.
- [Public-page leaders](../screenshots/leaderboard-round9.png): ranking-round heading, round label and selected level 8; captured **2026-11-14 21:35:12 UTC**.
- [Our public-page row](../screenshots/leaderboard-round9-team.png): rank 31 and neighbours; captured **2026-11-14 21:35:40 UTC**.
- [Offline chart renderer](../../tests/make_round9_charts.py): frozen exact-cent public figures; run `python tests/make_round9_charts.py` with Matplotlib installed.

Charts follow round 8's typography, colours, horizontal bars, exact-cent labels
and zero-based axes. Both screenshots are unaltered captures of the real public
page at a 1280 × 1000 CSS-pixel viewport (2560 × 2000 image pixels), scrolled to
the relevant rows. No data was changed, no rows were hidden, and the captures
were not cropped or annotated.

Only the public page and public JSON were read. No team API key was used, no
game worlds or runs were created, played or deleted, and no existing processes
were changed for this update. The existing README Test final block is preserved.

Validation: the CI-style offline command
`/home/agent/.t3/worktrees/Cheap-Drive/t3-a14884b2-9968a1fe51ca69bf/.venv/bin/python -m unittest discover -s tests`
passed **337 tests**.
