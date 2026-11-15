# Epsilon P1 paired results

Candidate minus stored current-Delta scores on matching seeds. Existing and fresh cohorts are separate. No policy is promoted.

| Policy | Cohort | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time |
| --- | --- | ---: | ---: | ---: | ---: |
| aged180-rescue85 | existing | 3 | €+469.87 | 2/3 | 92.593% |
| epsilon-aged-rescue | existing | 3 | €-12.18 | 1/3 | 91.375% |
| epsilon-earliest | existing | 4 | €+44.13 | 2/4 | 91.892% |
| epsilon-economic | existing | 4 | €-52.98 | 2/4 | 89.674% |
| epsilon-finish-band180 | existing | 2 | €+508.84 | 2/2 | 90.811% |
| epsilon-finish-band60 | existing | 2 | €+359.95 | 2/2 | 91.351% |
| epsilon-rescue-spare | existing | 4 | €+25.94 | 2/4 | 91.935% |
| epsilon-retry2 | existing | 2 | €-187.75 | 1/2 | 91.379% |
| rescue85-step25 | existing | 4 | €+829.05 | 3/4 | 89.785% |
| retry2 | existing | 3 | €+84.37 | 2/3 | 90.778% |
| stop-spare | existing | 4 | €-31.96 | 0/4 | 91.117% |
| tight | existing | 4 | €-55.59 | 0/4 | 91.117% |
| tight-rescue85 | existing | 3 | €+812.88 | 2/3 | 89.785% |
| tight-roads | existing | 19 | €-51.58 | 11/19 | 91.714% |
| tight-roads-stop-spare | existing | 4 | €+157.83 | 2/4 | 91.714% |
| tight-roads-stop-spare-rescue85 | existing | 4 | €+212.11 | 3/4 | 91.501% |

## Pair policies versus Early Epsilon

| Policy | Cohort | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Extra completed orders/week |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| epsilon-aged-rescue | existing | 3 | €-66.24 | 1/3 | 91.375% | -1.67 |
| epsilon-earliest | existing | 4 | €-169.28 | 2/4 | 91.892% | -2.00 |
| epsilon-economic | existing | 4 | €-266.39 | 1/4 | 89.674% | -2.50 |
| epsilon-finish-band180 | existing | 2 | €+406.17 | 2/2 | 90.811% | -1.50 |
| epsilon-finish-band60 | existing | 2 | €+257.29 | 1/2 | 91.351% | +0.00 |
| epsilon-rescue-spare | existing | 4 | €-187.47 | 1/4 | 91.935% | -0.50 |
| epsilon-retry2 | existing | 2 | €-290.42 | 1/2 | 91.379% | -0.50 |

The tight-roads 19-week result fails the positive-margin gate. Its queued fresh block was cancelled before launch when earliest selection became the priority. The isolated latest0 screen also fails the service gate. No production model JSON was changed.

Initial screen: f1-s07, f2-s04, f1-s06, f1-s08. Rescue screen stopped after three seeds per arm on orchestrator instruction. Delivery-stop spare uses the common s07/f2-s04/s01/s05 screen. Partial rows are unconfirmed.

Tight-roads differs from the previously rejected road-only policy by −€4.54/week over the nineteen pairs. Its initial screen uplift did not survive the full extension.

Completed records: 69. Error rows: 1. Raw outputs remain under ignored runs/epsilon-p1/. Only summary.md and runs.jsonl were read for selection.
