# Delta: round 10 leaderboard runs

All five official level-8 ranking runs completed and qualified in round
**10, Sunday 00:00 Helsinki** (15 November 2026). Team:
**Guardians of the Moonlight** (`guardians-of-the-moonlight`). The round opened
at `2026-11-14T22:00:17.097Z` and remains open until 01:00 UTC on 15 November.

## Model and execution

Command: `python scripts/board.py models/delta.json --runs 5 --fast`.
The five weeks ran sequentially, using the committed Delta configuration and
unchanged model/runner code at
[`cae1e58b8ce3234260328f78dcf2283cd2ebced7`](https://github.com/KotvicCodes/Cheap-Drive/commit/cae1e58b8ce3234260328f78dcf2283cd2ebced7).
The configuration uses a 42% win target, wide stop windows, private-delivery
rescue and extended pairing. No model tuning occurred between ranking weeks.
`--fast` skips optional diagnostics and coalesces passive wakes; scores come
from the official server. Compressed traces, execution log and file hashes
remain private under git-ignored `runs/board/`.

## Completed runs

| Delta run | Gross margin | On time | Orders won | Ranked |
| --- | ---: | ---: | ---: | :---: |
| 1 | €15,397.99 | 96.32% | 353 | Yes |
| 2 | €13,064.94 | 95.11% | 368 | Yes |
| 3 | €12,341.81 | 95.79% | 356 | Yes |
| 4 | €17,046.58 | 96.34% | 355 | Yes |
| 5 | €14,470.71 | 98.06% | 310 | Yes |
| **Total** | **€72,322.03** | **96.27%** | **1742** | **5 / 5** |

Every week cleared the required 90% on-time threshold. The official aggregate
on-time share is `0.9626865671641791`, rather than an average of rounded
weekly percentages. Local final scores were checked against the public feed.

## Standings snapshot

Retrieved **2026-11-14 23:13:42 UTC** from the public
[`/v1/leaderboards/practice?level=8`](https://spread.bahnexpress.com/v1/leaderboards/practice?level=8)
endpoint through the [public leaderboard](https://spread.bahnexpress.com/leaderboard).
Our position is **31 of 45 ranked teams**, with
**€72,322.03** gross margin and **96.27%** on time.
Only teams with a non-null public rank count; house teams are excluded.
This is an open-round snapshot; standings can change between retrieval and captures.

| Public rank | Team | Gross margin |
| --- | --- | ---: |
| 1 | Juhus | €102,581.93 |
| 2 | Seekers | €94,577.74 |
| 3 | Edge101 | €91,567.97 |
| 4 | Team Moonshot | €89,161.43 |
| 5 | DaVinci’s Night Shift | €87,686.77 |
| 6 | Upsala | €82,689.63 |
| 7 | blip_blip_2 | €81,840.13 |
| 8 | Halal Team | €81,046.16 |
| 9 | ppo | €80,864.79 |
| 10 | AppleJuice | €80,862.35 |
| 29 | bahn67 | €72,622.91 |
| 30 | monkey | €72,339.77 |
| 31 | Guardians of the Moonlight | €72,322.03 |
| 32 | Odyssey | €70,583.51 |
| 33 | EasyMoney | €69,204.62 |
| — | House best | €60,811.68 |

Round 9's closed result is **34 of 56 ranked teams**,
with €75,763.55 and 96.72% on time.
[The earlier round-9 report](delta-board-round9.md) retains its dated open-round snapshot.
Different rounds use different secret weeks, so totals do not form a paired
model comparison; see [paired practice evidence](delta-results.md).

## Evidence and reproduction

- [Leaders](../screenshots/leaderboard-round10.png): captured **2026-11-14 23:14:25 UTC**; ranking heading, round label, selected level 8 and leading teams.
- [Our row](../screenshots/leaderboard-round10-team.png): captured **2026-11-14 23:14:11 UTC**; all five weeks present and ranked, with neighbouring teams.
- [Totals](../screenshots/round10-totals.svg): top ten, our neighbours and House best.
- [Runs](../screenshots/round10-runs.svg): Delta versus Juhus on the same five secret weeks, with zero-based bars.
- [Offline chart renderer](../../tests/make_round10_charts.py): frozen exact-cent public data; run `python tests/make_round10_charts.py` with Matplotlib installed.

Screenshots are unaltered captures of the original public page at a
1280 × 1000 CSS-pixel viewport (2560 × 2000 image pixels), scrolled to the relevant rows. No data was
changed, no rows were hidden, and captures were not cropped or annotated.
The page rounds margins to whole euros and on-time percentages to one decimal;
the charts and tables retain exact cents. The run traces and credentials are
not published.

Validation: **387 offline tests passed** for the run revision. Each local final
score and qualification was reconciled with its public run result.
