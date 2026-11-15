# Week report previews

These screenshots show one completed ordinary level-4 practice week from the fixed-price baseline: EUR100 dealer quotes and EUR150 driver fees per car, seed `cheap-drive-review-1`. They illustrate the report, rather than competitive strategy performance.

- `week-overview.png`: overview at 1280px in the dark theme, with the provenance strip, KPIs, cumulative ledger, daily money in and out, score checkpoints, request arrival heatmap and reconciliation.
- `week-orders.png`: the requests and orders explorer with filters, per-day distribution and dense table.
- `week-history.png`: an order history drawer with facts, options, legs, linked ledger entries and day-grouped activity (cropped).
- `week-mobile.png`: the overview at 390px (cropped).

They were captured from a compact renderer copy that omits the redundant embedded original-byte attachment to fit the preview renderer's size limit; its banner says so and its original-byte download is disabled. The complete standalone report and its exact original source stay local in ignored `runs/`; no trace or full report is published here.

## Leaderboard visuals

Current round 10 (Delta), level 8, Sunday 00:00 Helsinki,
15 November 2026:

- [round10-totals.svg](round10-totals.svg): top ten, our neighbours and House best; 2026-11-14 23:13:42 UTC, rank 31 of 45, €72,322.03, 96.27% on time.
- [round10-runs.svg](round10-runs.svg): our five qualified Delta weeks versus leader Juhus, same snapshot; exact cents and zero-based bars.
- [leaderboard-round10.png](leaderboard-round10.png): original public-page ranking heading, round label, selected level 8 and leaders; 2026-11-14 23:14:25 UTC.
- [leaderboard-round10-team.png](leaderboard-round10-team.png): our ranked row and neighbours after all five weeks; 2026-11-14 23:14:11 UTC.

Both PNGs are unaltered public-page captures at a 1280 × 1000 CSS-pixel viewport
(2560 × 2000 image pixels),
scrolled without changing data, hiding rows, cropping or annotation.
The round was open until 01:00 UTC on 15 November; standings can change.
The page rounds margins to whole euros and shares to one decimal place.
[Exact results and provenance](../research/delta-board-round10.md) ·
[Offline chart renderer](../../tests/make_round10_charts.py) (Matplotlib required).

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
