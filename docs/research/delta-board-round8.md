# Delta: round 8 leaderboard runs

All five official level-8 ranking runs are present and ranked on the public
leaderboard in round **8, Saturday 18:00 Helsinki** (14 November 2026).
The public endpoint confirms the round opened at `2026-11-14T16:00:17.085Z`.
Team: **Guardians of the Moonlight** (`guardians-of-the-moonlight`).
Model: [Delta](../../models/delta.json).

## Completed runs

| Delta run | Gross margin | On time | Orders won | Ranked |
| --- | ---: | ---: | ---: | :---: |
| 1 | €11,250.74 | 95.90% | 244 | Yes |
| 2 | €14,659.69 | 98.07% | 259 | Yes |
| 3 | €11,197.75 | 96.75% | 246 | Yes |
| 4 | €8,822.73 | 96.50% | 257 | Yes |
| 5 | €9,708.71 | 97.52% | 242 | Yes |
| **Total** | **€55,639.62** | **96.96%** | **1248** | **5 / 5** |

The fifth run is present: €9,708.71, 97.52% on time, ranked.
The total on-time share is the official board aggregate, not an average of the
rounded weekly percentages. Qualification is checked separately for every week;
all five exceeded the required 90%.

## Standings snapshot

Retrieved **2026-11-14 17:53:55 UTC** from the public
[`/v1/leaderboards/practice?level=8`](https://spread.bahnexpress.com/v1/leaderboards/practice?level=8)
endpoint, with the page at [the public leaderboard](https://spread.bahnexpress.com/leaderboard).

Our rank: **37 of 58 ranked teams**, **€55,639.62**, **96.96% on time**.
The count includes only teams with a non-null public rank, excluding house teams
and teams that did not qualify.

Leader **Juhus**: €94,444.61; tenth place:
**hakunamaTATA**, €73,352.77 (we are €17,713.15 behind).
Organisers' **House best**: €58,677.10.
House teams have no public rank and are excluded from the ranked-team count.

This is a snapshot of the current round, not a final round position. Charts retain
exact cents; the original page rounds margins to whole euros and on-time shares
to one decimal place. Screenshots were captured on 14 November 2026 at
**17:53:55 UTC** (leaders) and **17:53:26 UTC** (our row), or 19:53:55 and
19:53:26 Helsinki. The board can update between retrieval and screenshots.

The same response's previous-round data records Gamma's closed round 7,
Saturday 15:00: **41st of 62**, **€66,880.48**, **96.75% on time**, all five qualified.
The [earlier round-7 note](gamma-board-round7.md) preserves its earlier open-round
snapshot. Different ranking rounds use different secret weeks; their totals
are not a paired model comparison.

## Test final

At **2026-11-14 17:53:35 UTC**, the public final feed was **scheduled** for
`2026-11-14T18:00:00.000Z` (20:00 Helsinki), with no teams displayed.
The test final had not started: our team, margin, on-time share and rank were
not yet present, so there is no final-result screenshot.

This status came from the page's public, read-only `/v1/leaderboard` event stream.
No game worlds, ranking runs or finals were created, advanced, deleted or played
for this update, and no team API key was used.

## Evidence

- [Round totals](../screenshots/round8-totals.svg): top ten, our neighbours and House best.
- [Five runs versus Juhus](../screenshots/round8-runs.svg): same numbered secret weeks within this round, zero-based bars.
- [Public-page leaders](../screenshots/leaderboard-round8.png): round label and selected level 8.
- [Our public-page row](../screenshots/leaderboard-round8-team.png): our row and neighbours.

The charts reuse the round-7 Matplotlib renderer and its typography, colours,
exact-cent labels and zero-based axes, with round-8 public data. The screenshots
show the real page scrolled to the relevant rows; no data was changed and no
rows were hidden.
