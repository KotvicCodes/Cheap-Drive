# Early Epsilon: round 11 leaderboard runs

All five official level-8 ranking runs completed in round **11, "Sunday 03:00"
(Helsinki, 15 November 2026)**. Team: **Guardians of the Moonlight**
(`guardians-of-the-moonlight`). The public feed says the round opened at
`2026-11-15T01:00:17.088Z` (03:00 Helsinki). Our controller launched at
**03:00 UTC / 05:00 Helsinki**; that launch time is distinct from the round label.

The model was [Early Epsilon](../../models/epsilon-early.json): Delta with
`premium_min_slack_minutes: 1440`. The controller's saved selection records
commit [`1dc923ae5de11e1d004e012c43299d18b1910869`](https://github.com/KotvicCodes/Cheap-Drive/commit/1dc923ae5de11e1d004e012c43299d18b1910869)
and selection time `2026-11-15T03:00:00.010571+00:00`.
The traces normalize the factory to the compatible `delta:make_delta` alias.
The frozen model and per-run trace headers identify the settings; the public
feed verifies results and qualification, not code provenance.

## Completed runs

| Early Epsilon run | Gross margin | On time | Orders won | Ranked |
| --- | ---: | ---: | ---: | :---: |
| 1 | €13,985.11 | 96.45% | 310 | Yes |
| 2 | €12,122.31 | 97.12% | 313 | Yes |
| 3 | €9,229.95 | 93.63% | 314 | Yes |
| 4 | €19,254.35 | 95.77% | 378 | Yes |
| 5 | €14,709.62 | 96.28% | 349 | Yes |
| **Total** | **€69,301.34** | **95.85%** | **1664** | **5 / 5** |

Exact-cent margins and on-time shares come from the official public feed.
The total on-time share is the board's aggregate (`0.9585336538461539`),
not an average of the rounded weekly percentages. Every run qualified under
the 90% requirement; the lowest on-time share was
**93.63%**.

## Standings snapshot

Retrieved **2026-11-15 03:16:23.416 UTC** (`2026-11-15T03:16:23.416Z`), **2026-11-15 05:16:23 Helsinki**,
from the public [`/v1/leaderboards/practice?level=8`](https://spread.bahnexpress.com/v1/leaderboards/practice?level=8)
endpoint through [the public leaderboard](https://spread.bahnexpress.com/leaderboard).

Our rank: **28 of 44 ranked teams**, **€69,301.34**,
**95.85% on time**. Only teams with a non-null public rank count;
house teams and unqualified teams are excluded. The page's completion counter
is a separate measure.

Leader **Seekers**: **€85,282.54**.
Tenth place **Upsala**: **€76,872.81**, **€7,571.47 ahead of us**.
Seventh place **iliada**: **€77,655.64**, **€8,354.30 ahead of us**.
Organisers' **House best**: **€56,128.21**, with no public rank.

| Public rank | Team | Gross margin |
| --- | --- | ---: |
| 1 | Seekers | €85,282.54 |
| 2 | No Empty Miles | €83,523.97 |
| 3 | blip_blip_2 | €83,341.93 |
| 4 | klmisbest | €79,277.21 |
| 5 | Elysa's Secret | €78,843.25 |
| 6 | HackandSeek | €78,160.61 |
| 7 | iliada | €77,655.64 |
| 8 | Granmamas Belotas | €77,119.38 |
| 9 | eth | €76,884.39 |
| 10 | Upsala | €76,872.81 |
| 26 | pfjfjfjfj | €69,800.12 |
| 27 | Odyssey | €69,786.13 |
| 28 | Guardians of the Moonlight | €69,301.34 |
| 29 | Bob the builders | €69,138.44 |
| 30 | katalyst | €68,867.01 |
| — | House best | €56,128.21 |

The run chart compares the same numbered secret weeks within round 11:

| Run | Early Epsilon | Seekers |
| --- | ---: | ---: |
| 1 | €13,985.11 | €18,155.55 |
| 2 | €12,122.31 | €15,592.58 |
| 3 | €9,229.95 | €12,520.34 |
| 4 | €19,254.35 | €20,920.32 |
| 5 | €14,709.62 | €18,093.75 |
| **Total** | **€69,301.34** | **€85,282.54** |

**The round was still open at retrieval and both screenshot captures, until
04:00 UTC / 06:00 Helsinki. Positions can change.** The board may update between
retrieval and screenshots. The public page rounds margins to whole euros and
on-time shares to one decimal place; charts retain exact cents.

## Previous rounds

**Delta**, round 10 ("Sunday 00:00", 15 November, Helsinki), finished
**38th of 58 ranked teams**, **€72,322.03**, **96.27% on time**, all five qualified.
Saved provenance and all five trace headers confirm `models/delta.json`,
`premium_min_slack_minutes: 600`, at
[`cae1e58`](https://github.com/KotvicCodes/Cheap-Drive/commit/cae1e58b8ce3234260328f78dcf2283cd2ebced7).

**Delta**, round 9 ("Saturday 21:00", 14 November), was **31st of 52**,
€75,763.55, 96.72% on time at its open-round snapshot (2026-11-14 21:34:23 UTC).
[Round-9 evidence](delta-board-round9.md).
**Early Delta**, round 8 ("Saturday 18:00"), was **37th of 58**,
€55,639.62, 96.96% on time at its open-round snapshot (2026-11-14 17:53:55 UTC).
[Round-8 evidence](delta-board-round8.md).
**Gamma** finished round 7 ("Saturday 15:00") **41st of 62**,
€66,880.48, 96.75% on time, all five qualified.
[Round-7 evidence](gamma-board-round7.md).
Different rounds use different secret weeks; their totals are not a paired
model comparison. See [paired Delta evidence](delta-results.md).

## Evidence and reproduction

- [Round totals](../screenshots/round11-totals.svg): top ten, our two neighbours on either side and House best.
- [Five runs versus Seekers](../screenshots/round11-runs.svg): same numbered weeks, zero-based bars.
- [Public-page leaders](../screenshots/leaderboard-round11.png): round label, level 8 and leaders; captured **2026-11-15 03:16:31 UTC**.
- [Our public-page row](../screenshots/leaderboard-round11-team.png): our rank and neighbours; captured **2026-11-15 03:16:47 UTC**.

Both PNGs are unaltered captures of the real public page at a **1280 × 1000
CSS-pixel viewport**, scrolled to the relevant rows. No data was changed, no
rows were hidden, and images were not cropped or annotated. Charts follow
[round 9's renderer](../../tests/make_round9_charts.py): typography, colours,
horizontal bars, exact-cent labels and axes starting at zero.

Local provenance (git-ignored): `runs/epsilon/ranking-0300/selection.json`,
`model.json`, `runs.jsonl`, `run1.log` through `run5.log`, and the five
`runs/board/20261115T03*-level8-*.jsonl.gz` traces in this worktree.
The read-only `client.worlds()` poll checked season 11's `boardRun` 1–5
and confirmed all five had `ended: true` at **2026-11-15 03:15:56 UTC**,
before the 04:10 UTC deadline.

Season-10 provenance is saved in the sibling worktree
`t3-4916049f-a8478bb92720e2dc` under `runs/board/round10-provenance.json`,
`round10.log` and the five dated gzip traces. All eight recorded file SHA-256
hashes were checked against commit `cae1e58b8ce3234260328f78dcf2283cd2ebced7`
and matched. Each trace's `run` record names Delta and 600-minute premium
slack; `client.worlds()` maps those five world IDs to season 10.
The closed-round figures above come from the same public retrieval's `previous` data.

This documentation task read the team world list, saved files, the public
page and public JSON. It created no game worlds or runs and did not alter
existing running processes. The README Test final block is preserved.

### Rebuild the charts offline

From the repository root, with Matplotlib installed, run this Python snippet.
It reuses the round-9 renderer with the frozen inputs below and writes only the
two round-11 SVGs.

```python
from pathlib import Path

path = Path("tests/make_round9_charts.py").resolve()
source = path.read_text()
for old, new in [
    ('round9', 'round11'), ('round-9', 'round-11'), ('Round 9', 'Round 11'),
    ('Saturday 21:00', 'Sunday 03:00'), ('Delta', 'Early Epsilon'),
    ('Juhus', 'Seekers'), ('#31', '#28'),
]:
    source = source.replace(old, new)
values = {'STAMP': '2026-11-15 03:16:23.416 UTC',
 'RANK': 28,
 'RANKED_TEAMS': 44,
 'TOTALS': [(1, 'Seekers', 8528254),
            (2, 'No Empty Miles', 8352397),
            (3, 'blip_blip_2', 8334193),
            (4, 'klmisbest', 7927721),
            (5, "Elysa's Secret", 7884325),
            (6, 'HackandSeek', 7816061),
            (7, 'iliada', 7765564),
            (8, 'Granmamas Belotas', 7711938),
            (9, 'eth', 7688439),
            (10, 'Upsala', 7687281),
            (26, 'pfjfjfjfj', 6980012),
            (27, 'Odyssey', 6978613),
            (28, 'Guardians of the Moonlight', 6930134),
            (29, 'Bob the builders', 6913844),
            (30, 'katalyst', 6886701),
            (None, 'House best', 5612821)],
 'OUR_RUNS': [(1, 1398511, 0.964516129032258, 310),
              (2, 1212231, 0.9712460063897763, 313),
              (3, 922995, 0.9363057324840764, 314),
              (4, 1925435, 0.9576719576719577, 378),
              (5, 1470962, 0.9627507163323782, 349)],
 'LEADER_RUNS': [(1, 1815555, 0.9722863741339491, 433),
                 (2, 1559258, 0.9811827956989247, 372),
                 (3, 1252034, 0.9792899408284024, 338),
                 (4, 2092032, 0.952808988764045, 445),
                 (5, 1809375, 0.9619952494061758, 421)]}
start = source.index("STAMP = ")
end = source.index("BLUE, GREY, HOUSE, INK = ")
source = source[:start] + "".join(
    f"{key} = {value!r}\n" for key, value in values.items()
) + source[end:]
source = source.replace("frameon=False, ncol=2, fontsize=9",
                        "frameon=False, ncol=1, fontsize=9")
source = source.replace("all five candidate runs qualified", "all five runs qualified")
exec(compile(source, str(path), "exec"), {"__file__": str(path), "__name__": "__main__"})
```

Validation: all five public rows match the saved controller receipts; trace
model names and settings match the frozen model. SVGs parse, screenshot bytes
match the original captures, and relative documentation links resolve. The
chart reproduction snippet regenerates identical SVG bytes.
