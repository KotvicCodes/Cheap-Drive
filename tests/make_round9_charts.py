"""Rebuild round-9 charts from the frozen public snapshot, without network access.

Requires Matplotlib. Run from any directory: python tests/make_round9_charts.py
Data: https://spread.bahnexpress.com/v1/leaderboards/practice?level=8
Retrieved 2026-11-14 21:34:23 UTC; round 9 was still open until 22:00 UTC.
Style follows the existing round-8 Matplotlib SVGs.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator

OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
STAMP = "2026-11-14 21:34:23 UTC"
RANK = 31
RANKED_TEAMS = 52
# Public rank (None for house), public name, exact margin in cents.
TOTALS = [
    (1, "Juhus", 10542426),
    (2, "MathNet1", 9684968),
    (3, "source-exp", 9429850),
    (4, "No Empty Miles", 9226671),
    (5, "Team Moonshot", 8931690),
    (6, "eth", 8872889),
    (7, "akanegakirru", 8672961),
    (8, "ppo", 8656008),
    (9, "klmisbest", 8620140),
    (10, "pelaaja juhlii", 8485664),
    (29, "The Delusionals", 7724549),
    (30, "katalyst", 7616901),
    (31, "Guardians of the Moonlight", 7576355),
    (32, "Test-Team1114", 7305642),
    (33, "monkey", 7216905),
    (None, "House best", 6613559),
]
# Run number, exact margin in cents, public on-time share, orders won.
# All ten runs below are ranked in the public response.
OUR_RUNS = [
    (1, 1376761, 0.9798850574712644, 348),
    (2, 1638265, 0.9358288770053476, 374),
    (3, 1390672, 0.9546742209631728, 353),
    (4, 1805750, 0.983957219251337, 374),
    (5, 1364907, 0.9828080229226361, 349),
]
LEADER_RUNS = [
    (1, 1909644, 0.9897330595482546, 487),
    (2, 2379188, 0.9613034623217923, 491),
    (3, 2073131, 0.9739696312364425, 461),
    (4, 2452927, 0.9303675048355899, 517),
    (5, 1727536, 0.980561555075594, 463),
]
BLUE, GREY, HOUSE, INK = "#1461b8", "#62758a", "#a85d00", "#172b40"


def style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 10,
        "svg.fonttype": "none",
        "svg.hashsalt": "cheap-drive-round9",
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
    fig.text(0.025, 0.956, "Round 9: Delta on the official leaderboard",
             fontsize=17, fontweight="bold")
    fig.text(0.025, 0.925,
             f"Level 8 · Saturday 21:00 · rank {RANK} of {RANKED_TEAMS} · {STAMP} · round open")
    fig.savefig(OUT / "round9-totals.svg", metadata={
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
    fig.text(0.025, 0.956, "Round 9: our five runs versus the leader",
             fontsize=17, fontweight="bold")
    fig.text(0.025, 0.91,
             f"Level 8 · Saturday 21:00 · all five candidate runs qualified · {STAMP} · round open")
    fig.savefig(OUT / "round9-runs.svg", metadata={
        "Date": None,
        "Description": "Paired secret-week margins from the official round-9 leaderboard. "
                       "Both teams ranked on all five weeks; bars start at zero.",
    })
    plt.close(fig)


if __name__ == "__main__":
    style()
    totals_chart()
    runs_chart()
    # Matplotlib emits trailing spaces in SVG paths; keep generated diffs clean.
    for name in ("round9-totals.svg", "round9-runs.svg"):
        path = OUT / name
        path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
