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
MUTED_INK = '#4A3B2C'    # Warm charcoal-ochre for secondary copy on sunlit cream
JUICY_TEXT = '#592800'   # Deep citrus-amber secondary copy on juicy yellow-orange canvases

ORANGE = '#FF6200'       # Vibrant juicy tangerine orange (primary hero & bar accent)
ORANGE_BRIGHT = '#FF7A00'# Juicy orange fill
MANGO = '#FF9500'        # Rich yellow-orange / mango
MARIGOLD = '#FFB700'     # Golden yellow-orange highlight
SUNBURST = '#FFD000'     # Bright citrus yellow-gold accent

CREAM = '#FFF8EB'        # Sunlit citrus cream background
CARD = '#FFFDF8'         # Crisp warm white-cream card surface
APRICOT = '#FFEAB8'      # Soft golden-apricot panel fill
GOLD_TRACK = '#FFD98A'   # Golden track fill for unloaded bar slots
GOLD_LINE = '#FFBE4F'    # Golden-orange structural border on cream scenes
JUICY_LINE = '#E05500'   # Rich tangerine structural border on juicy orange scenes
DANGER = '#E5383B'       # Crisp crimson for failed qualification / deadline warnings

SCENES = [
    (0, 6, 'The challenge'),
    (6, 15, 'Dispatch workflow'),
    (15, 22, 'Observability'),
    (22, 30, '1,155 practice runs'),
    (30, 38, 'Holdout vs. confirmation'),
    (38, 47, 'Gamma confirmation'),
    (47, 54, 'Official ranking rounds'),
    (54, 60, 'Ready for the final'),
]

GRAPH = json.loads((ROOT / 'data/graph-data.json').read_text())
CHART_DATA = json.loads((ROOT / 'data/chart-data.json').read_text())
COHORTS = list(csv.DictReader((ROOT / 'data/cohort-comparisons.csv').open()))
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


def badge(im, text, x, y, color=INK, bg=MARIGOLD, border=None, size=20, mono=False, weight=600):
    b = font(size, weight, mono).getbbox(text)
    w = b[2] + 34
    rect(im, (x, y, x + w, y + 42), bg, outline=border, r=8, width=1 if border else 0)
    txt(im, text, x + 17, y + 8, size, color, weight=weight, mono=mono)
    return w


def enter(im, text, x, y, size, t, delay=0, color=INK, weight=600, mono=False, span=0.42):
    p = ease((t - delay) / span)
    if p <= 0:
        return
    layer = Image.new('RGBA', (W, H))
    txt(layer, text, x, y + (1 - p) * 28, size, color, weight, mono)
    if p < 1:
        layer.putalpha(layer.getchannel('A').point(lambda a: round(a * p)))
    im.paste(layer, (0, 0), layer)


def chrome(im, idx, t, mode='juicy'):
    """Minimal team signature only—no side labels, no second timer, no Cheap-Drive header, no footnotes."""
    if idx == 7:
        return
    fg = INK if mode == 'juicy' else MUTED_INK
    txt(im, 'Guardians of the Moonlight', 80, 44, 20, fg, 650)


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


def network(im, t, box=(860, 180, 1830, 900), active=True, bg=CARD, border=GOLD_LINE):
    x, y, x2, y2 = box
    rect(im, box, bg, outline=border, r=18, width=2)
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
            car(im, *q, color=INK if i % 2 == 0 else ORANGE, scale=.85, angle=heading)
    return pts


def hero(t):
    im = base_canvas('juicy').copy()
    network(im, t, (820, 120, 1840, 960), bg=CREAM, border='#E05500')
    enter(im, 'Move cars.', 80, 180, 130, t, .05, color=INK, weight=700)
    enter(im, 'Make', 80, 322, 130, t, .18, color=INK, weight=700)
    enter(im, 'margin.', 80, 464, 130, t, .30, color=INK, weight=700)
    enter(im, 'A dispatcher that learns what to win,', 84, 678, 32, t, .50, color=INK, weight=600)
    enter(im, 'what to pay, and when to say no.', 84, 724, 32, t, .62, color=INK, weight=500)
    if t > .8:
        steps = ['1. Screen', '2. Quote', '3. Escalate', '4. Deliver']
        xx = 84
        active_step = min(3, int((t - .8) / 1.1))
        for i, s in enumerate(steps):
            is_act = i == active_step
            w = badge(im, s, xx, 832, color=SUNBURST if is_act else INK, bg=INK if is_act else CARD, border=None if is_act else '#E05500', size=20)
            xx += w + 12
    rect(im, (1295, 154, 1808, 230), APRICOT, GOLD_LINE, r=10, width=2)
    circle(im, 1324, 192, 6, ORANGE)
    txt(im, '1,165 scored worlds  /  58 scenarios', 1344, 178, 21, INK, 650)
    return im


def dispatcher(t):
    """Kinetic 2x2 Bento Grid showing all 4 dispatch rules in rapid succession."""
    im = base_canvas('citrus').copy()
    enter(im, 'From request to road in four rules.', 80, 114, 70, t, 0.05, color=INK, weight=700)
    enter(im, 'Transfer request: Helsinki to Tampere (178 km)  /  Beta & Gamma policy foundation', 84, 206, 26, t, 0.18, color=MUTED_INK, weight=500)

    phase = min(3, int(t / 2.1))

    cards = [
        (80, 286, '1. Screen the work', 'Admit only feasible routes', [
            ('Pickup slack', '≥ 8h (≥ 24h long)'),
            ('Route cap', '≤ 500 km baseline'),
            ('Trade-in', 'None (pass)'),
        ]),
        (565, 286, '2. Quote options', 'list × markup × (1 + trust/100)', [
            ('Same day', 'Guard slack first'),
            ('Tomorrow / Later', 'Price individually'),
            ('Dealer trust', 'On-time cap at 25'),
        ]),
        (80, 628, '3. Escalate driver fee', 'Ramp pay before deadline warning', []),
        (565, 628, '4. Guard qualification', '90.0% on-time gate every week', [
            ('Gig published', '0.80× opening offer'),
            ('Driver booked', 'Segment & pair checks'),
            ('Delivered on time', '≥ 90% required'),
        ]),
    ]

    for i, (cx, cy, title, sub, rows) in enumerate(cards):
        cw, ch = 465, 318
        active = i == phase
        done = i < phase
        rect(im, (cx, cy, cx + cw, cy + ch), CARD, None, r=16)
        hdr_bg = ORANGE if active else (MARIGOLD if done else APRICOT)
        hdr_fg = CARD if active else INK
        rect(im, (cx, cy, cx + cw, cy + 78), hdr_bg, None, r=16)
        rect(im, (cx, cy + 60, cx + cw, cy + 78), hdr_bg, None, r=0)
        line(im, [(cx, cy + 78), (cx + cw, cy + 78)], ORANGE if active else GOLD_LINE, 2)
        rect(im, (cx, cy, cx + cw, cy + ch), None, ORANGE if active else GOLD_LINE, r=16, width=3 if active else 2)
        txt(im, title, cx + 22, cy + 14, 23, hdr_fg, 700)
        txt(im, sub, cx + 22, cy + 45, 17, CARD if active else MUTED_INK, mono=(i == 1), weight=500)

        if i == 2:
            p_ramp = smooth(clamp((t - 2.0) / 4.2))
            val = mix(0.80, 1.50, p_ramp)
            txt(im, f'{val:.2f}×', cx + 24, cy + 98, 74, ORANGE, 700)
            txt(im, 'typical fee', cx + 235, cy + 136, 22, MUTED_INK, 600)
            ry = cy + 222
            line(im, [(cx + 28, ry), (cx + cw - 28, ry)], GOLD_TRACK, 10)
            line(im, [(cx + 28, ry), (cx + 28 + (cw - 56) * p_ramp, ry)], ORANGE, 10)
            circle(im, cx + 28 + (cw - 56) * p_ramp, ry, 12, MARIGOLD, outline=ORANGE, width=3)
            txt(im, '0.80× open', cx + 24, cy + 244, 17, MUTED_INK, mono=True)
            txt(im, '1.50× at warning', cx + cw - 24, cy + 244, 17, ORANGE, mono=True, anchor='ra')
        else:
            for r_idx, (k, v) in enumerate(rows):
                yy = cy + 106 + r_idx * 66
                circle(im, cx + 30, yy + 15, 7, ORANGE if (active or done) else GOLD_TRACK)
                txt(im, k, cx + 48, yy, 22, INK, 600)
                txt(im, v, cx + cw - 22, yy + 2, 19, ORANGE if (active or done) else MUTED_INK, mono=True, weight=600, anchor='ra')
                if r_idx < 2:
                    line(im, [(cx + 22, yy + 50), (cx + cw - 22, yy + 50)], APRICOT)

    network(im, t + 2.0, (1055, 286, 1840, 946), bg=CARD, border=GOLD_LINE)
    badge(im, f'Active step: {cards[phase][2]}', 1085, 314, color=INK, bg=MARIGOLD, size=20)
    return im


def observability(t):
    im = base_canvas('juicy').copy()
    enter(im, 'Every decision,', 80, 164, 76, t, 0.05, color=INK, weight=700)
    enter(im, 'inspectable.', 80, 256, 76, t, 0.18, color=INK, weight=700)
    for i, (n, s) in enumerate([('1', 'Capture the event stream.'), ('2', 'Reconcile the ledger.'), ('3', 'Find the failure.')]):
        yy = 452 + i * 104
        if t > .3 + i * .15:
            circle(im, 102, yy + 18, 19, INK, outline=SUNBURST, width=2)
            txt(im, n, 102, yy + 18, 20, SUNBURST, weight=700, anchor='mm')
        enter(im, s, 140, yy - 2, 29, t, .3 + i * .15, color=INK, weight=650)
    txt(im, 'Offline HTML report with replayable evidence.', 84, 825, 24, JUICY_TEXT, 600)
    crop_top = mix(0., 370., smooth((t - 0.6) / 5.6))
    viewport = Image.new('RGB', (1280, 910), '#0C0D0F')
    viewport.paste(REPORT.crop((0, 0, 1280, 194)), (0, 0))
    viewport.paste(REPORT.resize((1280, 716), Image.Resampling.BICUBIC, box=(0., 194 + crop_top, 1280., 910 + crop_top)), (0, 194))
    shade = Image.new('RGBA', (1280, 28))
    for yy in range(28):
        ImageDraw.Draw(shade).line((0, yy, 1280, yy), fill=(12, 13, 15, round(200 * (1 - yy / 28))))
    viewport.paste(shade, (0, 194), shade)
    crop = viewport.resize((1088, 774), Image.Resampling.LANCZOS)
    im.paste(crop, (755, 172))
    rect(im, (755, 172, 1843, 946), None, INK, r=10, width=3)
    badge(im, 'Real offline report (Fixed baseline, level 4)', 755, 114, color=SUNBURST, bg=INK, size=19)
    return im


@lru_cache(maxsize=1)
def graph_all_small():
    tinted = ImageChops.multiply(CHART_ALL, Image.new('RGB', CHART_ALL.size, CREAM)).resize((1790, 868), Image.Resampling.LANCZOS)
    # Mask embedded bottom footnotes from the matplotlib export
    rect(tinted, (0, 765, 1790, 868), CREAM)
    return tinted


@lru_cache(maxsize=1)
def graph_stages_small():
    tinted = ImageChops.multiply(CHART_STAGES, Image.new('RGB', CHART_STAGES.size, CARD)).resize((910, 650), Image.Resampling.LANCZOS)
    # Mask embedded bottom footnotes from the matplotlib export
    rect(tinted, (0, 585, 910, 650), CARD)
    return tinted


def experiments(t):
    """Fast-paced 6-stage all-run margin search (1,155 practice runs + 10 official worlds)."""
    im = base_canvas('chart').copy()
    im.paste(graph_all_small(), (65, 112))

    count = round(1155 * ease(t / 1.0))
    badge(im, f'{count:,} practice + 10 official = 1,165 scored worlds', 1255, 912, color=INK, bg=MARIGOLD, border=ORANGE, size=20)

    stages = [
        (1, 'Alpha stage: 677 runs (contextual pricing)'),
        (2, 'Beta Early: 64 runs (trust & fee ramp)'),
        (3, 'Beta Late: 204 runs (frozen 3-param baseline)'),
        (4, 'Gamma Early: 123 runs (guarded long routes)'),
        (5, 'Gamma Late: 85 runs (notes + pairs + segments)'),
    ]
    if t > 0.6:
        frac = clamp((t - 0.6) / 6.6)
        pos = mix(0.0, 4.0, smooth(frac))
        col = 1.0 + pos
        stage_idx = min(4, int(pos + 0.5))
        cx = 65 + 1790 * (0.09 + 0.89 * (col + 0.55) / 6.10)
        hw = 1790 * (0.89 * 0.46 / 6.10)
        rect(im, (cx - hw, 112 + 868 * 0.19, cx + hw, 112 + 868 * 0.77), None, ORANGE, r=6, width=4)
        bx = clamp(cx - 210, 80, 1360)
        badge(im, stages[stage_idx][1], bx, 232, color=CARD, bg=ORANGE, size=19)
    return im


def failure(t):
    """Why tuning is not validation: stress failure + first Gamma holdout failure vs. 4-stage progression."""
    im = base_canvas('sunburst').copy()
    enter(im, 'Tuning is not validation.', 80, 114, 74, t, 0.05, color=INK, weight=700)
    enter(im, 'Pushing volume or long routes broke on fresh weeks until recovery controls were repaired.', 84, 206, 25, t, 0.18, color=MUTED_INK, weight=500)

    # Left top card: Stress seed gamma-t04 (232 vs 294 wins)
    rect(im, (80, 278, 885, 602), CARD, outline=GOLD_LINE, r=18, width=2)
    txt(im, 'Capacity cliff on stress seed gamma-t04 (level 8)', 110, 304, 21, INK, 700)
    badge(im, 'Warnings: 17 to 54', 635, 296, color=CARD, bg=DANGER, size=18, mono=True)
    p = ease((t - 0.3) / 1.1)
    rows_stress = [
        ('500 km, 30% target', 232, 95.69, 10245.77, ORANGE, MARIGOLD, 'Qualified'),
        ('600 km, 38% target', 294, 89.80, 9960.69, DANGER, DANGER, 'Unqualified'),
    ]
    for i, (lbl, wins, ot, mgn, col, b_col, tag) in enumerate(rows_stress):
        yy = 364 + i * 114
        txt(im, lbl, 110, yy, 21, INK, 650)
        txt(im, f'{wins} won  /  €{mgn:,.0f}', 110, yy + 32, 20, MUTED_INK, mono=True)
        bx, bw = 415, 290
        rect(im, (bx, yy + 10, bx + bw, yy + 36), APRICOT, outline=GOLD_LINE, r=6)
        rect(im, (bx, yy + 10, bx + bw * (ot - 80) / 20 * p, yy + 36), col, r=6)
        gate_x = bx + bw * 0.5
        line(im, [(gate_x, yy + 2), (gate_x, yy + 44)], INK, 3)
        txt(im, f'{ot:.2f}% OT', bx + bw + 14, yy + 8, 22, col, mono=True, weight=700)

    # Left bottom card: Gamma Early tuning (+€1,232, 8/8) vs First fresh holdout (7/8, h07 at 89.956%)
    rect(im, (80, 624, 885, 956), CARD, outline=DANGER, r=18, width=2)
    txt(im, 'Gamma Early (guarded 700 km): first fresh holdout failed', 110, 648, 22, DANGER, 700)
    stages_summary = [
        ('1. Tuning (t01–t08)', '+€1,232/wk', '8/8 qualified', '92.98% worst OT', ORANGE),
        ('2. Holdout (h01–h08)', '+€830/wk', '7/8 FAILED', 'h07: 89.956% OT', DANGER),
        ('3. Screening (v01–v08)', '+€1,586/wk', '8/8 qualified', '94.57% worst OT', MANGO),
        ('4. Confirmation (v09–v16)', '+€2,031/wk', '8/8 qualified', '96.95% worst OT', ORANGE),
    ]
    for i, (st_lbl, d_eur, qual, w_ot, col) in enumerate(stages_summary):
        yy = 702 + i * 58
        if i == 1:
            rect(im, (98, yy - 6, 868, yy + 42), '#FFE5E5', outline=DANGER, r=8)
        elif i == 3:
            rect(im, (98, yy - 6, 868, yy + 42), APRICOT, outline=ORANGE, r=8)
        txt(im, st_lbl, 110, yy + 4, 19, INK, 650 if i in [1, 3] else 500)
        txt(im, d_eur, 505, yy + 4, 19, col, mono=True, weight=700, anchor='ra')
        txt(im, qual, 665, yy + 4, 19, col if i == 1 else INK, weight=700, anchor='ra')
        txt(im, w_ot, 856, yy + 4, 18, col if i == 1 else MUTED_INK, mono=True, weight=600, anchor='ra')

    # Right panel: The 4-panel learning-stages.png chart
    rect(im, (915, 278, 1840, 956), CARD, outline=GOLD_LINE, r=18, width=2)
    im.paste(graph_stages_small(), (922, 305))
    if t < 4.0:
        rect(im, (1405, 435, 1822, 617), None, DANGER, r=8, width=4)
    else:
        rect(im, (1405, 697, 1822, 879), None, ORANGE, r=8, width=4)
    return im


def gain(t):
    """Fresh Gamma confirmation on 8 unseen weeks (v09–v16): +€2,031/week (+20.21%), 8/8 qualified."""
    im = base_canvas('citrus').copy()
    enter(im, 'Gamma confirmed on unseen weeks.', 80, 114, 72, t, 0.05, color=INK, weight=700)
    enter(im, 'Notes + repaired pairs + segment controls  /  8 untouched confirmation seeds (gamma-v09…v16)', 84, 204, 25, t, 0.18, color=MUTED_INK, weight=500)

    p = ease((t - 0.25) / 1.1)
    txt(im, f'+€{2030.845 * p:,.0f}', 76, 288, 152, ORANGE, 700)
    txt(im, 'mean margin gain / week (+20.21%)', 84, 476, 30, INK, 650)
    txt(im, 'Beta €10,047.87  →  Gamma €12,078.71', 84, 522, 22, MUTED_INK, mono=True, weight=600)

    badge(im, '8/8 weeks positive   ·   8/8 qualified', 84, 588, color=INK, bg=MARIGOLD, border=ORANGE, size=21)
    badge(im, 'Worst on-time: 93.67% → 96.95%', 84, 646, color=CARD, bg=ORANGE, size=21)

    rect(im, (84, 718, 730, 946), CARD, outline=GOLD_LINE, r=16, width=2)
    txt(im, 'What changed in Gamma Late:', 110, 742, 22, INK, 700)
    bullets = [
        '1. Note-aware admission & pricing adjustments',
        '2. Repaired driver-pair & capacity brake logic',
        '3. Segment-level fee & slack controls',
    ]
    for i, b_txt in enumerate(bullets):
        txt(im, b_txt, 110, 788 + i * 44, 21, MUTED_INK, 600)

    # Right panel: Paired 8-week margin bars (v09–v16) + On-Time Share (%) trajectory
    rect(im, (765, 276, 1840, 946), CARD, outline=GOLD_LINE, r=18, width=2)
    txt(im, 'Paired weekly margin (seeds v09–v16)', 800, 304, 23, INK, 700)
    rect(im, (1325, 308, 1349, 326), GOLD_TRACK, r=3)
    txt(im, 'Beta baseline', 1357, 304, 19, MUTED_INK, 600)
    rect(im, (1515, 308, 1539, 326), ORANGE, r=3)
    txt(im, 'Gamma Late (confirmed)', 1547, 304, 19, ORANGE, 700)

    base_y = 665
    line(im, [(800, base_y), (1805, base_y)], GOLD_LINE, 2)
    ot_pts_beta = []
    ot_pts_gamma = []
    for i, r in enumerate(CONFIRM_WEEKS):
        x = 812 + i * 124
        pp = ease((t - 0.35 - i * 0.18) / 0.65)
        b_val = float(r['baseline_margin_eur'])
        g_val = float(r['candidate_margin_eur'])
        d_val = float(r['delta_eur'])
        bh = 250 * (b_val / 15500) * pp
        gh = 250 * (g_val / 15500) * pp
        rect(im, (x, base_y - bh, x + 42, base_y), GOLD_TRACK, outline=GOLD_LINE, r=4)
        rect(im, (x + 46, base_y - gh, x + 88, base_y), ORANGE, r=4)
        if pp > 0.4:
            txt(im, f'+€{d_val:,.0f}', x + 44, base_y - max(bh, gh) - 28, 17, ORANGE, mono=True, weight=700, anchor='ma')

        ot_b = float(r['baseline_on_time']) * 100
        ot_g = float(r['candidate_on_time']) * 100
        cx = x + 44
        yb = 868 - 125 * ((ot_b - 89) / 11)
        yg = 868 - 125 * ((ot_g - 89) / 11)
        ot_pts_beta.append((cx, yb))
        ot_pts_gamma.append((cx, yg))
        txt(im, f'v{i + 9:02d}', cx, 884, 18, INK, mono=True, weight=600, anchor='ma')

    txt(im, 'On-time delivery share (%) vs. 90% qualification gate', 800, 694, 19, MUTED_INK, 600)
    gate_y = 868 - 125 * ((90 - 89) / 11)
    line(im, [(800, gate_y), (1805, gate_y)], DANGER, 2)
    txt(im, '90% gate', 1805, gate_y - 22, 16, DANGER, mono=True, weight=600, anchor='ra')
    if len(ot_pts_beta) > 1:
        line(im, ot_pts_beta, MUTED_INK, 3)
        line(im, ot_pts_gamma, ORANGE, 4)
        for (xb, yb), (xg, yg) in zip(ot_pts_beta, ot_pts_gamma):
            circle(im, xb, yb, 5, CARD, outline=MUTED_INK, width=2)
            circle(im, xg, yg, 6, ORANGE, outline=INK, width=2)
    return im


def result(t):
    """Both saved 5-week official Beta ranking rounds: Round 5 (€50,541.26) & Round 6 (€59,528.62)."""
    im = base_canvas('sunburst').copy()
    enter(im, 'Ten official ranking weeks. 10/10 qualified.', 80, 114, 72, t, 0.05, color=INK, weight=700)
    enter(im, 'Two saved five-week official Beta ranking rounds  /  Every single week above 95.4% on-time', 84, 206, 25, t, 0.18, color=MUTED_INK, weight=600)

    rounds_ui = [
        (80, 'Round 5 — Beta (5 official weeks)', 50541.26, 10108.25, 95.49, ROUND5_RUNS, MARIGOLD, INK),
        (980, 'Round 6 — Beta (5 official weeks)', 59528.62, 11905.72, 96.11, ROUND6_RUNS, ORANGE, CARD),
    ]
    for rx, title, tot, mean_v, worst_ot, runs_list, bar_col, hdr_fg in rounds_ui:
        is_r6 = rx > 500
        rect(im, (rx, 276, rx + 860, 946), CARD, outline=ORANGE if is_r6 else GOLD_LINE, r=18, width=3 if is_r6 else 2)
        badge(im, title, rx + 32, 308, color=hdr_fg, bg=ORANGE if is_r6 else MARIGOLD, size=20)
        badge(im, '5/5 qualified', rx + 675, 308, color=INK, bg=APRICOT, border=GOLD_LINE, size=19)

        p_tot = ease((t - 0.25) / 1.1)
        txt(im, f'€{tot * p_tot:,.2f}', rx + 32, 374, 98, ORANGE if is_r6 else INK, 700)
        txt(im, f'Mean €{mean_v:,.2f}/week   ·   Worst on-time: {worst_ot:.2f}%', rx + 36, 502, 22, MUTED_INK, mono=True, weight=600)

        base_y = 838
        line(im, [(rx + 32, base_y), (rx + 828, base_y)], GOLD_LINE, 2)
        for j, w in enumerate(runs_list):
            bx = rx + 36 + j * 158
            p = ease((t - 0.35 - j * 0.15) / 0.7)
            v = w['score']['marginCents'] / 100.0
            ot = w['score']['onTimeShare'] * 100.0
            bh = 230 * (v / 14500.0) * p
            rect(im, (bx, base_y - bh, bx + 132, base_y), bar_col, outline=ORANGE if not is_r6 else None, r=6)
            if is_r6 and p > 0.05:
                rect(im, (bx, base_y - bh, bx + 132, min(base_y, base_y - bh + 8)), SUNBURST, r=3)
            if p > 0.3:
                txt(im, f'€{v / 1000:.2f}k', bx + 66, base_y - bh - 30, 19, INK, mono=True, weight=700, anchor='ma')
            txt(im, f'W{j + 1}', bx + 66, base_y + 16, 19, INK, 700, anchor='ma')
            txt(im, f'{ot:.1f}%', bx + 66, base_y + 46, 17, ORANGE if is_r6 else MUTED_INK, mono=True, weight=600, anchor='ma')
    return im


def ending(t):
    im = base_canvas('juicy').copy()
    road_layer = im.copy()
    for offset in [-210, 0, 210]:
        line(road_layer, [(1160 + offset, 1080), (1600 + offset, 650), (1400 + offset, 350), (1830 + offset, -50)], ORANGE, 46)
    line(road_layer, [(1160, 1080), (1600, 650), (1400, 350), (1830, -50)], SUNBURST, 6)
    im.paste(road_layer, (0, 0))

    enter(im, 'Guardians', 80, 166, 132, t, .05, color=INK, weight=700)
    enter(im, 'of the', 80, 304, 132, t, .16, color=INK, weight=700)
    enter(im, 'Moonlight.', 80, 442, 132, t, .28, color=INK, weight=700)
    enter(im, 'Win the right work.', 88, 636, 48, t, .42, color=INK, weight=650)
    enter(im, 'Deliver it reliably.', 88, 700, 48, t, .55, color=CARD, weight=650)
    badge(im, 'Gamma confirmed: +€2,031/wk (+20.21%) on v09–v16', 90, 796, color=SUNBURST, bg=INK, size=22)
    badge(im, 'Official Beta rounds: €50.5k & €59.5k (10/10 qualified)', 90, 852, color=INK, bg=CARD, border='#E05500', size=21)

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
    idx = next((i for i, (a, b, _) in enumerate(SCENES) if a <= t < b), 7)
    a, b, _ = SCENES[idx]
    im = FUNCS[idx](t - a)
    dt = t - a
    if idx and dt < .32:
        xx = round(W * ease(dt / .32))
        prev = FUNCS[idx - 1](SCENES[idx - 1][1] - SCENES[idx - 1][0] + dt)
        im.paste(prev.crop((xx, 0, W, H)), (xx, 0))
        rect(im, (max(0, xx - 12), 0, xx + 2, H), ORANGE if idx not in [0, 2, 7] else INK)
    mode = 'juicy' if idx in [0, 2, 7] else 'light'
    chrome(im, idx, t, mode)
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
