#!/usr/bin/env python3
"""Deterministic Cheap-Drive motion film. No simulator or network requests."""
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
W, H, FPS, DURATION = 1920, 1080, 30, 100

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
    (0, 9, 'The challenge'),
    (9, 25, 'Dispatch workflow'),
    (25, 35, 'Observability'),
    (35, 49, 'The full search'),
    (49, 61, 'Qualification constraint'),
    (61, 76, 'Selective route policy'),
    (76, 90, 'Official ranking round'),
    (90, 100, 'Next validation'),
]
GRAPH = json.loads((ROOT / 'data/graph-data.json').read_text())
OFFICIAL = list(csv.DictReader((ROOT / 'data/official-five-weeks.csv').open()))
PAIRED = list(csv.DictReader((ROOT / 'data/per-seed-comparisons.csv').open()))
LONG = [r for r in PAIRED if r['suite'] == 't2' and r['variant'] == 'long700g']
CHART = Image.open(ROOT / 'assets/all-run-margins.png').convert('RGB')
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
        # Radiant juicy yellow-orange: golden marigold (#FFB700) to juicy tangerine (#FF7400)
        g1 = np.exp(-(((xx - 1320) / 820) ** 2 + ((yy - 440) / 580) ** 2))
        g2 = np.exp(-(((xx - 280) / 700) ** 2 + ((yy - 220) / 520) ** 2))
        r = np.full_like(xx, 255.0)
        g = 122 + 54 * g1 + 32 * g2
        b = 8 + 18 * g1 + 10 * g2
    elif kind == 'sunburst':
        # Warm golden-apricot sunburst canvas for comparison/ranking scenes
        g1 = np.exp(-(((xx - 960) / 950) ** 2 + ((yy - 360) / 620) ** 2))
        r = np.full_like(xx, 255.0)
        g = 228 + 18 * g1
        b = 168 + 46 * g1
    else:
        # Sunlit citrus cream with a soft golden-mango glow on the right stage
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


def enter(im, text, x, y, size, t, delay=0, color=INK, weight=600, mono=False):
    p = ease((t - delay) / .8)
    if p <= 0:
        return
    layer = Image.new('RGBA', (W, H))
    txt(layer, text, x, y + (1 - p) * 38, size, color, weight, mono)
    if p < 1:
        layer.putalpha(layer.getchannel('A').point(lambda a: round(a * p)))
    im.paste(layer, (0, 0), layer)


def chrome(im, idx, t, mode='juicy'):
    if mode == 'juicy':
        brand_fg, fg, rule, bar, dot = INK, JUICY_TEXT, '#E55A00', INK, CARD
    else:
        brand_fg, fg, rule, bar, dot = INK, MUTED_INK, GOLD_LINE, ORANGE, ORANGE

    circle(im, 90, 58, 6, dot)
    txt(im, 'Cheap-Drive', 108, 43, 23, brand_fg, 700)
    txt(im, 'Guardians of the Moonlight', 1840, 45, 19, fg, 600, anchor='ra')
    line(im, [(80, 91), (1840, 91)], rule)

    txt(im, SCENES[idx][2], 80, 1008, 19, brand_fg, 600)
    txt(im, 'Bahn / Spread challenge, Junction 2026', 960, 1008, 18, fg, 500, anchor='ma')
    txt(im, f'{int(t):02d}s / {DURATION}s', 1840, 1009, 18, fg, mono=True, anchor='ra')
    rect(im, (80, 1050, 1840, 1054), rule)
    rect(im, (80, 1050, 80 + 1760 * clamp(t / DURATION), 1054), bar)


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


# An abstract route network, deliberately not represented as a geographic map.
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
        if i % 3 == 0:
            px, py = route_point([pts[a], pts[b]], (t * .14 + i * .13) % 1)
            circle(im, px, py, 4, MANGO)
    route = [pts[i] for i in [0, 1, 7, 6, 5, 11, 10]]
    path_partial(im, route, ease(t / 3), ORANGE, 6, glow='#FFE066')
    for i, p in enumerate(pts):
        is_hub = i in [0, 5, 10]
        circle(im, *p, 7 if is_hub else 5, CARD, ORANGE if is_hub else MANGO, 3 if is_hub else 2)
    for i in [0, 5, 10]:
        p = pts[i]
        circle(im, *p, 14 + 8 * ((t * .5 + i * .3) % 1), None, MARIGOLD, 2)
    if active:
        for i in range(3):
            p = (t * .1 + i * .3) % 1
            if p > ease(t / 3) or p < .025 or p > .975:
                continue
            q = route_point(route, p)
            ahead = route_point(route, min(p + .001, 1))
            heading = math.degrees(math.atan2(ahead[1] - q[1], ahead[0] - q[0]))
            car(im, *q, color=INK if i == 0 else ORANGE, scale=.85, angle=heading)
    txt(im, 'Illustrative route network', x + 24, y2 - 34, 17, MUTED_INK, 500)
    return pts


def hero(t):
    # Immediate juicy yellow-orange opening (zero brown!)
    im = base_canvas('juicy').copy()
    network(im, t, (820, 140, 1840, 945), bg=CREAM, border='#E05500')
    enter(im, 'Move cars.', 80, 184, 130, t, .15, color=INK, weight=700)
    enter(im, 'Make', 80, 326, 130, t, .42, color=INK, weight=700)
    enter(im, 'margin.', 80, 468, 130, t, .62, color=INK, weight=700)
    enter(im, 'A dispatcher that learns what to win,', 84, 686, 32, t, 1.15, color=INK, weight=600)
    enter(im, 'what to pay, and when to say no.', 84, 732, 32, t, 1.35, color=INK, weight=500)
    if t > 1.8:
        steps = ['1. Price', '2. Dispatch', '3. Deliver']
        xx = 84
        for i, s in enumerate(steps):
            w = badge(im, s, xx, 838, color=SUNBURST if not i else INK, bg=INK if not i else CARD, border=None if not i else '#E05500', size=21)
            xx += w + 14
    rect(im, (1375, 176, 1805, 250), APRICOT, GOLD_LINE, r=10, width=2)
    circle(im, 1404, 213, 6, ORANGE)
    txt(im, 'One simulated week per run', 1424, 199, 21, INK, 650)
    return im


def dispatcher(t):
    im = base_canvas('citrus').copy()
    enter(im, 'From request to road.', 80, 130, 76, t, color=INK, weight=650)
    enter(im, 'Screen the work. Price each option. Find a driver.', 84, 232, 30, t, .3, color=MUTED_INK, weight=500)
    phase = min(3, int(t / 4))
    q = clamp(t - phase * 4, 0, 3.999)
    labels = ['1. Screen the work', '2. Quote options', '3. Post the gig', '4. Track delivery']
    for i, l in enumerate(labels):
        x = 80 + i * 446
        active = i == phase
        done = i < phase
        rect(
            im,
            (x, 310, x + 418, 366),
            ORANGE if active else (MARIGOLD if done else APRICOT),
            outline=ORANGE if active else GOLD_LINE,
            r=8,
            width=2 if active else 1,
        )
        txt(im, l, x + 20, 324, 21, CARD if active else INK, weight=650 if (active or done) else 500)
    # Left: policy decision desk on crisp sunlit card with golden-orange accents.
    rect(im, (80, 398, 790, 916), CARD, None, r=18)
    rect(im, (80, 398, 790, 520), APRICOT, None, r=18)
    rect(im, (80, 502, 790, 520), APRICOT, None, r=0)
    line(im, [(80, 520), (790, 520)], GOLD_LINE, 2)
    rect(im, (80, 398, 790, 916), None, GOLD_LINE, r=18, width=2)
    txt(im, 'Transfer request: Helsinki to Tampere', 112, 426, 24, INK, 650)
    txt(im, '178 km, single vehicle', 112, 468, 22, MUTED_INK, 500)
    if phase == 1:
        txt(im, 'Delivery window', 112, 548, 19, MUTED_INK, 600)
        txt(im, 'Pricing rule', 735, 548, 19, MUTED_INK, 600, anchor='ra')
        for i, (a, b) in enumerate([('Same day', 'Check slack'), ('Tomorrow', 'Price individually'), ('Later window', 'Price individually')]):
            yy = 598 + i * 72
            txt(im, a, 112, yy, 30, INK, 600)
            txt(im, b, 735, yy + 4, 22, ORANGE if i else MUTED_INK, 650, anchor='ra')
            line(im, [(112, yy + 55), (758, yy + 55)], GOLD_LINE)
        txt(im, 'list × markup × (1 + trust / 100)', 112, 840, 22, ORANGE, mono=True, weight=600)
        txt(im, 'Trust: counted on-time orders, capped at 25.', 112, 880, 20, MUTED_INK)
    elif phase == 0:
        txt(im, 'Feasibility screen', 112, 550, 19, MUTED_INK, 600)
        checks = [('Pickup slack', '≥ 8 hours'), ('Route length', '≤ 500 km'), ('Trade-in', 'None (pass)')]
        for i, (a, b) in enumerate(checks):
            yy = 602 + i * 73
            circle(im, 124, yy + 18, 9, ORANGE)
            txt(im, a, 148, yy, 30, INK, 600)
            txt(im, b, 739, yy + 4, 23, ORANGE, mono=True, weight=600, anchor='ra')
        txt(im, 'Beta baseline admission rules', 112, 850, 22, MUTED_INK)
    elif phase == 2:
        txt(im, 'Offered driver fee vs. typical fee', 112, 550, 19, MUTED_INK, 600)
        p = smooth(q / 3)
        val = mix(.8, 1.5, p)
        txt(im, f'{val:.2f}×', 112, 592, 98, ORANGE, 700)
        yy = 776
        line(im, [(126, yy), (735, yy)], GOLD_TRACK, 10)
        line(im, [(126, yy), (126 + 609 * p, yy)], ORANGE, 10)
        circle(im, 126 + 609 * p, yy, 13, MARIGOLD, outline=ORANGE, width=3)
        txt(im, '0.80× opening', 112, 802, 18, MUTED_INK, mono=True)
        txt(im, '1.50× at warning', 740, 802, 18, ORANGE, mono=True, anchor='ra')
        txt(im, 'Escalate pay as the deadline warning approaches.', 112, 856, 23, INK, 600)
    else:
        txt(im, 'Delivery status', 112, 550, 19, MUTED_INK, 600)
        states = ['Gig published', 'Driver booked', 'Vehicle delivered']
        for i, s in enumerate(states):
            yy = 608 + i * 69
            good = q > i * .75
            circle(im, 125, yy + 17, 10, ORANGE if good else GOLD_TRACK)
            txt(im, s, 154, yy, 31, INK if good else MUTED_INK, 600 if good else 500)
        badge(im, 'Delivered on time' if q > 1.5 else 'In transit', 112, 848, color=CARD if q > 1.5 else INK, bg=ORANGE if q > 1.5 else APRICOT, size=20)
    network(im, t, (845, 398, 1820, 916), bg=CARD, border=GOLD_LINE)
    badge(im, labels[phase][3:], 875, 424, color=INK, bg=MARIGOLD, size=20)
    txt(im, 'Illustrative replay: Beta policy with compressed timing; emergency rescue follows warning.', 84, 952, 19, MUTED_INK)
    return im


def observability(t):
    im = base_canvas('juicy').copy()
    enter(im, 'Every decision,', 80, 168, 76, t, color=INK, weight=700)
    enter(im, 'inspectable.', 80, 260, 76, t, .25, color=INK, weight=700)
    for i, (n, s) in enumerate([('1', 'Capture the event stream.'), ('2', 'Reconcile the ledger.'), ('3', 'Find the failure.')]):
        yy = 462 + i * 106
        if t > .7 + i * .2:
            circle(im, 102, yy + 18, 19, INK, outline=SUNBURST, width=2)
            txt(im, n, 102, yy + 18, 20, SUNBURST, weight=700, anchor='mm')
        enter(im, s, 140, yy - 2, 29, t, .7 + i * .2, color=INK, weight=650)
    txt(im, 'Offline HTML report with replayable evidence.', 84, 835, 24, JUICY_TEXT, 600)
    # Slow pan across the actual repository screenshot, no browser required.
    crop_top = mix(0., 370., smooth((t - 2) / 8))
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
    txt(im, 'Tooling example; displayed scores come from the fixed baseline run.', 755, 958, 18, INK, 600)
    return im


@lru_cache(maxsize=1)
def graph_small():
    # Tint the chart's white matte seamlessly into sunlit citrus cream (#FFF8EB)
    tinted = ImageChops.multiply(CHART, Image.new('RGB', CHART.size, CREAM))
    return tinted.resize((1790, 872), Image.Resampling.LANCZOS)


def experiments(t):
    im = base_canvas('chart').copy()
    if t < 3.2:
        enter(im, 'We kept the whole search.', 80, 144, 84, t, weight=700, color=INK)
        count = round(1022 * ease((t - .15) / 1.1))
        txt(im, f'{count:,}', 80, 314, 220, ORANGE, 700)
        txt(im, 'completed practice worlds', 88, 594, 44, INK, 650)
        txt(im, '34 seed and level scenarios across repeated seeds.', 90, 676, 29, MUTED_INK)
        badge(im, 'Failed experiments stay in the record', 88, 808, color=INK, bg=MARIGOLD, border=ORANGE, size=24)
        rect(im, (1080, 320, 1765, 810), APRICOT, outline=GOLD_LINE, r=18, width=2)
        for i in range(70):
            x = 1138 + (i % 10) * 60
            y = 374 + (i // 10) * 60
            if i / 70 < ease(t / 2):
                if i % 11 == 0:
                    line(im, [(x - 7, y - 7), (x + 7, y + 7)], DANGER, 4)
                    line(im, [(x - 7, y + 7), (x + 7, y - 7)], DANGER, 4)
                else:
                    circle(im, x, y, 9, ORANGE if i % 2 == 0 else MANGO)
    else:
        # Complete original figure remains visible, preserving all axes and caveats.
        im.paste(graph_small(), (65, 112))
        if t < 3.9:
            im = Image.blend(experiments(3.19), im, smooth((t - 3.2) / .7))
        if t > 4.6:
            # A juicy orange focus outline scans the family groups; x is not a time axis.
            frac = smooth((t - 4.6) / 8.6)
            group = mix(3, 13, frac)
            x = 199 + group * 115.8
            rect(im, (x, 277, x + 110, 798), None, ORANGE, r=4, width=3)
    return im


def failure(t):
    im = base_canvas('sunburst').copy()
    enter(im, 'More wins can lose the week.', 80, 134, 77, t, color=INK, weight=700)
    txt(im, 'Matched stress seed: gamma-t04, level 8', 85, 250, 24, MUTED_INK, 600)
    badge(im, 'Deadline warnings: 17 to 54', 1505, 242, color=CARD, bg=DANGER, size=20, mono=True)
    # Two exact observed outcomes, with the qualification gate across both bars.
    entries = [
        (80, '500 km max route, 30% win target', 232, 95.69, 10245.77, ORANGE, ORANGE, True),
        (1000, '600 km max route, 38% win target', 294, 89.80, 9960.69, DANGER, DANGER, False),
    ]
    for x, label, wins, ot, margin, text_c, bar_c, ok in entries:
        rect(im, (x, 332, x + 840, 962), CARD, outline=GOLD_LINE if ok else DANGER, r=18, width=2)
        enter(im, label, x + 32, 360, 25, t, .4, color=text_c, weight=650)
        enter(im, str(wins), x + 32, 404, 118, t, .65, color=INK, weight=700)
        enter(im, 'orders won', x + 275, 480, 28, t, .85, color=MUTED_INK, weight=500)
        p = ease((t - 1) / 1.5)
        enter(im, f'{ot:.2f}%', x + 32, 562, 96, t, 1.25, color=text_c, weight=700)
        enter(im, 'on time', x + 435, 622, 26, t, 1.45, color=MUTED_INK, weight=500)
        bx = x + 32
        bw = 776
        rect(im, (bx, 726, bx + bw, 754), APRICOT, outline=GOLD_LINE, r=8)
        rect(im, (bx, 726, bx + bw * (ot - 80) / 20 * p, 754), bar_c, r=8)
        gate_x = bx + bw * 0.5
        line(im, [(gate_x, 704), (gate_x, 776)], INK, 3)
        txt(im, '90% gate', gate_x, 788, 18, INK, mono=True, weight=600, anchor='ma')
        txt(im, '80%', bx, 788, 18, MUTED_INK, mono=True)
        txt(im, '100%', bx + bw, 788, 18, MUTED_INK, mono=True, anchor='ra')
        enter(im, f'€{margin:,.2f} margin', x + 32, 838, 31, t, 3.3, color=INK, weight=650)
    if t > 3:
        badge(im, 'Qualified', 112, 898, color=INK, bg=MARIGOLD, size=20)
        badge(im, 'Unqualified', 1032, 898, color=CARD, bg=DANGER, size=20)
    enter(im, '0.20 pp below the 90% gate', 1245, 906, 22, t, 5.5, color=DANGER, weight=650)
    return im


def gain(t):
    im = base_canvas('citrus').copy()
    enter(im, 'Choose better work.', 80, 136, 88, t, weight=700, color=INK)
    enter(im, 'Selective longer routes (up to 700 km)', 84, 250, 33, t, .3, color=MUTED_INK, weight=500)
    p = ease((t - .7) / 1.8)
    txt(im, f'+€{1232 * p:,.0f}', 76, 338, 164, ORANGE, 700)
    txt(im, 'mean margin gain per week (rounded)', 86, 544, 31, MUTED_INK, 500)
    badge(im, '+10.93% across 8 matched seeds', 84, 620, color=INK, bg=MARIGOLD, border=ORANGE, size=21)

    # Right panel: Bars preserve the zero baseline; labels provide exact means.
    rect(im, (905, 316, 1840, 892), CARD, outline=GOLD_LINE, r=18, width=2)
    chart_x, chart_y = 945, 344
    for i, (label, val, c) in enumerate([('Baseline (500 km)', 11268.68, MARIGOLD), ('Selective 700 km policy', 12500.43, ORANGE)]):
        yy = chart_y + i * 156
        txt(im, label, chart_x, yy, 27, INK, weight=650 if i else 500)
        rect(im, (chart_x, yy + 44, chart_x + 790 * (val / 14000) * p, yy + 92), c, r=6)
        txt(im, f'€{val:,.2f}', chart_x, yy + 100, 23, INK, mono=True, weight=600)

    # Per-seed gain bars with golden tracks so all 8 positions are structured from the start.
    txt(im, 'Per-seed weekly gain (8 matched seeds)', chart_x, 668, 21, MUTED_INK, weight=600)
    line(im, [(chart_x, 796), (chart_x + 8 * 96 - 32, 796)], GOLD_LINE, 2)
    for i, row in enumerate(LONG):
        x = chart_x + i * 96
        rect(im, (x, 726, x + 58, 796), APRICOT, r=4)
        txt(im, f'S{i + 1}', x + 29, 804, 17, MUTED_INK, mono=True, anchor='ma')
        pp = ease((t - 2.2 - i * .45) / .75)
        if pp:
            h = 66 * float(row['delta_eur']) / 2400 * pp
            rect(im, (x, 796 - h, x + 58, 796), ORANGE, outline=MANGO, r=4)
    enter(im, '8/8 higher margin, 8/8 qualified', chart_x, 840, 25, t, 6.2, color=INK, weight=650)
    txt(im, 'Later delivery windows + ≥24h pickup slack', 84, 744, 28, INK, 600)
    txt(im, '+ cap on unbooked long-distance work', 84, 786, 28, INK, 600)
    line(im, [(80, 906), (1840, 906)], GOLD_LINE)
    txt(im, 'Seeds gamma-t01…08  /  Development comparison against 500 km, 30% target baseline', 84, 922, 20, MUTED_INK)
    enter(im, 'Mean on-time: 96.35% to 95.51% (worst seed: 92.98%). Unseen-week validation still needed.', 84, 954, 20, t, 8.5, color=MUTED_INK, weight=500)
    return im


def result(t):
    im = base_canvas('sunburst').copy()
    enter(im, 'Five official weeks.', 80, 130, 81, t, color=INK, weight=700)
    txt(im, 'Saved ranking round  /  Beta policy, level 8  /  All five weeks qualified', 84, 236, 24, MUTED_INK, 600)
    total = sum(float(r['margin_eur']) * ease((t - 1 - i * .7) / 1.8) for i, r in enumerate(OFFICIAL))
    txt(im, f'€{total:,.2f}', 75, 294, 156, ORANGE, 700)
    txt(im, 'gross margin in simulated euros, summed across five official weeks', 85, 492, 30, MUTED_INK, 500)
    vals = [float(r['margin_eur']) for r in OFFICIAL]
    line(im, [(85, 825), (85 + 4 * 260 + 197, 825)], GOLD_LINE, 2)
    for i, (v, r) in enumerate(zip(vals, OFFICIAL)):
        x = 85 + i * 260
        p = ease((t - 1 - i * .7) / 1.8)
        top = 825 - 220 * v / 14000 * p
        rect(im, (x, top, x + 197, 825), ORANGE, r=6)
        if p > 0.05:
            rect(im, (x, top, x + 197, min(825, top + 8)), MARIGOLD, r=3)
        enter(im, f'€{v:,.2f}', x, top - 40, 22, t, 1 + i * .7, color=INK, mono=True, weight=600)
        txt(im, f'Week {i + 1}', x, 846, 21, INK, 650)
        enter(im, f'{float(r["on_time_share"]) * 100:.2f}% on time', x, 880, 20, t, 3 + i * .7, color=ORANGE, mono=True, weight=600)
        if 6 <= t < 13 and min(4, int((t - 6) / 1.4)) == i:
            rect(im, (x - 9, top - 8, x + 206, 834), None, INK, r=10, width=3)
    rect(im, (1425, 590, 1840, 916), ORANGE, outline=JUICY_LINE, r=18, width=2)
    txt(im, '95.49%', 1465, 634, 68, SUNBURST, 700)
    txt(im, 'worst weekly', 1468, 728, 27, CARD, 600)
    txt(im, 'on-time delivery', 1468, 768, 27, CARD, 600)
    txt(im, '90.00% required to qualify', 1468, 832, 20, APRICOT, 500)
    txt(im, 'Historical ranking result; separate from the competition final and the route-policy experiment.', 85, 952, 21, MUTED_INK)
    return im


def ending(t):
    im = base_canvas('juicy').copy()
    # Warm yellow-orange highway geometry behind the typography
    road_layer = im.copy()
    for offset in [-210, 0, 210]:
        line(road_layer, [(1160 + offset, 1080), (1600 + offset, 650), (1400 + offset, 350), (1830 + offset, -50)], ORANGE, 46)
    line(road_layer, [(1160, 1080), (1600, 650), (1400, 350), (1830, -50)], SUNBURST, 6)
    im.paste(road_layer.crop((0, 108, W, 990)), (0, 108))

    enter(im, 'Cheap-', 80, 168, 182, t, .1, color=INK, weight=700)
    enter(im, 'Drive.', 80, 358, 182, t, .35, color=INK, weight=700)
    enter(im, 'Win the right work.', 88, 628, 50, t, .8, color=INK, weight=650)
    enter(im, 'Deliver it reliably.', 88, 696, 50, t, 1.1, color=CARD, weight=650)
    badge(im, 'Next step: validate on unseen weeks', 90, 810, color=SUNBURST, bg=INK, size=23)
    txt(im, 'github.com/KotvicCodes/Cheap-Drive', 90, 914, 26, INK, mono=True, weight=600)
    # Travel along the final road, rather than holding a static end card.
    road = [(1370, 1020), (1690, 650), (1490, 350), (1825, 15)]
    p = (.18 + t * .052) % 1
    pos = route_point(road, p)
    ahead = route_point(road, min(p + .001, 1))
    heading = math.degrees(math.atan2(ahead[1] - pos[1], ahead[0] - pos[0]))
    car(im, *pos, INK, 3, heading)
    return im


FUNCS = [hero, dispatcher, observability, experiments, failure, gain, result, ending]


def frame(t):
    idx = next((i for i, (a, b, _) in enumerate(SCENES) if a <= t < b), 7)
    a, b, _ = SCENES[idx]
    im = FUNCS[idx](t - a)
    dt = t - a
    # Wipe the content only. The outgoing scene keeps moving under the wipe.
    if idx and dt < .42:
        xx = round(W * ease(dt / .42))
        prev = FUNCS[idx - 1](SCENES[idx - 1][1] - SCENES[idx - 1][0] + dt)
        im.paste(prev.crop((xx, 108, W, 990)), (xx, 108))
        rect(im, (max(0, xx - 12), 108, xx + 2, 990), ORANGE if idx not in [0, 2, 7] else INK)
    mode = 'juicy' if idx in [0, 2, 7] else 'light'
    chrome(im, idx, t, mode)
    return im


def soundtrack(path):
    """Original 120 BPM instrumental; seeded percussion, no third-party samples."""
    sr = 44100
    n = sr * DURATION
    audio = np.zeros((n, 2), dtype=np.float32)
    rng = np.random.default_rng(20261114)

    def add(start, sig, vol=.1, pan=0):
        off = round(start * sr)
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
            env = np.minimum(ts / .4, 1) * np.minimum((sec - ts) / .6, 1)
            return ((np.sin(2 * np.pi * f * ts) + .25 * np.sin(2 * np.pi * f * 1.003 * ts) + .12 * np.sin(4 * np.pi * f * ts)) * env).astype(np.float32)
        env = (1 - np.exp(-ts * 180)) * np.exp(-ts * 5)
        return ((np.sin(2 * np.pi * f * ts) + .22 * np.sin(4 * np.pi * f * ts) + .08 * np.sin(6 * np.pi * f * ts)) * env).astype(np.float32)

    chords = [[50, 53, 57, 60], [46, 50, 53, 57], [53, 57, 60, 65], [48, 52, 55, 60]]
    for bar in range(50):
        start = bar * 2
        ch = chords[(bar // 2) % 4]
        for j, m in enumerate(ch):
            add(start, note(m + 12, 2.4, 'pad'), .023, (-.6 + j * .4))
        for beat in range(4):
            add(start + beat * .5, note(ch[0] - 12, .43), .105)
            if 4 <= bar < 47:
                for sub in range(2):
                    k = beat * 2 + sub
                    add(start + k * .25, note(ch[[0, 2, 1, 3, 2, 1, 3, 2][k]] + 24, .45), .028, (-1 if k % 2 else 1) * .55)
        if 4 <= bar < 47:
            for beat in range(4):
                ts = np.arange(round(sr * .28)) / sr
                kick = np.sin(2 * np.pi * (48 * ts + 6 * (1 - np.exp(-ts * 35)))) * np.exp(-ts * 18)
                add(start + beat * .5, kick, .19)
                if beat % 2:
                    sn = rng.standard_normal(len(ts)) * np.exp(-ts * 27)
                    sn = np.diff(np.r_[0, sn])
                    add(start + beat * .5, sn, .023)
            for j in range(8):
                ts = np.arange(round(sr * .07)) / sr
                noise = rng.standard_normal(len(ts))
                noise = np.diff(np.r_[0, noise]) * np.exp(-ts * 90)
                add(start + j * .25, noise, .011 if j % 2 else .006, (-1 if j % 2 else 1) * .3)
    for cut in [9, 25, 35, 49, 61, 76, 90]:
        ts = np.arange(sr) / sr
        noise = rng.standard_normal(sr)
        noise = np.convolve(noise, np.ones(12) / 12, mode='same')
        add(cut - .85, noise * np.sin(np.pi * ts) ** 2, .06)
    for cut in [9, 13, 17, 21]:
        add(cut + .08, note(86, .15), .03, .3)
    tt = np.arange(n) / sr
    fade = np.minimum(tt / 2, 1) * np.minimum((DURATION - tt) / 3.5, 1)
    audio *= fade[:, None]
    audio = np.tanh(audio * 1.6) * .8
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes((audio * 32767).astype('<i2').tobytes())


def stills(out):
    times = [3.5, 11, 15, 19, 23, 29, 36.8, 43, 54, 67, 82, 95]
    thumbs = []
    for i, t in enumerate(times):
        im = frame(t)
        im.save(out / f'frame-{i + 1:02d}-{t:04.1f}s.png')
        thumb = im.resize((640, 360), Image.Resampling.LANCZOS)
        tile = Image.new('RGB', (640, 396), '#FF8800')
        tile.paste(thumb, (0, 0))
        txt(tile, f'{t:05.1f}s', 16, 366, 18, INK, mono=True, weight=600)
        thumbs.append(tile)
    sheet = Image.new('RGB', (1920, 1584), '#FF7700')
    for i, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((i % 3) * 640, (i // 3) * 396))
    sheet.save(out / 'contact-sheet.jpg', quality=93)
    frame(4).save(out / 'poster.png')


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
    assert GRAPH['summary']['completed_practice'] == 1022
    assert sum(float(r['margin_eur']) for r in OFFICIAL) == 50541.26
    assert all(r['qualified'] == 'True' for r in OFFICIAL)
    assert min(float(r['on_time_share']) for r in OFFICIAL) > .9549
    assert len([r for r in GRAPH['runs'] if r['family'] != 'Official ranking']) == 1022
    assert len(LONG) == 8 and all(r['qualified'] == 'True' and float(r['delta_eur']) > 0 for r in LONG)
    assert round(sum(float(r['delta_eur']) for r in LONG) / 8, 2) == 1231.75
    assert round(sum(float(r['margin_eur']) for r in LONG) / 8, 2) == 12500.43
    stress = next(r for r in PAIRED if r['suite'] == 't1' and r['variant'] == 'km600-t38' and r['seed'] == 'gamma-t04')
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
