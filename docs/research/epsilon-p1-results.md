# Epsilon P1 paired results

Candidate minus stored current-Delta scores on matching seeds. Existing and fresh cohorts are separate. No policy is promoted.

| Policy | Cohort | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time |
| --- | --- | ---: | ---: | ---: | ---: |
| aged180-rescue85 | existing | 3 | €+469.87 | 2/3 | 92.593% |
| rescue85-step25 | existing | 4 | €+829.05 | 3/4 | 89.785% |
| retry2 | existing | 3 | €+84.37 | 2/3 | 90.778% |
| stop-spare | existing | 4 | €-31.96 | 0/4 | 91.117% |
| tight | existing | 4 | €-55.59 | 0/4 | 91.117% |
| tight-rescue85 | existing | 3 | €+812.88 | 2/3 | 89.785% |
| tight-roads | existing | 19 | €-51.58 | 11/19 | 91.714% |
| tight-roads-stop-spare | existing | 4 | €+157.83 | 2/4 | 91.714% |
| tight-roads-stop-spare-rescue85 | existing | 4 | €+212.11 | 3/4 | 91.501% |

## Earliest selection versus confirmed Epsilon

| Policy | Cohort | Paired weeks | Mean margin difference/week | Positive weeks | Worst on time | Extra completed orders/week |
| --- | --- | ---: | ---: | ---: | ---: | ---: |

The tight-roads 19-week result fails the positive-margin gate. Its queued fresh block was cancelled before launch when earliest selection became the priority. The isolated latest0 screen also fails the service gate. No production model JSON was changed.

Initial screen: f1-s07, f2-s04, f1-s06, f1-s08. Rescue screen stopped after three seeds per arm on orchestrator instruction. Delivery-stop spare uses the common s07/f2-s04/s01/s05 screen. Partial rows are unconfirmed.

Tight-roads differs from the previously rejected road-only policy by −€4.54/week over the nineteen pairs. Its failed screen uplift is not a repeatable margin gain.

Completed records: 48. Error rows: 0. Raw outputs remain under ignored runs/epsilon-p1/. Only summary.md and runs.jsonl were read for selection.
