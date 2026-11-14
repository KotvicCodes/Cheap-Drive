# Cheap-Drive event demo

A 100-second motion film for the Bahn/Spread challenge at Junction 2026. Full HD, 30 fps, H.264/AAC MP4. The film combines a clearly marked illustrative Beta policy replay, a real offline-report screenshot, the complete refreshed experiment chart, matched-policy comparisons, and the saved five-world ranking result.

The soundtrack is an original, deterministic 120 BPM instrumental synthesized by the renderer. There is no spoken narration. Main messages are on screen; an optional text track is supplied beside the video.

![Poster frame](assets/poster.png)

![12-frame review contact sheet](assets/contact-sheet.jpg)

## Render

Python 3.12+ with the pinned dependencies in an isolated environment:

```sh
python3 -m venv runs/demo-video/.venv
runs/demo-video/.venv/bin/pip install -r docs/demo-video/requirements.txt
runs/demo-video/.venv/bin/python docs/demo-video/render.py --stills
runs/demo-video/.venv/bin/python docs/demo-video/render.py --draft
runs/demo-video/.venv/bin/python docs/demo-video/render.py
```

Output defaults to `runs/demo-video/` (ignored by Git); `--output /absolute/path` overrides it. The final file is `cheap-drive-demo.mp4`. Still mode writes full-resolution review frames, a contact sheet, and a poster. Draft mode writes a 540p, 15 fps MP4. Rendering makes no simulator requests and needs no credentials or network access. `imageio-ffmpeg` supplies the encoder.

## Film timeline

| Time | Scene |
| --- | --- |
| 00:00–00:09 | Move cars. Make margin. Animated abstract route network. |
| 00:09–00:25 | Beta replay: screen, quote, post a gig, track delivery. |
| 00:25–00:35 | Real report screenshot, with fixed header and scrolling details. |
| 00:35–00:49 | 1,022 completed practice worlds and the complete original chart. |
| 00:49–01:01 | One matched stress seed: more wins, less margin, failed qualification. |
| 01:01–01:16 | Selective-700 policy: +€1,231.75/week, eight matched development seeds. |
| 01:16–01:30 | Saved official ranking round: €50,541.26; five qualifying weeks. |
| 01:30–01:40 | Brand close and next step: unseen-week validation. |

## Evidence and limits

The source is the presentation handoff prepared in the Presentation thread, including the refreshed snapshot at **2026-11-14 11:59:59 UTC**. Local source files originally lived under `/Users/kotvic/Desktop/GitHub/Cheap-Drive/runs/presentations/presentation-handoff/`.

- `data/graph-data.json` and `assets/all-run-margins.png` are copied from `updates/run-refresh-20261114T115959Z/`. There are **1,022 completed practice worlds across 34 seed+level scenarios**, plus five separate official worlds. Repeated seeds are correlated; this is not 1,022 independent validation weeks. The graph's full axes, legend, failure markers and notes remain visible. Its white matte is tinted to match the film.
- `data/per-seed-comparisons.csv` is copied from that update's `analysis/` folder. The selective-700 result is a **development comparison**, not a fresh holdout or the submitted final policy. It changes a bundle of route/admission rules. The gain scene states the on-time tradeoff and remaining validation need. The eight small bars are the actual per-seed margin gains, using a common zero baseline.
- The stress-test comparison is `gamma-t04`, baseline 500 km / 30% win target versus 600 km / 38%. Both settings change. The 90% on-time qualification gate is separate from simulated money.
- `data/official-five-weeks.csv` is copied from the handoff's `data/`. The total is a **historical ranking-round result**, separate from the selective-route experiment and the one-week competition final. It is not presented as a final result or a verified best-ever score.
- The report screenshot is the repository's `docs/screenshots/week-overview.png`: a **level-4 fixed-baseline tooling example**, not Beta/Gamma/official performance. Its negative margin is preserved.
- The dispatch replay is an explanatory animation, not footage of a live world. City names, route and compressed timing are illustrative. Baseline screening, trust-aware pricing and the fee ramp are drawn from `beta.py`; emergency rescue after a warning is simplified to a note.

The renderer checks the world count, cent-exact official total, all official qualification flags, all eight selective-route gains and qualification flags, paired averages, and the stress-test metrics before rendering.

## Assets

Space Grotesk and IBM Plex Mono are included under their accompanying SIL Open Font License files. Visuals are code-drawn apart from the existing report screenshot and supplied chart. The music contains no external recordings or samples.

The generated MP4, poster, captions, review sheet and verification report are delivered in `runs/demo-video/`. Source, frozen inputs, font licenses and this guide live here.
