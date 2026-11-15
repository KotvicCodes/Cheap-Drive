"""Build docs/readme/model-ladder.svg from presentations/run-data.json.

Run from the repository root: python3 docs/readme/make_model_ladder.py
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "presentations" / "run-data.json"
OUT = ROOT / "docs" / "readme" / "model-ladder.svg"

MODELS = [  # name, glyph, colour, what changed
    ("Alpha", "α", "#F2A31B", "Formula quotes"),
    ("Beta", "β", "#EE8213", "Dealer trust and fee timing"),
    ("Gamma", "γ", "#E8590C", "Dealer notes and two-car gigs"),
    ("Delta", "δ", "#D9300F", "Capacity and a 42% win target"),
    ("Epsilon", "ε", "#7B4DF2", "On-time brakes and more volume"),
]
BAR_X, BAR_MAX, SCALE_EUR = 300, 400, 15000


def build(groups, snapshot):
    rows = []
    for i, (name, glyph, colour, what) in enumerate(MODELS):
        g = groups[name]
        margin, runs, ranked = g["mean_margin_eur"], g["runs"], g["ranked"]
        w = round(margin / SCALE_EUR * BAR_MAX)
        y = 104 + i * 50
        rows.append(f'''  <g transform="translate(0,{y})">
    <circle cx="48" cy="20" r="17" fill="{colour}"/><text x="48" y="21" class="g">{glyph}</text>
    <text x="78" y="17" class="m">{name}</text><text x="78" y="35" class="r">{what}</text>
    <rect x="{BAR_X}" y="6" width="{w}" height="28" rx="6" fill="{colour}"/>
    <text x="{BAR_X + w + 10}" y="28" class="v">€{margin / 1000:.1f}k<tspan class="r" dx="8">{runs} runs, {ranked / runs:.0%} ranked</tspan></text>
  </g>''')
    desc = "; ".join(
        f"{n} €{groups[n]['mean_margin_eur'] / 1000:.1f}k over {groups[n]['runs']} runs, "
        f"{groups[n]['ranked'] / groups[n]['runs']:.0%} ranked" for n, *_ in MODELS)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="880" height="364" viewBox="0 0 880 364" role="img" aria-labelledby="t d">
  <title id="t">Average practice gross margin per week, Alpha to Epsilon</title>
  <desc id="d">Mean gross margin per completed practice week: {desc}. Snapshot {snapshot}.</desc>
  <style>
    text {{ font-family: "Space Grotesk", -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; fill: #2a1a0a; }}
    .h {{ font-size: 22px; font-weight: 700; }}
    .s {{ font-size: 13px; fill: #7a5a35; }}
    .m {{ font-size: 17px; font-weight: 700; }}
    .v {{ font-size: 20px; font-weight: 700; }}
    .r {{ font-size: 12.5px; font-weight: 400; fill: #7a5a35; }}
    .g {{ font-size: 20px; font-weight: 700; fill: #fff; text-anchor: middle; dominant-baseline: central; }}
  </style>
  <rect width="880" height="364" rx="18" fill="#FFF4DD"/>
  <text x="32" y="46" class="h">Average practice margin per week, by model</text>
  <text x="32" y="70" class="s">Mean gross margin of every completed practice week, including exploratory variants. A week ranks at 90% on time or better.</text>
{chr(10).join(rows)}
</svg>
'''


def main():
    data = json.loads(DATA.read_text())
    at = datetime.fromisoformat(data["summary"]["snapshot_at"]).astimezone(ZoneInfo("Europe/Helsinki"))
    snapshot = at.strftime("%-d %b %Y %H:%M Helsinki")
    OUT.write_text(build(data["groups"], snapshot))
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
