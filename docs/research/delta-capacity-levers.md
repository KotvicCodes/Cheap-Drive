# Delta capacity audit and opt-in pairing experiment

The largest observed delivery bottleneck is repeated unbooked posting; the
strongest independent lever available to this implementation is broader safe
pairing. No live worlds were created, advanced or deleted for this audit.

## Evidence and definitions

Source: all eleven `rescue-notes` (current Delta) weeks, seeds `delta-f1-s01`
through `s11`, in the saved `delta-final/b5`, `b6`, and `b8` batches. The other
eleven `gamma` weeks are comparison data, not pooled into Delta's funnel.
Events are deduplicated by sequence. Accepted posts are joined to action
results, bookings to gig identities, and payment totals to ledger entries.
Final orders and revealed note deadlines reconcile all 78 service failures to
the recorded score. Raw traces and derived per-order details remain in ignored
`runs/capacity/`.

"Competitive quotes" excludes deliberate ten-times-list-price decline quotes.
All 11,379 requests actually received a quote, including 1,617 declines. Won
events include 26 later cancellations; score wins exclude them. First-booking
columns below count legs (not booking events), once each; trade-ins and pairs
can move two legs. After-expiry excludes reposts caused only by pairing,
withdrawal or changes, so these columns do not exhaust all first bookings.

| Seed | Requests | Declined | Competitive quotes | Score wins | Posts | Booked gigs | Legs first booked on original post | Legs first booked after expiry | Orders in booked pairs | Late | Undelivered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| s01 | 1032 | 158 | 874 | 235 | 380 | 236 | 152 | 63 | 22 | 8 | 0 |
| s02 | 1038 | 128 | 910 | 274 | 483 | 278 | 170 | 92 | 16 | 6 | 0 |
| s03 | 1034 | 145 | 889 | 255 | 437 | 256 | 137 | 78 | 40 | 5 | 0 |
| s04 | 1039 | 157 | 882 | 268 | 451 | 271 | 162 | 80 | 20 | 4 | 0 |
| s05 | 1031 | 196 | 835 | 248 | 415 | 243 | 148 | 73 | 34 | 6 | 1 |
| s06 | 1032 | 155 | 877 | 271 | 430 | 273 | 172 | 68 | 26 | 8 | 0 |
| s07 | 1030 | 177 | 853 | 253 | 516 | 260 | 120 | 101 | 28 | 16 | 0 |
| s08 | 1033 | 135 | 898 | 254 | 448 | 250 | 136 | 85 | 26 | 7 | 0 |
| s09 | 1040 | 121 | 919 | 272 | 452 | 263 | 163 | 74 | 36 | 3 | 1 |
| s10 | 1035 | 127 | 908 | 275 | 395 | 267 | 197 | 61 | 30 | 6 | 0 |
| s11 | 1035 | 118 | 917 | 240 | 358 | 231 | 163 | 62 | 30 | 6 | 1 |
| Total | 11379 | 1617 | 9762 | 2845 | 4765 | 2828 | 1720 | 837 | 308 | 75 | 3 |

Per week: 1,034 requests, 147 declines, 887 competitive quotes, 259 noncancelled
wins (261 win events), 433 posts, 257 distinct booked gigs, and 141 expiries.
There are 3,052 booking events including bookings again after drops/no-shows.
1,714 booking events concern original postings; 926 occur after an earlier
expiry for at least one carried leg. Of 2,859 legs ever booked, 1,720 (60.2%)
first book on their original post, 837 (29.3%) after expiry, and 302 after other
reposting. Pair posts number 283; pair booking events number 155; 308 distinct
orders (10.7% of win events) enter a booked pair. This does not assert that
every booked pair eventually completes as a pair.

Declines: 855 insufficient option slack (77.7/week), 304 route too long
(27.6/week), 214 trade-ins disabled (19.5/week), 150 no eligible long-route
option (13.6/week), 93 long-route capacity (8.5/week), one premium slack.
Even recovering every slack decline at the current 29% competitive win rate
would add only about 23 wins/week. The gap to 400–500 weekly wins cannot be
explained by this admission threshold alone.

An additional offline check of the actual note-aware slack calculation finds
only 52 of those 855 slack declines have no physically feasible option. Of the
remainder, 691 have at least four hours of slack but only 126 have six hours.
Thus the eight-hour rule does reject physically feasible work, particularly
four-to-six-hour windows. Physical feasibility is not evidence that a compatible
driver would book; at the current competitive win rate a four-hour threshold
would recover roughly 18 wins/week, a six-hour threshold roughly three. These
are headroom estimates with fixed observed requests, not live predictions, and
do not justify a blanket admission relaxation before delivery capacity improves.
The per-week counts are emitted as `admissionSlack` by the pairing probe.

## Booking time and money

Booking delay is measured from each accepted gig post to its first booking.
Unbooked posts are included in the denominator, not assigned a delay.
The clock below is the *posting* hour, across the complete delivery tail.

| Posting hour | Posts | Ever booked | Median delay, minutes |
|---|---:|---:|---:|
| 00 | 39 | 20 | 370 |
| 01 | 39 | 38 | 327 |
| 06 | 3 | 2 | 71 |
| 07 | 2 | 2 | 107 |
| 08 | 35 | 27 | 19 |
| 09 | 268 | 173 | 8 |
| 10 | 341 | 214 | 5 |
| 11 | 332 | 228 | 17.5 |
| 12 | 304 | 177 | 13 |
| 13 | 329 | 187 | 10 |
| 14 | 455 | 265 | 22 |
| 15 | 410 | 188 | 10 |
| 16 | 449 | 176 | 10 |
| 17 | 443 | 189 | 8 |
| 18 | 586 | 361 | 26 |
| 19 | 446 | 341 | 24 |
| 20 | 263 | 222 | 22 |
| 21 | 18 | 15 | 121 |
| 22 | 3 | 3 | 8 |

No posts occurred at 02–05 or 23. Across 4,765 posts, 1,262 pickup-stop windows
are shorter than three hours. 64 of the 78 service failures involve at least one
expired gig; only four involve a recorded visit failure. All three undelivered
orders have expiries and zero bookings. Seventeen service failures start with
a pickup window shorter than three hours. These are associations, not proof
that widening a particular window would prevent lateness. Posting-window,
private-rescue and charging fixes belong to the separate bug-checking agent.

Driver fees paid: €195,371.41 (€17,761.04/week), 97.9% of all ledger costs.
For those paid gigs, the sum of their own opening fees is €181,773.94, a
€13,597.47 gap (€1,236.13/week) before counting fee ageing already embedded in
repost opening fees. This is descriptive, not recoverable savings: lowering
fees could lose bookings. All booking events total €217,273.08 versus their
own-post openings of €202,916.88; those totals include bookings later dropped
and must not be treated as paid costs.

10,243 of 31,690 post-schedule increases (32.3%) are during 23:00–07:00, but
4,076 of 116,446 gig views (3.5%) also occur then. The SDK/rules' no-reading
restriction concerns direct offers, not all gig viewing. The hypothesis that
overnight raises necessarily pay for nothing is unsupported. Urgent service
needs also make unconditional night freezes risky; no night-fee lever was added.

## Pairing experiment

Recorded skip diagnostics reject 61,482 candidate directions for transfer
distance, 1,854 for driving time, 1,146 for windows, and 310 for idle time.
Candidate counts are not distinct orders, and the first failing check masks
later restrictions. Therefore `scripts/pair_opportunities.py` reconstructs
observed waiting-order states and reruns the actual note-aware planner with
different distance/driving limits, leaving all other safety checks unchanged.

| Profile | Transfer km | Driving minutes | Decisions with a feasible partner | Distinct feasible order pairs |
|---|---:|---:|---:|---:|
| Baseline | 30 | 300 | 276 | 422 |
| Drive-only probe | 30 | 480 | 410 | 624 |
| Regional | 60 | 480 | 612 | 1117 |
| Extended | 90 | 720 | 883 | 1845 |

The probe evaluates 2,871 observed new-win decisions. Its reconstructed baseline
276 opportunities is close to, but not exactly, 283 actual pair posts: the probe
does not replay all hidden dispatcher lifecycle state or intermediate retries.
It holds bookings fixed and opportunities overlap. It cannot forecast weekly
profit or additional delivered orders. The increase survives actual calendar,
audience and route feasibility checks, supporting a live controlled experiment.

`delta_pairing="off"` is the default and preserves actions and journaling.
`"regional"` sets the driver's transfer/driving limits to 60 km / 480 minutes;
`"extended"` sets 90 km / 720 minutes, the documented legal multi-car driving
maximum. Both require `pairs=1` and combine with `delta_note_fixes=1` and
`delta_rescue_windows=1`. They override only these two pair-search limits;
the existing 180-minute arrival allowance, 60-minute deadline spare, audience,
note/calendar checks, pricing and one-hour single fallback remain in force.
Gamma and `models/delta.json` are unchanged.

Measure delivered paired orders, pair bookings/splits, expiries, driver spend
per delivered order, score wins, margin and *every week's* on-time share. Pairing
can free driver time without automatically changing the 30% quote win target;
the next experiment should combine the winning capacity profile with a modest
intake increase only after live service/margin evidence supports it. Another
promising follow-up is intake targeted at feasible backhaul partners rather
than lowering every quote. The global learner/outage hypothesis is not resolved
by this audit; no learner changes were made.

## Reproduce offline

With the installed project Python, run:

```sh
python scripts/capacity_funnel.py /path/to/delta-final/b5 /path/to/delta-final/b6 /path/to/delta-final/b8 > runs/capacity/funnel.json
python scripts/pair_opportunities.py /path/to/delta-final/b5 /path/to/delta-final/b6 /path/to/delta-final/b8 > runs/capacity/pair-opportunities.json
python -m unittest discover -s tests
```

Initial implementation validation: 311 tests pass (305 existing plus six
pairing tests), including explicit-off action/timer/journal parity and safe
fallback, legal driving cap, windows, audience and note/rescue combinations.
