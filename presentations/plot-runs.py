"""Regenerate the presentation's all-run chart from its frozen run-data.json.

Requires Matplotlib. No simulator, network or raw trace files are needed.
"""
from pathlib import Path
import hashlib
import json
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.ticker import FuncFormatter

root = Path(__file__).resolve().parent
data = json.loads((root / 'run-data.json').read_text())
runs = data['runs']
groups = list(data['groups'])
assert len(runs) == data['summary']['completed_practice']
assert len({r['world_id'] for r in runs}) == len(runs)
plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 11,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.edgecolor': '#cbd5e1', 'axes.labelcolor': '#334155',
    'text.color': '#0f172a', 'xtick.color': '#475569',
    'ytick.color': '#475569', 'figure.facecolor': 'white',
    'axes.facecolor': 'white', 'savefig.facecolor': 'white',
})
dpi = 190
fig, ax = plt.subplots(figsize=(13.8, 7.6))
fig.subplots_adjust(left=.09, right=.98, top=.97, bottom=.20)
for i, group in enumerate(groups):
    rows = [r for r in runs if r['chart_group'] == group]
    assert len(rows) == data['groups'][group]['runs']
    if i % 2 == 0:
        ax.axvspan(i - .48, i + .48, color='#f1f5f9', zorder=0)
    for ranked, color, marker in [(True, '#2563eb', 'o'), (False, '#dc2626', 'x')]:
        points = [
            (i + ((int(hashlib.sha256(r['world_id'].encode()).hexdigest()[:8], 16) % 10000) / 10000 - .5) * .73,
             r['score']['marginCents'] / 100)
            for r in rows if bool(r['score']['ranked']) == ranked
        ]
        if points:
            ax.scatter(*zip(*points), s=14, alpha=.55, color=color,
                       marker=marker, rasterized=True, zorder=3)
    mean = statistics.mean(r['score']['marginCents'] for r in rows) / 100
    assert abs(mean - data['groups'][group]['mean_margin_eur']) < 1e-8
    # Same black cross dimensions as the previous 2,622px chart: 48px long, 5px thick.
    ax.plot(i, mean, marker='+', color='#000000', linestyle='None',
            markersize=48 * 72 / dpi, markeredgewidth=5 * 72 / dpi, zorder=5)
ax.set_xticks(range(len(groups)), [g.replace(' ', '\n') + f"\n{data['groups'][g]['runs']} runs" for g in groups], fontsize=11)
ax.tick_params(axis='x', length=0, pad=9)
ax.set_xlim(-.55, len(groups) - .45)
ax.set_ylabel('Gross margin per simulated week')
ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'€{x / 1000:.0f}k'))
ax.grid(axis='y', alpha=.2)
ax.axhline(0, color='#64748b', lw=.8)
fig.legend(handles=[
    Line2D([], [], color='#2563eb', marker='o', linestyle='None', markersize=8, label='qualified'),
    Line2D([], [], color='#dc2626', marker='x', linestyle='None', markersize=9, markeredgewidth=1.8, label='disqualified'),
    Line2D([], [], color='#000000', marker='+', linestyle='None', markersize=48 * 72 / dpi,
           markeredgewidth=5 * 72 / dpi, label='average'),
], loc='lower center', bbox_to_anchor=(.5, .025), ncol=3, frameon=False,
   fontsize=14, handletextpad=.5, columnspacing=2.5)
assert all('—' not in t.get_text() for t in fig.findobj(match=Text))
for ext in ('png', 'pdf'):
    fig.savefig(root / f'all-run-margins.{ext}', dpi=dpi)
plt.close(fig)
print(f"Plotted {len(runs):,} unique completed practice runs across {len(groups)} groups")
