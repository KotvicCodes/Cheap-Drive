"""Rebuild round-10 charts from the frozen public snapshot, without network access.

Requires Matplotlib. Run from any directory: python tests/make_round10_charts.py
Data: https://spread.bahnexpress.com/v1/leaderboards/practice?level=8
Retrieved 2026-11-14 23:13:42 UTC; round 10 was still open until 01:00 UTC on 15 November.
Style follows the existing round-8 Matplotlib SVGs.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
STAMP = "2026-11-14 23:13:42 UTC"
RANK = 31
RANKED_TEAMS = 45
# Public rank (None for house), public name, exact margin in cents.
TOTALS = [
    (1, 'Juhus', 10258193),
    (2, 'Seekers', 9457774),
    (3, 'Edge101', 9156797),
    (4, 'Team Moonshot', 8916143),
    (5, 'DaVinci’s Night Shift', 8768677),
    (6, 'Upsala', 8268963),
    (7, 'blip_blip_2', 8184013),
    (8, 'Halal Team', 8104616),
    (9, 'ppo', 8086479),
    (10, 'AppleJuice', 8086235),
    (29, 'bahn67', 7262291),
    (30, 'monkey', 7233977),
    (31, 'Guardians of the Moonlight', 7232203),
    (32, 'Odyssey', 7058351),
    (33, 'EasyMoney', 6920462),
    (None, 'House best', 6081168),
]
OUR_RUNS = [
    (1, 1539799, 0.9631728045325779, 353),
    (2, 1306494, 0.9510869565217391, 368),
    (3, 1234181, 0.9578651685393258, 356),
    (4, 1704658, 0.9633802816901409, 355),
    (5, 1447071, 0.9806451612903225, 310),
]
LEADER_RUNS = [
    (1, 2027584, 0.9670781893004116, 486),
    (2, 2085270, 0.9830866807610994, 473),
    (3, 1889766, 0.9757709251101322, 454),
    (4, 2308744, 0.9678068410462777, 497),
    (5, 1946829, 0.9715536105032823, 457),
]
BLUE, GREY, HOUSE, INK = "#1461b8", "#62758a", "#a85d00", "#172b40"


def style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 10,
        "svg.fonttype": "none",
        "svg.hashsalt": "cheap-drive-round10",
        "text.color": INK,
        "axes.labelcolor": INK,
        "axes.edgecolor": "#d9e1e8",
        "xtick.color": INK,
        "ytick.color": INK,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
    })


def axes_style(ax):
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#e5eaf0", linewidth=0.8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=8)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"€{value:,.0f}"))


def totals_chart():
    rows = sorted(TOTALS, key=lambda row: row[2], reverse=True)
    fig, ax = plt.subplots(figsize=(11, 7.46))
    fig.subplots_adjust(left=0.32, right=0.99, bottom=0.12, top=0.87)
    positions = list(range(len(rows)))
    us = next(i for i, row in enumerate(rows) if row[0] == RANK)
    ax.axhspan(us - 0.48, us + 0.48, color="#e8f2ff", zorder=0)
    bars = ax.barh(
        positions, [row[2] / 100 for row in rows], height=0.64,
        color=[BLUE if row[0] == RANK else HOUSE if row[0] is None else GREY
               for row in rows],
    )
    ax.set_yticks(positions, [f"{rank if rank is not None else '—'}  {name}"
                              for rank, name, _ in rows])
    ax.get_yticklabels()[us].set_fontweight("bold")
    ax.invert_yaxis()
    ax.set_xlim(0, max(row[2] for row in rows) / 100 * 1.19)
    ax.set_xticks(range(0, max(row[2] for row in rows) // 100 + 1, 25000))
    ax.set_xlabel("Total gross margin across five secret weeks")
    axes_style(ax)
    ax.bar_label(bars, labels=[f"€{row[2] / 100:,.2f}" for row in rows],
                 padding=5, fontsize=9)
    fig.text(0.025, 0.956, "Round 10: Delta on the official leaderboard",
             fontsize=17, fontweight="bold")
    fig.text(0.025, 0.925,
             f"Level 8 · Sunday 00:00 · rank {RANK} of {RANKED_TEAMS} · {STAMP} · round open")
    fig.savefig(OUT / "round10-totals.svg", metadata={
        "Date": None,
        "Description": "Official leaderboard snapshot; top ten, our neighbours and House best. "
                       "House teams have no rank. Round still open at retrieval.",
    })
    plt.close(fig)


def runs_chart():
    fig, ax = plt.subplots(figsize=(11, 5.4))
    fig.subplots_adjust(left=0.24, right=0.99, bottom=0.12, top=0.79)
    positions = list(range(5))
    for runs, offset, color, label in (
        (OUR_RUNS, -0.19, BLUE, "Delta / Guardians of the Moonlight (#31)"),
        (LEADER_RUNS, 0.19, GREY, "Juhus (#1)"),
    ):
        bars = ax.barh([i + offset for i in positions],
                       [row[1] / 100 for row in runs], height=0.32,
                       color=color, label=label)
        ax.bar_label(bars, labels=[f"€{row[1] / 100:,.2f}" for row in runs],
                     padding=5, fontsize=9)
    ax.set_yticks(positions, [f"Run {run}\nDelta {share:.1%} on time"
                              for run, _, share, _ in OUR_RUNS])
    ax.invert_yaxis()
    ax.set_xlim(0, max(row[1] for row in LEADER_RUNS + OUR_RUNS) / 100 * 1.19)
    ax.xaxis.set_major_locator(MultipleLocator(5000))
    ax.set_xlabel("Gross margin per secret week")
    axes_style(ax)
    fig.legend(loc="upper left", bbox_to_anchor=(0.025, 0.855),
               frameon=False, ncol=2, fontsize=9)
    fig.text(0.025, 0.956, "Round 10: our five runs versus the leader",
             fontsize=17, fontweight="bold")
    fig.text(0.025, 0.91,
             f"Level 8 · Sunday 00:00 · all five Delta runs qualified · {STAMP} · round open")
    fig.savefig(OUT / "round10-runs.svg", metadata={
        "Date": None,
        "Description": "Paired secret-week margins from the official round-10 leaderboard. "
                       "Both teams ranked on all five weeks; bars start at zero.",
    })
    plt.close(fig)


if __name__ == "__main__":
    style()
    totals_chart()
    runs_chart()
    # Matplotlib emits trailing spaces in SVG paths; keep generated diffs clean.
    for name in ("round10-totals.svg", "round10-runs.svg"):
        path = OUT / name
        path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
