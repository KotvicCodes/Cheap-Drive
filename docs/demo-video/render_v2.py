#!/usr/bin/env python3
"""V2 comparison clone: nine-slide, deterministic 60-second motion film.

Keeps v1 untouched; every generated artifact uses a v2-specific filename.
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
    (0, 5),
    (5, 13),
    (13, 20),
    (20, 26),
    (26, 34),
    (34, 41),
    (41, 48),
    (48, 55),
    (55, 60),
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
    ('f01', 7353.40, 8178.10, 824.70, 97.0, 96.6),
    ('f02', 11918.61, 13468.72, 1550.11, 96.3, 97.8),
    ('f03', 11620.83, 12000.00, 379.17, 98.4, 98.0),
    ('f04', 14102.64, 14357.99, 255.35, 98.5, 98.5),
    ('f05', 10663.96, 11063.43, 399.47, 97.2, 97.2),
    ('f06', 15844.85, 16630.83, 785.98, 97.0, 97.0),
    ('f07', 10001.28, 12015.18, 2013.90, 94.9, 93.7),
    ('f08', 10566.66, 10586.94, 20.28, 97.2, 97.2),
    ('f09', 12836.87, 13601.21, 764.34, 97.4, 98.5),
    ('f10', 13810.94, 13962.56, 151.62, 98.6, 97.8),
    ('f11', 9770.47, 10128.71, 358.24, 97.1, 97.1),
]

CHART_ALL = Image.open(ROOT / 'assets/all-run-margins.png').convert('RGB')
CHART_STAGES = Image.open(ROOT / 'assets/learning-stages.png').convert('RGB')
REPORT = Image.open(REPO / 'docs/screenshots/week-overview.png').convert('RGB')
LOGO_BADGE = Image.open(ROOT / 'assets/cheap-drive-badge.png').convert('RGBA').resize((124, 124), Image.Resampling.LANCZOS)


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


def enter(im, text, x, y, size, t, delay=0, color=INK, weight=600, mono=False, span=0.38):
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
    ([0, 1, 7, 6, 5, 11, 10], 0.14, 0.24, INK, True),
    ([10, 9, 4, 3, 7, 8], 0.28, 0.27, ORANGE, True),
    ([5, 4, 3, 2, 0], 0.42, 0.22, INK, False),
    ([8, 1, 2, 9, 10, 11], 0.19, 0.26, ORANGE, False),
    ([6, 7, 3, 4, 11], 0.55, 0.25, INK, False),
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
        line(im, [pts[a], pts[b]], '#FFC266', 2)
    for i, (a, b) in enumerate(MAP_EDGES):
        if i % 2 == 0:
            px, py = route_point([pts[a], pts[b]], (t * .25 + i * .17) % 1)
            circle(im, px, py, 4, MANGO)
    for i, p in enumerate(pts):
        is_hub = i in [0, 5, 10, 3, 8]
        circle(im, *p, 7 if is_hub else 5, CARD, ORANGE if is_hub else MANGO, 3 if is_hub else 2)
    for i in [0, 5, 10, 3]:
        p = pts[i]
        circle(im, *p, 13 + 9 * ((t * .85 + i * .3) % 1), None, MARIGOLD, 2)
    if active:
        for t_idx, (nodes, p0, spd, c_col, is_prim) in enumerate(MAP_TRIPS):
            r_path = [pts[k] for k in nodes]
            p = (p0 + t * spd) % 1.0
            tail = max(0.0, p - 0.36)
            path_segment(im, r_path, tail, p, ORANGE if is_prim else MARIGOLD, 5 if is_prim else 4, glow='#FFE066' if is_prim else None)
            if 0.03 < p < 0.97:
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
    'helsinki': (60.1699, 24.9384, 'Helsinki', True),
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
    ('helsinki', 'espoo'), ('espoo', 'salo'), ('salo', 'turku'), ('turku', 'raisio'),
    ('raisio', 'rauma'), ('rauma', 'pori'), ('pori', 'vaasa'), ('vaasa', 'kokkola'),
    ('kokkola', 'ylivieska'), ('ylivieska', 'oulu'), ('oulu', 'kemi'), ('kemi', 'rovaniemi'),
    ('rovaniemi', 'sodankyla'), ('sodankyla', 'ivalo'),
    ('helsinki', 'vantaa'), ('vantaa', 'hyvinkaa'), ('hyvinkaa', 'hameenlinna'),
    ('hameenlinna', 'lempaala'), ('lempaala', 'tampere'), ('tampere', 'pori'),
    ('tampere', 'seinajoki'), ('seinajoki', 'vaasa'), ('seinajoki', 'kokkola'),
    ('tampere', 'jyvaskyla'), ('helsinki', 'lahti'), ('lahti', 'jyvaskyla'),
    ('jyvaskyla', 'ylivieska'), ('jyvaskyla', 'oulu'), ('jyvaskyla', 'kuopio'),
    ('helsinki', 'porvoo'), ('porvoo', 'kotka'), ('kotka', 'kouvola'), ('lahti', 'kouvola'),
    ('kouvola', 'mikkeli'), ('mikkeli', 'kuopio'), ('kuopio', 'kajaani'), ('kajaani', 'oulu'),
    ('kouvola', 'lappeenranta'), ('lappeenranta', 'savonlinna'), ('savonlinna', 'joensuu'),
    ('lappeenranta', 'joensuu'), ('joensuu', 'kuopio'), ('joensuu', 'kajaani'),
]

# 5 realistic main-highway transfers across 5 distinct regions of Finland
FINLAND_TRIPS = [
    # (waypoints, start_offset, speed, color, is_primary)
    (['ivalo', 'sodankyla', 'rovaniemi', 'kemi', 'oulu'], 0.14, 0.14, ORANGE, True),
    (['vaasa', 'kokkola', 'ylivieska', 'oulu'], 0.08, 0.15, MARIGOLD, False),
    (['joensuu', 'kuopio', 'jyvaskyla', 'tampere'], 0.20, 0.15, ORANGE, True),
    (['helsinki', 'hyvinkaa', 'hameenlinna', 'lempaala', 'tampere', 'pori'], 0.12, 0.16, MARIGOLD, False),
    (['turku', 'salo', 'espoo', 'helsinki', 'porvoo', 'kotka', 'lappeenranta'], 0.28, 0.14, ORANGE, True),
]


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


def finland_map(im, t, box=(820, 80, 1840, 1000), zoom_south=False, bg=CARD, border=GOLD_LINE):
    x, y, x2, y2 = box
    rect(im, box, bg, outline=border, r=20, width=2)
    w, h = x2 - x, y2 - y

    # Background grid dots
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

    # Clip drawing to the map card interior
    map_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(map_layer)
    poly_pts = [(round(px), round(py)) for lat, lon in FINLAND_BORDER for px, py in [proj(lat, lon)]]
    d.polygon(poly_pts, fill='#FFE5A3', outline=MANGO, width=3)

    # Crop map_layer to card bounds and composite
    cropped = map_layer.crop((x + 4, y + 4, x2 - 4, y2 - 4))
    im.paste(cropped, (x + 4, y + 4), cropped)

    def in_box(pt):
        return (x + 16) <= pt[0] <= (x2 - 16) and (y + 16) <= pt[1] <= (y2 - 16)

    # Road network across Finland
    for u, v in FINLAND_ROADS:
        pu = proj(*FINLAND_PLACES[u][:2])
        pv = proj(*FINLAND_PLACES[v][:2])
        if in_box(pu) and in_box(pv):
            line(im, [pu, pv], '#FFC266', 2)

    # Plot all 30 simulator towns
    for pid, (lat, lon, name, is_major) in FINLAND_PLACES.items():
        pt = proj(lat, lon)
        if not in_box(pt):
            continue
        circle(im, *pt, 5 if is_major else 3, CARD, ORANGE if is_major else MANGO, 2)
        if is_major:
            lx_off = -10 if pid in ('vaasa', 'turku') else 10
            anc = 'rm' if pid in ('vaasa', 'turku') else 'lm'
            txt(im, name, pt[0] + lx_off, pt[1], 16, INK, weight=650, anchor=anc)

    # 5 realistic highway transfers with subtle trailing progress
    for c_idx, (corr, p0, spd, col, is_prim) in enumerate(FINLAND_TRIPS):
        pts = [proj(*FINLAND_PLACES[pid][:2]) for pid in corr if in_box(proj(*FINLAND_PLACES[pid][:2]))]
        if len(pts) < 2:
            continue
        p = (p0 + t * spd) % 1.0
        tail = max(0.0, p - 0.22)
        path_segment(im, pts, tail, p, ORANGE if is_prim else MANGO, 4 if is_prim else 3)
        if 0.04 < p < 0.96:
            q = route_point(pts, p)
            ahead = route_point(pts, min(p + 0.008, 1.0))
            heading = math.degrees(math.atan2(ahead[1] - q[1], ahead[0] - q[0]))
            car(im, *q, color=INK if c_idx % 2 == 0 else ORANGE, scale=0.68, angle=heading)


def hero(t):
    im = base_canvas('juicy').copy()
    finland_map(im, t, (970, 64, 1840, 1016), bg=CARD, border='#E05500')
    im.paste(LOGO_BADGE, (80, 128), LOGO_BADGE)
    enter(im, 'Cheap-Drive', 232, 138, 98, t, .02, weight=700)
    enter(im, 'Quote requests.', 80, 414, 108, t, .12, weight=700)
    enter(im, 'Post driver gigs.', 80, 552, 108, t, .22, weight=700)
    if t > .4:
        badge(im, '≥90% on time', 86, 768, color=SUNBURST, bg=INK, size=32)
    return im

def evolution(t):
    """Iteration and run volume; category averages imply no profit progression."""
    im = base_canvas('sunburst').copy()
    enter(im, 'Prototype. Test. Loop. Repeat.', 80, 80, 88, t, .05, weight=700)
    txt(im, 'Each dot ≈10 practice runs', 84, 190, 24, MUTED_INK)
    p_car = clamp((t - .4) / 7.1)
    focus = min(3, int(p_car * 4))
    protos = [('01', 'Alpha', 677, 68, 'Formula quotes'),
              ('02', 'Beta', 268, 27, 'Trust + fee timing'),
              ('03', 'Gamma', 242, 24, 'Notes + two-car gigs'),
              ('04', 'Delta', 303, 30, 'Rescue windows')]
    for i, (num, name, count, dots, strategy) in enumerate(protos):
        x, y, cw = 80 + i * 448, 238, 416
        active = i == focus
        col = ORANGE if active else MARIGOLD
        rect(im, (x, y, x + cw, 974), CARD, ORANGE if active else GOLD_LINE, r=20, width=4 if active else 2)
        circle(im, x + 48, y + 56, 26, INK)
        txt(im, num, x + 48, y + 56, 22, SUNBURST, mono=True, anchor='mm')
        txt(im, name, x + 90, y + 30, 42, INK, 700)
        appear = ease((t - .15 - i * .18) / .55)
        txt(im, str(round(count * appear)), x + 28, y + 126, 92, ORANGE if active else INK, 700)
        txt(im, 'runs', x + 28, y + 240, 28, MUTED_INK)
        for j in range(70):
            on = j < round(dots * appear)
            circle(im, x + 32 + (j % 10) * 36, y + 320 + (j // 10) * 28,
                   8 if on else 4, col if on else '#F7E6C4')
        txt(im, strategy, x + 28, 810, 29, INK, 650)
    # A level road encodes the sequence, without implying category-average gains.
    line(im, [(110, 928), (1808, 928)], GOLD_TRACK, 12)
    path_partial(im, [(110, 928), (1808, 928)], p_car, INK, 6)
    car(im, mix(110, 1808, p_car), 928, ORANGE, 1.45)
    return im

def dispatcher(t):
    im = base_canvas('citrus').copy()
    enter(im, 'Beta: quote, then deliver', 80, 90, 84, t, .05, weight=700)
    phase = min(3, int(t / 1.7))
    cards = [(80, 236, '1. Filter requests'), (565, 236, '2. Price dealer trust'),
             (80, 616, '3. Time gig fees'), (565, 616, '4. Meet deadlines ≥90.0%')]
    for i, (x, y, title) in enumerate(cards):
        active = i == phase
        rect(im, (x, y, x + 465, y + 350), CARD, ORANGE if active else GOLD_LINE, r=18, width=3 if active else 2)
        rect(im, (x + 2, y + 2, x + 463, y + 68), ORANGE if active else APRICOT, r=16)
        txt(im, title, x + 22, y + 18, 25, CARD if active else INK, 700)
        if i == 0:
            for j, (label, value) in enumerate([('Pickup slack', '≥8h'), ('Route cap', '≤500 km'), ('Trade-in', 'None')]):
                yy = y + 102 + j * 76
                txt(im, label, x + 26, yy, 27, INK, 600)
                txt(im, value, x + 438, yy + 3, 24, ORANGE, mono=True, anchor='ra')
        elif i == 1:
            txt(im, 'Quote each option', x + 26, y + 104, 31, INK, 650)
            txt(im, 'list × markup × trust', x + 26, y + 164, 25, ORANGE, mono=True)
            txt(im, 'Check same-day slack', x + 26, y + 244, 28, INK)
        elif i == 2:
            # No fee escalation while pickup is unavailable. The ramp starts
            # only when the pickup window opens and usable time starts shrinking.
            progress = clamp((t - .6) / 5.5)
            usable = clamp((progress - .4) / .6)
            txt(im, f'{mix(.80, 1.50, usable):.2f}×', x + 26, y + 84, 62, ORANGE, 700)
            txt(im, '0.80× → 1.50×', x + 438, y + 118, 21, MUTED_INK, mono=True, anchor='ra')
            pts = [(x + 30, y + 252), (x + 192, y + 252), (x + 435, y + 184)]
            rect(im, (x + 30, y + 176, x + 192, y + 268), APRICOT, r=4)
            line(im, pts, GOLD_TRACK, 6)
            # Match time to the piecewise pickup curve rather than its length.
            end = (x + 30 + 405 * progress, y + 252 - 68 * usable)
            trail = [pts[0], end] if progress <= .4 else [pts[0], pts[1], end]
            line(im, trail, ORANGE, 6)
            circle(im, *end, 9, ORANGE)
            line(im, [(x + 192, y + 173), (x + 192, y + 270)], MUTED_INK, 2)
            txt(im, 'Pickup unavailable', x + 26, y + 282, 17, MUTED_INK)
            txt(im, 'Usable time runs out', x + 437, y + 311, 18, INK, anchor='ra')
        else:
            txt(im, '≥90.0%', x + 26, y + 96, 72, ORANGE, 700)
            txt(im, 'On-time deliveries', x + 26, y + 198, 28, INK, 650)
            txt(im, 'Protect the ranking gate', x + 26, y + 266, 25, MUTED_INK)
    network(im, t + 2, (1055, 236, 1840, 966))
    return im

def observability(t):
    """Sequential inspection, with an explicitly illustrative order detail."""
    im = base_canvas('juicy').copy()
    enter(im, 'Find what broke', 80, 80, 92, t, .05, weight=700)
    phase = min(2, int(t / 1.9))
    for i, (label, x) in enumerate([('Note', 80), ('Pickup window', 326), ('Outcome', 810)]):
        badge(im, label, x, 222, color=SUNBURST if i == phase else INK,
              bg=INK if i == phase else APRICOT, size=32)
        if i < 2:
            txt(im, '→', 264 if i == 0 else 744, 221, 40, INK, 700)
    # Preserve the report imagery, with a schematic 6-run selector above it.
    rect(im, (80, 340, 1020, 978), INK, r=18)
    txt(im, 'Report', 108, 366, 27, CARD, 700)
    txt(im, '6 runs', 991, 370, 22, SUNBURST, mono=True, anchor='ra')
    for i in range(6):
        bx = 108 + i * 145
        rect(im, (bx, 422, bx + 130, 468), ORANGE if i == 0 else '#303034', r=8)
        txt(im, f'Run {i + 1}', bx + 65, 445, 22, CARD, anchor='mm')
    crop = REPORT.crop((260, 0, 1280, 560)).resize((884, 486), Image.Resampling.LANCZOS)
    im.paste(crop, (108, 486))
    rect(im, (1060, 340, 1840, 978), CARD, GOLD_LINE, r=18, width=2)
    txt(im, 'Example order · Helsinki → Tampere', 1090, 370, 30, INK, 700)
    details = [('Note', ['“Ready tomorrow after 11:30.”']),
               ('Pickup window', ['Tue 11:30–16:00', 'Fee clock starts at 11:30']),
               ('Outcome', ['Missed pickup → late delivery', 'Inspect the note parser'])]
    for i, (label, rows) in enumerate(details):
        yy = 450 + i * 166
        rect(im, (1084, yy, 1816, yy + 148), APRICOT if i == phase else CREAM,
             ORANGE if i == phase else GOLD_LINE, r=12, width=4 if i == phase else 1)
        txt(im, label, 1110, yy + 15, 29, ORANGE if i == phase else MUTED_INK, 700)
        for j, row in enumerate(rows):
            txt(im, row, 1110, yy + 64 + j * 36, 28 if j == 0 else 24, INK)
    return im

def graph_all_small():
    return ImageChops.multiply(CHART_ALL, Image.new('RGB', CHART_ALL.size, CREAM)).resize((1760, 860), Image.Resampling.LANCZOS)


@lru_cache(maxsize=1)
def graph_stages_small():
    tinted = ImageChops.multiply(CHART_STAGES, Image.new('RGB', CHART_STAGES.size, CARD)).resize((910, 680), Image.Resampling.LANCZOS)
    rect(tinted, (0, 0, 910, 92), CARD)
    rect(tinted, (0, 608, 910, 680), CARD)
    return tinted


def experiments(t):
    """Clean 5-stage all-run margin search (1,492 practice runs)."""
    im = base_canvas('chart').copy()
    im.paste(graph_all_small(), (80, 195))
    enter(im, '1,492 practice runs', 80, 64, 84, t, 0.05, color=INK, weight=700)

    stages = [
        (1, 'Alpha: 84.6% ranked'),
        (2, 'Beta: 88.1% ranked'),
        (3, 'Gamma: 97.9% ranked'),
        (4, 'Delta: 99.0% ranked'),
    ]
    if t > 0.4:
        frac = clamp((t - 0.4) / 6.8)
        pos = mix(0.0, 3.0, smooth(frac))
        col = 1.0 + pos
        stage_idx = min(3, int(pos + 0.5))
        # Exact column math from plot-runs.py: left=0.09, right=0.98, xlim=(-0.55, 4.45) -> span=5.0
        cx = 80 + 1760 * (0.09 + 0.89 * (col + 0.55) / 5.00)
        hw = 1760 * (0.89 * 0.45 / 5.00)
        rect(im, (cx - hw, 195 + 860 * 0.03, cx + hw, 195 + 860 * 0.80), None, ORANGE, r=6, width=4)
        bx = clamp(cx - 155, 80, 1480)
        badge(im, stages[stage_idx][1], bx, 172, color=CARD, bg=ORANGE, size=21)
    return im


def failure(t):
    im = base_canvas('sunburst').copy()
    enter(im, 'Gamma: more margin. One failed week.', 80, 88, 76, t, .05, weight=700)
    txt(im, 'First Gamma holdout', 84, 242, 34, INK, 650)
    txt(im, f'+€{830.44375 * ease((t - .2) / 1):,.0f}', 76, 300, 138, ORANGE, 700)
    txt(im, 'gross margin/week vs Beta', 84, 472, 32, INK, 650)
    badge(im, '7/8 weeks ranked', 84, 552, color=CARD, bg=DANGER, size=29)
    txt(im, '89.96% worst on time', 84, 638, 36, DANGER, 700)
    # Detail scale makes the actual 89.956% miss visible without rounding to 90%.
    rect(im, (80, 728, 728, 966), CARD, GOLD_LINE, r=18, width=2)
    txt(im, 'Worst on time · detail', 108, 747, 25, INK, 650)
    def oy(v): return 918 - (v - 89.9) / .2 * 100
    for value in [89.9, 90.0, 90.1]:
        yy = oy(value)
        line(im, [(204, yy), (690, yy)], DANGER if value == 90 else APRICOT, 3 if value == 90 else 1)
        txt(im, f'{value:g}%', 184, yy, 20, DANGER if value == 90 else MUTED_INK, mono=True, anchor='rm')
    circle(im, 438, oy(89.95633187772926), 10, DANGER)
    txt(im, '89.96%', 464, oy(89.95633187772926) + 6, 24, DANGER, mono=True)
    # Four separate cohorts, each containing eight paired practice weeks.
    rect(im, (774, 236, 1840, 966), CARD, GOLD_LINE, r=18, width=2)
    stages = [('Original candidate: tuning', 'Tuning', '+€1,232', '8/8 ranked'),
              ('Original candidate: fresh holdout', 'First holdout', '+€830', '7/8 ranked'),
              ('Revised candidate: screening', 'Screening', '+€1,586', '8/8 ranked'),
              ('Revised candidate: fresh confirmation', 'Confirmation', '+€2,031', '8/8 ranked')]
    for i, (cohort, title, delta, ranked) in enumerate(stages):
        x, y = 798 + (i % 2) * 518, 258 + (i // 2) * 344
        col = DANGER if i == 1 else ORANGE
        if i == 1:
            rect(im, (x - 8, y - 8, x + 498, y + 322), '#FFF0EE', DANGER, r=12, width=3)
        txt(im, title, x + 10, y + 4, 28, INK, 700)
        txt(im, f'{delta} · {ranked}', x + 10, y + 47, 24, col, 650)
        txt(im, '8 new practice weeks' if i == 1 else '8 paired practice weeks', x + 10, y + 84, 21, MUTED_INK)
        rows = [r for r in PAIRED_WEEKS if r['comparison'] == cohort]
        def py(v): return y + 266 - v / 22000 * 134
        for val in [0, 10000, 20000]:
            yy = py(val)
            line(im, [(x + 60, yy), (x + 474, yy)], APRICOT, 1)
            txt(im, f'€{val // 1000}k', x + 50, yy, 16, MUTED_INK, mono=True, anchor='rm')
        for row in rows:
            yb, yc = py(float(row['baseline_margin_eur'])), py(float(row['candidate_margin_eur']))
            line(im, [(x + 152, yb), (x + 384, yc)], GOLD_TRACK, 2)
            circle(im, x + 152, yb, 4, MUTED_INK)
            if row['candidate_qualified'] == 'False':
                line(im, [(x + 377, yc - 7), (x + 391, yc + 7)], DANGER, 4)
                line(im, [(x + 377, yc + 7), (x + 391, yc - 7)], DANGER, 4)
            else:
                circle(im, x + 384, yc, 5, col)
        txt(im, 'Beta', x + 152, y + 281, 21, MUTED_INK, anchor='ma')
        txt(im, 'Gamma', x + 384, y + 281, 21, col, anchor='ma')
    return im

def paired_chart(im, t, rows, baseline, candidate, label):
    """Shared chart grammar: paired margins and deadline trajectory, W1..Wn."""
    rect(im, (755, 236, 1840, 966), CARD, GOLD_LINE, r=18, width=2)
    txt(im, label, 790, 264, 30, INK, 700)
    txt(im, 'Gross margin / week', 790, 320, 23, MUTED_INK)
    for x, name, col in [(1434, baseline, GOLD_TRACK), (1630, candidate, ORANGE)]:
        rect(im, (x, 325, x + 26, 345), col, r=4)
        txt(im, name, x + 38, 319, 23, INK, 650)
    base_y, left, right = 660, 842, 1796
    for value in [0, 5000, 10000, 15000]:
        yy = base_y - 278 * value / 18000
        line(im, [(left - 16, yy), (right + 12, yy)], APRICOT, 1)
        txt(im, f'€{value // 1000}k', 818, yy, 17, MUTED_INK, mono=True, anchor='rm')
    n = len(rows)
    step = (right - left) / n
    bw = min(42, step * .36)
    ot_b, ot_c = [], []
    for i, (bv, cv, bot, cot) in enumerate(rows):
        cx = left + (i + .5) * step
        pp = ease((t - .3 - i * .11) / .6)
        rect(im, (cx - bw - 2, base_y - 278 * bv / 18000 * pp, cx - 2, base_y), GOLD_TRACK, GOLD_LINE, r=4)
        rect(im, (cx + 2, base_y - 278 * cv / 18000 * pp, cx + bw + 2, base_y), ORANGE, r=4)
        ot_b.append((cx, 882 - 130 * (bot - 89) / 11))
        ot_c.append((cx, 882 - 130 * (cot - 89) / 11))
        txt(im, f'W{i + 1}', cx, 910, 20 if n == 8 else 18, INK, mono=True, anchor='ma')
    txt(im, 'On time', 790, 700, 23, MUTED_INK)
    gate_y = 882 - 130 / 11
    line(im, [(826, gate_y), (1808, gate_y)], DANGER, 2)
    txt(im, '90%', 818, gate_y, 18, DANGER, mono=True, anchor='rm')
    txt(im, '100%', 818, 752, 17, MUTED_INK, mono=True, anchor='rm')
    line(im, ot_b, MUTED_INK, 3)
    line(im, ot_c, ORANGE, 4)
    for pb, pc in zip(ot_b, ot_c):
        circle(im, *pb, 4, CARD, MUTED_INK, 2)
        circle(im, *pc, 6, ORANGE, INK, 2)


def gain(t):
    im = base_canvas('citrus').copy()
    enter(im, 'Gamma: notes + two-car gigs', 80, 88, 80, t, .05, weight=700)
    txt(im, f'+€{2030.845 * ease((t - .2) / 1):,.0f}', 76, 294, 132, ORANGE, 700)
    txt(im, 'gross margin/week vs Beta', 84, 468, 32, INK, 650)
    badge(im, '8/8 weeks ranked', 84, 570, color=INK, bg=MARIGOLD, border=ORANGE, size=29)
    badge(im, '96.95% worst on time', 84, 652, color=CARD, bg=ORANGE, size=29)
    rows = [(float(r['baseline_margin_eur']), float(r['candidate_margin_eur']),
             100 * float(r['baseline_on_time']), 100 * float(r['candidate_on_time'])) for r in CONFIRM_WEEKS]
    paired_chart(im, t, rows, 'Beta', 'Gamma', '8 new practice weeks')
    return im

def result(t):
    """Both saved 5-week official ranking rounds—clean totals & bars, zero subtitles."""
    im = base_canvas('sunburst').copy()
    enter(im, 'Ten official weeks — 10/10 qualified', 80, 96, 80, t, 0.05, color=INK, weight=700)

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
            p = ease((t - 0.25 - j * 0.12) / 0.55)
            v = w['score']['marginCents'] / 100.0
            bh = 280 * (v / 14500.0) * p
            rect(im, (bx, base_y - bh, bx + 132, base_y), bar_col, outline=ORANGE if not is_r6 else None, r=6)
            if is_r6 and p > 0.05:
                rect(im, (bx, base_y - bh, bx + 132, min(base_y, base_y - bh + 8)), SUNBURST, r=3)
            if p > 0.3:
                txt(im, f'€{v / 1000:.1f}k', bx + 66, base_y - bh - 34, 21, INK, mono=True, weight=700, anchor='ma')
            txt(im, f'W{j + 1}', bx + 66, base_y + 20, 22, INK, 700, anchor='ma')
    return im


def delta_confirm(t):
    im = base_canvas('sunburst').copy()
    enter(im, 'Delta: rescue stranded orders', 80, 88, 80, t, .05, weight=700)
    txt(im, f'+€{682.11 * ease((t - .2) / 1):,.0f}', 76, 294, 138, ORANGE, 700)
    txt(im, 'gross margin/week vs Gamma', 84, 468, 30, INK, 650)
    badge(im, '11/11 weeks ranked', 84, 570, color=INK, bg=MARIGOLD, border=ORANGE, size=29)
    badge(im, '93.7% worst on time', 84, 652, color=CARD, bg=ORANGE, size=29)
    rows = [(r[1], r[2], r[4], r[5]) for r in DELTA_CONFIRM]
    paired_chart(im, t, rows, 'Gamma', 'Delta', '11 paired practice weeks')
    return im

def ending(t):
    im = base_canvas('juicy').copy()
    road_layer = im.copy()
    for offset in [-210, 0, 210]:
        line(road_layer, [(1160 + offset, 1080), (1600 + offset, 650), (1400 + offset, 350), (1830 + offset, -50)], ORANGE, 46)
    line(road_layer, [(1160, 1080), (1600, 650), (1400, 350), (1830, -50)], SUNBURST, 6)
    im.paste(road_layer, (0, 0))

    enter(im, 'Win the right work.', 80, 336, 108, t, .05, color=INK, weight=700)
    enter(im, 'Deliver it.', 80, 482, 138, t, .20, color=CARD, weight=700)

    road = [(1370, 1020), (1690, 650), (1490, 350), (1825, 15)]
    for idx_c, offset_p in enumerate([0.12, 0.54]):
        p = (offset_p + t * .11) % 1
        pos = route_point(road, p)
        ahead = route_point(road, min(p + .002, 1))
        heading = math.degrees(math.atan2(ahead[1] - pos[1], ahead[0] - pos[0]))
        car(im, *pos, INK if idx_c == 0 else CARD, 2.8, heading)
    return im


FUNCS = [hero, evolution, dispatcher, observability, experiments, failure, gain, delta_confirm, ending]


def frame(t):
    idx = next((i for i, (a, b) in enumerate(SCENES) if a <= t < b), 8)
    a, b = SCENES[idx]
    im = FUNCS[idx](t - a)
    dt = t - a
    if idx and dt < .30:
        xx = round(W * ease(dt / .30))
        prev = FUNCS[idx - 1](SCENES[idx - 1][1] - SCENES[idx - 1][0] + dt)
        im.paste(prev.crop((xx, 0, W, H)), (xx, 0))
        rect(im, (max(0, xx - 12), 0, xx + 2, H), ORANGE if idx not in [0, 3, 8] else INK)
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
    for cut in [5, 13, 20, 26, 34, 41, 48, 55]:
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
    times = [2.2, 7.5, 11.2, 14.5, 18.2, 21.0, 23.0, 25.0, 28.5, 30.5, 32.0, 38.0, 45.0, 52.0, 57.5]
    thumbs = []
    for p in out.glob('frame-v2-*.png'):
        p.unlink()
    for i, t in enumerate(times):
        im = frame(t)
        im.save(out / f'frame-v2-{i + 1:02d}-{t:04.1f}s.png')
        thumb = im.resize((640, 360), Image.Resampling.LANCZOS)
        thumbs.append(thumb)
    sheet = Image.new('RGB', (1920, math.ceil(len(thumbs) / 3) * 360), '#FF7700')
    for i, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((i % 3) * 640, (i // 3) * 360))
    sheet.save(out / 'contact-sheet-v2.jpg', quality=93)
    sheet.save(ROOT / 'assets/contact-sheet-v2.jpg', quality=93)
    poster = frame(2.2)
    poster.save(out / 'poster-v2.png')
    poster.save(ROOT / 'assets/poster-v2.png')


def render(out, draft=False):
    soundtrack(out / 'soundtrack-v2.wav')
    for caption in ['captions-v2.srt', 'captions-v2.vtt']:
        (out / caption).write_bytes((ROOT / caption).read_bytes())
    width, height = (960, 540) if draft else (W, H)
    fps = 15 if draft else FPS
    name = 'cheap-drive-draft-v2.mp4' if draft else 'cheap-drive-demo-v2.mp4'
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    args = [
        ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', str(fps), '-i', '-',
        '-i', str(out / 'soundtrack-v2.wav'),
        '-i', str(ROOT / 'captions-v2.srt'),
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
    assert RUN_DATA['summary']['completed_practice'] == 1492
    assert RUN_DATA['summary']['chart_groups'] == {
        'Baseline': 2,
        'Alpha': 677,
        'Beta': 268,
        'Gamma': 242,
        'Delta': 303,
    }
    assert {name: round(group['ranked'] / group['runs'] * 100, 1)
            for name, group in RUN_DATA['groups'].items() if name != 'Baseline'} == {
                'Alpha': 84.6, 'Beta': 88.1, 'Gamma': 97.9, 'Delta': 99.0}
    first_holdout = next(c for c in CHART_DATA['cohorts']
                         if c['comparison'] == 'Original candidate: fresh holdout')
    assert round(first_holdout['mean_delta_eur']) == 830
    assert first_holdout['candidate_qualified'] == 7
    assert round(first_holdout['candidate_worst_on_time'] * 100, 2) == 89.96
    assert len(CONFIRM_WEEKS) == 8
    assert all(r['candidate_qualified'] == 'True' and float(r['delta_eur']) > 0 for r in CONFIRM_WEEKS)
    assert round(sum(float(r['delta_eur']) for r in CONFIRM_WEEKS) / 8, 3) == 2030.845
    assert len(DELTA_CONFIRM) == 11
    assert all(d[3] > 0 for d in DELTA_CONFIRM)
    assert round(sum(d[3] for d in DELTA_CONFIRM) / 11, 2) == 682.11
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
