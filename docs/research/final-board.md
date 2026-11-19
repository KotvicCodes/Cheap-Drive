# Epsilon Prime: the real final

**15 November 2026, Sunday 09:00 Helsinki (07:00 UTC).**
Team: **Guardians of the Moonlight** (`guardians-of-the-moonlight`).
The real final is public and **ended**: **29 of 58 ranked teams**,
**€16,760.47 gross margin**, **97.61% on time**, **376 orders won**.

## Public standings

Retrieved **2026-11-15 07:55:28.929 UTC** from the public
[`/v1/leaderboard`](https://spread.bahnexpress.com/v1/leaderboard) event stream,
the feed used by [the public leaderboard](https://spread.bahnexpress.com/leaderboard).
The [complete frozen message](final-board-public.json) records the source and
retrieval time. No team key was used.

The feed says `status: "ended"`, `startsAt: "2026-11-15T07:00:00.000Z"`,
`now: 14280`, `endsAt: 14280`. Its `clock.endsAtWall: 1794728058000`
corresponds to **07:34:18 UTC / 09:34:18 Helsinki**, a 34-minute-18-second
scheduled duration. The page's announcement says **“The final moved to Sunday
09:00. It was 08:00.”** The saved final trace independently records the 07:00 UTC
start. Thus 08:00 Helsinki is the superseded schedule, not this final's start.

There are **58 non-null public ranks** among **236 listed teams**. Count ranks,
not listed teams or entries with a `ranked` flag alone. The final feed contains
**no House best or other House entry**; a final House benchmark is unavailable.

| Public rank | Team | Gross margin |
| --- | --- | ---: |
| 1 | Juhus | €22,930.87 |
| 2 | blib_blib | €21,744.80 |
| 3 | Progresful | €21,111.65 |
| 4 | Seekers | €19,974.72 |
| 5 | MathNet1 | €19,965.41 |
| 6 | DaVinci’s Night Shift | €19,918.93 |
| 7 | pelaaja juhlii | €19,863.03 |
| 8 | source-exp | €19,573.97 |
| 9 | Team Moonshot | €19,366.40 |
| 10 | Evil Club | €19,083.95 |
| 27 | car | €16,955.22 |
| 28 | Dz-dealer | €16,780.32 |
| **29** | **Guardians of the Moonlight** | **€16,760.47** |
| 30 | alignas | €16,526.15 |
| 31 | one boy | €16,241.42 |

Leader **Juhus** is **€6,170.40 ahead of us**; tenth-place **Evil Club** is
**€2,323.48 ahead**. Their public order counts are 474 and 443 respectively.
Our exact fields are `marginCents: 1676047`, `revenueCents: 4058375`,
`wonOrders: 376`, `onTimeShare: 0.976063829787234`, `undeliveredShare: 0`,
`rank: 29`, `ranked: true`. The exact on-time percentage is
**97.6063829787234%**, rounded here to two decimals.

## Model and local provenance

The final used **[Epsilon Prime](../../models/epsilon-prime.json)** with the
**43% win target** (`win_target_bps: 4300`). Both the saved checkpoint and trace
header agree on the full model settings below. The factory is normalized in
the trace to `delta:make_delta`; the model file names the compatible
`models.delta:make_delta` factory.

Read-only provenance was found in sibling worktree
`/home/agent/.t3/worktrees/Cheap-Drive/final-prime/`:

- `runs/final/20261115T063024083406Z-final-fd21c913b2616e5aed02a.jsonl.gz`: header identifies final world `fd21c913b2616e5aed02a`, level 8, Epsilon Prime and `startsAt: "2026-11-15T07:00:00.000Z"`.
- `runs/final/fd21c913b2616e5aed02a-checkpoint.json`: same world and model; `lastSeq: 14902`.
- `runs/final/standby-1115.log`: completed result €16,760.47, 97.61%, 376 orders; matches the public feed. The trace's final saved score matches all seven public score fields exactly.
- `models/epsilon-prime.json`: settings match the trace and checkpoint. The sibling's inspected HEAD is `6c1822e97409b9d6fcc6b07e05a7c34dcce21932`; **the actual runtime source commit is unverified**, because the trace does not stamp a source revision.

```json
{
  "max_km": 500,
  "win_target_bps": 4300,
  "opening_fee_bps": 8000,
  "long_max_km": 700,
  "pairs": 1,
  "short_fee_km": 45,
  "short_opening_fee_bps": 11000,
  "short_km": 300,
  "short_bps": 9300,
  "premium_opening_fee_bps": 10500,
  "premium_min_slack_minutes": 1440,
  "delta_note_fixes": 1,
  "delta_rescue_windows": 1,
  "delta_wide_windows": 1,
  "delta_private_delivery_rescue": 1,
  "delta_pairing": "extended",
  "pair_once": 0,
  "pair_max_idle_minutes": 120,
  "delta_pair_max_wait_minutes": 180,
  "delta_pair_min_slack_minutes": 480,
  "trade_ins": 1,
  "delta_guarded_trade_ins": 1,
  "delta_relaxed_slack_minutes": 300,
  "delta_corridor_open_cap": 5,
  "delta_intake_max_backlog": 12,
  "long_markup_bps": 10500,
  "epsilon_breaker": 1,
  "epsilon_breaker_on_time_bps": 9500,
  "epsilon_breaker_window_minutes": 1440,
  "epsilon_breaker_risk_orders": 0,
  "epsilon_breaker_restore_pairing": 0
}
```

SHA-256 of the trace:
`a08e4f9b0dc5e6d4045b7027cdaac656d45db4cd0202a73713d46b110b135584`.
Checkpoint:
`b1305bc8f1990ed7b025a45be76dcb97a13b9f65b81b7358ede846924503ffc2`.
Model file:
`3c993472b9f4ab568b9499c11fc7503ec0d6147a76c23aa54e3c5acfa6c1dba0`.
These are hashes of the files inspected, not a claim that a runtime source
checkout was immutable. Public results establish score and rank, not model provenance.

## Evidence and caveats

- [Final totals](../screenshots/final-totals.svg): top ten and our two neighbours on each side; exact cents, our team highlighted, zero-based bars.
- [Real public-page leaders](../screenshots/final-leaders.png): “The final”, “Ended” and leaders; captured **2026-11-15 07:58:29 UTC**.
- [Our public-page row](../screenshots/final-team.png): rank 29 and neighbours; captured **2026-11-15 07:56:53 UTC**.
- [Early live view](../screenshots/final-live-start.png): **€1,137** at **place 6, live** near the start of the final; team-supplied screenshot, 1568 × 1092 pixels, stored byte-for-byte; its original file name records 09:08:08 (capturing machine's clock). Live position only, not the result.
- [Round 12 results and provenance](epsilon-prime-board-round12.md).
- [Round 11 closed-position correction](epsilon-board-round11.md#closed-round-update).

The leaders and team-row PNGs are unaltered public-page browser captures at a **1280 × 1000 CSS-pixel
viewport** (**2560 × 2000 image pixels**). Only scrolling was used; no data
changed, rows hidden, cropping or annotation. The page rounds our margin to
**€16,760** and on time to **97.6%**; the feed and chart retain cents.
Screenshots and feed have separate retrieval times. Final status was ended
at both those captures and the feed retrieval; the early live view was taken while the final was running. Results from different secret weeks are not paired model comparisons.

This evidence refresh used only public GET requests/page loads and read-only
local file inspection. It created or advanced no game world or run, loaded no
team key, and did not signal or modify any existing running process.

## Rebuild the charts offline

The following Python snippet runs from the repository root with **Matplotlib
3.11.2**. It reads the two frozen JSON snapshots and the existing round-9
renderer, writes only the three new SVGs, and makes no network requests.

```python
import json, runpy
from pathlib import Path
from matplotlib.ticker import MultipleLocator

root = Path.cwd()
renderer = root / 'tests/make_round9_charts.py'
base = renderer.read_text()
public_final = json.loads((root / 'docs/research/final-board-public.json').read_text())
public_round = json.loads((root / 'docs/research/round12-board-public.json').read_text())
slug = 'guardians-of-the-moonlight'

def selected(teams):
    us = next(t for t in teams if t['team'] == slug)
    return [(t['rank'], t['name'], t['marginCents']) for t in teams
            if (t['rank'] is not None and (t['rank'] <= 10 or abs(t['rank'] - us['rank']) <= 2))
            or t['name'] == 'House best']

for event, public, board, title, subtitle, note, tick in [
    ('final', public_final, public_final['data'],
     'Final: Epsilon Prime on the official leaderboard',
     'Sunday 09:00 Helsinki · rank 29 of 58 · 2026-11-15 07:55:28.929 UTC · ended',
     'Top ten and our neighbours; no House best entry is published in the final feed.', 5000),
    ('round12', public_round, public_round['data']['current'],
     'Round 12: Epsilon Prime on the official leaderboard',
     'Level 8 · Sunday 06:00 Helsinki · rank 34 of 51 · 2026-11-15 07:55:28.783 UTC',
     'Public snapshot; the ranking feed publishes no round-closed flag.', 25000),
]:
    source = base.replace('cheap-drive-round9', 'cheap-drive-' + event)
    source = source.replace('round9-totals.svg', event + '-totals.svg')
    source = source.replace('Round 9: Delta on the official leaderboard', title)
    source = source.replace('f"Level 8 · Saturday 21:00 · rank {RANK} of {RANKED_TEAMS} · {STAMP} · round open"', repr(subtitle))
    source = source.replace('fig.subplots_adjust(left=0.32, right=0.99, bottom=0.12, top=0.87)',
                            'fig.subplots_adjust(left=0.32, right=0.99, bottom=0.12, top=0.85)')
    source = source.replace('    fig.savefig(OUT / "' + event + '-totals.svg",',
                            '    fig.text(0.025, 0.897, ' + repr(note) + ', fontsize=9)\n    fig.savefig(OUT / "' + event + '-totals.svg",')
    source = source.replace('Round still open at retrieval.', note)
    source = source.replace('25000))', str(tick) + '))')
    if event == 'final':
        source = source.replace('Total gross margin across five secret weeks', 'Gross margin in the final secret week')
        source = source.replace('Official leaderboard snapshot; top ten, our neighbours and House best. ',
                                'Ended final leaderboard; top ten and our neighbours. No House best is published. ')
    namespace = {'__file__': str(renderer), '__name__': 'offline_evidence'}
    exec(compile(source, str(renderer), 'exec'), namespace)
    us = next(t for t in board['teams'] if t['team'] == slug)
    namespace.update(TOTALS=selected(board['teams']), RANK=us['rank'],
                     RANKED_TEAMS=sum(t['rank'] is not None for t in board['teams']))
    namespace['style']()
    namespace['totals_chart']()

# Reuse the established run-chart renderer and its exact-cent labels.
source = base
for old, new in [('round9', 'round12'), ('round-9', 'round-12'),
                 ('Round 9', 'Round 12'), ('Saturday 21:00', 'Sunday 06:00 Helsinki'),
                 ('Delta', 'Epsilon Prime'), ('#31', '#34')]:
    source = source.replace(old, new)
source = source.replace('round open', 'public snapshot')
source = source.replace('all five candidate runs qualified', 'all five runs qualified')
source = source.replace('frameon=False, ncol=2, fontsize=9', 'frameon=False, ncol=1, fontsize=9')
# Put the long retrieval timestamp on its own line.
source = source.replace('f"Level 8 · Sunday 06:00 Helsinki · all five runs qualified · {STAMP} · public snapshot"',
                        '"Level 8 · Sunday 06:00 Helsinki · all five runs qualified"')
source = source.replace('    fig.savefig(OUT / "round12-runs.svg",',
                        '    fig.text(0.55, 0.91, "2026-11-15 07:55:28.783 UTC", fontsize=9)\n    fig.savefig(OUT / "round12-runs.svg",')
ns = {'__file__': str(renderer), '__name__': 'offline_evidence'}
exec(compile(source, str(renderer), 'exec'), ns)
r = public_round['data']['current']
us = next(t for t in r['teams'] if t['team'] == slug)
leader = next(t for t in r['teams'] if t['rank'] == 1)
as_runs = lambda team: [(x['run'], x['marginCents'], x['onTimeShare'], x['wonOrders']) for x in team['runs']]
ns.update(OUR_RUNS=as_runs(us), LEADER_RUNS=as_runs(leader))
ns['style']()
ns['runs_chart']()
for name in ['final-totals.svg', 'round12-totals.svg', 'round12-runs.svg']:
    p = root / 'docs/screenshots' / name
    p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines()) + '\n')
    print(p.relative_to(root))
```

Validation: all selected chart labels match the frozen public feeds; all five
round-12 margins sum to the published total. The final saved score and all five
completed round-12 trace scores match their public rows. SVGs parse, local
documentation links resolve, PNG bytes match their original browser captures,
and the offline snippet regenerates identical SVG bytes.
