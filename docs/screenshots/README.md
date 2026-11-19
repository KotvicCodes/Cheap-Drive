# Week report previews

These screenshots show one completed ordinary level-4 practice week from the fixed-price baseline: EUR100 dealer quotes and EUR150 driver fees per car, seed `cheap-drive-review-1`. They illustrate the report, rather than competitive strategy performance.

- `week-overview.png`: overview at 1280px in the dark theme, with the provenance strip, KPIs, cumulative ledger, daily money in and out, score checkpoints, request arrival heatmap and reconciliation.
- `week-orders.png`: the requests and orders explorer with filters, per-day distribution and dense table.
- `week-history.png`: an order history drawer with facts, options, legs, linked ledger entries and day-grouped activity (cropped).
- `week-mobile.png`: the overview at 390px (cropped).

They were captured from a compact renderer copy that omits the redundant embedded original-byte attachment to fit the preview renderer's size limit; its banner says so and its original-byte download is disabled. The complete standalone report and its exact original source stay local in ignored `runs/`; no trace or full report is published here.

## Leaderboard visuals

Real final (Epsilon Prime, 43% win target), Sunday **09:00 Helsinki**,
15 November 2026; moved from 08:00, ended at 09:34:18 Helsinki:

- [final-totals.svg](final-totals.svg): top ten and our neighbours; our team highlighted, exact cents, zero-based bars. Feed retrieved 2026-11-15 07:55:28.929 UTC: **29 of 58**, **€16,760.47**, **97.61% on time**, **376 orders**. No House best entry is published for the final.
- [final-leaders.png](final-leaders.png): unaltered real public-page “The final”, ended status and leaders; captured **2026-11-15 07:58:29 UTC**.
- [final-team.png](final-team.png): unaltered real public-page rank 29 and neighbours; captured **2026-11-15 07:56:53 UTC**.
- [final-live-start.png](final-live-start.png): early live view from the start of the final, **€1,137** at **place 6, live**. Supplied by the team and stored byte-for-byte (1568 × 1092 pixels); its original file name records **09:08:08** on 15 November 2026 by the capturing machine's clock. A live snapshot, not the finishing position (29 of 58).

[Exact final figures, public JSON, model provenance and chart reproduction](../research/final-board.md).

Latest ranking round 12 (Epsilon Prime, 43% win target), level 8,
"Sunday 06:00" Helsinki, 15 November 2026:

- [round12-totals.svg](round12-totals.svg): top ten, our neighbours and House best; our team highlighted. Feed retrieved **2026-11-15 07:55:28.783 UTC**: **34 of 51**, **€69,640.20**, **97.25% on time**, **1779 orders**.
- [round12-runs.svg](round12-runs.svg): all five qualified Epsilon Prime runs versus leader Juhus on the same numbered weeks; exact cents and zero-based bars.
- [leaderboard-round12.png](leaderboard-round12.png): unaltered public-page round label, selected level 8 and leaders; captured **2026-11-15 07:58:45 UTC**.
- [leaderboard-round12-team.png](leaderboard-round12-team.png): unaltered public-page rank 34 and neighbours; captured **2026-11-15 07:57:18 UTC**.

All four new PNGs use a **1280 × 1000 CSS-pixel viewport**
(**2560 × 2000 image pixels**), scrolling only, with no data changed, rows
hidden, cropping or annotation. The page rounds euros and on-time shares.
Round 12 is still `current` in the feed, which provides no explicit closed
flag; these are its latest public standings at retrieval. Its separate page
counter, 65 of 67 teams complete, is not the ranked denominator.
[Exact round-12 results, public JSON and provenance](../research/epsilon-prime-board-round12.md).

Historical round 11 (Early Epsilon), level 8, "Sunday 03:00" Helsinki,
15 November 2026; our runs launched at 05:00 Helsinki:

- [round11-totals.svg](round11-totals.svg): top ten, our neighbours and House best, with our team highlighted; 2026-11-15 03:16:23.416 UTC, rank 28 of 44, €69,301.34, 95.85% on time.
- [round11-runs.svg](round11-runs.svg): all five Early Epsilon runs versus Seekers on the same weeks, exact cents and zero-based bars.
- [leaderboard-round11.png](leaderboard-round11.png): unaltered public-page leaders, round label and selected level 8; captured 2026-11-15 03:16:31 UTC.
- [leaderboard-round11-team.png](leaderboard-round11-team.png): unaltered public-page team row and neighbours; captured 2026-11-15 03:16:47 UTC.

PNG viewport: 1280 × 1000 CSS pixels. Scrolling only; no changed data,
hidden rows, cropping or annotation. All five runs are present and ranked.
**The round was open until 06:00 Helsinki (04:00 UTC)** at retrieval and both
captures. The later closed result was **32 of 48**, retrieved
**2026-11-15 07:55:28.783 UTC**, with the same score; the preserved images below
show the original open-round position. The page rounds euros and percentages.
[Exact results, provenance and offline chart reproduction](../research/epsilon-board-round11.md).

Historical round 9 (Delta), level 8, Saturday 21:00 Helsinki,
14 November 2026:

- [round9-totals.svg](round9-totals.svg): official-board totals; top ten, ranks 29–33 and House best, with Guardians of the Moonlight highlighted. Snapshot: 2026-11-14 21:34:23 UTC; rank 31 of 52 ranked teams, €75,763.55 and 96.72% on time.
- [round9-runs.svg](round9-runs.svg): our five qualified Delta runs versus leader Juhus, from the same snapshot. Exact cents; bars start at zero.
- [leaderboard-round9.png](leaderboard-round9.png): real public-page screenshot of the ranking-round heading, round label, selected level 8 and leading teams, captured 2026-11-14 21:35:12 UTC.
- [leaderboard-round9-team.png](leaderboard-round9-team.png): real public-page screenshot of our rank-31 row and neighbours, captured 2026-11-14 21:35:40 UTC.

Both screenshots are unaltered captures at a 1280 × 1000 CSS-pixel viewport
(2560 × 2000 image pixels), scrolled without changing data, hiding rows,
cropping or annotation. The fifth run is present and ranked. The public page
rounds margins to whole euros and on-time shares to one decimal place; the
charts retain exact cents. **The round was still open until 22:00 UTC** at
retrieval and at both captures, so positions can change and the page can update
between captures.

[Exact Delta results and snapshot details](../research/delta-board-round9.md).
[Offline chart renderer with frozen public data](../../tests/make_round9_charts.py)
(`python tests/make_round9_charts.py`, requires Matplotlib).
Rounds 9, 8 and 7 used different secret weeks, so their totals are not a paired
comparison of the models; see the [paired practice evidence](../research/delta-results.md).

Historical round 8 (Early Delta), level 8, Saturday 18:00 Helsinki, 14 November 2026:

- [round8-totals.svg](round8-totals.svg): official-board totals; top ten, ranks 35–39 and House best, with Guardians of the Moonlight highlighted. Snapshot: 2026-11-14 17:53:55 UTC; rank 37 of 58 ranked teams.
- [round8-runs.svg](round8-runs.svg): our five qualified Delta runs versus leader Juhus, from the same snapshot. Exact cents; bars start at zero.
- [leaderboard-round8.png](leaderboard-round8.png): real public-page screenshot of the round label, selected level 8 and leading teams, captured 2026-11-14 17:53:55 UTC.
- [leaderboard-round8-team.png](leaderboard-round8-team.png): real public-page screenshot of our ranked row and neighbours, captured 2026-11-14 17:53:26 UTC.

The screenshots show the original page, scrolled without changing its data or
hiding rows. The fifth run is present and ranked. The public page rounds margins
to whole euros; the charts retain exact cents. These preserve the earlier
open-round snapshot at 37 of 58, not a final round position.

[Exact Delta results and snapshot details](../research/delta-board-round8.md).
Different rounds use different secret weeks, so their totals are not a paired
model comparison.

Test final 2 (Delta via `final.py`), Saturday 20:00 Helsinki (18:00 UTC),
14 November 2026:

- [test-final-2-leaders.png](test-final-2-leaders.png): real public-page screenshot of "The final", its ended status and leading teams, captured 2026-11-14 18:41:23 UTC.
- [test-final-2-team.png](test-final-2-team.png): real public-page screenshot of Guardians of the Moonlight at rank 42 and neighbouring teams, captured 2026-11-14 18:41:39 UTC.

These screenshots show the original page at a 1280 × 1000 viewport, scrolled
without changing its data, hiding rows, cropping or annotating the captures.
The public feed retrieved at **2026-11-14 18:40:38 UTC** confirms **42 of 75
ranked teams**, **€12,816.67**, **99.61% on time**, **256 orders won**;
the page displays rounded **€12,817** and **99.6%**.
The interrupted run rebuilt its desk on simulated Saturday and won no further
orders, so it understates a clean run.
[Exact figures, public JSON and interruption details](../research/delta-test-final-2.md).

Historical round 7, level 8, Saturday 15:00 Helsinki, 14 November 2026:

- [round7-totals.svg](round7-totals.svg): generated official-board totals chart; top ten, our neighbours and House best, with Guardians of the Moonlight highlighted. Snapshot: 2026-11-14 15:05:59 UTC.
- [round7-runs.svg](round7-runs.svg): generated comparison of our five Gamma runs with leader source-exp, from the same snapshot. Exact cents; bars start at zero.
- [leaderboard-round7.png](leaderboard-round7.png): real public-page screenshot of the round label, selected level and leading teams, after all five Gamma runs; 14 November 2026, 15:07 UTC (17:07 Helsinki).
- [leaderboard-round7-team.png](leaderboard-round7-team.png): real public-page screenshot of our ranked row and neighbours, after all five Gamma runs; 14 November 2026, 15:07 UTC (17:07 Helsinki).

The screenshots show the original page, scrolled to the relevant rows, without
changing its data or hiding rows. The public page rounds margins to whole euros.
This preserves the earlier open-round snapshot; the closed round finished at
rank 41 of 62 for our team (retrieved 2026-11-14 17:53:55 UTC).
[Exact results and snapshot details](../research/gamma-board-round7.md).

Historical round 6 (Beta), retrieved 14 November 2026, 13:20:20 UTC:

- [round6-totals.svg](round6-totals.svg): top ten, ranks 42–47 and House best; our team highlighted.
- [round6-runs.svg](round6-runs.svg): our five round-6 runs versus leader Juhus.
