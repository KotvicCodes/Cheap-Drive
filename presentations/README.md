# Cheap-Drive presentation

Open [cheap-drive-alpha-to-gamma.html](cheap-drive-alpha-to-gamma.html) locally in a browser. Keep this directory and the repository's existing [car logo](../assets/cheap-drive.svg) together. The deck has eight 16:9 slides, an embedded heading font, local chart images, and no remote dependencies.

Use the arrow keys, Page Up/Down, Space or number keys 1–8 to navigate; Home/End jump to the ends and F toggles full screen. Landscape also supports the wheel and horizontal swipes. Portrait view scrolls through the slides. Print to PDF in landscape with no browser headers/footers: print CSS gives one page per slide. Slide notes and citations are stored in each section's `data-speaker-notes` attribute.

## One maintained version

The HTML is the editable presentation source. `assets/` contains one PNG per chart; there are no embedded copies, alternate exports or historical decks in this directory. [evidence.json](evidence.json) contains only the numeric evidence needed for these slides. The already tracked research reports supply technical context rather than duplicated document copies.

The uploaded visual style is preserved. The duplicate run-count/token summary and unfinished Delta slide are removed. Alpha is described as Optuna TPE tuning. The final slide uses Gamma's published round-7 result. The all-run chart has no title or explanatory footnotes, with a bottom blue-dot “qualified” / red-cross “disqualified” legend. Graphs use colons instead of em dashes; methodology belongs in speaker notes.

## Evidence and dates

| Slide | Evidence | Qualification |
| --- | --- | --- |
| 1. Three generations | [Prototype specifications](../PROTOTYPES.md) | Covers published Alpha, Beta and Gamma, not the separate Delta branch |
| 2. The goal | [Official rules](https://spread.bahnexpress.com/kit/RULES.md) | At least one scored won order and ≥90% on time in every week; margin is the ledger sum |
| 3. Alpha | [Alpha results](../docs/research/alpha-results.md), [evaluation method](../PROTOTYPES.md#evaluation) | About €6,200/week on six tuning seeds; not a fresh-test estimate |
| 4. Practice history | `evidence.json` → `all_run_history` | Frozen 14 November 2026, 14:25 UTC: 1,155 completed worlds, 58 repeated seed+level scenarios |
| 5. Beta decisions | `evidence.json` → `beta_paired_tests`, [Beta research](../docs/research/beta-results.md) | Fee timing +€1,511.13/week on 3 matched seeds; trust +€851.47/week on 4; separate tests, do not sum |
| 6. Gamma's first failure | [Gamma research](../docs/research/gamma-results.md), `gamma_cohorts` | 7/8 new weeks qualified; failed week 89.956%, below 90% |
| 7. Revised Gamma | [Recovery and frozen confirmation](../docs/research/gamma-recovery-results.md), `gamma_confirmation` | +€2,030.845/week (+20.21%) on eight new matched weeks; both policies 8/8 qualified |
| 8. Official Gamma | [Round 7 report](../docs/research/gamma-board-round7.md), `gamma_official_round7` | €66,880.48; 5/5 qualified; 91.35% worst week. Snapshot rank 32/45 at 15:05:59 UTC, not a final rank |

All money is simulated euros. Practice-history counts remain frozen even though later runs exist. Qualification includes undelivered orders as late and excludes cancelled orders. A five-week ranking round needs every week to qualify; the actual final is one secret level-8 week. Round 7 and practice confirmation are different samples, and different ranking-round totals are not paired policy gains.

Early/Late denote broad experiment stages. Beta Early is s1–s3; Beta Late includes s4–s6, checks, the Beta sweep, and unchanged Beta controls used in Gamma suites. Gamma Early covers the original experiments and tests; Gamma Late covers the revised recovery experiments and tests. Repeated seeds are correlated. Horizontal jitter has no time meaning.

Gamma's successful practice test still had 22 failed-visit events and 12 undelivered orders. The code replay matches one tested case, not complete final-mode resilience. Neither the final result nor the exact final deployment is established here. Update those claims from official evidence before presenting. Delta's separate work can be added once its intended results and deployment status are chosen; it is not represented as already in production.

The complete deck, notes and evidence are kept under ten files. Private traces, reveals, credentials and the local prototype journal are excluded. No competition runs are needed to view or validate the presentation.
