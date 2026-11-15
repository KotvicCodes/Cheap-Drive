# Archived Gamma-era demo evidence

These original files came from the 14 November 2026 14:25 UTC presentation
handoff. They are preserved byte-for-byte for historical reproducibility,
separately from the current 72-second video renderer:

- `graph-data.json`: 1,155 practice worlds plus ten official Beta worlds. All
  practice scores also appear unchanged in `presentations/run-data.json`; the
  ten official world records are unique to this inventory.
- `chart-data.json`: the original stage/cohort metadata and audit provenance.
- `per-seed-comparisons.csv`: the original Gamma screening comparisons,
  including rejected experiments.
- `assets/learning-stages.png`, `assets/gamma-confirmation.png`, and
  `assets/official-rounds.png`: the original rendered charts. They have no
  identical remaining copy and preserve the historical presentation visuals.
- `original-manifest.json`: the original handoff checksums and file inventory.
  Its paths and hashes describe that handoff, not the current renderer or
  this archive's layout; it is retained as provenance, not a current validator.

The current renderer reads the canonical presentation inventory and chart,
plus `docs/demo-video/data/paired-weeks.csv`. The redundant cohort and official
CSV summaries were removed; their values remain in the archived JSON. Official
ranking reports and all round screenshots remain in `docs/research/` and
`docs/screenshots/`.
