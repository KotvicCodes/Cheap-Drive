#!/usr/bin/env python3
"""Deterministic 60-second motion film. No simulator or network requests."""
from __future__ import annotations
import argparse, csv, json, math, subprocess, wave
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUT = REPO / 'runs/demo-video'
W, H, FPS, DURATION = 1920, 1080, 30, 60

# Juicy yellow-orange, golden marigold, and sunlit citrus palette (zero brown/taupe/umber).
INK = '#141416'          # Crisp neutral carbon ink for typography & vehicle silhouettes
MUTED_INK = '#4A3B2C'    # Warm charcoal-ochre for secondary labels
ORANGE = '#FF6200'       # Vibrant juicy tangerine orange (primary hero & bar accent)
MANGO = '#FF9500'        # Rich yellow-orange / mango
MARIGOLD = '#FFB700'     # Golden yellow-orange highlight
SUNBURST = '#FFD000'     # Bright citrus yellow-gold accent

CREAM = '#FFF8EB'        # Sunlit citrus cream background
CARD = '#FFFDF8'         # Crisp warm white-cream card surface
APRICOT = '#FFEAB8'      # Soft golden-apricot panel fill
GOLD_TRACK = '#FFD98A'   # Golden track fill for unloaded bar slots
GOLD_LINE = '#FFBE4F'    # Golden-orange structural border on cream scenes
DANGER = '#E5383B'       # Crisp crimson for failed qualification / deadline warnings

SCENES = [
    (0, 6),
    (6, 15),
    (15, 22),
    (22, 30),
    (30, 38),
    (38, 47),
    (47, 54),
    (54, 60),
]

GRAPH = json.loads((ROOT / 'data/graph-data.json').read_text())
CHART_DATA = json.loads((ROOT / 'data/chart-data.json').read_text())
PAIRED_WEEKS = list(csv.DictReader((ROOT / 'data/paired-weeks.csv').open()))
CONFIRM_WEEKS = [r for r in PAIRED_WEEKS if r['comparison'] == 'Revised candidate: fresh confirmation']
OFFICIAL_ROUNDS = list(csv.DictReader((ROOT / 'data/official-rounds.csv').open()))
OFFICIAL_RUNS = [r for r in GRAPH['runs'] if r['family'] == 'Official ranking']
ROUND5_RUNS = OFFICIAL_RUNS[:5]
ROUND6_RUNS = OFFICIAL_RUNS[5:10]
PAIRED_OLD = list(csv.DictReader((ROOT / 'data/per-seed-comparisons.csv').open()))

CHART_ALL = Image.open(ROOT / 'assets/all-run-margins.png').convert('RGB')
CHART_STAGES = Image.open(ROOT / 'assets/learning-stages.png').convert('RGB')
REPORT = Image.open(REPO / 'docs/screenshots/week-overview.png').convert('RGB')


def clamp(x, a=0, b=1): return max(a, min(b, x))
def ease(x): return 1 - (1 - clamp(x)) ** 3
def smooth(x): x = clamp(x); return x * x * (3 - 2 * x)
def mix(a, b, p): return a + (b - a) * p


@lru_cache(maxsize=6)
def base_canvas(kind='juicy'):
    """Precomputed high-chroma yellow-orange & sunlit golden canvases (no brown)."""
    if kind == 'chart':
        return Image.new('RGB', (W, H), CREAM)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    if kind == 'juicy':
        g1 = np.exp(-(((xx - 1320) / 820) ** 2 + ((yy - 440) / 580) ** 2))
        g2 = np.exp(-(((xx - 280) / 700) ** 2 + ((yy - 220) / 520) ** 2))
        r = np.full_like(xx, 255.0)
        g = 124 + 54 * g1 + 32 * g2
        b = 8 + 18 * g1 + 10 * g2
    elif kind == 'sunburst':
        g1 = np.exp(-(((xx - 960) / 950) ** 2 + ((yy - 360) / 620) ** 2))
        r = np.full_like(xx, 255.0)
        g = 228 + 18 * g1
        b = 168 + 46 * g1
    else:
        g1 = np.exp(-(((xx - 1380) / 780) ** 2 + ((yy - 500) / 560) ** 2))
        r = np.full_like(xx, 255.0)
        g = 248 - 10 * g1
        b = 235 - 38 * g1
    arr = np.clip(np.stack([r, g, b], axis=-1), 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode='RGB')


@lru_cache(maxsize=150)
def font(size, weight=500, mono=False):
    f = ImageFont.truetype(str(ROOT / 'assets' / ('IBMPlexMono.ttf' if mono else 'SpaceGrotesk.ttf')), int(size))
    if not mono:
        f.set_variation_by_axes([weight])
    return f


def txt(im, text, x, y, size=32, color=INK, weight=500, mono=False, anchor=None):
    ImageDraw.Draw(im).text((round(x), round(y)), str(text), font=font(size, weight, mono), fill=color, anchor=anchor, stroke_width=0)


def line(im, pts, fill=GOLD_LINE, width=2):
    ImageDraw.Draw(im).line([(round(x), round(y)) for x, y in pts], fill=fill, width=width, joint='curve')


def rect(im, box, fill, outline=None, r=0, width=1):
    d = ImageDraw.Draw(im)
    box = tuple(round(n) for n in box)
    if box[2] <= box[0] or box[3] <= box[1]:
        return
    if r:
        d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)
    else:
        d.rectangle(box, fill=fill, outline=outline, width=width)


def circle(im, x, y, r, fill, outline=None, width=1):
    ImageDraw.Draw(im).ellipse((round(x - r), round(y - r), round(x + r), round(y + r)), fill=fill, outline=outline, width=width)


def badge(im, text, x, y, color=INK, bg=MARIGOLD, border=None, size=22, mono=False, weight=650):
    b = font(size, weight, mono).getbbox(text)
    w = b[2] + 36
    rect(im, (x, y, x + w, y + 46), bg, outline=border, r=10, width=2 if border else 0)
    txt(im, text, x + 18, y + 9, size, color, weight=weight, mono=mono)
    return w


def enter(im, text, x, y, size, t, delay=0, color=INK, weight=600, mono=False, span=0.40):
    p = ease((t - delay) / span)
    if p <= 0:
        return
    layer = Image.new('RGBA', (W, H))
    txt(layer, text, x, y + (1 - p) * 28, size, color, weight, mono)
    if p < 1:
        layer.putalpha(layer.getchannel('A').point(lambda a: round(a * p)))
    im.paste(layer, (0, 0), layer)


def route_point(points, p):
    p = clamp(p)
    ds = [math.dist(points[i], points[i + 1]) for i in range(len(points) - 1)]
    target = sum(ds) * p
    for i, d in enumerate(ds):
        if target <= d:
            a = target / d if d else 0
            return (mix(points[i][0], points[i + 1][0], a), mix(points[i][1], points[i + 1][1], a))
        target -= d
    return points[-1]


def path_partial(im, points, p, color=ORANGE, width=5, glow=None):
    if p <= 0:
        return
    distances = [math.dist(points[i], points[i + 1]) for i in range(len(points) - 1)]
    target = sum(distances) * clamp(p)
    pts = [points[0]]
    for i, dist in enumerate(distances):
        if target >= dist:
            pts.append(points[i + 1])
            target -= dist
        else:
            frac = target / dist
            pts.append((mix(points[i][0], points[i + 1][0], frac), mix(points[i][1], points[i + 1][1], frac)))
            break
    if len(pts) > 1:
        if glow:
            line(im, pts, glow, width + 8)
        line(im, pts, color, width)


def car(im, x, y, color=INK, scale=1, angle=0):
    if angle:
        sprite = Image.new('RGBA', (int(64 * scale), int(64 * scale)))
        car(sprite, 32 * scale, 32 * scale, color, scale)
        sprite = sprite.rotate(-angle, resample=Image.Resampling.BICUBIC, expand=True)
        im.paste(sprite, (round(x - sprite.width / 2), round(y - sprite.height / 2)), sprite)
        return
    rect(im, (x - 18 * scale, y - 10 * scale, x + 18 * scale, y + 10 * scale), color, r=max(2, int(5 * scale)))
    rect(im, (x - 5 * scale, y - 8 * scale, x + 7 * scale, y + 8 * scale), SUNBURST if color == INK else INK, r=2)
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            rect(im, (x + sx * 13 * scale - 4 * scale, y + sy * 11 * scale - 2 * scale, x + sx * 13 * scale + 4 * scale, y + sy * 11 * scale + 2 * scale), INK if color != INK else ORANGE, r=1)


MAP_NODES = [(120, 590), (280, 500), (410, 610), (530, 415), (710, 460), (810, 230), (620, 170), (360, 240), (180, 180), (780, 640), (1010, 530), (1030, 320)]
MAP_EDGES = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 1), (7, 3), (4, 9), (9, 10), (10, 11), (11, 5), (11, 4), (2, 9), (0, 2)]


def network(im, t, box=(820, 100, 1840, 980), active=True, bg=CARD, border=GOLD_LINE):
    x, y, x2, y2 = box
    rect(im, box, bg, outline=border, r=20, width=2)
    sx = (x2 - x) / 1100
    sy = (y2 - y) / 800
    pts = [(x + a * sx, y + b * sy) for a, b in MAP_NODES]
    for gx in range(int(x) + 36, int(x2) - 20, 52):
        for gy in range(int(y) + 36, int(y2) - 20, 52):
            circle(im, gx, gy, 1, '#FFD480')
    for a, b in MAP_EDGES:
        line(im, [pts[a], pts[b]], '#FFC266', 2)
    for i, (a, b) in enumerate(MAP_EDGES):
        if i % 2 == 0:
            px, py = route_point([pts[a], pts[b]], (t * .28 + i * .13) % 1)
            circle(im, px, py, 4, MANGO)
    route_main = [pts[i] for i in [0, 1, 7, 6, 5, 11, 10]]
    route_alt = [pts[i] for i in [8, 1, 2, 3, 4, 9, 10]]
    path_partial(im, route_alt, ease(t / 1.4), MARIGOLD, 4)
    path_partial(im, route_main, ease(t / 1.2), ORANGE, 6, glow='#FFE066')
    for i, p in enumerate(pts):
        is_hub = i in [0, 5, 10, 3]
        circle(im, *p, 7 if is_hub else 5, CARD, ORANGE if is_hub else MANGO, 3 if is_hub else 2)
    for i in [0, 5, 10]:
        p = pts[i]
        circle(im, *p, 13 + 9 * ((t * .85 + i * .3) % 1), None, MARIGOLD, 2)
    if active:
        for i in range(4):
            r_path = route_main if i < 3 else route_alt
            p = (t * .22 + i * .27) % 1
            if p > ease(t / 1.2) or p < .025 or p > .975:
                continue
            q = route_point(r_path, p)
            ahead = route_point(r_path, min(p + .002, 1))
            heading = math.degrees(math.atan2(ahead[1] - q[1], ahead[0] - q[0]))
            car(im, *q, color=INK if i % 2 == 0 else ORANGE, scale=.88, angle=heading)
    return pts


def hero(t):
    im = base_canvas('juicy').copy()
    network(im, t, (820, 100, 1840, 980), bg=CREAM, border='#E05500')
    enter(im, 'Move cars.', 80, 210, 142, t, .05, color=INK, weight=700)
    enter(im, 'Make', 80, 368, 142, t, .18, color=INK, weight=700)
    enter(im, 'margin.', 80, 526, 142, t, .30, color=INK, weight=700)
    if t > .6:
        steps = ['1. Screen', '2. Quote', '3. Escalate', '4. Deliver']
        xx = 84
        active_step = min(3, int((t - .6) / 1.1))
        for i, s in enumerate(steps):
            is_act = i == active_step
            w = badge(im, s, xx, 780, color=SUNBURST if is_act else INK, bg=INK if is_act else CARD, border=None if is_act else '#E05500', size=22)
            xx += w + 14
    return im


def dispatcher(t):
    """Kinetic 2x2 Bento Grid—zero subtitles, pure rules & live network."""
    im = base_canvas('citrus').copy()
    enter(im, 'Four dispatch rules.', 80, 96, 82, t, 0.05, color=INK, weight=700)

    phase = min(3, int(t / 2.1))

    cards = [
        (80, 236, '1. Screen', [
            ('Pickup slack', '≥ 8h'),
            ('Route cap', '≤ 500 km'),
            ('Trade-in', 'None'),
        ]),
        (565, 236, '2. Quote', [
            ('Same day', 'Check slack'),
            ('Later window', 'Per option'),
            ('Formula', 'list × markup × trust'),
        ]),
        (80, 616, '3. Escalate fee', []),
        (565, 616, '4. Qualify', [
            ('Opening offer', '0.80× fee'),
            ('Driver pairs', 'Capacity check'),
            ('On-time gate', '≥ 90.0%'),
        ]),
    ]

    for i, (cx, cy, title, rows) in enumerate(cards):
        cw, ch = 465, 350
        active = i == phase
        done = i < phase
        rect(im, (cx, cy, cx + cw, cy + ch), CARD, None, r=18)
        hdr_bg = ORANGE if active else (MARIGOLD if done else APRICOT)
        hdr_fg = CARD if active else INK
        rect(im, (cx, cy, cx + cw, cy + 68), hdr_bg, None, r=18)
        rect(im, (cx, cy + 50, cx + cw, cy + 68), hdr_bg, None, r=0)
        line(im, [(cx, cy + 68), (cx + cw, cy + 68)], ORANGE if active else GOLD_LINE, 2)
        rect(im, (cx, cy, cx + cw, cy + ch), None, ORANGE if active else GOLD_LINE, r=18, width=3 if active else 2)
        txt(im, title, cx + 24, cy + 16, 26, hdr_fg, 700)

        if i == 2:
            p_ramp = smooth(clamp((t - 1.8) / 4.2))
            val = mix(0.80, 1.50, p_ramp)
            txt(im, f'{val:.2f}×', cx + 28, cy + 96, 92, ORANGE, 700)
            ry = cy + 242
            line(im, [(cx + 28, ry), (cx + cw - 28, ry)], GOLD_TRACK, 12)
            line(im, [(cx + 28, ry), (cx + 28 + (cw - 56) * p_ramp, ry)], ORANGE, 12)
            circle(im, cx + 28 + (cw - 56) * p_ramp, ry, 14, MARIGOLD, outline=ORANGE, width=3)
            txt(im, '0.80×', cx + 28, cy + 270, 20, MUTED_INK, mono=True, weight=600)
            txt(im, '1.50×', cx + cw - 28, cy + 270, 20, ORANGE, mono=True, weight=700, anchor='ra')
        else:
            for r_idx, (k, v) in enumerate(rows):
                yy = cy + 98 + r_idx * 80
                circle(im, cx + 30, yy + 16, 8, ORANGE if (active or done) else GOLD_TRACK)
                txt(im, k, cx + 50, yy, 24, INK, 650)
                txt(im, v, cx + cw - 24, yy + 2, 21, ORANGE if (active or done) else MUTED_INK, mono=True, weight=600, anchor='ra')
                if r_idx < 2:
                    line(im, [(cx + 24, yy + 58), (cx + cw - 24, yy + 58)], APRICOT)

    network(im, t + 2.0, (1055, 236, 1840, 966), bg=CARD, border=GOLD_LINE)
    return im


def observability(t):
    im = base_canvas('juicy').copy()
    enter(im, 'Every decision,', 80, 164, 80, t, 0.05, color=INK, weight=700)
    enter(im, 'inspectable.', 80, 262, 80, t, 0.18, color=INK, weight=700)
    for i, (n, s) in enumerate([('1', 'Capture stream'), ('2', 'Reconcile ledger'), ('3', 'Spot failure')]):
        yy = 470 + i * 116
        if t > .3 + i * .15:
            circle(im, 104, yy + 20, 21, INK, outline=SUNBURST, width=2)
            txt(im, n, 104, yy + 20, 22, SUNBURST, weight=700, anchor='mm')
        enter(im, s, 146, yy - 2, 34, t, .3 + i * .15, color=INK, weight=650)
    crop_top = mix(0., 370., smooth((t - 0.6) / 5.6))
    viewport = Image.new('RGB', (1280, 910), '#0C0D0F')
    viewport.paste(REPORT.crop((0, 0, 1280, 194)), (0, 0))
    viewport.paste(REPORT.resize((1280, 716), Image.Resampling.BICUBIC, box=(0., 194 + crop_top, 1280., 910 + crop_top)), (0, 194))
    shade = Image.new('RGBA', (1280, 28))
    for yy in range(28):
        ImageDraw.Draw(shade).line((0, yy, 1280, yy), fill=(12, 13, 15, round(200 * (1 - yy / 28))))
    viewport.paste(shade, (0, 194), shade)
    crop = viewport.resize((1120, 796), Image.Resampling.LANCZOS)
    im.paste(crop, (720, 142))
    rect(im, (720, 142, 1840, 938), None, INK, r=12, width=3)
    return im


@lru_cache(maxsize=1)
def graph_all_small():
    tinted = ImageChops.multiply(CHART_ALL, Image.new('RGB', CHART_ALL.size, CREAM)).resize((1790, 868), Image.Resampling.LANCZOS)
    # Mask embedded matplotlib header/subtitle and bottom footnotes
    rect(tinted, (0, 0, 1790, 145), CREAM)
    rect(tinted, (0, 765, 1790, 868), CREAM)
    return tinted


@lru_cache(maxsize=1)
def graph_stages_small():
    tinted = ImageChops.multiply(CHART_STAGES, Image.new('RGB', CHART_STAGES.size, CARD)).resize((910, 680), Image.Resampling.LANCZOS)
    # Mask embedded matplotlib title/subtitle and bottom footnotes
    rect(tinted, (0, 0, 910, 92), CARD)
    rect(tinted, (0, 608, 910, 680), CARD)
    return tinted


def experiments(t):
    """Clean 6-stage all-run margin search—headline + chart + stage scanner only."""
    im = base_canvas('chart').copy()
    im.paste(graph_all_small(), (65, 140))
    enter(im, '1,155 practice runs.', 80, 96, 84, t, 0.05, color=INK, weight=700)

    stages = [
        (1, 'Alpha · 677'),
        (2, 'Beta Early · 64'),
        (3, 'Beta Late · 204'),
        (4, 'Gamma Early · 123'),
        (5, 'Gamma Late · 85'),
    ]
    if t > 0.5:
        frac = clamp((t - 0.5) / 6.6)
        pos = mix(0.0, 4.0, smooth(frac))
        col = 1.0 + pos
        stage_idx = min(4, int(pos + 0.5))
        cx = 65 + 1790 * (0.09 + 0.89 * (col + 0.55) / 6.10)
        hw = 1790 * (0.89 * 0.46 / 6.10)
        rect(im, (cx - hw, 140 + 868 * 0.19, cx + hw, 140 + 868 * 0.77), None, ORANGE, r=6, width=4)
        bx = clamp(cx - 110, 80, 1520)
        badge(im, stages[stage_idx][1], bx, 242, color=CARD, bg=ORANGE, size=21)
    return im


def failure(t):
    """Holdout vs. confirmation—no subtitles, bold numbers & 4-panel chart."""
    im = base_canvas('sunburst').copy()
    enter(im, 'Tuning is not validation.', 80, 96, 82, t, 0.05, color=INK, weight=700)

    # Left top card: Stress seed gamma-t04
    rect(im, (80, 236, 885, 576), CARD, outline=GOLD_LINE, r=18, width=2)
    txt(im, 'Stress seed gamma-t04', 112, 266, 26, INK, 700)
    p = ease((t - 0.25) / 1.0)
    rows_stress = [
        ('500 km · 30%', 232, 95.69, ORANGE),
        ('600 km · 38%', 294, 89.80, DANGER),
    ]
    for i, (lbl, wins, ot, col) in enumerate(rows_stress):
        yy = 344 + i * 112
        txt(im, lbl, 112, yy, 24, INK, 650)
        txt(im, f'{wins} won', 112, yy + 34, 21, MUTED_INK, mono=True)
        bx, bw = 365, 320
        rect(im, (bx, yy + 10, bx + bw, yy + 40), APRICOT, outline=GOLD_LINE, r=8)
        rect(im, (bx, yy + 10, bx + bw * (ot - 80) / 20 * p, yy + 40), col, r=8)
        gate_x = bx + bw * 0.5
        line(im, [(gate_x, yy + 2), (gate_x, yy + 48)], INK, 3)
        txt(im, f'{ot:.2f}%', bx + bw + 18, yy + 8, 26, col, mono=True, weight=700)

    # Left bottom card: 4-stage progression
    rect(im, (80, 606, 885, 966), CARD, outline=DANGER, r=18, width=2)
    txt(im, 'Gamma validation stages', 112, 634, 26, INK, 700)
    stages_summary = [
        ('1. Tuning', '+€1,232/wk', '8/8', ORANGE),
        ('2. First holdout', '+€830/wk', '7/8 FAILED', DANGER),
        ('3. Screening', '+€1,586/wk', '8/8', MANGO),
        ('4. Confirmation', '+€2,031/wk', '8/8', ORANGE),
    ]
    for i, (st_lbl, d_eur, qual, col) in enumerate(stages_summary):
        yy = 702 + i * 62
        if i == 1:
            rect(im, (98, yy - 6, 868, yy + 46), '#FFE5E5', outline=DANGER, r=8)
        elif i == 3:
            rect(im, (98, yy - 6, 868, yy + 46), APRICOT, outline=ORANGE, r=8)
        txt(im, st_lbl, 114, yy + 4, 23, INK, 700 if i in [1, 3] else 600)
        txt(im, d_eur, 585, yy + 4, 23, col, mono=True, weight=700, anchor='ra')
        txt(im, qual, 850, yy + 4, 22, col if i == 1 else INK, mono=True, weight=700, anchor='ra')

    # Right panel: The 4-panel learning-stages.png chart (header & footnotes masked)
    rect(im, (915, 236, 1840, 966), CARD, outline=GOLD_LINE, r=18, width=2)
    im.paste(graph_stages_small(), (922, 240))
    if t < 4.0:
        rect(im, (1405, 382, 1822, 574), None, DANGER, r=8, width=4)
    else:
        rect(im, (1405, 656, 1822, 848), None, ORANGE, r=8, width=4)
    return im


def gain(t):
    """Fresh Gamma confirmation (v09–v16)—clean hero metric + paired 8-week chart."""
    im = base_canvas('citrus').copy()
    enter(im, 'Gamma confirmed.', 80, 96, 84, t, 0.05, color=INK, weight=700)

    p = ease((t - 0.2) / 1.0)
    txt(im, f'+€{2030.845 * p:,.0f}', 76, 268, 142, ORANGE, 700)
    txt(im, 'per week (+20.21%)', 84, 452, 36, INK, 650)

    badge(im, '8/8 weeks positive', 84, 560, color=INK, bg=MARIGOLD, border=ORANGE, size=24)
    badge(im, '8/8 qualified', 84, 625, color=INK, bg=MARIGOLD, border=ORANGE, size=24)
    badge(im, '96.95% worst on-time', 84, 690, color=CARD, bg=ORANGE, size=24)

    # Right panel: Paired 8-week margin bars (v09–v16) + On-Time Share (%) trajectory
    rect(im, (755, 236, 1840, 966), CARD, outline=GOLD_LINE, r=18, width=2)
    txt(im, 'Fresh confirmation (v09–v16)', 790, 268, 26, INK, 700)
    rect(im, (1430, 274, 1456, 294), GOLD_TRACK, r=4)
    txt(im, 'Beta', 1466, 268, 22, MUTED_INK, 650)
    rect(im, (1570, 274, 1596, 294), ORANGE, r=4)
    txt(im, 'Gamma', 1606, 268, 22, ORANGE, 700)

    base_y = 665
    line(im, [(790, base_y), (1805, base_y)], GOLD_LINE, 2)
    ot_pts_beta = []
    ot_pts_gamma = []
    for i, r in enumerate(CONFIRM_WEEKS):
        x = 800 + i * 125
        pp = ease((t - 0.30 - i * 0.16) / 0.60)
        b_val = float(r['baseline_margin_eur'])
        g_val = float(r['candidate_margin_eur'])
        d_val = float(r['delta_eur'])
        bh = 270 * (b_val / 15500) * pp
        gh = 270 * (g_val / 15500) * pp
        rect(im, (x, base_y - bh, x + 42, base_y), GOLD_TRACK, outline=GOLD_LINE, r=4)
        rect(im, (x + 46, base_y - gh, x + 88, base_y), ORANGE, r=4)
        if pp > 0.4:
            txt(im, f'+€{d_val:,.0f}', x + 44, base_y - max(bh, gh) - 30, 18, ORANGE, mono=True, weight=700, anchor='ma')

        ot_b = float(r['baseline_on_time']) * 100
        ot_g = float(r['candidate_on_time']) * 100
        cx = x + 44
        yb = 885 - 135 * ((ot_b - 89) / 11)
        yg = 885 - 135 * ((ot_g - 89) / 11)
        ot_pts_beta.append((cx, yb))
        ot_pts_gamma.append((cx, yg))
        txt(im, f'v{i + 9:02d}', cx, 904, 19, INK, mono=True, weight=650, anchor='ma')

    txt(im, 'On-time %', 790, 694, 21, MUTED_INK, 650)
    gate_y = 885 - 135 * ((90 - 89) / 11)
    line(im, [(790, gate_y), (1805, gate_y)], DANGER, 2)
    txt(im, '90%', 1805, gate_y - 24, 18, DANGER, mono=True, weight=700, anchor='ra')
    if len(ot_pts_beta) > 1:
        line(im, ot_pts_beta, MUTED_INK, 3)
        line(im, ot_pts_gamma, ORANGE, 4)
        for (xb, yb), (xg, yg) in zip(ot_pts_beta, ot_pts_gamma):
            circle(im, xb, yb, 5, CARD, outline=MUTED_INK, width=2)
            circle(im, xg, yg, 6, ORANGE, outline=INK, width=2)
    return im


def result(t):
    """Both saved 5-week official ranking rounds—clean totals & bars, zero subtitles."""
    im = base_canvas('sunburst').copy()
    enter(im, 'Ten official weeks. 10/10 qualified.', 80, 96, 80, t, 0.05, color=INK, weight=700)

    rounds_ui = [
        (80, 'Round 5', 50541.26, ROUND5_RUNS, MARIGOLD, INK),
        (980, 'Round 6', 59528.62, ROUND6_RUNS, ORANGE, CARD),
    ]
    for rx, title, tot, runs_list, bar_col, hdr_fg in rounds_ui:
        is_r6 = rx > 500
        rect(im, (rx, 236, rx + 860, 966), CARD, outline=ORANGE if is_r6 else GOLD_LINE, r=18, width=3 if is_r6 else 2)
        badge(im, title, rx + 36, 272, color=hdr_fg, bg=ORANGE if is_r6 else MARIGOLD, size=22)
        badge(im, '5/5 qualified', rx + 665, 272, color=INK, bg=APRICOT, border=GOLD_LINE, size=20)

        p_tot = ease((t - 0.20) / 1.0)
        txt(im, f'€{tot * p_tot:,.2f}', rx + 36, 352, 108, ORANGE if is_r6 else INK, 700)

        base_y = 875
        line(im, [(rx + 36, base_y), (rx + 824, base_y)], GOLD_LINE, 2)
        for j, w in enumerate(runs_list):
            bx = rx + 38 + j * 158
            p = ease((t - 0.30 - j * 0.14) / 0.65)
            v = w['score']['marginCents'] / 100.0
            bh = 280 * (v / 14500.0) * p
            rect(im, (bx, base_y - bh, bx + 132, base_y), bar_col, outline=ORANGE if not is_r6 else None, r=6)
            if is_r6 and p > 0.05:
                rect(im, (bx, base_y - bh, bx + 132, min(base_y, base_y - bh + 8)), SUNBURST, r=3)
            if p > 0.3:
                txt(im, f'€{v / 1000:.1f}k', bx + 66, base_y - bh - 34, 21, INK, mono=True, weight=700, anchor='ma')
            txt(im, f'W{j + 1}', bx + 66, base_y + 20, 22, INK, 700, anchor='ma')
    return im


def ending(t):
    im = base_canvas('juicy').copy()
    road_layer = im.copy()
    for offset in [-210, 0, 210]:
        line(road_layer, [(1160 + offset, 1080), (1600 + offset, 650), (1400 + offset, 350), (1830 + offset, -50)], ORANGE, 46)
    line(road_layer, [(1160, 1080), (1600, 650), (1400, 350), (1830, -50)], SUNBURST, 6)
    im.paste(road_layer, (0, 0))

    enter(im, 'Win the', 80, 196, 146, t, .05, color=INK, weight=700)
    enter(im, 'right work.', 80, 356, 146, t, .16, color=INK, weight=700)
    enter(im, 'Deliver it.', 80, 516, 146, t, .28, color=CARD, weight=700)
    badge(im, '+€2,031 / week confirmed', 86, 760, color=SUNBURST, bg=INK, size=26)

    road = [(1370, 1020), (1690, 650), (1490, 350), (1825, 15)]
    for idx_c, offset_p in enumerate([0.12, 0.54]):
        p = (offset_p + t * .11) % 1
        pos = route_point(road, p)
        ahead = route_point(road, min(p + .002, 1))
        heading = math.degrees(math.atan2(ahead[1] - pos[1], ahead[0] - pos[0]))
        car(im, *pos, INK if idx_c == 0 else CARD, 2.8, heading)
    return im


FUNCS = [hero, dispatcher, observability, experiments, failure, gain, result, ending]


def frame(t):
    idx = next((i for i, (a, b) in enumerate(SCENES) if a <= t < b), 7)
    a, b = SCENES[idx]
    im = FUNCS[idx](t - a)
    dt = t - a
    if idx and dt < .32:
        xx = round(W * ease(dt / .32))
        prev = FUNCS[idx - 1](SCENES[idx - 1][1] - SCENES[idx - 1][0] + dt)
        im.paste(prev.crop((xx, 0, W, H)), (xx, 0))
        rect(im, (max(0, xx - 12), 0, xx + 2, H), ORANGE if idx not in [0, 2, 7] else INK)
    return im


def soundtrack(path):
    """Energetic 128 BPM instrumental for the 60s cut; seeded percussion, no third-party samples."""
    sr = 44100
    n = sr * DURATION
    audio = np.zeros((n, 2), dtype=np.float32)
    rng = np.random.default_rng(20261114)
    beat_sec = 60.0 / 128.0
    bar_sec = beat_sec * 4.0

    def add(start, sig, vol=.1, pan=0):
        off = round(start * sr)
        if off >= n or off < 0:
            return
        sig = sig[:max(0, n - off)]
        l = math.sqrt((1 - pan) / 2)
        r = math.sqrt((1 + pan) / 2)
        if len(sig):
            audio[off:off + len(sig), 0] += sig * vol * l
            audio[off:off + len(sig), 1] += sig * vol * r

    def note(midi, sec, kind='pluck'):
        ts = np.arange(round(sec * sr)) / sr
        f = 440 * 2 ** ((midi - 69) / 12)
        if kind == 'pad':
            env = np.minimum(ts / .25, 1) * np.minimum((sec - ts) / .4, 1)
            return ((np.sin(2 * np.pi * f * ts) + .25 * np.sin(2 * np.pi * f * 1.003 * ts) + .12 * np.sin(4 * np.pi * f * ts)) * env).astype(np.float32)
        env = (1 - np.exp(-ts * 210)) * np.exp(-ts * 6.5)
        return ((np.sin(2 * np.pi * f * ts) + .26 * np.sin(4 * np.pi * f * ts) + .10 * np.sin(6 * np.pi * f * ts)) * env).astype(np.float32)

    chords = [[50, 53, 57, 60], [46, 50, 53, 57], [53, 57, 60, 65], [48, 52, 55, 60]]
    num_bars = int(DURATION / bar_sec) + 2
    for bar in range(num_bars):
        start = bar * bar_sec
        ch = chords[(bar // 2) % 4]
        for j, m in enumerate(ch):
            add(start, note(m + 12, bar_sec * 1.1, 'pad'), .022, (-.6 + j * .4))
        for beat in range(4):
            b_start = start + beat * beat_sec
            add(b_start, note(ch[0] - 12, beat_sec * 0.85), .11)
            if 1 <= bar < num_bars - 2:
                for sub in range(2):
                    k = beat * 2 + sub
                    add(start + k * (beat_sec / 2), note(ch[[0, 2, 1, 3, 2, 1, 3, 2][k]] + 24, beat_sec * 0.8), .030, (-1 if k % 2 else 1) * .55)
        if 1 <= bar < num_bars - 2:
            for beat in range(4):
                b_start = start + beat * beat_sec
                ts = np.arange(round(sr * .24)) / sr
                kick = np.sin(2 * np.pi * (50 * ts + 6 * (1 - np.exp(-ts * 40)))) * np.exp(-ts * 20)
                add(b_start, kick, .19)
                if beat % 2:
                    sn = rng.standard_normal(len(ts)) * np.exp(-ts * 30)
                    sn = np.diff(np.r_[0, sn])
                    add(b_start, sn, .025)
            for j in range(8):
                ts = np.arange(round(sr * .06)) / sr
                noise = rng.standard_normal(len(ts))
                noise = np.diff(np.r_[0, noise]) * np.exp(-ts * 95)
                add(start + j * (beat_sec / 2), noise, .012 if j % 2 else .006, (-1 if j % 2 else 1) * .3)
    for cut in [6, 15, 22, 30, 38, 47, 54]:
        ts = np.arange(round(sr * 0.7)) / sr
        noise = rng.standard_normal(len(ts))
        noise = np.convolve(noise, np.ones(12) / 12, mode='same')
        add(cut - .55, noise * np.sin(np.pi * ts / 0.7) ** 2, .055)
        add(cut + .04, note(86, .14), .032, .25)
    tt = np.arange(n) / sr
    fade = np.minimum(tt / 1.2, 1) * np.minimum((DURATION - tt) / 2.2, 1)
    audio *= fade[:, None]
    audio = np.tanh(audio * 1.6) * .8
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes((audio * 32767).astype('<i2').tobytes())


def stills(out):
    times = [2.5, 7.2, 10.5, 13.8, 18.5, 24.5, 28.0, 32.5, 36.5, 43.5, 51.0, 57.5]
    thumbs = []
    for p in out.glob('frame-*.png'):
        p.unlink()
    for i, t in enumerate(times):
        im = frame(t)
        im.save(out / f'frame-{i + 1:02d}-{t:04.1f}s.png')
        thumb = im.resize((640, 360), Image.Resampling.LANCZOS)
        thumbs.append(thumb)
    sheet = Image.new('RGB', (1920, 1440), '#FF7700')
    for i, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((i % 3) * 640, (i // 3) * 360))
    sheet.save(out / 'contact-sheet.jpg', quality=93)
    sheet.save(ROOT / 'assets/contact-sheet.jpg', quality=93)
    poster = frame(2.5)
    poster.save(out / 'poster.png')
    poster.save(ROOT / 'assets/poster.png')


def render(out, draft=False):
    soundtrack(out / 'soundtrack.wav')
    for caption in ['captions.srt', 'captions.vtt']:
        (out / caption).write_bytes((ROOT / caption).read_bytes())
    width, height = (960, 540) if draft else (W, H)
    fps = 15 if draft else FPS
    name = 'cheap-drive-draft.mp4' if draft else 'cheap-drive-demo.mp4'
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    args = [
        ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', str(fps), '-i', '-',
        '-i', str(out / 'soundtrack.wav'),
        '-i', str(ROOT / 'captions.srt'),
        '-map', '0:v', '-map', '1:a', '-map', '2:s',
        '-c:s', 'mov_text', '-metadata:s:s:0', 'language=eng', '-disposition:s:0', '0',
        '-c:v', 'libx264', '-preset', 'fast' if draft else 'medium', '-crf', '24' if draft else '18', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-ar', '48000', '-b:a', '192k', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=9',
        '-movflags', '+faststart', '-t', str(DURATION), str(out / name)
    ]
    proc = subprocess.Popen(args, stdin=subprocess.PIPE)
    try:
        for i in range(DURATION * fps):
            im = frame(i / fps)
            if draft:
                im = im.resize((width, height), Image.Resampling.LANCZOS)
            proc.stdin.write(im.tobytes())
            if i % (fps * 5) == 0:
                print(f'{name}: {i / fps:.0f}/{DURATION}s', flush=True)
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError('ffmpeg failed')
    except BaseException:
        proc.kill()
        raise
    print(out / name, flush=True)


def validate():
    assert GRAPH['summary']['completed_practice'] == 1155
    assert GRAPH['summary']['completed_official'] == 10
    assert GRAPH['summary']['completed_total'] == 1165
    assert CHART_DATA['chart_groups'] == {
        'Baseline': 2,
        'Alpha': 677,
        'Beta Early': 64,
        'Beta Late': 204,
        'Gamma Early': 123,
        'Gamma Late': 85,
    }
    assert len(CONFIRM_WEEKS) == 8
    assert all(r['candidate_qualified'] == 'True' and float(r['delta_eur']) > 0 for r in CONFIRM_WEEKS)
    assert round(sum(float(r['delta_eur']) for r in CONFIRM_WEEKS) / 8, 3) == 2030.845
    assert round(sum(float(r['baseline_margin_eur']) for r in CONFIRM_WEEKS) / 8, 2) == 10047.87
    assert round(sum(float(r['candidate_margin_eur']) for r in CONFIRM_WEEKS) / 8, 2) == 12078.71
    assert len(OFFICIAL_ROUNDS) == 2
    assert float(OFFICIAL_ROUNDS[0]['total_margin_eur']) == 50541.26
    assert float(OFFICIAL_ROUNDS[1]['total_margin_eur']) == 59528.62
    assert len(ROUND5_RUNS) == 5 and len(ROUND6_RUNS) == 5
    stress = next(r for r in PAIRED_OLD if r['suite'] == 't1' and r['variant'] == 'km600-t38' and r['seed'] == 'gamma-t04')
    assert int(stress['won_orders']) == 294 and round(float(stress['on_time_share']) * 100, 2) == 89.80


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=OUT)
    p.add_argument('--stills', action='store_true')
    p.add_argument('--draft', action='store_true')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    validate()
    if a.stills:
        stills(a.output)
    else:
        render(a.output, a.draft)
