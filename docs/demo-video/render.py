#!/usr/bin/env python3
"""Deterministic 60-second Cheap-Drive motion film combining the best of v1 and v2.

No simulator or network requests.
"""
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
W, H, FPS, DURATION = 1920, 1080, 30, 66

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
    (0, 5),
    (5, 13),
    (13, 20),
    (20, 26),
    (26, 33),
    (33, 40),
    (40, 47),
    (47, 53),
    (53, 61),
    (61, 66),
]

GRAPH = json.loads((ROOT / 'data/graph-data.json').read_text())
RUN_DATA = json.loads((ROOT / 'data/run-data.json').read_text())
CHART_DATA = json.loads((ROOT / 'data/chart-data.json').read_text())
PAIRED_WEEKS = list(csv.DictReader((ROOT / 'data/paired-weeks.csv').open()))
CONFIRM_WEEKS = [r for r in PAIRED_WEEKS if r['comparison'] == 'Revised candidate: fresh confirmation']
OFFICIAL_ROUNDS = list(csv.DictReader((ROOT / 'data/official-rounds.csv').open()))
OFFICIAL_RUNS = [r for r in GRAPH['runs'] if r['family'] == 'Official ranking']
ROUND5_RUNS = OFFICIAL_RUNS[:5]
ROUND6_RUNS = OFFICIAL_RUNS[5:10]
PAIRED_OLD = list(csv.DictReader((ROOT / 'data/per-seed-comparisons.csv').open()))

DELTA_CONFIRM = [
    ('W1', 8178.10, 9711.04, 1532.94, 96.60, 95.74),
    ('W2', 13468.72, 15218.71, 1749.99, 97.81, 96.97),
    ('W3', 12000.00, 14376.53, 2376.53, 98.04, 97.00),
    ('W4', 14357.99, 16230.16, 1872.17, 98.51, 97.77),
    ('W5', 11063.43, 13499.61, 2436.18, 97.18, 96.18),
    ('W6', 16630.83, 18366.42, 1735.59, 97.05, 94.78),
    ('W7', 12015.18, 11462.67, -552.51, 93.68, 91.12),
    ('W8', 10586.94, 11575.92, 988.98, 97.24, 95.27),
    ('W9', 13601.21, 15608.46, 2007.25, 98.53, 98.57),
    ('W10', 13962.56, 17344.20, 3381.64, 97.82, 97.54),
    ('W11', 10128.71, 13098.79, 2970.08, 97.08, 96.57),
    ('W12', 13711.55, 16020.64, 2309.09, 98.05, 95.85),
    ('W13', 10508.26, 12712.21, 2203.95, 96.80, 97.32),
    ('W14', 10428.83, 11161.66, 732.83, 94.07, 93.33),
    ('W15', 13944.07, 14206.55, 262.48, 94.77, 91.64),
    ('W16', 9533.15, 10967.42, 1434.27, 96.34, 96.21),
    ('W17', 10011.06, 9894.92, -116.14, 96.58, 94.23),
    ('W18', 14309.52, 16115.66, 1806.14, 95.62, 95.25),
    ('W19', 11391.33, 13872.46, 2481.13, 98.81, 96.47),
]

CHART_ALL = Image.open(ROOT / 'assets/all-run-margins.png').convert('RGB')
CHART_STAGES = Image.open(ROOT / 'assets/learning-stages.png').convert('RGB')
LIVE_DEMO = Image.open(ROOT / 'assets/live-demo-overview.png').convert('RGB')
LIVE_DEMO_SCROLL = Image.open(ROOT / 'assets/live-demo-scroll.png').convert('RGB')
LOGO_BADGE = Image.open(ROOT / 'assets/cheap-drive-badge.png').convert('RGBA').resize((124, 124), Image.Resampling.LANCZOS)
LOGO_BADGE_SM = Image.open(ROOT / 'assets/cheap-drive-badge.png').convert('RGBA').resize((76, 76), Image.Resampling.LANCZOS)
QR_CODE = Image.open(ROOT / 'assets/qr-live-demo.png').convert('RGB').resize((268, 268), Image.Resampling.LANCZOS)
GREEK_FONT = ImageFont.truetype(str(ROOT / 'assets/DejaVuSans-Bold.ttf'), 26)


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


def badge(im, text, x, y, color=INK, bg=MARIGOLD, border=None, size=22, mono=False, weight=650, fixed_w=None):
    f = font(size, weight, mono)
    b = f.getbbox(str(text))
    cap_b = f.getbbox('H')
    pad_x = max(18, round(size * 0.72))
    w = fixed_w if fixed_w is not None else ((b[2] - b[0]) + 2 * pad_x)
    h = max(36, round(size * 1.90))
    rect(im, (x, y, x + w, y + h), bg, outline=border, r=max(8, round(h * 0.24)), width=2 if border else 0)
    tx = x + w / 2 - (b[0] + b[2]) / 2
    ty = y + h / 2 - (cap_b[1] + cap_b[3]) / 2
    txt(im, text, tx, ty, size, color, weight=weight, mono=mono)
    return w


def enter(im, text, x, y, size, t, delay=0, color=INK, weight=600, mono=False, span=0.38):
    p = ease((t - delay) / span)
    if p <= 0:
        return
    layer = Image.new('RGBA', (W, H))
    txt(layer, text, x, y + (1 - p) * 28, size, color, weight, mono)
    if p < 1:
        layer.putalpha(layer.getchannel('A').point(lambda a: round(a * p)))
    im.paste(layer, (0, 0), layer)


def enter_model_hdr(im, model_prefix, rest_text, x, y, size, t, delay=0, model_color=ORANGE, rest_color=INK, weight=700, span=0.38):
    p = ease((t - delay) / span)
    if p <= 0:
        return
    layer = Image.new('RGBA', (W, H))
    yy = y + (1 - p) * 28
    txt(layer, model_prefix, x, yy, size, model_color, weight)
    pw = font(size, weight).getbbox(model_prefix)[2]
    txt(layer, rest_text, x + pw, yy, size, rest_color, weight)
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


def path_segment(im, points, p0, p1, color=ORANGE, width=5, glow=None):
    """Draw a sub-segment [p0, p1] of a polyline for live directional trails."""
    p0, p1 = clamp(p0), clamp(p1)
    if p1 <= p0 or len(points) < 2:
        return
    ds = [math.dist(points[i], points[i + 1]) for i in range(len(points) - 1)]
    total = sum(ds)
    if total <= 0:
        return
    d0, d1 = total * p0, total * p1
    pts = [route_point(points, p0)]
    acc = 0.0
    for i, d in enumerate(ds):
        nxt = acc + d
        if d0 < nxt < d1:
            pts.append(points[i + 1])
        acc = nxt
    pts.append(route_point(points, p1))
    if len(pts) > 1:
        if glow:
            line(im, pts, glow, width + 6)
        line(im, pts, color, width)


def car(im, x, y, color=INK, scale=1, angle=None):
    if angle is not None:
        sprite = Image.new('RGBA', (int(64 * scale), int(64 * scale)))
        car(sprite, 32 * scale, 32 * scale, color, scale, None)
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

MAP_TRIPS = [
    ([8, 7, 6, 5, 11, 10], 0.04, 0.14, INK, True),
    ([0, 1, 2, 3, 4, 11], 0.05, 0.14, ORANGE, True),
    ([0, 2, 9, 10, 11, 5], 0.03, 0.14, INK, True),
    ([5, 6, 7, 3, 2, 1, 8], 0.06, 0.13, ORANGE, True),
    ([10, 9, 4, 3, 7, 8, 1], 0.04, 0.13, INK, True),
]


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
        line(im, [pts[a], pts[b]], '#FFC266', 3)
    if active:
        for t_idx, (nodes, p0, spd, c_col, is_prim) in enumerate(MAP_TRIPS):
            r_path = [pts[k] for k in nodes]
            p = clamp(p0 + t * spd)
            path_partial(im, r_path, p, ORANGE, 5)
    for i, p in enumerate(pts):
        is_hub = i in [0, 5, 10, 3, 8]
        circle(im, *p, 7 if is_hub else 5, CARD, ORANGE if is_hub else MANGO, 3 if is_hub else 2)
    if active:
        for t_idx, (nodes, p0, spd, c_col, is_prim) in enumerate(MAP_TRIPS):
            r_path = [pts[k] for k in nodes]
            p = clamp(p0 + t * spd)
            if 0.02 < p < 0.98:
                q = route_point(r_path, p)
                ahead = route_point(r_path, min(p + .006, 1.0))
                heading = math.degrees(math.atan2(ahead[1] - q[1], ahead[0] - q[0]))
                car(im, *q, color=c_col, scale=.86, angle=heading)
    return pts


# Accurate Natural Earth 50m (lat, lon) outline of mainland Finland
FINLAND_BORDER = [
    (65.805, 24.155), (66.253, 23.700), (66.481, 23.701), (66.811, 23.989), (67.129, 23.642),
    (67.423, 23.734), (67.460, 23.455), (67.875, 23.502), (67.954, 23.639), (68.367, 22.854),
    (68.521, 21.997), (69.037, 20.622), (69.042, 21.066), (69.214, 21.066), (69.274, 21.594),
    (68.720, 22.411), (68.649, 23.324), (68.806, 23.854), (68.593, 24.941), (68.821, 25.249),
    (68.990, 25.748), (69.653, 26.012), (69.915, 26.525), (69.906, 27.128), (70.062, 27.890),
    (69.823, 28.412), (69.671, 29.142), (69.473, 29.333), (69.177, 28.846), (69.022, 28.966),
    (68.904, 28.414), (68.814, 28.778), (68.488, 28.471), (68.190, 28.685), (68.062, 29.344),
    (67.668, 29.988), (66.892, 29.066), (65.787, 30.087), (65.682, 30.095), (65.625, 29.716),
    (65.569, 29.819), (65.249, 29.608), (65.145, 29.827), (64.968, 29.604), (64.804, 29.783),
    (64.733, 30.110), (64.524, 29.987), (64.366, 30.108), (64.237, 30.488), (64.077, 30.526),
    (63.735, 29.992), (63.208, 31.181), (62.885, 31.534), (62.481, 31.187), (61.288, 29.252),
    (60.536, 27.798), (60.465, 27.462), (60.543, 27.205), (60.413, 26.535), (60.625, 26.569),
    (60.424, 26.378), (60.474, 25.956), (60.342, 26.036), (60.268, 25.758), (60.333, 25.656),
    (60.114, 24.600), (60.021, 24.446), (59.986, 23.464), (59.816, 23.021), (60.022, 23.198),
    (60.210, 22.912), (60.057, 22.750), (60.029, 22.463), (60.381, 22.585), (60.505, 21.854),
    (60.594, 21.805), (60.531, 21.613), (60.596, 21.436), (60.967, 21.361), (61.592, 21.606),
    (61.990, 21.256), (62.277, 21.343), (62.623, 21.104), (63.033, 21.474), (63.039, 21.651),
    (63.204, 21.545), (63.310, 22.320), (63.438, 22.243), (63.648, 22.532), (64.041, 23.599),
    (64.801, 24.558), (64.884, 24.942), (64.860, 25.288), (65.479, 25.348), (65.671, 24.675),
    (65.859, 24.628), (65.780, 24.404), (65.812, 24.238), (65.805, 24.155),
]

# All 30 real simulator places in Finland
FINLAND_PLACES = {
    'helsinki': (60.2300, 24.9384, 'Helsinki', True),
    'espoo': (60.2055, 24.6559, 'Espoo', False),
    'vantaa': (60.2934, 25.0378, 'Vantaa', False),
    'porvoo': (60.3932, 25.6650, 'Porvoo', False),
    'kotka': (60.4664, 26.9458, 'Kotka', False),
    'salo': (60.3833, 23.1333, 'Salo', False),
    'turku': (60.4518, 22.2666, 'Turku', True),
    'raisio': (60.4859, 22.1689, 'Raisio', False),
    'hyvinkaa': (60.6311, 24.8616, 'Hyvinkää', False),
    'hameenlinna': (60.9959, 24.4643, 'Hämeenlinna', False),
    'lahti': (60.9827, 25.6612, 'Lahti', False),
    'kouvola': (60.8679, 26.7042, 'Kouvola', False),
    'lappeenranta': (61.0587, 28.1887, 'Lappeenranta', False),
    'rauma': (61.1287, 21.5113, 'Rauma', False),
    'pori': (61.4851, 21.7975, 'Pori', False),
    'lempaala': (61.3139, 23.7529, 'Lempäälä', False),
    'tampere': (61.4978, 23.7610, 'Tampere', True),
    'mikkeli': (61.6886, 27.2723, 'Mikkeli', False),
    'savonlinna': (61.8699, 28.8799, 'Savonlinna', False),
    'jyvaskyla': (62.2426, 25.7473, 'Jyväskylä', True),
    'joensuu': (62.6010, 29.7636, 'Joensuu', True),
    'seinajoki': (62.7903, 22.8403, 'Seinäjoki', False),
    'kuopio': (62.8924, 27.6770, 'Kuopio', True),
    'vaasa': (63.0951, 21.6165, 'Vaasa', True),
    'kokkola': (63.8385, 23.1307, 'Kokkola', False),
    'ylivieska': (64.0731, 24.5395, 'Ylivieska', False),
    'kajaani': (64.2273, 27.7285, 'Kajaani', False),
    'oulu': (65.0121, 25.4651, 'Oulu', True),
    'kemi': (65.7364, 24.5637, 'Kemi', False),
    'rovaniemi': (66.5039, 25.7294, 'Rovaniemi', True),
    'sodankyla': (67.4160, 26.5890, 'Sodankylä', False),
    'ivalo': (68.6576, 27.5397, 'Ivalo', True),
}

FINLAND_ROADS = [
    ('ivalo', 'rovaniemi'),
    ('rovaniemi', 'oulu'),
    ('oulu', 'jyvaskyla'),
    ('oulu', 'kuopio'),
    ('vaasa', 'jyvaskyla'),
    ('vaasa', 'tampere'),
    ('kuopio', 'joensuu'),
    ('kuopio', 'jyvaskyla'),
    ('joensuu', 'jyvaskyla'),
    ('jyvaskyla', 'tampere'),
    ('jyvaskyla', 'helsinki'),
    ('tampere', 'turku'),
    ('tampere', 'helsinki'),
    ('turku', 'helsinki'),
]

FINLAND_TRIPS = [
    (['ivalo', 'rovaniemi', 'oulu', 'jyvaskyla'], 0.04, 0.19, ORANGE, True),
    (['vaasa', 'tampere', 'helsinki'], 0.05, 0.19, ORANGE, True),
    (['joensuu', 'kuopio', 'oulu'], 0.06, 0.19, ORANGE, True),
    (['turku', 'helsinki', 'jyvaskyla', 'kuopio'], 0.04, 0.19, ORANGE, True),
    (['oulu', 'jyvaskyla', 'tampere', 'turku'], 0.05, 0.19, ORANGE, True),
]


def finland_map(im, t, box=(820, 80, 1840, 1000), zoom_south=False, bg=CARD, border=GOLD_LINE):
    x, y, x2, y2 = box
    rect(im, box, bg, outline=border, r=20, width=2)
    w, h = x2 - x, y2 - y

    for gx in range(int(x) + 34, int(x2) - 20, 48):
        for gy in range(int(y) + 34, int(y2) - 20, 48):
            circle(im, gx, gy, 1, '#FFD480')

    min_lat, max_lat = (59.65, 65.40) if zoom_south else (59.65, 70.25)
    min_lon, max_lon = (20.80, 30.50) if zoom_south else (20.10, 31.80)
    k = math.cos(math.radians(64.0))
    span_x = (max_lon - min_lon) * k
    span_y = max_lat - min_lat
    pad = 28
    scale = min((w - 2 * pad) / span_x, (h - 2 * pad) / span_y)
    ox = x + (w - span_x * scale) / 2
    oy = y + (h - span_y * scale) / 2

    def proj(lat, lon):
        return (ox + (lon - min_lon) * k * scale, y2 - (oy - y) - (lat - min_lat) * scale)

    map_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(map_layer)
    poly_pts = [(round(px), round(py)) for lat, lon in FINLAND_BORDER for px, py in [proj(lat, lon)]]
    d.polygon(poly_pts, fill='#FFE5A3', outline=MANGO, width=3)

    cropped = map_layer.crop((x + 4, y + 4, x2 - 4, y2 - 4))
    im.paste(cropped, (x + 4, y + 4), cropped)

    def in_box(pt):
        return (x + 16) <= pt[0] <= (x2 - 16) and (y + 16) <= pt[1] <= (y2 - 16)

    for u, v in FINLAND_ROADS:
        pu = proj(*FINLAND_PLACES[u][:2])
        pv = proj(*FINLAND_PLACES[v][:2])
        if in_box(pu) and in_box(pv):
            line(im, [pu, pv], '#FFC266', 3)

    # Recolor the road between the two cities from the origin city to the car as it goes
    for c_idx, (corr, p0, spd, col, is_prim) in enumerate(FINLAND_TRIPS):
        pts = [proj(*FINLAND_PLACES[pid][:2]) for pid in corr if in_box(proj(*FINLAND_PLACES[pid][:2]))]
        if len(pts) < 2:
            continue
        p = clamp(p0 + t * spd)
        path_partial(im, pts, p, ORANGE, 5)

    for pid, (lat, lon, name, is_major) in FINLAND_PLACES.items():
        if not is_major:
            continue
        pt = proj(lat, lon)
        if not in_box(pt):
            continue
        circle(im, *pt, 6, CARD, ORANGE, 3)
        lx_off = -12 if pid in ('vaasa', 'turku') else 12
        anc = 'rm' if pid in ('vaasa', 'turku') else 'lm'
        txt(im, name, pt[0] + lx_off, pt[1], 17, INK, weight=700, anchor=anc)

    for c_idx, (corr, p0, spd, col, is_prim) in enumerate(FINLAND_TRIPS):
        pts = [proj(*FINLAND_PLACES[pid][:2]) for pid in corr if in_box(proj(*FINLAND_PLACES[pid][:2]))]
        if len(pts) < 2:
            continue
        p = clamp(p0 + t * spd)
        if 0.02 < p < 0.98:
            q = route_point(pts, p)
            ahead = route_point(pts, min(p + 0.008, 1.0))
            heading = math.degrees(math.atan2(ahead[1] - q[1], ahead[0] - q[0]))
            car(im, *q, color=INK if c_idx % 2 == 0 else ORANGE, scale=0.72, angle=heading)


# ---------------------------------------------------------------------------
# Slide 1 (0–5s): Keep old version as-is
# ---------------------------------------------------------------------------
def hero(t):
    im = base_canvas('juicy').copy()
    finland_map(im, t, (950, 64, 1840, 1016), zoom_south=False, bg=CARD, border='#E05500')
    im.paste(LOGO_BADGE, (80, 132), LOGO_BADGE)
    enter(im, 'Cheap-Drive', 232, 134, 102, t, .02, color='#231A14', weight=700)
    enter(im, 'Move cars,', 80, 415, 130, t, .12, color=INK, weight=700)
    enter(im, 'Win margins', 80, 575, 130, t, .22, color=INK, weight=700)
    return im


# ---------------------------------------------------------------------------
# Slide 2 (5–13s): Sol header + Greek letters in circles + vertical score car
# ---------------------------------------------------------------------------
def evolution(t):
    im = base_canvas('sunburst').copy()
    enter(im, 'Prototype. Test. Loop. Repeat.', 80, 80, 84, t, .05, color=INK, weight=700)
    txt(im, 'Each dot ≈10 practice runs', 84, 188, 24, MUTED_INK, 600)

    # 3 headline summary pills from Slide 3 of the updated presentation,
    # right-aligned to x = 1840 along the subtitle row (y = 182).
    summary_pills = [
        '1,685 testing runs',
        '5 models',
        '1.5B tokens burned',
    ]
    pill_size = 20
    pill_weight = 700
    pill_gap = 12
    pill_widths = []
    for label in summary_pills:
        b = font(pill_size, pill_weight, False).getbbox(label)
        pad_x = max(18, round(pill_size * 0.72))
        pill_widths.append((b[2] - b[0]) + 2 * pad_x)
    px = 1840 - (sum(pill_widths) + pill_gap * (len(summary_pills) - 1))
    for label, pw in zip(summary_pills, pill_widths):
        badge(im, label, px, 182, color=INK, bg=CARD, border=ORANGE, size=pill_size, weight=pill_weight, fixed_w=pw)
        px += pw + pill_gap

    p_car = clamp((t - 0.4) / 7.5)
    focus_idx = min(3, int(p_car * 3.999))

    protos = [
        ('α', 'Alpha', 677, 68, 4466, 'Formula quotes', '#E59400', '#FFE066'),
        ('β', 'Beta', 268, 27, 10602, 'Trust + fee timing', '#EB7300', '#FFB700'),
        ('γ', 'Gamma', 242, 24, 11157, 'Notes + two-car gigs', '#FF5500', '#FF8000'),
        ('δ', 'Delta', 496, 50, 12975, 'Rescue windows + quantity', '#E62E00', '#FF4D2E'),
    ]

    curve_pts = []
    for i, (greek_sym, name, r_cnt, n_dots, mgn, tag, col, greek_col) in enumerate(protos):
        cx = 80 + i * 448
        cw = 416
        cy, cy2 = 236, 976
        appear = ease((t - 0.15 - i * 0.20) / 0.50)
        is_focus = i == focus_idx

        rect(im, (cx, cy, cx + cw, cy2), CARD, None, r=20)
        hdr_bg = col if is_focus else (col if i < focus_idx else APRICOT)
        hdr_fg = CARD if i <= focus_idx else INK
        rect(im, (cx, cy, cx + cw, cy + 92), hdr_bg, None, r=20)
        rect(im, (cx, cy + 70, cx + cw, cy + 92), hdr_bg, None, r=0)
        rect(im, (cx, cy, cx + cw, cy2), None, col if is_focus else GOLD_LINE, r=20, width=5 if is_focus else 2)

        # Greek letter & Name (with animated glow ring on active column)
        gx_c, gy_c = cx + 48, cy + 46
        if is_focus:
            pulse = 0.5 + 0.5 * math.sin(t * 6.0)
            circle(im, gx_c, gy_c, 32 + 3.0 * pulse, None, outline=SUNBURST, width=3)
            circle(im, gx_c, gy_c, 28, None, outline=CARD, width=2)
        circle(im, gx_c, gy_c, 26, INK)
        ImageDraw.Draw(im).text((round(gx_c), round(gy_c)), greek_sym, font=GREEK_FONT, fill=greek_col, anchor='mm')
        txt(im, name, cx + 90, cy + 28, 34, hdr_fg, 700)

        # Run count & dot matrix
        cnt_now = round(r_cnt * appear)
        txt(im, f'{cnt_now}', cx + 28, cy + 114, 82, col if is_focus else INK, 700)
        txt(im, 'runs', cx + 28 + font(82, 700).getbbox(f'{cnt_now}')[2] + 14, cy + 156, 26, MUTED_INK, 650)

        gx0, gy0 = cx + 30, cy + 232
        for d_idx in range(70):
            dx = gx0 + (d_idx % 10) * 36
            dy = gy0 + (d_idx // 10) * 28
            active_dot = d_idx < round(n_dots * appear)
            circle(im, dx, dy, 8 if active_dot else 4, col if active_dot else '#F7E6C4')

        badge(
            im,
            tag,
            cx + 28,
            cy + 442,
            color=CARD if is_focus else INK,
            bg=col if is_focus else APRICOT,
            border=None if is_focus else GOLD_LINE,
            size=20,
            fixed_w=cw - 56,
        )

        # Rising weekly margin bar at bottom of card
        bar_base = cy2 - 32
        max_h = 195
        bh = max_h * (mgn / 14000.0) * appear
        by = bar_base - bh
        rect(im, (cx + 28, bar_base - max_h, cx + cw - 28, bar_base), '#FFF3D6', outline=GOLD_LINE, r=10)
        rect(im, (cx + 28, by, cx + cw - 28, bar_base), col, r=10)
        lbl_mgn = f'€{mgn / 1000:.1f}k / wk'
        if appear > 0.35:
            txt(im, lbl_mgn, cx + cw / 2, bar_base - 36, 24, CARD, mono=True, weight=700, anchor='ma')
        if i == 0:
            curve_pts.append((cx + 48, by + 10))
        curve_pts.append((cx + cw / 2, by))
        if i == 3:
            curve_pts.append((cx + cw - 48, by - 4))

        if i < 3:
            ax = cx + cw + 16
            ay = cy + 360
            circle(im, ax, ay, 14, ORANGE if i < focus_idx else APRICOT)
            line(im, [(ax - 5, ay - 6), (ax + 5, ay), (ax - 5, ay + 6)], CARD if i < focus_idx else MUTED_INK, 3)

    if len(curve_pts) > 1 and t > 0.4:
        path_partial(im, curve_pts, p_car, INK, 5, glow=SUNBURST)
        q = route_point(curve_pts, p_car)
        p_prev = max(0.0, p_car - 0.01)
        p_next = min(1.0, p_car + 0.01)
        q0 = route_point(curve_pts, p_prev)
        q1 = route_point(curve_pts, p_next)
        heading = math.degrees(math.atan2(q1[1] - q0[1], q1[0] - q0[0]))
        car(im, *q, color=ORANGE, scale=1.15, angle=heading)

    return im


# ---------------------------------------------------------------------------
# Slide 3 (13–20s): Sol's Bento cards + old multi-car network animation
# ---------------------------------------------------------------------------
def dispatcher(t):
    im = base_canvas('citrus').copy()
    enter_model_hdr(im, 'Beta:', ' quote, then deliver', 80, 90, 84, t, .05, model_color='#EB7300', rest_color=INK, weight=700)
    phase = min(3, int(t / 1.7))
    cards = [
        (80, 236, '1. Filter requests'),
        (565, 236, '2. Price dealer trust'),
        (80, 616, '3. Time gig fees'),
        (565, 616, '4. Meet deadlines'),
    ]
    for i, (x, y, title) in enumerate(cards):
        active = i == phase
        fg_main = INK if active else '#7A6855'
        fg_acc = ORANGE if active else '#A67B4B'
        rect(im, (x, y, x + 465, y + 350), CARD if active else '#FFF9EE', ORANGE if active else GOLD_LINE, r=18, width=4 if active else 2)
        rect(im, (x + 2, y + 2, x + 463, y + 68), ORANGE if active else APRICOT, r=16)
        txt(im, title, x + 24, y + 16, 26, CARD if active else INK, 700)
        if i == 0:
            for j, line_s in enumerate(['≥8h slack', '≤500 km', 'No trade-in']):
                yy = y + 98 + j * 76
                circle(im, x + 34, yy + 20, 8, fg_acc)
                txt(im, line_s, x + 56, yy, 33, fg_main, 700 if active else 600)
        elif i == 1:
            txt(im, 'Price for', x + 28, y + 124, 42, fg_main, 700)
            txt(im, 'dealer trust', x + 28, y + 182, 42, fg_acc, 700)
        elif i == 2:
            progress = clamp((t - .6) / 5.5)
            usable = clamp((progress - .4) / .6)
            txt(im, f'{mix(.80, 1.50, usable):.2f}×', x + 26, y + 80, 64, fg_acc, 700)
            txt(im, 'Raise fees after pickup opens', x + 26, y + 160, 29, fg_main, 700 if active else 600)
            pts = [(x + 30, y + 294), (x + 192, y + 294), (x + 435, y + 228)]
            rect(im, (x + 30, y + 218, x + 192, y + 310), APRICOT, r=6)
            line(im, pts, GOLD_TRACK, 7)
            end = (x + 30 + 405 * progress, y + 294 - 66 * usable)
            trail = [pts[0], end] if progress <= .4 else [pts[0], pts[1], end]
            line(im, trail, fg_acc, 7)
            circle(im, *end, 10, fg_acc)
            line(im, [(x + 192, y + 214), (x + 192, y + 314)], MUTED_INK, 2)
        else:
            txt(im, '≥90%', x + 28, y + 104, 86, fg_acc, 700)
            txt(im, 'on time', x + 28, y + 214, 40, fg_main, 700)
    network(im, t, (1055, 236, 1840, 966))
    return im


@lru_cache(maxsize=1)
def live_demo_tall_main():
    """Seamless 1182px-wide tall scrollable main column (x=248..1430) with zero cut lines or overlays."""
    main_w = 1430 - 248
    top_bar = LIVE_DEMO.crop((248, 0, 1430, 149))
    body_src = LIVE_DEMO_SCROLL.crop((232, 238, 1430, 1715))
    body_h = round(body_src.height * (main_w / body_src.width))
    body_resized = body_src.resize((main_w, body_h), Image.Resampling.LANCZOS)
    tall = Image.new('RGB', (main_w, 14 + top_bar.height + body_h), '#141413')
    tall.paste(top_bar, (0, 14))
    tall.paste(body_resized, (0, 14 + top_bar.height))
    return tall


# ---------------------------------------------------------------------------
# Slide 4 (20–26s): Sol's observability + new live demo app preview
# ---------------------------------------------------------------------------
def observability(t):
    im = base_canvas('juicy').copy()
    enter(im, 'Find what broke', 80, 80, 92, t, .05, weight=700)
    phase = min(2, int(t / 1.9))
    pill_y = 216
    pill_size = 32
    pill_h = max(36, round(pill_size * 1.90))
    mid_y = pill_y + pill_h / 2
    cur_x = 80
    gap = 96
    for i, label in enumerate(['Note', 'Pickup window', 'Outcome']):
        w = badge(im, label, cur_x, pill_y, color=SUNBURST if i == phase else INK,
                  bg=INK if i == phase else APRICOT, size=pill_size, weight=700)
        if i < 2:
            ax = cur_x + w + gap / 2
            line(im, [(ax - 16, mid_y), (ax + 14, mid_y)], INK, 4)
            line(im, [(ax + 4, mid_y - 10), (ax + 15, mid_y), (ax + 4, mid_y + 10)], INK, 4)
        cur_x += w + gap

    rect(im, (80, 336, 1020, 978), INK, r=18)
    bezel_w, bezel_h = 1004 - 96, 962 - 352
    viewport = Image.new('RGB', (1430, 960), '#141413')
    # Fixed left sidebar (exact 248px width including vertical divider at x=247)
    side_top = LIVE_DEMO.crop((0, 0, 248, 1)).resize((248, 14), Image.Resampling.NEAREST)
    viewport.paste(side_top, (0, 0))
    viewport.paste(LIVE_DEMO.crop((0, 0, 248, 946)), (0, 14))

    # Smoothly scroll the entire right-hand main column (x=248..1430, y=0..960) with no overlays
    tall_main = live_demo_tall_main()
    max_scroll = float(tall_main.height - 960)
    crop_top = mix(0.0, max_scroll, smooth((t - 0.35) / 4.8))
    scrolled_main = tall_main.resize(
        (1430 - 248, 960),
        Image.Resampling.BICUBIC,
        box=(0.0, crop_top, float(1430 - 248), crop_top + 960.0),
    )
    viewport.paste(scrolled_main, (248, 0))

    app_view = viewport.resize((bezel_w, bezel_h), Image.Resampling.LANCZOS)
    mask = Image.new('L', (bezel_w, bezel_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bezel_w - 1, bezel_h - 1), radius=12, fill=255)
    im.paste(app_view, (96, 352), mask)
    rect(im, (96, 352, 1004, 962), None, outline='#2E2D2A', r=12, width=1)

    rect(im, (1060, 336, 1840, 978), CARD, GOLD_LINE, r=18, width=2)
    txt(im, 'Illustrative order', 1090, 366, 32, INK, 700)
    details = [
        ('Note', 'Ready after 11:30'),
        ('Pickup window', 'Pickup opens 11:30'),
        ('Outcome', 'Missed window. Late delivery.'),
    ]
    for i, (label, principal) in enumerate(details):
        yy = 442 + i * 170
        rect(im, (1084, yy, 1816, yy + 148), APRICOT if i == phase else CREAM,
             ORANGE if i == phase else GOLD_LINE, r=14, width=4 if i == phase else 2)
        txt(im, label, 1116, yy + 30, 25, ORANGE if i == phase else MUTED_INK, 700)
        txt(im, principal, 1116, yy + 74, 36, INK, 700)
    return im


# ---------------------------------------------------------------------------
# Slide 5 (26–34s): Sol heading & ranked % + smooth moving border of old video
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def graph_all_small():
    return ImageChops.multiply(CHART_ALL, Image.new('RGB', CHART_ALL.size, CREAM)).resize((1760, 825), Image.Resampling.LANCZOS)


def experiments(t):
    im = base_canvas('chart').copy()
    im.paste(graph_all_small(), (80, 230))
    enter(im, 'More runs cleared the ranking gate', 80, 56, 72, t, 0.05, color=INK, weight=700)
    txt(im, '1,685 practice runs', 84, 148, 28, MUTED_INK, 650)

    stages = [
        (1, 'Alpha: 84.6% ranked', '#E59400', INK),
        (2, 'Beta: 88.1% ranked', '#EB7300', CARD),
        (3, 'Gamma: 97.9% ranked', '#FF5500', CARD),
        (4, 'Delta: 98.6% ranked', '#E62E00', CARD),
    ]
    if t > 0.4:
        frac = clamp((t - 0.4) / 6.8)
        pos = mix(0.0, 3.0, smooth(frac))
        col = 1.0 + pos
        stage_idx = min(3, int(pos + 0.5))
        _, stage_lbl, stage_bg, stage_fg = stages[stage_idx]
        cx = 80 + 1760 * (0.09 + 0.89 * (col + 0.55) / 5.00)
        hw = 1760 * (0.89 * 0.45 / 5.00)
        rect(im, (cx - hw, 230 + 825 * 0.03, cx + hw, 230 + 825 * 0.80), None, stage_bg, r=6, width=4)
        badge_w = 350
        bx = clamp(cx - badge_w / 2, 80, 1840 - badge_w)
        badge(im, stage_lbl, bx, 178, color=stage_fg, bg=stage_bg, size=28, fixed_w=badge_w)
    return im


# ---------------------------------------------------------------------------
# Slide 6 (34–41s): Sol's version with "Gamma" in the header
# ---------------------------------------------------------------------------
def failure(t):
    im = base_canvas('sunburst').copy()
    enter_model_hdr(im, 'Gamma:', ' higher margin, but one week missed the gate', 80, 88, 68, t, .05, model_color='#FF5500', rest_color=INK, weight=700)
    txt(im, f'+€{830.44375 * ease((t - .2) / 1):,.0f}', 76, 278, 142, ORANGE, 700)
    txt(im, 'gross margin/week vs Beta', 84, 456, 32, INK, 650)
    badge(im, '7/8 weeks ranked', 84, 548, color=CARD, bg=DANGER, size=30)
    badge(im, '89.96% worst on time', 84, 634, color=INK, bg=MARIGOLD, border=DANGER, size=30)

    rect(im, (774, 236, 1840, 966), CARD, GOLD_LINE, r=18, width=2)
    txt(im, '8 new practice weeks', 814, 268, 32, INK, 700)

    line_p = clamp((t - 0.25) / 2.2)
    if line_p >= 6 / 7.0:
        badge(im, '1 of 8 weeks failed', 1500, 262, color=CARD, bg=DANGER, size=24)

    holdout_rows = [r for r in PAIRED_WEEKS if r['comparison'] == 'Original candidate: fresh holdout']
    left, right = 885, 1780
    top_y, bot_y = 390, 845

    def oy(pct):
        return bot_y - (pct - 88.0) / 12.0 * (bot_y - top_y)

    for val in [88.0, 90.0, 95.0, 100.0]:
        yy = oy(val)
        is_gate = val == 90.0
        line(im, [(left - 20, yy), (right + 16, yy)], DANGER if is_gate else APRICOT, 4 if is_gate else 2)
        txt(im, f'{val:.0f}%', left - 26, yy, 21 if is_gate else 19, DANGER if is_gate else MUTED_INK, mono=True, weight=700 if is_gate else 500, anchor='rm')
        if is_gate:
            txt(im, '90% required', left + 8, yy - 28, 20, DANGER, weight=700)

    step = (right - left) / 7.0
    pts_b, pts_g = [], []
    for i, r in enumerate(holdout_rows):
        cx = left + i * step
        ot_b = float(r['baseline_on_time']) * 100.0
        ot_g = float(r['candidate_on_time']) * 100.0
        pts_b.append((cx, oy(ot_b)))
        pts_g.append((cx, oy(ot_g)))
        txt(im, f'W{i + 1}', cx, 896, 22, DANGER if (i == 6 and line_p >= 6 / 7.0) else INK, mono=True, weight=700, anchor='ma')

    path_partial(im, pts_b, line_p, MUTED_INK, 3)
    path_partial(im, pts_g, line_p, ORANGE, 4, glow='#FFE066')
    for i, ((xb, yb), (xg, yg)) in enumerate(zip(pts_b, pts_g)):
        if line_p < i / 7.0:
            continue
        circle(im, xb, yb, 6, CARD, MUTED_INK, 2)
        if i == 6:
            pulse = ((t - 2.14) * 1.2) % 1.0
            circle(im, xg, yg, round(15 + 5 * pulse), None, DANGER, 2)
            circle(im, xg, yg, 12, DANGER, CARD, 3)
            badge(im, '89.96%', xg - 72, yg + 22, color=CARD, bg=DANGER, size=26, mono=True)
        else:
            circle(im, xg, yg, 8, ORANGE, INK, 2)

    line(im, [(1180, 340), (1220, 340)], MUTED_INK, 3)
    circle(im, 1200, 340, 5, CARD, MUTED_INK, 2)
    txt(im, 'Beta', 1232, 326, 22, MUTED_INK, 650)
    line(im, [(1330, 340), (1370, 340)], ORANGE, 4)
    circle(im, 1350, 340, 6, ORANGE, INK, 2)
    txt(im, 'First Gamma', 1382, 326, 22, ORANGE, 700)
    return im


def paired_chart(im, t, rows, baseline, candidate, label, diff_only=False):
    rect(im, (755, 236, 1840, 966), CARD, GOLD_LINE, r=18, width=2)
    txt(im, label, 790, 264, 30, INK, 700)
    if diff_only:
        txt(im, f'Extra margin vs {baseline}', 790, 320, 24, ORANGE, 700)
    else:
        txt(im, 'Gross margin / week', 790, 320, 23, MUTED_INK)
        for x, name, col in [(1434, baseline, GOLD_TRACK), (1630, candidate, ORANGE)]:
            rect(im, (x, 325, x + 26, 345), col, r=4)
            txt(im, name, x + 38, 319, 23, INK, 650)

    base_y, left, right = (615 if diff_only else 650), 842, 1796
    if diff_only:
        for value in [0, 1500, 3000]:
            yy = base_y - 235 * value / 3500
            line(im, [(left - 16, yy), (right + 12, yy)], GOLD_LINE if value == 0 else APRICOT, 2 if value == 0 else 1)
            txt(im, f'+€{value / 1000:.1f}k' if value == 1500 else (f'+€{value // 1000}k' if value else '€0'), 818, yy, 17, MUTED_INK, mono=True, anchor='rm')
    else:
        for value in [0, 5000, 10000, 15000]:
            yy = base_y - 268 * value / 18000
            line(im, [(left - 16, yy), (right + 12, yy)], APRICOT, 1)
            txt(im, f'€{value // 1000}k', 818, yy, 17, MUTED_INK, mono=True, anchor='rm')

    n = len(rows)
    step = (right - left) / n
    bw = min(42, step * .36)
    ot_b, ot_c = [], []
    for i, (bv, cv, bot, cot) in enumerate(rows):
        cx = left + (i + .5) * step
        pp = ease((t - .25 - i * .07) / .5)
        if diff_only:
            dv = cv - bv
            dh = 235 * (abs(dv) / 3500.0) * pp
            if dv >= 0:
                rect(im, (cx - bw * 0.82, base_y - dh, cx + bw * 0.82, base_y), ORANGE, r=4)
            else:
                rect(im, (cx - bw * 0.82, base_y, cx + bw * 0.82, base_y + dh), MANGO, r=4)
        else:
            rect(im, (cx - bw - 2, base_y - 268 * bv / 18000 * pp, cx - 2, base_y), GOLD_TRACK, GOLD_LINE, r=4)
            rect(im, (cx + 2, base_y - 268 * cv / 18000 * pp, cx + bw + 2, base_y), ORANGE, r=4)
        ot_b.append((cx, 882 - 130 * (bot - 89) / 11))
        ot_c.append((cx, 882 - 130 * (cot - 89) / 11))
        txt(im, f'W{i + 1}', cx, 910, 20 if n == 8 else 14, INK, mono=True, anchor='ma')

    txt(im, 'On time', 790, 694, 23, MUTED_INK, 650)
    line(im, [(1360, 710), (1396, 710)], MUTED_INK, 3)
    circle(im, 1378, 710, 4, CARD, MUTED_INK, 2)
    txt(im, baseline, 1408, 695, 21, MUTED_INK, 650)
    line(im, [(1610, 710), (1646, 710)], ORANGE, 4)
    circle(im, 1628, 710, 6, ORANGE, INK, 2)
    txt(im, candidate, 1658, 695, 21, ORANGE, 700)

    gate_y = 882 - 130 / 11
    line(im, [(826, gate_y), (1808, gate_y)], DANGER, 2)
    txt(im, '90%', 818, gate_y, 18, DANGER, mono=True, anchor='rm')
    txt(im, '100%', 818, 752, 17, MUTED_INK, mono=True, anchor='rm')
    line(im, ot_b, MUTED_INK, 3)
    line(im, ot_c, ORANGE, 4)
    for pb, pc in zip(ot_b, ot_c):
        circle(im, *pb, 4, CARD, MUTED_INK, 2)
        circle(im, *pc, 6, ORANGE, INK, 2)


# ---------------------------------------------------------------------------
# Slide 7 (41–48s): Sol's Gamma slide with normal sentences (no dotted fragments)
# ---------------------------------------------------------------------------
def gain(t):
    im = base_canvas('citrus').copy()
    enter_model_hdr(im, 'Gamma:', ' read dealer notes and combine cars in one gig', 80, 88, 62, t, .05, model_color='#FF5500', rest_color=INK, weight=700)
    txt(im, f'+€{2030.845 * ease((t - .2) / 1):,.0f}', 76, 278, 132, ORANGE, 700)
    txt(im, 'gross margin/week vs Beta', 84, 448, 32, INK, 650)
    badge(im, '8/8 weeks qualified', 84, 540, color=INK, bg=MARIGOLD, border=ORANGE, size=29)
    badge(im, '96.95% worst on time', 84, 622, color=INK, bg=ORANGE, size=29)

    rect(im, (84, 738, 690, 948), CARD, GOLD_LINE, r=18, width=2)
    txt(im, 'One driver gig carries two sequential cars', 114, 762, 23, INK, 700)

    gig_route = [(150, 868), (385, 868), (620, 868)]
    cycle = ((t + 2.45) / 3.5) % 1.0
    if cycle < 0.5:
        leg1_p = smooth(cycle / 0.5)
        leg2_p = 0.0
        route_p = 0.5 * leg1_p
        active_leg = 1
    else:
        leg1_p = 1.0
        leg2_p = smooth((cycle - 0.5) / 0.5)
        route_p = 0.5 + 0.5 * leg2_p
        active_leg = 2

    # Base route track + glowing active route segment
    line(im, gig_route, GOLD_TRACK, 8)
    path_segment(im, gig_route, 0.0, route_p, color=ORANGE, width=6, glow=MARIGOLD)
    trail_p0 = 0.0 if active_leg == 1 else 0.5
    path_segment(im, gig_route, max(trail_p0, route_p - 0.26), route_p, color='#FF5500', width=7, glow=SUNBURST)

    # Sequential leg labels above each segment
    txt(im, 'Car 1', 268, 818, 21, ORANGE if active_leg == 1 else INK, 700, anchor='mm')
    txt(im, 'Car 2', 502, 818, 21, ORANGE if active_leg == 2 else MUTED_INK, 700, anchor='mm')

    # Route nodes (start, handoff, finish)
    for idx_p, cx_p in enumerate([150, 385, 620]):
        reached = route_p >= (idx_p * 0.5 - 0.02)
        circle(im, cx_p, 868, 10, ORANGE if reached else CARD, INK if reached else ORANGE, 3)

    # Smooth sequential car positions along Leg 1 (150 -> 385) and Leg 2 (385 -> 620)
    car1_x = mix(188, 336, leg1_p)
    car2_x = mix(434, 582, leg2_p)
    car(im, car1_x, 868, color=INK, scale=1.15, angle=0)
    car(im, car2_x, 868, color=ORANGE, scale=1.15, angle=0)

    rows = [(float(r['baseline_margin_eur']), float(r['candidate_margin_eur']),
             100 * float(r['baseline_on_time']), 100 * float(r['candidate_on_time'])) for r in CONFIRM_WEEKS]
    paired_chart(im, t, rows, 'Beta', 'Gamma', '8 new practice weeks')
    return im


# ---------------------------------------------------------------------------
# Slide 7 (40–46s): Delta in production (matching presentation Slide 8)
# ---------------------------------------------------------------------------
def delta_production(t):
    im = base_canvas('sunburst').copy()
    enter_model_hdr(im, 'Delta', ' in production', 80, 88, 78, t, .05, model_color='#E62E00', rest_color=INK, weight=700)
    txt(im, f'+€{1663.8205 * ease((t - .2) / 1):,.0f}', 76, 240, 134, ORANGE, 700)
    txt(im, 'gross margin/week vs Early Delta', 84, 404, 30, INK, 650)

    # Card 1: 19/19 practice weeks ranked
    rect(im, (84, 486, 690, 694), CARD, GOLD_LINE, r=18, width=2)
    txt(im, '19/19', 112, 502, 74, ORANGE, 700)
    txt(im, 'practice weeks ranked', 318, 550, 26, INK, 700)
    badge(im, '17/19 weeks ahead · 91.1% worst on time', 112, 616, color=INK, bg=MARIGOLD, border=ORANGE, size=22)

    # Card 2: €75,764 round 9 total: 5/5 weeks ranked
    rect(im, (84, 718, 690, 948), CARD, GOLD_LINE, r=18, width=2)
    txt(im, '€75,764', 112, 728, 70, '#E62E00', 700)
    txt(im, 'round 9 total: 5/5 weeks ranked', 112, 820, 25, INK, 700)
    badge(im, '1,798 orders won · 96.7% on time', 112, 874, color=INK, bg=APRICOT, border=GOLD_LINE, size=22)

    rows = [(r[1], r[2], r[4], r[5]) for r in DELTA_CONFIRM]
    paired_chart(im, t, rows, 'Early Delta', 'Delta', '19 paired practice weeks', diff_only=True)
    return im


# ---------------------------------------------------------------------------
# Slide 8 (47–53s): Delta: Quantity > the best margins (focused Orders won / week graph)
# ---------------------------------------------------------------------------
def delta_iteration(t):
    im = base_canvas('citrus').copy()
    enter_model_hdr(im, 'Delta:', ' Quantity > the best margins', 80, 88, 84, t, .05, model_color='#E62E00', rest_color=INK, weight=700)

    rect(im, (460, 236, 1460, 966), CARD, GOLD_LINE, r=20, width=2)
    txt(im, 'Orders won / week', 512, 268, 38, INK, 700)
    badge(im, '+33% more orders', 1106, 264, color=CARD, bg='#E62E00', size=25, weight=700)

    base_y = 824
    max_h = 420
    left_x, right_x = 580, 1380
    for val in [0, 100, 200, 300]:
        yy = round(base_y - max_h * (val / 360.0))
        line(im, [(left_x, yy), (right_x, yy)], GOLD_LINE if val == 0 else APRICOT, 3 if val == 0 else 2)
        txt(im, f'{val}', left_x - 20, yy, 21, MUTED_INK, mono=True, weight=650, anchor='rm')

    bw = 220
    # Left bar: Early Delta (257)
    p1 = ease((t - 0.15) / 0.7)
    h1 = round(max_h * (257.0 / 360.0) * p1)
    bx1 = 680
    rect(im, (bx1, base_y - h1, bx1 + bw, base_y), GOLD_TRACK, outline=GOLD_LINE, r=14, width=2)
    txt(im, f'{round(257 * p1)}', bx1 + bw / 2, base_y - h1 - 72, 60, MUTED_INK, 700, anchor='ma')
    txt(im, 'Early Delta', bx1 + bw / 2, base_y + 24, 28, MUTED_INK, 700, anchor='ma')
    txt(im, '30% win target', bx1 + bw / 2, base_y + 62, 22, MUTED_INK, 600, anchor='ma')

    # Right bar: Delta (342)
    p2 = ease((t - 0.30) / 0.8)
    h2 = round(max_h * (342.0 / 360.0) * p2)
    bx2 = 1060
    rect(im, (bx2, base_y - h2, bx2 + bw, base_y), '#E62E00', r=14)
    txt(im, f'{round(342 * p2)}', bx2 + bw / 2, base_y - h2 - 78, 68, '#E62E00', 700, anchor='ma')
    txt(im, 'Delta', bx2 + bw / 2, base_y + 24, 28, '#E62E00', 700, anchor='ma')
    txt(im, '42% win target', bx2 + bw / 2, base_y + 62, 22, INK, 650, anchor='ma')

    return im


# ---------------------------------------------------------------------------
# Slide 10 (61–66s): Sol's closing highway slide + QR code ("Try it yourself")
# ---------------------------------------------------------------------------
def ending(t):
    im = base_canvas('juicy').copy()
    road_layer = im.copy()
    for offset in [-210, 0, 210]:
        line(road_layer, [(1160 + offset, 1080), (1600 + offset, 650), (1400 + offset, 350), (1830 + offset, -50)], ORANGE, 46)
    line(road_layer, [(1160, 1080), (1600, 650), (1400, 350), (1830, -50)], SUNBURST, 6)
    im.paste(road_layer, (0, 0))

    im.paste(LOGO_BADGE_SM, (80, 96), LOGO_BADGE_SM)
    enter(im, 'Cheap-Drive', 176, 106, 52, t, .02, color='#231A14', weight=700)
    enter(im, 'Win the right work.', 80, 236, 102, t, .08, color=INK, weight=700)
    enter(im, 'Deliver it.', 80, 370, 128, t, .18, color=CARD, weight=700)

    # QR code + "Try it yourself" lockup
    qr_x, qr_y = 80, 628
    qr_mask = Image.new('L', (268, 268), 0)
    ImageDraw.Draw(qr_mask).rounded_rectangle((0, 0, 267, 267), radius=24, fill=255)
    im.paste(QR_CODE, (qr_x, qr_y), qr_mask)
    rect(im, (qr_x, qr_y, qr_x + 268, qr_y + 268), None, outline=INK, r=24, width=3)

    enter(im, 'Try it yourself', qr_x + 304, qr_y + 92, 64, t, .26, color=INK, weight=700)

    road = [(1370, 1020), (1690, 650), (1490, 350), (1825, 15)]
    for idx_c, offset_p in enumerate([0.12, 0.54]):
        p = (offset_p + t * .11) % 1
        pos = route_point(road, p)
        ahead = route_point(road, min(p + .002, 1))
        heading = math.degrees(math.atan2(ahead[1] - pos[1], ahead[0] - pos[0]))
        car(im, *pos, INK if idx_c == 0 else CARD, 2.8, heading)
    return im


FUNCS = [hero, evolution, dispatcher, observability, failure, gain, delta_production, delta_iteration, experiments, ending]


def frame(t):
    idx = next((i for i, (a, b) in enumerate(SCENES) if a <= t < b), len(SCENES) - 1)
    a, b = SCENES[idx]
    im = FUNCS[idx](t - a)
    dt = t - a
    if idx and dt < .30:
        xx = round(W * ease(dt / .30))
        prev = FUNCS[idx - 1](SCENES[idx - 1][1] - SCENES[idx - 1][0] + dt)
        im.paste(prev.crop((xx, 0, W, H)), (xx, 0))
        rect(im, (max(0, xx - 12), 0, xx + 2, H), ORANGE if idx not in [0, 3, 9] else INK)
    return im


def soundtrack(path):
    """Energetic 128 BPM instrumental for the 60s cut; seeded percussion, no third-party samples,
    layered with frame-accurate micro-sonic UI and data sound design for all 9 scenes.
    """
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
        if kind == 'chime':
            env = (1 - np.exp(-ts * 320)) * np.exp(-ts * 4.8)
            sig = (
                np.sin(2 * np.pi * f * ts)
                + .38 * np.sin(2 * np.pi * (f * 2.0) * ts) * np.exp(-ts * 7.0)
                + .18 * np.sin(2 * np.pi * (f * 3.0) * ts) * np.exp(-ts * 11.0)
                + .09 * np.sin(2 * np.pi * (f * 4.02) * ts) * np.exp(-ts * 16.0)
            )
            return (sig * env).astype(np.float32)
        if kind == 'click':
            env = (1 - np.exp(-ts * 600)) * np.exp(-ts * 38.0)
            f_inst = f * (1.0 + 0.35 * np.exp(-ts * 180))
            phase = 2 * np.pi * np.cumsum(f_inst) / sr
            sig = np.sin(phase) + .32 * np.sin(2 * phase) + .14 * np.sin(3 * phase)
            return (sig * env).astype(np.float32)
        if kind == 'sonar':
            env = (1 - np.exp(-ts * 180)) * np.exp(-ts * 7.5)
            sig = np.sin(2 * np.pi * f * ts) + .20 * np.sin(2 * np.pi * (f * 2.0) * ts) * np.exp(-ts * 12.0)
            return (sig * env).astype(np.float32)
        if kind == 'tick':
            env = (1 - np.exp(-ts * 800)) * np.exp(-ts * 65.0)
            sig = np.sin(2 * np.pi * f * ts) + .30 * np.sin(2 * np.pi * (f * 2.5) * ts)
            return (sig * env).astype(np.float32)
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

    # 1. Transition whooshes + bells at the new scene cuts
    for cut in [5, 13, 20, 26, 33, 40, 47, 53, 61]:
        ts = np.arange(round(sr * 0.7)) / sr
        noise = rng.standard_normal(len(ts))
        noise = np.convolve(noise, np.ones(12) / 12, mode='same')
        add(cut - .55, noise * np.sin(np.pi * ts / 0.7) ** 2, .055)
        add(cut + .04, note(86, .14), .032, .25)

    def add_counter_ticks(t_start, t_end, count=12, midi_start=72, midi_end=84, vol=0.022):
        for i in range(count):
            frac = i / max(1, count - 1)
            t_tick = t_start + frac * (t_end - t_start)
            m_tick = midi_start + frac * (midi_end - midi_start)
            pan = -0.25 + 0.5 * frac
            add(t_tick, note(m_tick, 0.04, 'tick'), vol * (0.85 + 0.3 * frac), pan)

    # 2. Slide 2 (5-13s, evolution): 4 ascending crystalline harmonic chimes
    for i, (t_chime, m) in enumerate(zip([5.9, 7.6, 9.3, 11.0], [74, 77, 81, 86])):
        pan = -0.36 + i * 0.24
        add(t_chime, note(m, 0.48, 'chime'), .036, pan)
        add(t_chime + 0.018, note(m + 12, 0.32, 'chime'), .016, -pan * 0.5)

    # 3. Slide 3 (13-20s, dispatcher): 4 subtle, crisp tactile UI clicks/plucks
    for i, (t_click, m) in enumerate(zip([13.3, 15.0, 16.7, 18.4], [69, 72, 76, 81])):
        pan = -0.3 + i * 0.2
        add(t_click, note(m, 0.095, 'click'), .034, pan)
        add(t_click + 0.008, note(m + 12, 0.055, 'tick'), .015, pan)

    # 4. Slide 4 (20-26s, observability): 3 diagnostic sonar/pulse tones
    for i, (t_ping, m) in enumerate(zip([20.2, 22.0, 23.9], [72, 76, 67])):
        pan = -0.25 + i * 0.25
        add(t_ping, note(m, 0.36, 'sonar'), .035, pan)
        add(t_ping + 0.095, note(m, 0.22, 'sonar'), .013, -pan * 0.6)

    # 5. Slide 5 (26-33s, failure): Fast pitch-rising counter ticks (26.2..27.1) + low warning drop (180Hz -> 95Hz) at 28.4
    add_counter_ticks(26.2, 27.1, count=11, midi_start=72, midi_end=82, vol=0.022)
    warn_dur = 0.58
    ts_w = np.arange(round(warn_dur * sr)) / sr
    f_slide = 180.0 - (180.0 - 95.0) * (ts_w / warn_dur) ** 0.85
    phase_w = 2 * np.pi * np.cumsum(f_slide) / sr
    tri_w = (2.0 / np.pi) * np.arcsin(np.sin(phase_w))
    sin_w = np.sin(phase_w) + 0.25 * np.sin(2 * phase_w)
    env_w = np.minimum(ts_w / 0.025, 1.0) * np.exp(-ts_w * 3.8)
    warn_sig = ((0.62 * sin_w + 0.38 * tri_w) * env_w).astype(np.float32)
    add(28.4, warn_sig, .065, 0.0)

    # 6. Slide 6 (33-40s, gain): Counter ticks (33.2..34.2) + 8 soft ascending bar-pop plucks + warm two-note harmony at 35.5
    add_counter_ticks(33.2, 34.2, count=13, midi_start=72, midi_end=84, vol=0.022)
    bar_midis = [69, 71, 72, 74, 76, 77, 79, 81]
    for i, m in enumerate(bar_midis):
        t_pop = 33.4 + i * 0.11
        add(t_pop, note(m, 0.14, 'pluck'), .025, -0.35 + i * 0.1)
    add(35.5, note(74, 0.65, 'chime'), .032, -0.2)
    add(35.53, note(77, 0.65, 'chime'), .030, 0.2)
    add(35.5, note(62, 0.70, 'pad'), .024, 0.0)

    # 7. Slide 7 (40-47s, delta_production): Counter ticks (40.2..41.2) + bright triumphant major triad chime at 42.0
    add_counter_ticks(40.2, 41.2, count=13, midi_start=74, midi_end=86, vol=0.022)
    for j, m in enumerate([74, 78, 81, 86]):
        add(42.0 + j * 0.018, note(m, 0.58, 'chime'), .030, -0.3 + j * 0.2)

    # 8. Slide 8 (47-53s, delta_iteration): 4 snappy ascending lever-activation plucks at 47.3, 48.7, 50.1, 51.5
    for i, (t_lev, m) in enumerate(zip([47.3, 48.7, 50.1, 51.5], [74, 77, 81, 86])):
        pan = -0.3 + i * 0.2
        add(t_lev, note(m, 0.18, 'pluck'), .034, pan)
        add(t_lev, note(m + 12, 0.08, 'click'), .018, pan)

    # 9. Slide 9 (53-61s, experiments): 4 ascending lock-in chimes at 53.8, 55.5, 57.2, 58.9
    for i, (t_lock, m) in enumerate(zip([53.8, 55.5, 57.2, 58.9], [72, 76, 79, 84])):
        pan = -0.3 + i * 0.2
        add(t_lock, note(m, 0.46, 'chime'), .034, pan)
        add(t_lock + 0.015, note(m + 12, 0.28, 'chime'), .015, -pan * 0.5)

    # 10. Slide 10 (61-66s, ending): Warm sustained D-major / F-major swell
    swell_notes = [(50, -0.4), (57, 0.35), (62, -0.25), (65, 0.25), (66, -0.15), (69, 0.15), (74, -0.3), (77, 0.3), (81, 0.0)]
    for m, pan in swell_notes:
        add(61.2, note(m, 4.2, 'pad'), .018, pan)

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
    times = [2.2, 7.5, 11.2, 15.0, 18.2, 23.0, 29.5, 36.5, 43.5, 51.8, 59.5, 63.5]
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
    poster = frame(2.2)
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
    assert RUN_DATA['summary']['completed_practice'] == 1685
    assert RUN_DATA['summary']['chart_groups'] == {
        'Baseline': 2,
        'Alpha': 677,
        'Beta': 268,
        'Gamma': 242,
        'Delta': 496,
    }
    assert {name: round(group['ranked'] / group['runs'] * 100, 1)
            for name, group in RUN_DATA['groups'].items() if name != 'Baseline'} == {
                'Alpha': 84.6, 'Beta': 88.1, 'Gamma': 97.9, 'Delta': 98.6}
    first_holdout = next(c for c in CHART_DATA['cohorts']
                         if c['comparison'] == 'Original candidate: fresh holdout')
    assert round(first_holdout['mean_delta_eur']) == 830
    assert first_holdout['candidate_qualified'] == 7
    assert round(first_holdout['candidate_worst_on_time'] * 100, 2) == 89.96
    assert len(CONFIRM_WEEKS) == 8
    assert all(r['candidate_qualified'] == 'True' and float(r['delta_eur']) > 0 for r in CONFIRM_WEEKS)
    assert round(sum(float(r['delta_eur']) for r in CONFIRM_WEEKS) / 8, 3) == 2030.845
    assert len(DELTA_CONFIRM) == 19
    assert sum(d[3] > 0 for d in DELTA_CONFIRM) == 17
    assert round(sum(d[3] for d in DELTA_CONFIRM) / 19, 2) == 1663.82
    stress = next(r for r in PAIRED_OLD if r['suite'] == 't1' and r['variant'] == 'km600-t38' and r['seed'] == 'gamma-t04')
    assert int(stress['won_orders']) == 294 and round(float(stress['on_time_share']) * 100, 2) == 89.80
    edge_set = set(MAP_EDGES) | {(b, a) for a, b in MAP_EDGES}
    for nodes, *_ in MAP_TRIPS:
        for u, v in zip(nodes, nodes[1:]):
            assert (u, v) in edge_set, f'Missing MAP_EDGE {(u, v)}'
    road_set = set(FINLAND_ROADS) | {(b, a) for a, b in FINLAND_ROADS}
    for corr, *_ in FINLAND_TRIPS:
        for u, v in zip(corr, corr[1:]):
            assert (u, v) in road_set, f'Missing FINLAND_ROAD {(u, v)}'


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
