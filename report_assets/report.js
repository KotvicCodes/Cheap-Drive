'use strict';
/* Cheap-Drive week analysis. Builds every element with safe DOM text APIs; imported values never become markup. */
let D = JSON.parse(document.getElementById('report-data').textContent);
const $ = id => document.getElementById(id);
const N = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined && text !== null) e.textContent = String(text); if (cls) e.className = cls; return e; };
const add = (parent, ...children) => { for (const child of children.flat()) if (child !== undefined && child !== null) parent.append(child instanceof Node ? child : document.createTextNode(String(child))); return parent; };
const clear = e => e.replaceChildren();
const arr = value => Array.isArray(value) ? value : [];
const EUR = new Intl.NumberFormat('en-IE', {style: 'currency', currency: 'EUR'});
const EUR_WHOLE = new Intl.NumberFormat('en-IE', {style: 'currency', currency: 'EUR', maximumFractionDigits: 0});
const EUR_COMPACT = new Intl.NumberFormat('en-IE', {style: 'currency', currency: 'EUR', notation: 'compact', maximumFractionDigits: 1});
const fmt = n => Number.isFinite(n) ? EUR.format(n / 100) : 'Unavailable';
const fmtWhole = n => Number.isFinite(n) ? EUR_WHOLE.format(Math.round(n / 100)) : 'Unavailable';
const compact = n => Number.isFinite(n) ? EUR_COMPACT.format(n / 100) : 'Unavailable';
const num = n => new Intl.NumberFormat('en-IE').format(n || 0);
const pct = n => Number.isFinite(n) ? (n * 100).toFixed(1) + '%' : 'Unavailable';
const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const weekday = d => days[((d % 7) + 7) % 7];
const dayName = d => `Day ${d + 1} · ${weekday(d)}`;
const clockOf = at => `${String(Math.floor(((at % 1440) + 1440) % 1440 / 60)).padStart(2, '0')}:${String(((at % 60) + 60) % 60).padStart(2, '0')}`;
const time = at => Number.isInteger(at) ? `${dayName(Math.floor(at / 1440))} ${clockOf(at)}` : 'Time not captured';
const human = s => String(s || 'unknown').replaceAll('_', ' ');
const GOOD = new Set(['won', 'accepted', 'parsed', 'matches', 'delivered', 'done', 'booked', 'started', 'picked up', 'revenue', 'accepted quote observed']);
const WARN = new Set(['cancelled', 'unknown', 'uncertain', 'invalid or ambiguous', 'dropped', 'expired', 'no show', 'withdrawn', 'no outcome captured', 'not captured', 'mismatch', 'no recorded final score']);
const BAD = new Set(['rejected', 'conflicting sequence']);
const toneOf = text => { const t = human(text); return BAD.has(t) ? 'bad' : GOOD.has(t) ? 'good' : WARN.has(t) ? 'warn' : ''; };
const badge = (text, tone) => N('span', human(text), 'badge ' + (tone === undefined ? toneOf(text) : tone));
const button = (text, fn, cls = '') => { const b = N('button', text, cls); b.type = 'button'; b.addEventListener('click', fn); return b; };
const icon = paths => { const s = svg('svg', {viewBox: '0 0 16 16', 'aria-hidden': 'true', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round', 'stroke-linejoin': 'round'}); for (const d of paths) s.append(svg('path', {d})); return s; };
const pre = value => N('pre', typeof value === 'string' ? value : JSON.stringify(value, null, 2));
const details = (label, value, open = false) => { const d = N('details', null, 'raw'); d.open = open; return add(d, N('summary', label), pre(value)); };
const PLACE_NAMES = {
  helsinki: 'Helsinki', espoo: 'Espoo', vantaa: 'Vantaa', porvoo: 'Porvoo', kotka: 'Kotka',
  salo: 'Salo', turku: 'Turku', raisio: 'Raisio', hyvinkaa: 'Hyvinkää', hameenlinna: 'Hämeenlinna',
  lahti: 'Lahti', kouvola: 'Kouvola', lappeenranta: 'Lappeenranta', rauma: 'Rauma', pori: 'Pori',
  lempaala: 'Lempäälä', tampere: 'Tampere', mikkeli: 'Mikkeli', savonlinna: 'Savonlinna',
  jyvaskyla: 'Jyväskylä', joensuu: 'Joensuu', seinajoki: 'Seinäjoki', kuopio: 'Kuopio',
  vaasa: 'Vaasa', kokkola: 'Kokkola', ylivieska: 'Ylivieska', kajaani: 'Kajaani',
  oulu: 'Oulu', kemi: 'Kemi', rovaniemi: 'Rovaniemi', sodankyla: 'Sodankylä', ivalo: 'Ivalo'
};
function placeName(id) {
  if (!id) return '';
  const s = String(id);
  if (PLACE_NAMES[s.toLowerCase()]) return PLACE_NAMES[s.toLowerCase()];
  return s.replace(/(^|[-_\s])([a-z])/g, (_, sep, ch) => (sep === '_' ? ' ' : sep) + ch.toUpperCase());
}
const FI_FIRST = ['Kimi', 'Valtteri', 'Mika', 'Matti', 'Pekka', 'Teemu', 'Jari', 'Sanna', 'Aino', 'Juha', 'Sami', 'Olli', 'Tuomas', 'Heikki', 'Kalle', 'Roope', 'Antti', 'Ville', 'Jukka', 'Aleksi', 'Veikko', 'Tapio', 'Paavo', 'Eero', 'Timo', 'Lasse', 'Onni', 'Matias', 'Ilkka', 'Risto', 'Laura', 'Emilia'];
const FI_LAST = ['Virtanen', 'Korhonen', 'Mäkinen', 'Nieminen', 'Hämäläinen', 'Laine', 'Heikkinen', 'Koskinen', 'Järvinen', 'Lehtonen', 'Lehtinen', 'Saarinen', 'Salminen', 'Heinonen', 'Niemi', 'Heikkilä', 'Kinnunen', 'Salonen', 'Turunen', 'Salo', 'Laitinen', 'Rantanen', 'Karjalainen', 'Jokinen', 'Mattila', 'Savolainen', 'Lahtinen', 'Ahonen', 'Ojala', 'Väisänen', 'Hiltunen', 'Miettinen', 'Aaltonen', 'Kallio', 'Hakala'];
const SV_FIRST = ['Henrik', 'Erik', 'Johan', 'Anders', 'Oskar', 'Lukas', 'Filip', 'Astrid', 'Freja', 'Emil'];
const SV_LAST = ['Lindqvist', 'Lindström', 'Nyman', 'Blomqvist', 'Sundqvist', 'Bergström', 'Holmström', 'Ekström', 'Sjöblom', 'Karlsson', 'Granlund', 'Forsberg'];
function driverName(id) {
  const s = String(id || '');
  const m = s.match(/(\d+)$/);
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  const idx = m ? Number(m[1]) : Math.abs(h);
  if (idx % 5 === 3) {
    const k = Math.floor(idx / 5);
    return SV_FIRST[k % SV_FIRST.length] + ' ' + SV_LAST[(k * 5 + Math.floor(k / SV_FIRST.length)) % SV_LAST.length];
  }
  return FI_FIRST[idx % FI_FIRST.length] + ' ' + FI_LAST[(idx * 13 + Math.floor(idx / FI_FIRST.length)) % FI_LAST.length];
}
const lineButton = line => button('L' + line, () => openDetail(() => rawDetail(line)), 'link mono');
const entityButton = (kind, id) => {
  const b = button(kind === 'driver' ? driverName(id) : id, () => openDetail(() => entityDetail(kind, id)), 'link id');
  if (kind === 'driver') b.title = id;
  return b;
};
const refCell = (kind, ids) => {
  const list = add(N('div', null, 'cell-stack'), ids.length ? ids.map(id => entityButton(kind, id)) : N('span', 'Not captured', 'unavail'));
  if (ids.length <= 4) return list;
  const group = N('details');
  add(group, N('summary', num(ids.length) + ' ' + kind + ' references'), list);
  return group;
};
const whenCell = at => {
  if (!Number.isInteger(at)) return N('span', 'Time not captured', 'unavail');
  const d = Math.floor(at / 1440);
  return add(N('span', null, 'when'), N('span', dayName(d), 'day'), ' ', N('span', clockOf(at), 'clock'));
};
const moneyCell = (cents, signed = false, whole = false) => N('span', whole ? fmtWhole(cents) : fmt(cents), cents < 0 ? 'negative' : signed && cents > 0 ? 'positive' : '');
let recorded = {}, R = {}, lookup = {}, incidentRows = [], sourceBytes = null;
let active = 'overview', filtered = [], page = 0, size = 50, sortKey = '', direction = 1, debounce;
let currentRows = [], columns = [], firstTimes = new Map();
const cache = new Map();
const activity = entity => entity.history.map(i => D.timeline[i]);
const firstAt = entity => activity(entity).find(x => Number.isInteger(x.at))?.at ?? null;
const lastAt = entity => [...activity(entity)].reverse().find(x => Number.isInteger(x.at))?.at ?? null;
const eventOf = row => row.event || row.action || {};
const payload = row => row.event || (row.action ? {action: row.action, result: row.result} : D.records[row.line - 1]?.value);
const eventSummary = row => {
  const v = eventOf(row);
  if (row.action) return row.status + (row.result?.reason ? ': ' + row.result.reason : '') + (v.prices ? ' · ' + Object.entries(v.prices).map(([k, n]) => human(k) + ' ' + fmt(n)).join(', ') : '');
  if (v.line) return fmt(v.line.cents) + ' · ' + human(v.line.kind) + ' · ' + (v.line.detail || '');
  return v.message?.text || v.reason || v.text || (v.leg !== undefined ? `Leg ${v.leg + 1} · ${placeName(v.placeId)}` : '') || (v.feeCents !== undefined ? fmt(v.feeCents) : '') || v.request?.note?.text || v.order?.option || '';
};
const color = name => `var(--${name})`;

/* Downloads stay in memory; nothing is uploaded. */
function download(name, value, type = 'application/json') {
  const bytes = value instanceof Uint8Array ? value : typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  const url = URL.createObjectURL(new Blob([bytes], {type}));
  const a = N('a'); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
function source() {
  if (!sourceBytes) {
    if (D.source.base64) {
      const s = atob(D.source.base64);
      sourceBytes = Uint8Array.from(s, c => c.charCodeAt(0));
    } else {
      const lines = D.records.map(r => JSON.stringify(r.value ?? {}) + '\n').join('');
      sourceBytes = new TextEncoder().encode(lines);
    }
  }
  return sourceBytes;
}
function sliceRecordText(r) {
  if (D.source.base64) return new TextDecoder().decode(source().subarray(r.offset, r.offset + r.length));
  return JSON.stringify(r.value ?? {});
}
$('export-source').onclick = () => download('cheap-drive-original.jsonl', source(), 'application/octet-stream');
$('export-model').onclick = () => download('cheap-drive-analysis.json', D);

/* Theme: follows the system unless the viewer picks one. Storage is optional. */
const THEME_KEY = 'cheap-drive-report-theme', THEMES = ['system', 'light', 'dark'];
let theme = 'system';
try { theme = THEMES.includes(localStorage.getItem(THEME_KEY)) ? localStorage.getItem(THEME_KEY) : 'system'; } catch (_) { theme = 'system'; }
function themeIcon(mode) {
  if (mode === 'light') {
    const s = svg('svg', {viewBox: '0 0 18 18', 'aria-hidden': 'true', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.7, 'stroke-linecap': 'round', 'stroke-linejoin': 'round'});
    const c = svg('circle', {cx: 9, cy: 9, r: 3.4, fill: 'currentColor', 'fill-opacity': 0.2});
    s.append(c, svg('path', {d: 'M9 1.8v1.8M9 14.4v1.8M1.8 9h1.8M14.4 9h1.8M3.9 3.9l1.3 1.3M12.8 12.8l1.3 1.3M3.9 14.1l1.3-1.3M12.8 5.2l1.3-1.3'}));
    return s;
  }
  if (mode === 'dark') {
    const s = svg('svg', {viewBox: '0 0 18 18', 'aria-hidden': 'true', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.7, 'stroke-linecap': 'round', 'stroke-linejoin': 'round'});
    s.append(svg('path', {d: 'M14.5 11.4A5.8 5.8 0 0 1 6.6 3.5a5.8 5.8 0 1 0 7.9 7.9Z', fill: 'currentColor', 'fill-opacity': 0.2}));
    return s;
  }
  const s = svg('svg', {viewBox: '0 0 32 16', 'aria-hidden': 'true', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round'});
  s.append(
    svg('circle', {cx: 6, cy: 8, r: 2.3, fill: 'currentColor', 'fill-opacity': 0.22}),
    svg('path', {d: 'M6 2.5v1.3M6 12.2v1.3M0.8 8h1.3M9.9 8h1.3M2.3 4.3l.9.9M8.8 10.8l.9.9M2.3 11.7l.9-.9M8.8 5.2l.9-.9'}),
    svg('path', {d: 'M14.8 13L17.2 3', opacity: 0.45}),
    svg('path', {d: 'M29.8 10.2A4.4 4.4 0 0 1 24.2 4.6a4.4 4.4 0 1 0 5.6 5.6Z', fill: 'currentColor', 'fill-opacity': 0.22})
  );
  return s;
}
function applyTheme(next) {
  theme = next;
  if (theme === 'system') document.documentElement.removeAttribute('data-theme'); else document.documentElement.dataset.theme = theme;
  const t = $('theme-toggle'); clear(t);
  add(t, themeIcon(theme), N('span', {system: 'Auto', light: 'Light', dark: 'Dark'}[theme]));
  t.setAttribute('aria-label', `Color theme: ${theme}. Activate to switch.`);
  try { if (theme === 'system') localStorage.removeItem(THEME_KEY); else localStorage.setItem(THEME_KEY, theme); } catch (_) { /* storage unavailable */ }
}
$('theme-toggle').onclick = () => applyTheme(THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length]);
applyTheme(theme);

const check = (tone = '') => add(N('span', null, 'check ' + tone), icon(tone ? ['M8 4.2v4.6', 'M8 11.6v.2'] : ['M4.4 8.3l2.4 2.4 4.8-5']));

function getNavItems() {
  const isDemo = Boolean($('report-runs'));
  return [
    ['overview', 'Overview', null, false],
    ['orders', isDemo ? 'Orders' : 'Requests & orders', D.orders.length, false],
    ['gigs', isDemo ? 'Gigs' : 'Gigs & stops', D.gigs.length, false],
    ['drivers', 'Drivers', D.drivers.length, false],
    ['captures', isDemo ? 'Map' : 'Captured context', null, false],
    ['timeline', 'Event timeline', D.timeline.length, isDemo],
    ['incidents', 'Incidents', incidentRows.length, isDemo],
    ['ledger', 'Financial ledger', D.ledger.length, isDemo],
    ['source', 'Source & integrity', D.source.lines, isDemo]
  ];
}

function renderNav() {
  const navEl = $('nav'); clear(navEl);
  for (const [id, label, count, hide] of getNavItems()) {
    const b = button('', () => navigate(id)); b.dataset.tab = id; b.hidden = Boolean(hide);
    if (id === active) { b.classList.add('active'); b.setAttribute('aria-current', 'page'); }
    add(b, N('span', label), count === null ? null : N('span', num(count), 'count'));
    navEl.append(b);
  }
}

function loadModel(nextD, labelOverride) {
  D = nextD;
  sourceBytes = null;
  cache.clear();
  firstTimes = new Map();
  recorded = [...D.scores].reverse().find(s => s.final)?.score || {};
  R = D.reconciliation;
  lookup = {order: new Map(D.orders.map(x => [x.id, x])), gig: new Map(D.gigs.map(x => [x.id, x])), driver: new Map(D.drivers.map(x => [x.id, x]))};
  incidentRows = D.timeline.filter(x => x.incident || x.status === 'rejected' || x.conflict);
  $('version').textContent = '';
  $('run-label').textContent = '';
  const modeLabel = labelOverride || (D.run.mode === 'demo' ? 'Synthetic demo' : D.run.mode === 'practice' ? 'Practice' : 'Level ' + (D.run.level ?? 8));
  $('mode').hidden = true;
  const card = $('run-card'); clear(card);
  for (const [k, v] of [['Level', D.run.level ?? '8'], ['Margin', fmt(recorded.marginCents)], ['On time', pct(recorded.onTimeShare)]]) {
    add(card, add(N('div', null, 'row'), N('span', k), N('b', v)));
  }
  renderNav();
}

loadModel(D);

/* Generic building blocks */
function section(title, subtitle, cls = '') {
  const panel = N('section', null, 'panel ' + cls), header = N('div', null, 'panel-header'), t = N('div');
  add(t, N('h2', title), subtitle ? N('p', subtitle) : null); add(header, t); panel.append(header);
  return panel;
}
function metric(label, value, note, cls = '') {
  const e = N('div', null, 'panel metric ' + cls);
  add(e, N('div', label, 'metric-label'), N('div', value, 'metric-value ' + (typeof value === 'string' && value.startsWith('-') ? 'negative' : '')), N('small', note || ''));
  return e;
}
function svg(tag, attrs = {}) { const e = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v)); return e; }
function svgText(attrs, text, cls) { const t = svg('text', attrs); t.textContent = text; if (cls) t.setAttribute('class', cls); return t; }
function legend(items) {
  const l = N('div', null, 'legend');
  for (const [label, c, shape] of items) { const i = N('i', null, shape || ''); i.style.setProperty('--legend', c); l.append(add(N('span'), i, label)); }
  return l;
}

/* Tooltip */
const tip = $('tip');
function showTip(evt, title, rows) {
  clear(tip); tip.append(N('b', title));
  for (const [label, value, c] of rows) {
    const s = N('span'); if (c) { const i = N('i'); i.style.setProperty('--legend', c); s.append(i); } s.append(label);
    tip.append(add(N('div', null, 'r'), s, N('strong', value)));
  }
  tip.hidden = false;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let x = evt.clientX + 14, y = evt.clientY + 14;
  if (x + w > innerWidth - 8) x = Math.max(8, evt.clientX - w - 14);
  if (y + h > innerHeight - 8) y = Math.max(8, evt.clientY - h - 14);
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
}
const hideTip = () => { tip.hidden = true; };

/* Charts are drawn at their real pixel width so text stays crisp, and redrawn on resize. */
let observers = [], stopReplay = null;
function responsive(draw, cls = 'chart-box') {
  const box = N('div', null, cls);
  const run = () => { const w = Math.max(260, Math.round(box.clientWidth || 720)); if (box.dataset.w === String(w)) return; box.dataset.w = String(w); clear(box); draw(box, w); };
  run();
  if ('ResizeObserver' in window) { const ro = new ResizeObserver(run); ro.observe(box); observers.push(ro); }
  return box;
}
function niceTicks(min, max, count = 5) {
  const span = max - min || 1, raw = span / count, mag = 10 ** Math.floor(Math.log10(raw)), n = raw / mag;
  const step = (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * mag, out = [];
  for (let v = Math.floor(min / step) * step; v <= Math.ceil(max / step) * step + step / 2; v += step) out.push(Math.round(v / step) * step);
  return out;
}
function lastIndexAtOrBefore(points, x) { let lo = 0, hi = points.length - 1, ans = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (points[m][0] <= x) { ans = m; lo = m + 1; } else hi = m - 1; } return ans; }
function weekAxis(s, xmin, xmax, x, top, bottom, width) {
  const firstDay = Math.floor(xmin / 1440), lastDay = Math.ceil(xmax / 1440) - 1, bw = x(1440) - x(0);
  for (let d = firstDay; d <= lastDay; d++) {
    if (d % 2) s.append(svg('rect', {x: x(d * 1440), y: top, width: Math.max(0, Math.min(x((d + 1) * 1440), width) - x(d * 1440)), height: bottom - top, class: 'day-band'}));
    const label = bw >= 58 ? `D${d + 1} ${weekday(d)}` : bw >= 26 ? `D${d + 1}` : (d % 2 ? '' : `D${d + 1}`);
    if (label) s.append(svgText({x: x(d * 1440 + 720), y: bottom + 16, 'text-anchor': 'middle'}, label));
  }
}
function lineChart({title, series, height = 260, stepped = true, markers = false}) {
  return responsive((box, width) => {
    const points = series.flatMap(s => s.points).filter(p => Number.isFinite(p[0]) && Number.isFinite(p[1]));
    const s = svg('svg', {viewBox: `0 0 ${width} ${height}`, width, height, class: 'chart', role: 'img', 'aria-label': title});
    const t = svg('title'); t.textContent = title; s.append(t);
    if (!points.length) { s.append(svgText({x: 20, y: 40}, 'No observations')); box.append(s); return; }
    const L = width < 480 ? 46 : 58, Rm = width < 480 ? 8 : 70, T = 10, B = height - 26;
    const xmin = Math.min(0, ...points.map(p => p[0])), xmax = Math.max(1440, Math.ceil(Math.max(...points.map(p => p[0])) / 1440) * 1440);
    const vals = points.map(p => p[1]), yt = niceTicks(Math.min(0, ...vals), Math.max(0, ...vals));
    const ymin = yt[0], ymax = yt[yt.length - 1] === ymin ? ymin + 100 : yt[yt.length - 1];
    const x = n => L + (n - xmin) / (xmax - xmin) * (width - L - Rm), y = n => B - (n - ymin) / (ymax - ymin) * (B - T);
    weekAxis(s, xmin, xmax, x, T, B, width - Rm);
    for (const v of yt) { s.append(svg('line', {x1: L, x2: width - Rm, y1: y(v), y2: y(v), class: v === 0 ? 'zero-line' : 'grid-line'})); s.append(svgText({x: L - 8, y: y(v) + 4, 'text-anchor': 'end'}, compact(v))); }
    const drawn = [];
    for (const ser of series) {
      const pts = ser.points.filter(p => Number.isFinite(p[0]) && Number.isFinite(p[1]));
      if (!pts.length) continue;
      const useStep = ser.stepped !== undefined ? ser.stepped : stepped;
      const d = pts.map((p, i) => i ? (useStep ? `H${x(p[0]).toFixed(1)}V${y(p[1]).toFixed(1)}` : `L${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`) : `M${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join('');
      const path = svg('path', {d, class: 'series'}); path.style.stroke = ser.color; s.append(path);
      if (ser.markers ?? markers) for (const p of pts) { const c = svg('circle', {cx: x(p[0]), cy: y(p[1]), r: 4, class: 'hover-dot'}); c.style.fill = ser.color; s.append(c); }
      drawn.push({...ser, pts, useStep});
    }
    if (Rm > 20) {
      const ends = drawn.map(ser => ({ser, y: y(ser.pts.at(-1)[1]), x: x(ser.pts.at(-1)[0])})).sort((a, b) => a.y - b.y);
      if (ends.every((e, i) => !i || e.y - ends[i - 1].y >= 14)) for (const e of ends) {
        const c = svg('circle', {cx: e.x, cy: e.y, r: 4, class: 'hover-dot'}); c.style.fill = e.ser.color; s.append(c);
        s.append(svgText({x: e.x + 8, y: e.y + 4}, compact(e.ser.pts.at(-1)[1]), 'end-label'));
      }
    }
    const cross = svg('line', {y1: T, y2: B, class: 'crosshair', visibility: 'hidden'}), dots = drawn.map(ser => { const c = svg('circle', {r: 4, class: 'hover-dot', visibility: 'hidden'}); c.style.fill = ser.color; return c; });
    add(s, cross, dots);
    const hit = svg('rect', {x: L, y: T, width: width - L - Rm, height: B - T, class: 'hit'});
    hit.addEventListener('pointermove', evt => {
      const r = s.getBoundingClientRect(), px = (evt.clientX - r.left) * (width / r.width);
      const minute = Math.round(xmin + (px - L) / (width - L - Rm) * (xmax - xmin));
      const rows = [];
      cross.setAttribute('x1', px); cross.setAttribute('x2', px); cross.setAttribute('visibility', 'visible');
      drawn.forEach((ser, i) => {
        const k = lastIndexAtOrBefore(ser.pts, minute);
        if (k < 0) { dots[i].setAttribute('visibility', 'hidden'); return; }
        const p = ser.pts[k];
        dots[i].setAttribute('cx', ser.useStep ? px : x(p[0])); dots[i].setAttribute('cy', y(p[1])); dots[i].setAttribute('visibility', 'visible');
        rows.push([ser.label, fmt(p[1]), ser.color]);
      });
      showTip(evt, time(Math.max(0, minute)), rows.length ? rows : [['No observation yet', '']]);
    });
    hit.addEventListener('pointerleave', () => { hideTip(); cross.setAttribute('visibility', 'hidden'); dots.forEach(d => d.setAttribute('visibility', 'hidden')); });
    s.append(hit);
    box.append(s);
  });
}
function barPath(x, w, y0, y1, r = 4) {
  const up = y1 < y0, h = Math.abs(y1 - y0), rr = Math.min(r, h, w / 2);
  if (h < .5) return '';
  return up
    ? `M${x},${y0}V${y1 + rr}Q${x},${y1} ${x + rr},${y1}H${x + w - rr}Q${x + w},${y1} ${x + w},${y1 + rr}V${y0}Z`
    : `M${x},${y0}V${y1 - rr}Q${x},${y1} ${x + rr},${y1}H${x + w - rr}Q${x + w},${y1} ${x + w},${y1 - rr}V${y0}Z`;
}
function dailyChart(rows, height = 240) {
  return responsive((box, width) => {
    const title = 'Ledger revenue and other entries per world day';
    const s = svg('svg', {viewBox: `0 0 ${width} ${height}`, width, height, class: 'chart', role: 'img', 'aria-label': title});
    const t = svg('title'); t.textContent = title; s.append(t);
    if (!rows.length) { s.append(svgText({x: 20, y: 40}, 'No timed ledger entries')); box.append(s); return; }
    const L = width < 480 ? 46 : 58, Rm = 10, T = 10, B = height - 26;
    const vals = rows.flatMap(r => [r.rev, r.other, r.net, 0]), yt = niceTicks(Math.min(...vals), Math.max(...vals));
    const ymin = yt[0], ymax = yt.at(-1) === ymin ? ymin + 100 : yt.at(-1);
    const first = rows[0].d, count = rows.at(-1).d - first + 1, bw = (width - L - Rm) / count;
    const y = n => B - (n - ymin) / (ymax - ymin) * (B - T), cx = d => L + (d - first + .5) * bw;
    for (const v of yt) { s.append(svg('line', {x1: L, x2: width - Rm, y1: y(v), y2: y(v), class: v === 0 ? 'zero-line' : 'grid-line'})); s.append(svgText({x: L - 8, y: y(v) + 4, 'text-anchor': 'end'}, compact(v))); }
    const colW = Math.max(3, Math.min(22, bw * .32));
    for (const r of rows) {
      const c = cx(r.d);
      const a = svg('path', {d: barPath(c - colW - 1, colW, y(0), y(r.rev)), class: 'col'}); a.style.fill = color('s-rev');
      const b = svg('path', {d: barPath(c + 1, colW, y(0), y(r.other)), class: 'col'}); b.style.fill = color('s-cost');
      const n = svg('line', {x1: c - colW - 5, x2: c + colW + 5, y1: y(r.net), y2: y(r.net), 'stroke-width': 2.5, 'stroke-linecap': 'round'}); n.style.stroke = color('s-net');
      add(s, a, b, n);
      const label = bw >= 58 ? `D${r.d + 1} ${weekday(r.d)}` : bw >= 26 ? `D${r.d + 1}` : (r.d % 2 ? '' : `D${r.d + 1}`);
      if (label) s.append(svgText({x: c, y: B + 16, 'text-anchor': 'middle'}, label));
      const hit = svg('rect', {x: c - bw / 2, y: T, width: bw, height: B - T, class: 'col-hit', tabindex: 0, role: 'button', 'aria-label': `${dayName(r.d)}: revenue ${fmt(r.rev)}, other ${fmt(r.other)}, net ${fmt(r.net)}. Open ledger for this day.`});
      hit.style.cursor = 'pointer';
      hit.addEventListener('pointermove', evt => showTip(evt, dayName(r.d), [['Revenue', fmt(r.rev), color('s-rev')], ['Costs & fees', fmt(r.other), color('s-cost')], ['Net', fmt(r.net), color('s-net')], ['Entries', num(r.count)]]));
      hit.addEventListener('pointerleave', hideTip);
      hit.addEventListener('click', () => { hideTip(); navigate('ledger', {day: String(r.d)}); });
      hit.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate('ledger', {day: String(r.d)}); } });
      s.append(hit);
    }
    box.append(s);
  });
}
function bars(parent, entries, {money = false} = {}) {
  const list = N('div', null, 'bar-list'), max = Math.max(1, ...entries.map(x => Math.abs(x.value)));
  for (const item of entries) {
    const track = N('div', null, 'bar-track'), fill = N('div', null, 'bar-fill');
    fill.style.width = (Math.abs(item.value) / max * 100) + '%'; fill.style.background = item.color; track.append(fill);
    const value = money ? moneyCell(item.value, false, true) : N('span', num(item.value));
    value.classList.add('bar-value');
    const row = add(N('div', null, 'bar-row' + (item.value === 0 ? ' zero' : '')), N('span', item.label), track, value);
    row.title = `${item.label}: ${money ? fmtWhole(item.value) : num(item.value)}`;
    list.append(row);
  }
  parent.append(list);
}
function heatmap() {
  const counts = new Map();
  for (const x of D.timeline) if (x.kind === 'price_request' && !x.conflict && Number.isInteger(x.at)) { const k = Math.floor(x.at / 1440) * 24 + Math.floor(((x.at % 1440) + 1440) % 1440 / 60); counts.set(k, (counts.get(k) || 0) + 1); }
  const dayList = [...new Set([...counts.keys()].map(k => Math.floor(k / 24)))].sort((a, b) => a - b);
  const wrap = N('div');
  if (!dayList.length) { wrap.append(N('p', 'No timed arrivals.', 'muted')); return wrap; }
  const max = Math.max(...counts.values()), grid = N('div', null, 'heatmap');
  const level = n => n ? Math.min(5, Math.ceil(n / max * 5)) : 0;
  for (const d of dayList) {
    const row = N('div', null, 'heat-row');
    for (let h = 0; h < 24; h++) {
      const n = counts.get(d * 24 + h) || 0, hh = String(h).padStart(2, '0');
      const cell = N('button'); cell.type = 'button'; cell.style.background = color('heat-' + level(n));
      cell.setAttribute('aria-label', `${dayName(d)} ${hh}:00 to ${hh}:59, ${num(n)} requests`);
      if (!n) cell.disabled = true;
      cell.addEventListener('pointermove', evt => showTip(evt, `${dayName(d)} · ${hh}:00–${hh}:59`, [['Requests', num(n)]]));
      cell.addEventListener('pointerleave', hideTip);
      cell.addEventListener('click', () => { hideTip(); navigate('timeline', {kind: 'price_request', day: String(d), from: hh + ':00', to: hh + ':59'}); });
      row.append(cell);
    }
    add(grid, add(N('span', null, 'heat-label'), N('span', dayName(d), 'long'), N('span', `D${d + 1} ${weekday(d)}`, 'short')), row);
  }
  const hours = N('div', null, 'heat-hours'); for (let h = 0; h < 24; h++) hours.append(N('span', String(h).padStart(2, '0')));
  add(grid, N('span'), hours);
  const lg = add(N('div', null, 'heat-legend'), N('span', 'None'));
  for (let i = 0; i <= 5; i++) { const sw = N('i'); sw.style.background = color('heat-' + i); lg.append(sw); }
  add(lg, N('span', 'Peak'));
  return add(wrap, grid, lg);
}

/* Overview — clean, zero-fluff presentation */
function overview() {
  const root = $('overview'); clear(root);
  const metrics = N('div', null, 'metrics');
  add(metrics,
    metric('Margin', fmtWhole(recorded.marginCents), R.status === 'matches' ? '' : human(R.status), 'accent'),
    metric('Revenue', fmtWhole(recorded.revenueCents), R.status === 'matches' ? '' : fmtWhole(R.ledgerRevenueCents)),
    metric('On time', pct(recorded.onTimeShare), recorded.ranked === true ? 'Ranked' : recorded.ranked === false ? 'Unranked' : ''),
    metric('Orders won', recorded.wonOrders === undefined ? 'Unavailable' : num(recorded.wonOrders), num(D.gigs.length) + ' gigs'));
  root.append(metrics);

  const strip = N('div', null, 'stat-strip'), requests = D.stats.price_request || 0;
  for (const [label, value] of [
    ['Requests', num(requests)],
    ['Win rate', requests ? pct((D.stats.order_won || 0) / requests) : 'Unavailable'],
    ['Gigs', num(D.gigs.length)],
    ['Drivers', num(D.drivers.length)],
    ['Ledger', num(D.ledger.length)],
    ['Incidents', num(incidentRows.length)]
  ]) strip.append(add(N('div'), N('span', label), N('b', value)));
  root.append(strip);

  let net = 0, rev = 0, cost = 0;
  const netPts = [[0, 0]], revPts = [[0, 0]], costPts = [[0, 0]], perDay = new Map();
  for (const l of D.ledger) {
    net += l.cents; if (l.kind === 'revenue') rev += l.cents; else cost += l.cents;
    if (Number.isInteger(l.at)) {
      netPts.push([l.at, net]); revPts.push([l.at, rev]); costPts.push([l.at, cost]);
      const d = Math.floor(l.at / 1440), e = perDay.get(d) || {d, rev: 0, other: 0, net: 0, count: 0};
      if (l.kind === 'revenue') e.rev += l.cents; else e.other += l.cents; e.net += l.cents; e.count++; perDay.set(d, e);
    }
  }
  const dayRows = [];
  if (perDay.size) { const ks = [...perDay.keys()]; for (let d = Math.min(...ks); d <= Math.max(...ks); d++) dayRows.push(perDay.get(d) || {d, rev: 0, other: 0, net: 0, count: 0}); }

  const isDemo = Boolean($('report-runs'));
  const row1 = N('div', null, 'grid');
  const finance = section('Cumulative ledger', null, isDemo ? 'span-7' : 'span-8');
  const series = [{label: 'Revenue', points: revPts, color: color('s-rev')}, {label: 'Costs & fees', points: costPts, color: color('s-cost')}, {label: 'Margin', points: netPts, color: color('s-net')}];
  add(finance, lineChart({title: 'Cumulative ledger', series, height: 240}), legend(series.map(x => [x.label, x.color])));
  const daily = section('Daily flow', null, isDemo ? 'span-5' : 'span-7');
  add(daily, dailyChart(dayRows, 240), legend([['Revenue', color('s-rev'), 'sq'], ['Costs & fees', color('s-cost'), 'sq'], ['Net', color('s-net')]]));
  const flow = section('Requests', null, 'span-4');
  flow.hidden = isDemo;
  const won = D.stats.order_won || 0, lost = D.stats.order_lost || 0, open = Math.max(0, requests - won - lost);
  add(flow, add(N('div', null, 'funnel-head'), N('strong', requests ? pct(won / requests) : 'Unavailable'), N('span', 'won')));
  const seg = N('div', null, 'segbar'); seg.setAttribute('aria-hidden', 'true');
  for (const [v, c] of [[won, color('s-net')], [lost, color('s-cost')], [open, 'var(--line-strong)']]) if (v) { const p = N('div'); p.style.flex = String(v); p.style.background = c; seg.append(p); }
  flow.append(seg);
  const kv = N('div', null, 'kv');
  for (const [label, value, c] of [['Requests', requests, color('s-rev')], ['Won', won, color('s-net')], ['Lost', lost, color('s-cost')], ['Cancelled', D.stats.order_cancelled || 0, color('warn')]]) {
    const s = N('span'); if (c) { const i = N('i'); i.style.setProperty('--legend', c); s.append(i); } s.append(label);
    kv.append(add(N('div'), s, N('b', num(value))));
  }
  flow.append(kv);
  if (isDemo) add(row1, finance, daily);
  else add(row1, finance, flow);
  root.append(row1);

  const row2 = N('div', null, 'grid');
  row2.hidden = isDemo;
  const scores = section('Score', null, 'span-5');
  const rawScorePoints = D.scores.filter(x => Number.isInteger(x.at) && Number.isFinite(x.score.marginCents)).map(x => [x.at, x.score.marginCents]);
  const scorePoints = rawScorePoints.length === 1 ? [[0, 0], ...rawScorePoints] : rawScorePoints;
  const scoreSeries = rawScorePoints.length === 1 && netPts.length > 1
    ? [{label: 'Ledger net', points: netPts, color: color('s-cost'), stepped: true, markers: false}, {label: 'Score', points: scorePoints, color: color('s-net'), stepped: false, markers: true}]
    : [{label: 'Score', points: scorePoints, color: color('s-net'), stepped: false, markers: true}];
  scores.append(lineChart({title: 'Recorded margin at score checkpoints', series: scoreSeries, height: 240, stepped: false, markers: true}), legend(scoreSeries.map(x => [x.label, x.color])));
  if (!isDemo) add(row2, daily, scores);
  else add(row2, scores);
  root.append(row2);

  const row3 = N('div', null, 'grid');
  row3.hidden = isDemo;
  const heat = section('Arrivals', null, 'span-12');
  heat.append(heatmap());
  row3.append(heat); root.append(row3);

  const row4 = N('div', null, 'grid');
  const accounting = section('Breakdown', null, isDemo ? 'span-6' : 'span-4 flex-3');
  bars(accounting, Object.entries(R.totals).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).map(([label, value]) => ({label: human(label), value, color: label === 'revenue' ? color('s-rev') : value < 0 ? color('s-cost') : color('s-net')})), {money: true});
  const health = section('Exceptions', null, isDemo ? 'span-6' : 'span-4 flex-3');
  bars(health, ['deadline_close', 'gig_dropped', 'no_show', 'driver_late', 'visit_failed', 'gig_expired'].map(k => ({label: human(k), value: D.stats[k] || 0, color: color('brand')})).sort((a, b) => b.value - a.value));
  const checkPanel = section('Reconciliation', null, 'span-4 flex-3');
  checkPanel.hidden = isDemo;
  checkPanel.querySelector('.panel-header').append(badge(R.status, R.status === 'matches' ? 'good' : 'warn'));
  const table = N('table', null, 'mini-table'), head = N('tr');
  add(head, N('th', 'Metric'), N('th', 'Recorded'), N('th', 'Ledger'), N('th', 'Diff')); table.append(head);
  for (const [label, a, b, diff] of [['Margin', recorded.marginCents, R.ledgerMarginCents, R.marginDifferenceCents], ['Revenue', recorded.revenueCents, R.ledgerRevenueCents, R.revenueDifferenceCents]]) {
    add(table, add(N('tr'), N('td', label), add(N('td'), moneyCell(a)), add(N('td'), moneyCell(b)), add(N('td'), moneyCell(diff))));
  }
  checkPanel.append(table);
  add(row4, accounting, health, checkPanel); root.append(row4);
}

/* Explorer configuration */
const entityRefs = (kind, e) => ({order: kind === 'order' ? [e.id] : (kind === 'gig' ? e.related : []), gig: kind === 'gig' ? [e.id] : (kind === 'order' ? e.related : activity(e).flatMap(x => x.refs.gig)), driver: kind === 'driver' ? [e.id] : activity(e).flatMap(x => x.refs.driver)});
function searchText(row) {
  const key = active + ':' + (row.id ?? row.line ?? row.sourceLine);
  if (cache.has(key)) return cache.get(key);
  const extra = active === 'drivers' ? driverName(row.id) : (row.refs?.driver || []).map(driverName).join(' ');
  const data = active === 'orders' || active === 'gigs' || active === 'drivers' ? {entity: row, extra, activity: activity(row).map(payload)} : active === 'source' ? {...row, original: sliceRecordText(row)} : {...row, extra};
  const s = JSON.stringify(data).toLowerCase(); cache.set(key, s); return s;
}
const col = (key, title, value, render, cls = '') => ({key, title, value, render, cls});
const gigNet = x => x.ledger.reduce((s, i) => s + D.ledger[i].cents, 0);
const gigStops = x => (x.data.post || x.data.snapshot)?.stops?.length || 0;
const kindBadge = x => badge(x.kind, x.conflict ? 'bad' : x.status === 'rejected' ? 'bad' : x.incident ? 'warn' : x.status === 'accepted' ? 'good' : 'info');
const colsTimeline = [col('at', 'World time', x => x.at, x => whenCell(x.at)), col('kind', 'Kind', x => x.kind, kindBadge), col('order', 'Order', x => x.refs.order.join(), x => refCell('order', x.refs.order)), col('gig', 'Gig', x => x.refs.gig.join(), x => refCell('gig', x.refs.gig)), col('driver', 'Driver', x => x.refs.driver.join(), x => refCell('driver', x.refs.driver)), col('detail', 'Detail', eventSummary, x => N('span', eventSummary(x)), 'wrap'), col('line', 'Source', x => x.line, x => lineButton(x.line))];
function configure(id) {
  if (id === 'timeline' || id === 'incidents') { currentRows = id === 'incidents' ? incidentRows : D.timeline; columns = colsTimeline; return; }
  if (id === 'orders') { currentRows = D.orders; columns = [col('id', 'Order', x => x.id, x => entityButton('order', x.id)), col('at', 'First seen', firstAt, x => whenCell(firstAt(x))), col('dealer', 'Dealer', x => (x.data.request || x.data.order)?.dealerId, x => (x.data.request || x.data.order)?.dealerId ? N('span', (x.data.request || x.data.order).dealerId, 'mono') : N('span', 'Not captured', 'unavail')), col('route', 'Route', x => route(x), x => N('span', route(x)), 'wrap'), col('outcome', 'Outcome', x => x.data.outcome, x => badge(x.data.outcome, x.data.outcome === 'won' ? 'good' : x.data.outcome === 'lost' ? '' : x.data.outcome === 'cancelled' ? 'warn' : 'plain')), col('quote', 'Quote', x => x.data.quoteStatus, x => { const q = x.data.quoteStatus, e = N('span', {'accepted quote observed': 'Observed', 'no accepted quote captured': 'Not captured', 'unquoted (reveal)': 'Unquoted (reveal)'}[q] || q, q === 'accepted quote observed' ? '' : 'unavail'); e.title = q; return e; }), col('price', 'Won price', x => x.data.order?.priceCents, x => x.data.order?.priceCents === undefined ? N('span', 'Unavailable', 'unavail') : moneyCell(x.data.order.priceCents), 'numeric'), col('net', 'Direct net', x => x.directNetCents, x => moneyCell(x.directNetCents), 'numeric')]; return; }
  if (id === 'gigs') { currentRows = D.gigs; columns = [col('id', 'Gig', x => x.id, x => entityButton('gig', x.id)), col('at', 'First seen', firstAt, x => whenCell(firstAt(x))), col('status', 'State', x => x.data.lastObservedStatus, x => badge(x.data.lastObservedStatus || x.data.snapshot?.status || 'not captured')), col('orders', 'Orders', x => x.related.join(), x => refCell('order', x.related)), col('stops', 'Stops', gigStops, x => num(gigStops(x)), 'numeric'), col('views', 'Views', x => x.viewsCount ?? activity(x).filter(e => e.kind === 'gig_viewed').length, x => num(x.viewsCount ?? activity(x).filter(e => e.kind === 'gig_viewed').length), 'numeric'), col('net', 'Gig net', gigNet, x => moneyCell(gigNet(x)), 'numeric')]; return; }
  if (id === 'drivers') { currentRows = D.drivers; columns = [col('id', 'Driver', x => x.id, x => entityButton('driver', x.id)), col('at', 'First seen', firstAt, x => whenCell(firstAt(x))), col('home', 'Home', x => placeName(x.data.profile?.homePlaceId), x => x.data.profile?.homePlaceId ? placeName(x.data.profile.homePlaceId) : N('span', 'Unavailable', 'unavail')), col('rating', 'Rating', x => x.data.profile?.rating, x => x.data.profile?.rating ?? N('span', 'Unavailable', 'unavail'), 'numeric'), ...[['gig_viewed', 'Gigs viewed'], ['gig_booked', 'Gigs booked'], ['gig_dropped', 'Gigs dropped'], ['no_show', 'No-shows']].map(([k, label]) => col(k, label, x => x.counts?.[k] ?? activity(x).filter(e => e.kind === k).length, x => num(x.counts?.[k] ?? activity(x).filter(e => e.kind === k).length), 'numeric'))]; return; }
  if (id === 'ledger') { currentRows = D.ledger; columns = [col('at', 'World time', x => x.at, x => whenCell(x.at)), col('kind', 'Kind', x => x.kind, x => badge(x.kind, x.kind === 'revenue' ? 'good' : '')), col('cents', 'Amount', x => x.cents, x => moneyCell(x.cents, true), 'numeric'), col('order', 'Order', x => x.orderId, x => x.orderId ? entityButton('order', x.orderId) : N('span', 'Not assigned', 'unavail')), col('gig', 'Gig', x => x.gigId, x => x.gigId ? entityButton('gig', x.gigId) : N('span', 'Not captured', 'unavail')), col('detail', 'Detail', x => x.detail, x => N('span', x.detail || ''), 'wrap'), col('sourceLine', 'Source', x => x.sourceLine, x => lineButton(x.sourceLine))]; return; }
  if (id === 'source') { currentRows = D.records; columns = [col('line', 'Line', x => x.line, x => lineButton(x.line)), col('offset', 'Offset', x => x.offset, x => num(x.offset), 'numeric'), col('length', 'Bytes', x => x.length, x => num(x.length), 'numeric'), col('kind', 'Type', x => x.value?.type || 'unknown', x => badge(x.value?.type || 'unknown', 'info')), col('error', 'State', x => x.error || '', x => x.error ? badge(x.error, 'warn') : badge('parsed', 'good')), col('fields', 'Fields', x => JSON.stringify(Object.keys(x.value || {})), x => N('span', x.value && typeof x.value === 'object' ? Object.keys(x.value).join(', ') : typeof x.value), 'wrap')]; }
}
function route(o) { return arr((o.data.order || o.data.request)?.legs).map(l => (placeName(l?.pickup?.placeId) || '?') + ' → ' + (placeName(l?.delivery?.placeId) || '?')).join(' · ') || 'Route unavailable'; }
function rowRefs(row) { if (active === 'orders') return entityRefs('order', row); if (active === 'gigs') return entityRefs('gig', row); if (active === 'drivers') return entityRefs('driver', row); if (active === 'ledger') return {order: row.orderId ? [row.orderId] : [], gig: row.gigId ? [row.gigId] : [], driver: []}; return row.refs || {order: [], gig: [], driver: []}; }
function rowTimes(row) { return ['orders', 'gigs', 'drivers'].includes(active) ? activity(row).map(e => e.at) : [row.at ?? row.value?.at]; }
function rowFirst(row) { if (!firstTimes.has(row)) firstTimes.set(row, rowTimes(row).find(Number.isInteger) ?? null); return firstTimes.get(row); }
function rowKind(row) { return active === 'source' ? row.value?.type || 'unknown' : row.kind || ''; }
function rowState(row) { return active === 'orders' ? row.data.outcome : active === 'gigs' ? row.data.lastObservedStatus || row.data.snapshot?.status || 'not captured' : active === 'source' ? (row.error ? 'invalid or ambiguous' : 'parsed') : row.conflict ? 'conflicting sequence' : row.status || ''; }
function primaryOpen(row) {
  if (active === 'orders') return () => openDetail(() => entityDetail('order', row.id));
  if (active === 'gigs') return () => openDetail(() => entityDetail('gig', row.id));
  if (active === 'drivers') return () => openDetail(() => entityDetail('driver', row.id));
  const line = row.sourceLine ?? row.line; return line ? () => openDetail(() => rawDetail(line)) : null;
}

/* Filters */
const filterIds = ['search', 'day', 'from', 'to', 'kind', 'state', 'order-filter', 'gig-filter', 'driver-filter'];
const filterLabels = {search: 'Search', day: 'Day', from: 'From', to: 'To', kind: 'Kind', state: 'State', 'order-filter': 'Order ID', 'gig-filter': 'Gig ID', 'driver-filter': 'Driver ID'};
for (const kind of ['order', 'gig', 'driver']) { const label = N('label', kind === 'order' ? 'Order ID' : kind === 'gig' ? 'Gig ID' : 'Driver ID'); const input = N('input'); input.id = kind + '-filter'; input.placeholder = 'Any'; input.type = 'search'; label.append(input); $('filter-grid').append(label); }
function setupFilters() {
  for (const id of filterIds) $(id).value = '';
  firstTimes = new Map();
  const allTimes = currentRows.flatMap(rowTimes).filter(Number.isInteger), daySet = [...new Set(allTimes.map(x => Math.floor(x / 1440)))].sort((a, b) => a - b);
  for (const [id, values, label] of [['day', daySet, dayName], ['kind', [...new Set(currentRows.map(rowKind).filter(Boolean))].sort(), human], ['state', [...new Set(currentRows.map(rowState).filter(Boolean))].sort(), human]]) {
    clear($(id)); add($(id), new Option('All ' + (id === 'day' ? 'days' : id === 'state' ? 'states' : 'kinds'), ''));
    for (const v of values) $(id).append(new Option(label(v), String(v)));
    $(id).parentElement.hidden = values.length === 0;
  }
  $('day').parentElement.hidden = allTimes.length === 0; $('from').parentElement.hidden = allTimes.length === 0; $('to').parentElement.hidden = allTimes.length === 0;
  for (const kind of ['order', 'gig', 'driver']) $(kind + '-filter').parentElement.hidden = active === 'source';
}
function clockValue(s) { const p = s.split(':').map(Number); return p.length === 2 ? p[0] * 60 + p[1] : null; }
function applyFilters() {
  const q = $('search').value.trim().toLowerCase(), day = $('day').value, from = clockValue($('from').value), to = clockValue($('to').value), kind = $('kind').value, state = $('state').value;
  filtered = currentRows.filter(row => {
    if (kind && rowKind(row) !== kind) return false; if (state && rowState(row) !== state) return false;
    if (q && !searchText(row).includes(q)) return false;
    const refs = rowRefs(row);
    for (const type of ['order', 'gig', 'driver']) { const v = $(type + '-filter').value.trim().toLowerCase(); if (v && !refs[type].some(id => id.toLowerCase().includes(v) || (type === 'driver' && driverName(id).toLowerCase().includes(v)))) return false; }
    if (day !== '' || from !== null || to !== null) {
      if (!rowTimes(row).some(at => { if (!Number.isInteger(at)) return false; if (day !== '' && Math.floor(at / 1440) !== Number(day)) return false; const clock = ((at % 1440) + 1440) % 1440; return from !== null && to !== null && from > to ? clock >= from || clock <= to : (from === null || clock >= from) && (to === null || clock <= to); })) return false;
    }
    return true;
  });
  if (sortKey) { const c = columns.find(c => c.key === sortKey); if (c) filtered.sort((a, b) => { const av = c.value(a), bv = c.value(b); if (av == null) return bv == null ? 0 : 1; if (bv == null) return -1; return direction * (typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv), undefined, {numeric: true})); }); }
  page = 0; drawChips(); drawDistribution(); drawTable();
}
function drawChips() {
  const root = $('active-filters'); clear(root); let secondary = 0;
  for (const id of filterIds) {
    const v = $(id).value; if (!v) continue;
    if (id !== 'search') secondary++;
    const shown = id === 'day' ? dayName(Number(v)) : id === 'kind' || id === 'state' ? human(v) : v;
    const chip = button('', () => { $(id).value = ''; applyFilters(); }, 'chip');
    chip.setAttribute('aria-label', `Remove filter ${filterLabels[id]} ${shown}`);
    add(chip, N('span', filterLabels[id] + ':'), N('b', shown), N('span', '×', 'x'));
    root.append(chip);
  }
  if (root.children.length > 1) root.append(button('Clear all', () => $('reset').click(), 'link more'));
  $('filters-toggle').textContent = secondary ? `Filters · ${secondary}` : 'Filters';
}
function drawDistribution() {
  const root = $('distribution'); clear(root);
  const all = new Map(), hits = new Map();
  for (const row of currentRows) { const at = rowFirst(row); if (Number.isInteger(at)) { const d = Math.floor(at / 1440); all.set(d, (all.get(d) || 0) + 1); } }
  if (!all.size) return;
  for (const row of filtered) { const at = rowFirst(row); if (Number.isInteger(at)) { const d = Math.floor(at / 1440); hits.set(d, (hits.get(d) || 0) + 1); } }
  const ks = [...all.keys()], lo = Math.min(...ks), hi = Math.max(...ks), max = Math.max(...all.values()), sel = $('day').value;
  add(root, add(N('div', null, 'dist-head'), N('b', 'By day')));
  const barsEl = N('div', null, 'dist-bars'), labels = N('div', null, 'dist-labels');
  for (let d = lo; d <= hi; d++) {
    const total = all.get(d) || 0, n = hits.get(d) || 0, b = N('button');
    b.type = 'button'; if (sel === String(d)) b.classList.add('sel');
    const ghost = N('span', null, 'ghost'); ghost.style.height = (total / max * 100) + '%';
    const fill = N('span', null, 'fill'); fill.style.height = (n / max * 100) + '%';
    add(b, ghost, fill);
    b.setAttribute('aria-label', `${dayName(d)}: ${num(n)} of ${num(total)} rows. ${sel === String(d) ? 'Clear day filter' : 'Filter to this day'}.`);
    b.addEventListener('pointermove', evt => showTip(evt, dayName(d), [['Matching', num(n)], ['Total', num(total)]]));
    b.addEventListener('pointerleave', hideTip);
    b.addEventListener('click', () => { hideTip(); $('day').value = sel === String(d) ? '' : String(d); applyFilters(); });
    barsEl.append(b); labels.append(N('span', hi - lo > 10 ? `D${d + 1}` : `D${d + 1} ${weekday(d)}`));
  }
  add(root, barsEl, labels);
}
function drawTable() {
  const thead = $('table').querySelector('thead'), tbody = $('table').querySelector('tbody'); clear(thead); clear(tbody);
  const hr = N('tr');
  for (const c of columns) {
    const th = N('th', null, c.cls === 'numeric' ? 'numeric' : ''); th.scope = 'col';
    th.setAttribute('aria-sort', sortKey === c.key ? (direction === 1 ? 'ascending' : 'descending') : 'none');
    const b = button(c.title, () => { direction = sortKey === c.key ? -direction : 1; sortKey = c.key; applyFilters(); });
    b.append(N('span', sortKey === c.key ? (direction === 1 ? ' ↑' : ' ↓') : ' ↕', 'arrow'));
    th.append(b); hr.append(th);
  }
  thead.append(hr);
  const step = Number.isFinite(size) ? size : Math.max(1, filtered.length);
  const pages = Math.max(1, Math.ceil(filtered.length / step)); page = Math.max(0, Math.min(page, pages - 1));
  for (const row of filtered.slice(page * step, (page + 1) * step)) {
    const tr = N('tr'), open = primaryOpen(row);
    for (const c of columns) { const td = N('td', null, c.cls); add(td, c.render(row)); tr.append(td); }
    if (open) { tr.classList.add('clickable'); tr.addEventListener('click', e => { if (!e.target.closest('button,a,summary,input,select') && !getSelection().toString()) open(); }); }
    tbody.append(tr);
  }
  const unit = active === 'source' ? 'source records' : 'rows';
  $('row-count').textContent = `${num(filtered.length)} of ${num(currentRows.length)} ${unit}`;
  const sorted = columns.find(c => c.key === sortKey);
  $('sort-info').textContent = sorted ? `· ${sorted.title} ${direction === 1 ? '↑' : '↓'}` : '';
  $('page-info').textContent = filtered.length ? `${num(page * step + 1)}–${num(Math.min((page + 1) * step, filtered.length))} of ${num(filtered.length)}` : '0 rows';
  $('page-total').textContent = `of ${num(pages)}`;
  $('page-number').value = page + 1; $('page-number').max = pages;
  $('first').disabled = $('prev').disabled = page === 0; $('last').disabled = $('next').disabled = page >= pages - 1;
  $('empty').hidden = filtered.length !== 0; $('table').hidden = filtered.length === 0; $('table').parentElement.hidden = filtered.length === 0;
}
$('filters').onsubmit = e => e.preventDefault();
for (const id of filterIds) $(id).addEventListener(id === 'search' || id.endsWith('-filter') ? 'input' : 'change', () => { clearTimeout(debounce); debounce = setTimeout(applyFilters, id === 'search' ? 160 : 0); });
$('reset').onclick = () => { for (const id of filterIds) $(id).value = ''; applyFilters(); };
$('filters-toggle').onclick = () => { const open = $('filters').classList.toggle('expanded'); $('filters-toggle').setAttribute('aria-expanded', String(open)); };
$('page-size').onchange = () => { size = $('page-size').value === 'all' ? Infinity : Number($('page-size').value); page = 0; drawTable(); };
$('first').onclick = () => { page = 0; drawTable(); }; $('prev').onclick = () => { page--; drawTable(); }; $('next').onclick = () => { page++; drawTable(); }; $('last').onclick = () => { const step = Number.isFinite(size) ? size : Math.max(1, filtered.length); page = Math.ceil(filtered.length / step) - 1; drawTable(); }; $('page-number').onchange = () => { page = Number($('page-number').value) - 1; drawTable(); };
$('export-filtered').onclick = () => download('cheap-drive-' + active + '-filtered.json', filtered);
document.addEventListener('keydown', e => {
  if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey || $('workspace').hidden || $('detail').open) return;
  if (e.target.closest && e.target.closest('input,select,textarea')) return;
  e.preventDefault(); $('search').focus();
});

/* Detail drawer with back navigation between linked entities */
let detailStack = [], currentDetail = null;
function openDetail(render) {
  if ($('detail').open && currentDetail) detailStack.push(currentDetail);
  currentDetail = render; render();
  $('detail-back').hidden = detailStack.length === 0;
}
$('detail-back').onclick = () => { const prev = detailStack.pop(); if (!prev) return; currentDetail = prev; prev(); $('detail-back').hidden = detailStack.length === 0; };
function showDialog(label, title) {
  $('detail-label').textContent = label; $('detail-title').textContent = title; clear($('detail-crumbs')); clear($('detail-body'));
  if (!$('detail').open) $('detail').showModal();
  $('detail').scrollTop = 0; hideTip();
  return $('detail-body');
}
$('close-detail').onclick = () => $('detail').close();
$('detail').addEventListener('close', () => { detailStack = []; currentDetail = null; $('detail-back').hidden = true; });
$('detail').addEventListener('click', e => { if (e.target === $('detail')) { const r = $('detail').getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) $('detail').close(); } });
function rawDetail(line) {
  const r = D.records[line - 1]; if (!r) return;
  const body = showDialog('Source record', 'Line ' + line);
  add($('detail-crumbs'), badge(r.value?.type || 'unknown', 'info'), r.error ? badge(r.error, 'warn') : badge('parsed', 'good'));
  add(body, stats([['Line', num(line)], ['Byte offset', num(r.offset)], ['Length', num(r.length) + ' bytes'], ['World time', time(r.value?.at)]]),
    r.error ? N('p', r.error, 'muted') : null,
    add(N('div'), button('↓ Download line', () => download('cheap-drive-line-' + line + '.bin', D.source.base64 ? source().slice(r.offset, r.offset + r.length) : sliceRecordText(r), 'application/octet-stream'))),
    details('Parsed value', r.value, true),
    details('Original text', sliceRecordText(r), true));
}
function stats(items) { const g = N('div', null, 'detail-stats'); for (const [k, v, cls] of items) g.append(add(N('div'), N('span', k), v instanceof Node ? add(N('b'), v) : N('b', v, cls || ''))); return g; }
function facts(parent, values) { const dl = N('dl'); for (const [k, v] of values) add(dl, N('dt', k), add(N('dd'), v ?? '')); parent.append(dl); return dl; }
function miniTable(head, rows) {
  const t = N('table', null, 'mini-table'), hr = N('tr'); for (const h of head) hr.append(N('th', h)); t.append(hr);
  for (const r of rows) { const tr = N('tr'); for (const c of r) tr.append(add(N('td'), c)); t.append(tr); }
  return t;
}
function entityDetail(kind, id) {
  const entity = lookup[kind].get(id); if (!entity) return;
  const body = showDialog({order: 'Order', gig: 'Gig', driver: 'Driver'}[kind], kind === 'driver' ? driverName(id) : id), data = entity.data, acts = activity(entity), crumbs = $('detail-crumbs');
  if (kind === 'order') {
    const request = data.request || {}, order = data.order || {}, legs = arr(order.legs || request.legs);
    add(crumbs, badge(data.outcome, data.outcome === 'won' ? 'good' : data.outcome === 'cancelled' ? 'warn' : ''), badge(data.quoteStatus, 'plain'));
    body.append(stats([['Outcome', human(data.outcome)], ['Won price', fmt(order.priceCents)], ['Direct net', fmt(entity.directNetCents), entity.directNetCents < 0 ? 'negative' : ''], ['First seen', time(firstAt(entity))], ['Last seen', time(lastAt(entity))], ['Activity', num(acts.length)]]));
    const info = section('Facts'); body.append(info);
    facts(info, [['Outcome', data.outcome], ['Quote', data.quoteStatus], ['Dealer', request.dealerId || order.dealerId || 'Unavailable'], ['Route', route(entity)], ['Respond by', time(request.respondBy)], ['Option', order.option || 'Unavailable'], ['Deadline', time(order.deadline)], ['Last pickup', time(order.lastPickupAt)], ['Direct net', fmt(entity.directNetCents)]]);
    if (request.note) { const n = section('Original request note'); if (typeof request.note?.text === 'string') n.append(N('p', request.note.text, 'callout')); n.append(details('Original request note', request.note, !(typeof request.note?.text === 'string'))); body.append(n); }
    if (request.options) {
      const o = section('Offered options');
      if (Array.isArray(request.options)) o.append(miniTable(['Option', 'Deadline', 'List price'], request.options.map(x => [human(x?.kind), time(x?.deadline), moneyCell(x?.listPriceCents)])));
      o.append(details('Offered options', request.options, !Array.isArray(request.options))); body.append(o);
    }
    if (data.quotes?.length) body.append(details('Quotes and results', data.quotes.map(i => payload(D.timeline[i])), true));
    const grid = N('div', null, 'detail-grid');
    legs.forEach((value, i) => {
      const leg = value || {}, p = section('Leg ' + (i + 1)), le = acts.filter(x => x.event?.leg === i);
      p.append(add(N('div', null, 'leg-route'), N('span', placeName(leg.pickup?.placeId) || '?'), N('span', '→', 'arrow'), N('span', placeName(leg.delivery?.placeId) || '?')));
      facts(p, [['Pickup window', time(leg.pickup?.window?.from) + ' to ' + time(leg.pickup?.window?.to)], ['Delivery window', time(leg.delivery?.window?.from) + ' to ' + time(leg.delivery?.window?.to)], ['Pickups', le.filter(e => e.kind === 'picked_up').map(e => time(e.at)).join(', ') || 'Not captured'], ['Deliveries', le.filter(e => e.kind === 'delivered').map(e => time(e.at)).join(', ') || 'Not captured'], ['Delivered at', time(arr(order.deliveredAt)[i])]]);
      p.append(details('Leg payload', leg)); grid.append(p);
    });
    if (legs.length) body.append(grid);
    if (entity.related.length) { const g = section('Related gigs'); g.append(refCell('gig', entity.related)); body.append(g); }
    if (data.reveal) body.append(details('Captured reveal request', data.reveal, true)); if (data.truth) body.append(details('Captured revealed leg truth', data.truth, true));
  } else if (kind === 'gig') {
    const post = data.post || data.snapshot || {}, state = data.lastObservedStatus || data.snapshot?.status || 'Unavailable', net = gigNet(entity);
    add(crumbs, badge(state));
    body.append(stats([['State', human(state)], ['Stops', post.stops?.length ?? 'Unavailable'], ['Orders', num(entity.related.length)], ['Ledger entries', num(entity.ledger.length)], ['Gig ledger net', fmt(net), net < 0 ? 'negative' : ''], ['Activity', num(acts.length)]]));
    const carried = section('Orders carried'); carried.append(refCell('order', entity.related)); body.append(carried);
    if (Array.isArray(post.stops) && post.stops.length) {
      const st = section('Stops');
      st.append(miniTable(['#', 'Kind', 'Order', 'Leg', 'Place'], post.stops.map((x, i) => [num(i + 1), human(x?.kind), identity(x?.orderId) ? entityButton('order', x.orderId) : 'Not captured', Number.isInteger(x?.leg) ? num(x.leg + 1) : 'Not captured', placeName(x?.placeId) || 'Not captured'])));
      body.append(st);
    }
    body.append(details('Stops, windows, audience and original fee schedule', post, true));
    const schedules = acts.filter(x => x.action?.schedule || x.event?.feeCents !== undefined); body.append(details('All schedule changes, offers and booking fees', schedules.map(payload), true));
  } else {
    const profile = data.profile, gigs = [...new Set(acts.flatMap(x => x.refs.gig))];
    add(crumbs, badge(profile ? 'roster profile captured' : 'no roster profile', profile ? 'good' : 'plain'));
    body.append(stats([['Activity', num(acts.length)], ['Gigs', num(gigs.length)], ['Rating', profile?.rating ?? 'Unavailable'], ['Home', placeName(profile?.homePlaceId) || 'Unavailable'], ['First seen', time(firstAt(entity))]]));
    const info = section('Driver facts'); body.append(info);
    facts(info, [['Activity', num(acts.length)], ['Roster profile', profile ? 'Captured' : 'Unavailable']]);
    if (profile) body.append(details('Captured driver profile', profile, true));
    const g = section('Observed gigs'); g.append(refCell('gig', gigs)); body.append(g);
  }
  if (entity.ledger.length) {
    const l = section('Ledger entries');
    l.append(miniTable(['World time', 'Kind', 'Gig', 'Amount', 'Source'], entity.ledger.map(i => { const e = D.ledger[i]; return [time(e.at), human(e.kind), e.gigId ? entityButton('gig', e.gigId) : 'Not captured', moneyCell(e.cents), lineButton(e.sourceLine)]; })));
    l.append(details('Ledger entries JSON', entity.ledger.map(i => D.ledger[i])));
    body.append(l);
  }
  body.append(details('All normalized entity fields', entity.data));
  body.append(N('h3', 'Complete captured activity'));
  const linked = kind === 'order' ? [...new Set([...entity.history, ...entity.related.flatMap(g => lookup.gig.get(g)?.history || [])])].sort((a, b) => a - b).map(i => D.timeline[i]) : acts;
  historyList(body, linked);
}
function identity(v) { return typeof v === 'string' && v ? v : null; }
function historyList(parent, items) {
  const PER = 40, box = N('div', null, 'history'), controls = N('div', null, 'history-controls'), search = N('input');
  search.type = 'search'; search.placeholder = 'Search history'; search.setAttribute('aria-label', 'Search entity history');
  const status = N('span', null, 'status'), list = N('div'); let p = 0, matched = items;
  const prev = button('‹ Prev', () => { p--; draw(); }), next = button('Next ›', () => { p++; draw(); });
  add(controls, search, status, prev, next); add(box, controls, list); parent.append(box);
  function draw() {
    p = Math.max(0, Math.min(p, Math.max(0, Math.ceil(matched.length / PER) - 1))); clear(list);
    status.textContent = `${num(matched.length)} · ${p + 1}/${Math.max(1, Math.ceil(matched.length / PER))}`;
    prev.disabled = p === 0; next.disabled = (p + 1) * PER >= matched.length;
    let lastDay = null;
    for (const x of matched.slice(p * PER, (p + 1) * PER)) {
      const d = Number.isInteger(x.at) ? Math.floor(x.at / 1440) : 'none';
      if (d !== lastDay) { list.append(N('div', d === 'none' ? 'Untimed' : dayName(d), 'history-day')); lastDay = d; }
      list.append(add(N('div', null, 'history-row'), N('span', Number.isInteger(x.at) ? clockOf(x.at) : 'n/a', 'clock'), kindBadge(x), N('span', eventSummary(x)), lineButton(x.line)));
    }
    if (!matched.length) list.append(N('p', 'No activity matches.', 'muted empty-note'));
  }
  search.oninput = () => { const q = search.value.toLowerCase(); matched = items.filter(x => JSON.stringify(payload(x)).toLowerCase().includes(q)); p = 0; draw(); };
  draw();
}

/* Source & integrity */
function sourceIntro() {
  const panel = N('div', null, 'stack'), grid = N('div', null, 'integrity-grid');
  for (const [label, value, note, tone] of [
    ['Ingestion', 'Complete', `${num(D.source.bytes)} bytes · ${num(D.source.lines)} lines`, ''],
    ['Validity', D.integrity.invalidLines ? 'Needs inspection' : 'All lines parsed', `${num(D.integrity.duplicates)} duplicates · ${num(D.integrity.conflicts)} conflicts · ${num(D.integrity.gaps.length)} gaps`, D.integrity.invalidLines || D.integrity.conflicts || D.integrity.gaps.length ? 'warn' : ''],
    ['Week status', D.integrity.verifiedEnd ? 'Verified' : 'Unverified', D.integrity.finalScoreCaptured ? 'Final score captured' : 'No final score', D.integrity.verifiedEnd ? '' : 'warn']]) {
    const p = N('div', null, 'panel status-card'); add(p, check(tone), add(N('div'), N('span', label), N('strong', value), N('p', note, 'muted'))); grid.append(p);
  }
  panel.append(grid);
  const integrity = section('SHA-256');
  add(integrity, N('p', D.source.sha256, 'hash'), add(N('div', null, 'download-row'), button('↓ JSONL', () => $('export-source').click()), button('↓ JSON', () => $('export-model').click()), button('↓ Filtered', () => $('export-filtered').click())));
  integrity.querySelector('.download-row').style.marginTop = '10px';
  panel.append(integrity);
  const diag = N('details', null, 'raw'); diag.open = true; diag.append(N('summary', `${num(D.diagnostics.length)} diagnostics`));
  const list = N('ul', null, 'diag-list');
  for (const x of D.diagnostics) { const li = N('li'); add(li, add(N('span'), badge(x.code, 'warn'), ' ', x.message), x.line ? lineButton(x.line) : null); list.append(li); }
  if (!D.diagnostics.length) list.append(N('li', 'No detected integrity issues.'));
  diag.append(list); panel.append(diag);
  return panel;
}

/* Captured context & Interactive Finland Replay */
const FINLAND_BORDER = [
  [65.805, 24.155], [66.253, 23.700], [66.481, 23.701], [66.811, 23.989], [67.129, 23.642],
  [67.423, 23.734], [67.460, 23.455], [67.875, 23.502], [67.954, 23.639], [68.367, 22.854],
  [68.521, 21.997], [69.037, 20.622], [69.042, 21.066], [69.214, 21.066], [69.274, 21.594],
  [68.720, 22.411], [68.649, 23.324], [68.806, 23.854], [68.593, 24.941], [68.821, 25.249],
  [68.990, 25.748], [69.653, 26.012], [69.915, 26.525], [69.906, 27.128], [70.062, 27.890],
  [69.823, 28.412], [69.671, 29.142], [69.473, 29.333], [69.177, 28.846], [69.022, 28.966],
  [68.904, 28.414], [68.814, 28.778], [68.488, 28.471], [68.190, 28.685], [68.062, 29.344],
  [67.668, 29.988], [66.892, 29.066], [65.787, 30.087], [65.682, 30.095], [65.625, 29.716],
  [65.569, 29.819], [65.249, 29.608], [65.145, 29.827], [64.968, 29.604], [64.804, 29.783],
  [64.733, 30.110], [64.524, 29.987], [64.366, 30.108], [64.237, 30.488], [64.077, 30.526],
  [63.735, 29.992], [63.208, 31.181], [62.885, 31.534], [62.481, 31.187], [61.288, 29.252],
  [60.536, 27.798], [60.465, 27.462], [60.543, 27.205], [60.413, 26.535], [60.625, 26.569],
  [60.424, 26.378], [60.474, 25.956], [60.342, 26.036], [60.268, 25.758], [60.333, 25.656],
  [60.114, 24.600], [60.021, 24.446], [59.986, 23.464], [59.816, 23.021], [60.022, 23.198],
  [60.210, 22.912], [60.057, 22.750], [60.029, 22.463], [60.381, 22.585], [60.505, 21.854],
  [60.594, 21.805], [60.531, 21.613], [60.596, 21.436], [60.967, 21.361], [61.592, 21.606],
  [61.990, 21.256], [62.277, 21.343], [62.623, 21.104], [63.033, 21.474], [63.039, 21.651],
  [63.204, 21.545], [63.310, 22.320], [63.438, 22.243], [63.648, 22.532], [64.041, 23.599],
  [64.801, 24.558], [64.884, 24.942], [64.860, 25.288], [65.479, 25.348], [65.671, 24.675],
  [65.859, 24.628], [65.780, 24.404], [65.812, 24.238], [65.805, 24.155]
];
const FINLAND_HIGHWAYS = [
  ['helsinki', 'espoo'], ['espoo', 'salo'], ['salo', 'turku'], ['turku', 'raisio'],
  ['raisio', 'rauma'], ['rauma', 'pori'], ['pori', 'vaasa'], ['vaasa', 'kokkola'],
  ['kokkola', 'ylivieska'], ['ylivieska', 'oulu'], ['oulu', 'kemi'], ['kemi', 'rovaniemi'],
  ['helsinki', 'vantaa'], ['vantaa', 'hyvinkaa'], ['hyvinkaa', 'hameenlinna'],
  ['hameenlinna', 'lempaala'], ['lempaala', 'tampere'], ['tampere', 'pori'],
  ['tampere', 'seinajoki'], ['seinajoki', 'vaasa'], ['seinajoki', 'kokkola'],
  ['tampere', 'jyvaskyla'], ['helsinki', 'lahti'], ['lahti', 'hameenlinna'], ['lahti', 'jyvaskyla'],
  ['jyvaskyla', 'ylivieska'], ['jyvaskyla', 'oulu'], ['jyvaskyla', 'kuopio'],
  ['helsinki', 'porvoo'], ['porvoo', 'kotka'], ['kotka', 'kouvola'], ['lahti', 'kouvola'],
  ['kouvola', 'mikkeli'], ['mikkeli', 'kuopio'], ['kuopio', 'kajaani'], ['kajaani', 'oulu'],
  ['kouvola', 'lappeenranta'], ['lappeenranta', 'savonlinna'], ['savonlinna', 'joensuu'],
  ['lappeenranta', 'joensuu'], ['joensuu', 'kuopio'], ['joensuu', 'kajaani']
];

function extractRunTrips(byId) {
  const gigDriver = new Map(), pickups = new Map(), trips = [];
  for (const x of D.timeline) {
    const ev = x.event || {};
    if ((x.kind === 'gig_booked' || x.kind === 'gig_started') && ev.gigId && ev.driverId) gigDriver.set(ev.gigId, ev.driverId);
    if (x.kind === 'picked_up' && ev.orderId && Number.isInteger(x.at)) {
      pickups.set(ev.orderId + ':' + (ev.leg ?? 0), {at: x.at, placeId: ev.placeId, gigId: ev.gigId});
    } else if (x.kind === 'delivered' && ev.orderId && Number.isInteger(x.at)) {
      const key = ev.orderId + ':' + (ev.leg ?? 0), p = pickups.get(key);
      const ord = lookup.order.get(ev.orderId), legObj = arr((ord?.data?.order || ord?.data?.request)?.legs)[ev.leg ?? 0];
      const from = p?.placeId || legObj?.pickup?.placeId, to = ev.placeId || legObj?.delivery?.placeId;
      if (from && to && byId.has(from) && byId.has(to)) {
        const gid = ev.gigId || p?.gigId || ord?.related?.[0] || '';
        const t0 = p ? p.at : Math.max(480, x.at - 180), t1 = Math.max(t0 + 15, x.at);
        const paired = (lookup.gig.get(gid)?.related?.length || 0) >= 2;
        trips.push({orderId: ev.orderId, gigId: gid, driverId: gigDriver.get(gid) || gid || ev.orderId, from, to, t0, t1, paired});
      }
    }
  }
  return trips.sort((a, b) => a.t0 - b.t0);
}

function buildRouter(byId) {
  const adj = new Map();
  const addEdge = (a, b) => {
    const pa = byId.get(a), pb = byId.get(b);
    if (!pa || !pb) return;
    const d = Math.hypot((pa.lon - pb.lon) * 0.5, pa.lat - pb.lat);
    if (!adj.has(a)) adj.set(a, []);
    if (!adj.has(b)) adj.set(b, []);
    adj.get(a).push([b, d]);
    adj.get(b).push([a, d]);
  };
  for (const [a, b] of FINLAND_HIGHWAYS) addEdge(a, b);
  const memo = new Map();
  return (from, to) => {
    if (from === to) return [from];
    const key = from + '>' + to;
    if (memo.has(key)) return memo.get(key);
    if (!adj.has(from) || !adj.has(to)) return [from, to];
    const dist = new Map([[from, 0]]), prev = new Map(), visited = new Set();
    while (true) {
      let u = null, best = Infinity;
      for (const [k, v] of dist) if (!visited.has(k) && v < best) { best = v; u = k; }
      if (!u || u === to) break;
      visited.add(u);
      for (const [v, w] of adj.get(u) || []) {
        const nd = best + w;
        if (nd < (dist.get(v) ?? Infinity)) { dist.set(v, nd); prev.set(v, u); }
      }
    }
    if (!prev.has(to)) { memo.set(key, [from, to]); return [from, to]; }
    const out = [];
    for (let cur = to; cur; cur = prev.get(cur)) out.push(cur);
    out.reverse();
    memo.set(key, out);
    return out;
  };
}

function polySlice(pts, p0, p1) {
  if (pts.length < 2 || p1 <= p0) return [pts[0], pts.at(-1)];
  const segs = []; let total = 0;
  for (let i = 0; i < pts.length - 1; i++) {
    const d = Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]);
    segs.push(d); total += d;
  }
  if (total <= 0) return [pts[0], pts.at(-1)];
  const pointAt = target => {
    let rem = target;
    for (let i = 0; i < segs.length; i++) {
      if (rem <= segs[i] || i === segs.length - 1) {
        const f = segs[i] ? Math.max(0, Math.min(1, rem / segs[i])) : 0;
        return [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f];
      }
      rem -= segs[i];
    }
    return pts.at(-1);
  };
  const d0 = total * Math.max(0, p0), d1 = total * Math.min(1, p1), out = [pointAt(d0)];
  let acc = 0;
  for (let i = 0; i < segs.length; i++) {
    acc += segs[i];
    if (acc > d0 && acc < d1) out.push(pts[i + 1]);
  }
  out.push(pointAt(d1));
  return out;
}

function capturedContext() {
  const root = $('captures'); clear(root);
  const grid = N('div', null, 'capture-grid');
  let mapRecord = null;
  for (const kind of ['snapshot', 'map', 'roster', 'reveal']) {
    const lines = D.captures[kind] || [];
    const panel = section({snapshot: 'Snapshots', map: 'Map', roster: 'Rosters', reveal: 'Reveal'}[kind]);
    panel.querySelector('.panel-header').append(badge(lines.length ? num(lines.length) : 'none', lines.length ? 'good' : 'warn'));
    for (const line of lines) { const rec = D.records[line - 1].value; add(panel, add(N('div', null, 'capture-row'), N('span', human(rec.phase || 'captured') + ' · ' + time(rec.at)), button('L' + line, () => openDetail(() => rawDetail(line))))); }
    if (kind === 'map' && lines.length) mapRecord = D.records[lines[lines.length - 1] - 1].value.map;
    grid.append(panel);
  }
  root.append(grid);
  if (mapRecord && Array.isArray(mapRecord.places)) {
    const panel = N('section', null, 'panel');
    panel.append(mapView(mapRecord)); root.append(panel);
  }
}
function placeActivity() {
  const counts = new Map(), bump = (id, k) => { if (!id) return; const c = counts.get(id) || {pickups: 0, deliveries: 0}; c[k]++; counts.set(id, c); };
  for (const o of D.orders) for (const l of arr((o.data.order || o.data.request)?.legs)) { bump(l?.pickup?.placeId, 'pickups'); bump(l?.delivery?.placeId, 'deliveries'); }
  return counts;
}
function mapView(map) {
  if (stopReplay) { stopReplay(); stopReplay = null; }
  const places = map.places.filter(p => p && Number.isFinite(p.lat) && Number.isFinite(p.lon));
  if (!places.length) return N('p', 'No coordinates in map.', 'muted');
  const isFinland = places.length >= 10;
  const byId = new Map(places.map(p => [p.id, p])), act = placeActivity();
  const rawRoads = arr(map.roads).filter(Boolean);
  const displayRoads = isFinland ? FINLAND_HIGHWAYS.map(([from, to]) => ({from, to})) : rawRoads;
  const routeFor = buildRouter(byId);
  const trips = isFinland ? extractRunTrips(byId) : [];
  const total = p => { const c = act.get(p.id); return c ? c.pickups + c.deliveries : 0 }, maxAct = Math.max(1, ...places.map(total));

  const allLats = [...places.map(p => p.lat), ...(isFinland ? FINLAND_BORDER.map(b => b[0]) : [])];
  const allLons = [...places.map(p => p.lon), ...(isFinland ? FINLAND_BORDER.map(b => b[1]) : [])];
  const midLat = places.reduce((s, p) => s + p.lat, 0) / places.length, k = Math.cos(midLat * Math.PI / 180);
  const minLat = Math.min(...allLats), maxLat = Math.max(...allLats), minLon = Math.min(...allLons), maxLon = Math.max(...allLons);
  const spanX = ((maxLon - minLon) * k) || 1, spanY = (maxLat - minLat) || 1;

  const minMin = trips.length ? Math.max(480, trips[0].t0 - 15) : 480;
  const maxMin = trips.length ? Math.max(...trips.map(t => t.t1)) + 30 : 10080;
  let simMin = minMin, playing = isFinland && trips.length > 0, speed = 2, rafId = 0, lastTs = 0;

  const layout = N('div', null, 'map-layout'), left = N('div'), right = N('div', null, 'map-side');
  const replayBar = N('div', null, 'replay-bar');
  const setPlayLabel = label => {
    clear(playBtn);
    const ic = svg('svg', {viewBox: '0 0 14 14', width: 12, height: 12, fill: 'currentColor', 'aria-hidden': 'true'});
    if (playing) ic.append(svg('rect', {x: 2.2, y: 2, width: 3.2, height: 10, rx: 1}), svg('rect', {x: 8.6, y: 2, width: 3.2, height: 10, rx: 1}));
    else ic.append(svg('path', {d: 'M3 1.8l9 5.2-9 5.2V1.8z'}));
    add(playBtn, ic, N('span', label));
  };
  const playBtn = button('', () => {
    if (simMin >= maxMin) simMin = minMin;
    playing = !playing;
    setPlayLabel(playing ? 'Pause' : 'Play');
    if (playing) { lastTs = performance.now(); rafId = requestAnimationFrame(tick); }
  }, 'replay-play');
  setPlayLabel(playing ? 'Pause' : 'Play');
  const slider = N('input', null, 'replay-slider');
  slider.type = 'range'; slider.min = String(minMin); slider.max = String(maxMin); slider.step = '1'; slider.value = String(simMin);
  slider.setAttribute('aria-label', 'Simulation world minute');
  const speedWrap = N('div', null, 'speed-pills');
  for (const sp of [1, 2, 4]) {
    const sb = button(sp + '×', () => {
      speed = sp;
      for (const c of speedWrap.children) c.classList.toggle('active', c.textContent === sp + '×');
    }, 'speed-pill' + (sp === speed ? ' active' : ''));
    speedWrap.append(sb);
  }
  const toggle = N('input'); toggle.type = 'checkbox'; toggle.checked = true;
  const roadToggleLabel = add(N('label', null, 'road-toggle'), toggle, 'Roads');

  const statClock = N('b', time(simMin)), statActive = N('b', '0'), statDeliv = N('b', '0 / ' + num(trips.length)), statMargin = N('b', '€0.00');
  const liveStats = N('div', null, 'replay-stats');
  for (const [lbl, el] of [['Clock', statClock], ['On road', statActive], ['Delivered', statDeliv], ['Margin', statMargin]]) {
    liveStats.append(add(N('div', null, 'replay-stat'), N('span', lbl), el));
  }
  add(replayBar, add(N('div', null, 'replay-controls'), playBtn, slider, speedWrap, roadToggleLabel), liveStats);

  let roadsGroup = null, replayGroup = null, projectPt = null;
  const activeList = N('div', null, 'active-cars-list');

  function renderFrame() {
    slider.value = String(Math.round(simMin));
    statClock.textContent = time(Math.round(simMin));
    let doneCount = 0;
    const activeTrips = [];
    for (const tr of trips) {
      if (tr.t1 <= simMin) doneCount++;
      else if (tr.t0 <= simMin && simMin <= tr.t1) activeTrips.push(tr);
    }
    statActive.textContent = num(activeTrips.length) + (activeTrips.length === 1 ? ' car' : ' cars');
    statDeliv.textContent = `${num(doneCount)} / ${num(trips.length)}`;
    let liveNet = 0;
    for (const l of D.ledger) {
      if (Number.isInteger(l.at) && l.at <= simMin) liveNet += l.cents;
      else break;
    }
    statMargin.textContent = fmtWhole(liveNet);

    if (replayGroup && projectPt) {
      clear(replayGroup);
      for (const tr of trips) {
        const dtPick = simMin - tr.t0, dtDrop = simMin - tr.t1;
        for (const [pid, dt] of [[tr.from, dtPick], [tr.to, dtDrop]]) {
          if (dt >= 0 && dt <= 28) {
            const pObj = byId.get(pid);
            if (pObj) {
              const [px, py] = projectPt(pObj), r = 6 + (dt / 28) * 14, op = (1 - dt / 28) * 0.75;
              const ring = svg('path', {d: `M${(px - r).toFixed(1)},${py.toFixed(1)}a${r.toFixed(1)},${r.toFixed(1)} 0 1,0 ${(r * 2).toFixed(1)},0a${r.toFixed(1)},${r.toFixed(1)} 0 1,0 ${(-r * 2).toFixed(1)},0`, class: 'pulse-ring'});
              ring.style.strokeOpacity = String(op.toFixed(2));
              replayGroup.append(ring);
            }
          }
        }
      }
      for (const tr of activeTrips) {
        const p = (simMin - tr.t0) / Math.max(1, tr.t1 - tr.t0);
        const waypoints = routeFor(tr.from, tr.to).map(id => byId.get(id)).filter(Boolean).map(projectPt);
        if (waypoints.length < 2) continue;
        const seg = polySlice(waypoints, Math.max(0, p - 0.34), p);
        const dPath = seg.map((pt, i) => (i ? 'L' : 'M') + pt[0].toFixed(1) + ',' + pt[1].toFixed(1)).join('');
        const glow = svg('path', {d: dPath, class: 'route-glow' + (tr.paired ? ' paired' : '')});
        const trail = svg('path', {d: dPath, class: 'route-trail' + (tr.paired ? ' paired' : '')});
        replayGroup.append(glow, trail);

        const cur = seg.at(-1), prev = seg.length >= 2 ? seg.at(-2) : waypoints[0];
        const ahead = polySlice(waypoints, p, Math.min(1, p + 0.03)).at(-1);
        const dx = (ahead[0] - prev[0]) || 1, dy = (ahead[1] - prev[1]) || 0;
        const deg = Math.atan2(dy, dx) * 180 / Math.PI;
        const carG = svg('g', {transform: `translate(${cur[0].toFixed(1)},${cur[1].toFixed(1)}) rotate(${deg.toFixed(1)})`, class: 'car-sprite' + (tr.paired ? ' paired' : '')});
        carG.append(
          svg('rect', {x: -8.5, y: -4.8, width: 17, height: 9.6, rx: 3.2, class: 'car-body'}),
          svg('rect', {x: -1.8, y: -3.5, width: 5.8, height: 7, rx: 1.4, class: 'car-glass'})
        );
        carG.addEventListener('pointermove', evt => showTip(evt, `${driverName(tr.driverId)} · ${tr.orderId}`, [[`${placeName(tr.from)} → ${placeName(tr.to)}`, Math.round(p * 100) + '%'], ['Mode', tr.paired ? '2-car paired gig' : 'Single car']]));
        carG.addEventListener('pointerleave', hideTip);
        carG.addEventListener('click', () => { hideTip(); openDetail(() => entityDetail('order', tr.orderId)); });
        replayGroup.append(carG);
      }
    }

    clear(activeList);
    if (!activeTrips.length) {
      activeList.append(N('p', simMin >= maxMin ? 'Week completed.' : 'Waiting for next departure…', 'muted'));
    } else {
      for (const tr of activeTrips.slice(0, 7)) {
        const p = Math.round(((simMin - tr.t0) / Math.max(1, tr.t1 - tr.t0)) * 100);
        const item = N('button', null, 'active-car-item'); item.type = 'button';
        const top = add(N('div', null, 'ac-top'), N('strong', driverName(tr.driverId)), N('span', tr.paired ? '2-car' : tr.orderId, 'ac-tag' + (tr.paired ? ' paired' : '')));
        const routeRow = add(N('div', null, 'ac-route'), N('span', `${placeName(tr.from)} → ${placeName(tr.to)}`), N('span', p + '%', 'mono'));
        const bar = N('div', null, 'ac-bar'), fill = N('div', null, 'ac-fill' + (tr.paired ? ' paired' : ''));
        fill.style.width = p + '%'; bar.append(fill);
        add(item, top, routeRow, bar);
        item.addEventListener('click', () => openDetail(() => entityDetail('order', tr.orderId)));
        activeList.append(item);
      }
    }
  }

  function tick(ts) {
    if (!playing || active !== 'captures') return;
    const dt = Math.min(64, ts - (lastTs || ts));
    lastTs = ts;
    simMin += (dt / 1000) * 42 * speed;
    if (simMin >= maxMin) {
      simMin = maxMin;
      playing = false;
      setPlayLabel('Replay');
      renderFrame();
      return;
    }
    renderFrame();
    rafId = requestAnimationFrame(tick);
  }

  slider.addEventListener('input', () => {
    simMin = Number(slider.value);
    renderFrame();
  });

  const box = responsive((b, width) => {
    const pad = 32, height = Math.round(Math.min(660, Math.max(380, (width - pad * 2) * spanY / spanX + pad * 2)));
    const scale = Math.min((width - pad * 2) / spanX, (height - pad * 2) / spanY), ox = (width - spanX * scale) / 2, oy = (height - spanY * scale) / 2;
    const x = p => ox + (p.lon - minLon) * k * scale, y = p => height - oy - (p.lat - minLat) * scale;
    projectPt = p => [x(p), y(p)];
    const s = svg('svg', {viewBox: `0 0 ${width} ${height}`, width, height, class: 'map-svg', role: 'img', 'aria-label': 'Captured places and road connections; schematic projection'});
    if (isFinland) {
      const borderPts = FINLAND_BORDER.map(([lat, lon]) => `${(ox + (lon - minLon) * k * scale).toFixed(1)},${(height - oy - (lat - minLat) * scale).toFixed(1)}`).join(' ');
      s.append(svg('polygon', {points: borderPts, class: 'finland-border'}));
    }
    roadsGroup = svg('g', {class: 'map-roads'}); roadsGroup.style.display = toggle.checked ? '' : 'none';
    for (const r of displayRoads) { const a = byId.get(r.from), c = byId.get(r.to); if (a && c && a !== c) roadsGroup.append(svg('line', {x1: x(a), x2: x(c), y1: y(a), y2: y(c)})); }
    s.append(roadsGroup);
    replayGroup = svg('g', {class: 'replay-layer'});
    s.append(replayGroup);

    const placed = [], labels = svg('g');
    for (const p of [...places].sort((a, b) => total(b) - total(a))) {
      const g = svg('g'), c = svg('circle', {cx: x(p), cy: y(p), r: 3.5 + Math.sqrt(total(p) / maxAct) * 8.5}), t = svg('title'), a = act.get(p.id) || {pickups: 0, deliveries: 0};
      t.textContent = `${p.name || p.id} (${p.lat}, ${p.lon}) · ${a.pickups} pickups · ${a.deliveries} deliveries`; c.append(t); g.append(c); s.append(g);
      const label = String(p.name || p.id), w = label.length * 6.2, lx = x(p) + 9, ly = y(p) + 4, box2 = [lx - 2, ly - 11, lx + w + 2, ly + 3];
      if (box2[2] < width && !placed.some(q => !(box2[2] < q[0] || box2[0] > q[2] || box2[3] < q[1] || box2[1] > q[3]))) { placed.push(box2); labels.append(svgText({x: lx, y: ly}, label)); }
    }
    s.append(labels); b.append(s);
    renderFrame();
  });
  toggle.onchange = () => { if (roadsGroup) roadsGroup.style.display = toggle.checked ? '' : 'none'; };
  add(left, isFinland ? replayBar : roadToggleLabel, box);

  const list = N('div', null, 'place-list');
  list.append(add(N('div', null, 'r h'), N('span', 'Place'), N('span', 'Pick'), N('span', 'Drop')));
  for (const p of [...places].sort((a, b) => total(b) - total(a))) { const a = act.get(p.id) || {pickups: 0, deliveries: 0}; list.append(add(N('div', null, 'r'), N('span', p.name || p.id), N('span', num(a.pickups)), N('span', num(a.deliveries)))); }
  if (isFinland) add(right, N('h3', 'Active fleet'), activeList, N('h3', 'Places'), list);
  else add(right, N('h3', 'Places'), list);
  add(layout, left, right);

  stopReplay = () => { playing = false; if (rafId) cancelAnimationFrame(rafId); };
  if (playing) { lastTs = performance.now(); rafId = requestAnimationFrame(tick); }
  return layout;
}

/* Routing */
const titles = {
  overview: ['Overview', ''],
  orders: ['Requests & orders', ''],
  timeline: ['Event timeline', ''],
  gigs: ['Gigs & stops', ''],
  drivers: ['Drivers', ''],
  incidents: ['Incidents', ''],
  ledger: ['Financial ledger', ''],
  source: ['Source & integrity', ''],
  captures: ['Map', '']
};
function navigate(id, preset) {
  if (stopReplay && id !== 'captures') { stopReplay(); stopReplay = null; }
  active = getNavItems().some(x => x[0] === id) ? id : 'overview'; sortKey = ''; direction = 1; page = 0;
  for (const o of observers) o.disconnect(); observers = []; hideTip();
  for (const b of $('nav').querySelectorAll('button')) {
    b.classList.toggle('active', b.dataset.tab === active);
    if (b.dataset.tab === active) { b.setAttribute('aria-current', 'page'); if (b.scrollIntoView && innerWidth <= 900) b.scrollIntoView({block: 'nearest', inline: 'nearest'}); }
    else b.removeAttribute('aria-current');
  }
  $('title').textContent = titles[active][0];
  $('subtitle').textContent = '';
  $('overview').hidden = active !== 'overview';
  $('workspace').hidden = ['overview', 'captures'].includes(active);
  $('captures').hidden = active !== 'captures';
  if (active === 'overview') overview();
  else if (active === 'captures') capturedContext();
  else {
    configure(active); clear($('section-intro'));
    if (active === 'source') $('section-intro').append(sourceIntro());
    setupFilters();
    if (preset) for (const [k, v] of Object.entries(preset)) { const el = $(k); if (el && (el.tagName !== 'SELECT' || [...el.options].some(o => o.value === v))) el.value = v; }
    $('filter-help').textContent = '';
    applyFilters();
  }
  if (active !== 'overview' || location.hash) history.replaceState(null, '', '#' + active);
  window.scrollTo(0, 0);
  requestAnimationFrame(() => window.scrollTo(0, 0));
}

/* Multi-Run Live Demo Switcher & Quick Jump Bar */
const runsScript = $('report-runs');
if (runsScript) {
  const RUNS = JSON.parse(runsScript.textContent);
  const defaultRun = RUNS.find(r => r.default) || RUNS.at(-1) || RUNS[0];
  for (const r of RUNS) if (!r.model && r.id === defaultRun?.id) r.model = D;
  if (defaultRun) loadModel(defaultRun.model, defaultRun.title);
  const TOUR = [
    {num: '1', label: 'Paired gig g124', run: 'gamma-late', tab: 'gigs', entity: ['gig', 'g124']},
    {num: '2', label: 'Finnish note R00013', run: 'gamma-late', tab: 'orders', entity: ['order', 'R00013']},
    {num: '3', label: 'Delta rescue R00739', run: 'delta', tab: 'orders', entity: ['order', 'R00739']},
    {num: '4', label: 'Gamma miss R00207', run: 'gamma-early', tab: 'orders', entity: ['order', 'R00207']},
    {num: '5', label: 'Finland map', run: 'beta-early', tab: 'captures', entity: null},
    {num: '6', label: 'Reveal R00001', run: 'beta-early', tab: 'orders', entity: ['order', 'R00001']}
  ];
  let currentRunId = defaultRun?.id || '';
  let activeTourIdx = -1;
  const demoBar = $('demo-bar');
  demoBar.hidden = false;

  function renderDemoBar() {
    clear(demoBar);
    const switcher = N('div', null, 'run-switcher');
    for (const r of RUNS) {
      const btn = N('button', null, 'run-btn' + (r.id === currentRunId ? ' active' : ''));
      btn.type = 'button';
      btn.dataset.run = r.id;
      const top = add(N('div', null, 'run-btn-top'), N('span', r.badge, 'greek ' + r.tone), N('span', r.title, 'run-title'));
      add(btn, top, N('div', r.margin, 'run-margin'), N('div', r.meta, 'run-meta'));
      btn.addEventListener('click', () => {
        activeTourIdx = -1;
        selectRun(r.id);
      });
      switcher.append(btn);
    }
    const tourStrip = N('div', null, 'tour-strip');
    TOUR.forEach((item, idx) => {
      const pill = N('button', null, 'tour-pill' + (idx === activeTourIdx ? ' active' : ''));
      pill.type = 'button';
      add(pill, N('span', item.num, 'num'), N('span', item.label));
      pill.addEventListener('click', () => {
        activeTourIdx = idx;
        selectRun(item.run, item.tab, item.entity);
      });
      tourStrip.append(pill);
    });
    add(demoBar, switcher, tourStrip);
  }

  function selectRun(runId, targetTab, entityTarget) {
    const found = RUNS.find(r => r.id === runId);
    if (!found) return;
    if ($('detail').open) $('detail').close();
    currentRunId = found.id;
    loadModel(found.model, found.title);
    renderDemoBar();
    navigate(targetTab || active);
    if (entityTarget) {
      openDetail(() => entityDetail(entityTarget[0], entityTarget[1]));
    }
  }

  renderDemoBar();
}

window.addEventListener('hashchange', () => { if (location.hash !== '#main') navigate(location.hash.slice(1)); });
navigate(location.hash.slice(1) || 'overview');
