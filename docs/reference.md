# Operational reference

Detailed setup, practice, capture and reporting instructions. See the
[README](../README.md) for the current model and results. Commands below run
from the repository root.

## Event schedule and run limits

Published schedule for **13–15 November 2026**. All event times are **Helsinki time (EET, UTC+2)**. Recheck the [judging page](https://spread.bahnexpress.com/judging) and Junction schedule before relying on them:

| Run Type | Schedule (Starts / Opens) | How Many You Can Submit |
| --- | --- | --- |
| **Ranking Rounds** (`scripts/board.py` / `board: true`) | **Opens** at:<br>• **Fri:** `19:30`<br>• **Sat:** `00:00`, `09:00`, `12:00`, **`15:00`**, `18:00`, `21:00`<br>• **Sun:** `00:00`, `03:00`, `06:00`<br>*(e.g. the 15:00 round **starts** at 15:00 and stays open until 18:00)* | **5 runs per level, per round** (played one at a time in order 1–5; each secret week once).<br>• After 5 runs at a level, `board: true` returns `409` until the next round opens.<br>• Deleting an unfinished ranking run **still counts** (the server runs it to completion without your system).<br>• Runs started before the next round opens still count in the round they were created in. |
| **Practice Runs** (`--seed` / regular) | Anytime | **Unlimited** total runs.<br>• **Max 8 active (unended) worlds** at once per team (including `fork` copies and active ranking runs). Ended/deleted practice worlds free their slot. |
| **Test Finals** (official kit final mode) | **Starts** on **Sat** at **`14:00`** and **`20:00`** (~19 min each; set 15 min before at `13:45` and `19:45`) | **1 live world per team** per test final (2 test finals total). Restarting reconnects to the same world. |
| **The Final** (official kit final mode) | **Starts** on **Sun** at **`08:00`** (~34 min, ends ~`08:35`; set at `07:30`) | **1 live world per team** (Level 8). Top 10 ranked teams (≥90% on-time) advance to the jury. |
| **Junction Submission** | **Prelim:** Fri `23:59`<br>**Final:** Sun `10:00` | **1 team submission** on the Junction platform (submission hash, code link, 5–10 slides or short video). |

The final starts Sunday 15 November at **06:00 UTC**, with registration
closing at **05:30 UTC**; start the dispatcher before the clock begins. Final
submission is **08:00 UTC**. Test finals start Saturday at **12:00 and 18:00 UTC**,
begin on Thursday in the simulated week and last about 19 minutes.

Submission needs the team-page submission hash, a code link and a presentation
(ideally 5–10 slides or a short video). Explain decisions with paired evidence,
including failures and limits.

**The repository has no final-mode runner.** `dispatch.py`, `compare.py` and
`scripts/sweep.py` run ordinary practice; `scripts/board.py` runs public practice
rankings. The official kit's final mode is not wired into these commands.
[Final integration requirements](challenge.md#final-integration-requirements)
still need implementation and test-final validation before any baseline is
used on final clocks.

## Setup

Python 3.9 or later is supported by the official kit. We use Python 3.12 for GitHub practice runs and check 3.9, 3.12 and 3.14 in CI. From the repository root, create a local environment and install the official client:

```bash
bash scripts/setup.sh
source .venv/bin/activate
python -m unittest discover -s tests -v
python dispatch.py --demo
```

The setup command checks installed dependencies and verifies the kit's SHA-256 against `requirements.txt`. It uses Python's built-in `venv`, falling back to `uv` if installed when Python cannot bootstrap pip. If neither works, install your Python's venv support (for example, `python3-venv` on Debian/Ubuntu) or [uv](https://docs.astral.sh/uv/getting-started/installation/), then rerun it. Select a particular installed interpreter with `PYTHON=python3.12 bash scripts/setup.sh`. Setup and offline checks require no team key; installation requires network access to download the kit.

For local live runs, optionally copy `.env.example` to `.env`, fill in the key locally and load it with `set -a; source .env; set +a`. The `.env` file is ignored by Git. GitHub secrets are available to Actions workflows; they do not automatically populate your local terminal.

## GitHub setup and practice runs

The **Checks** workflow installs the kit, runs the offline tests and exercises the demo on each pull request and push to `main`. It needs no secrets.

Add the following under [Settings → Secrets and variables → Actions → Repository secrets](https://github.com/KotvicCodes/Cheap-Drive/settings/secrets/actions):

| Secret | Required | Value |
| --- | --- | --- |
| `SPREAD_KEY` | Yes, for live practice | Your team's key from the challenge registration page. |
| `SPREAD_URL` | No | Server address; defaults to `https://spread.bahnexpress.com`. |

Open **Actions → Practice comparison → Run workflow**. Select a level or `all` and a shared seed. The default runs both existing models at all eight levels on one seed: **16 ordinary practice weeks**. A single level runs two weeks.

To verify credentials and live execution before merging a repository branch, add the **run-practice** label to its pull request. This runs both models at level 4 on seed `github-pr-smoke-1` (two ordinary practice weeks). Remove and reapply the label to request another run. Fork pull requests are excluded. Runs start only when manually dispatched or labeled; adding a secret or pushing a commit does not start practice.

The workflow shows the leaderboard in its run summary and uploads `leaderboard.md`, `results.json` and the JSONL traces as a **practice-comparison** artifact retained for 14 days. Failed runs also upload any partial results and traces that were written. Download results before they expire. Practice weeks run concurrently using up to eight free team slots. Local runs and other users share the team's unfinished-world slots and rate limit; a suite refuses to create worlds when all slots are occupied. A forced cancellation or timeout may leave an unfinished world; check the world IDs in the traces if you need to clean one up.

## Pre-Alpha baseline

The pre-Alpha fixed-price prototype uses constant prices:

- Quote **€100 per order** for every offered delivery option, regardless of distance or the reference prices.
- Pay **€150 per car** to a driver. A combined two-car trade-in gig pays €300; each car posted separately pays €150.
- Keep driver fees constant, including after deadline warnings. No automatic increases, direct offers or adaptive pricing.

Both amounts are configurable. These defaults demonstrate the API flow; they are not a recommended competitive policy.

## Try it without a team key

```bash
python dispatch.py --demo
python dispatch.py --demo --dealer-price 400 --driver-fee 175
```

The demo feeds a scripted request, win, booking and delivery through our actual dispatch loop. It is **not the Spread simulator** and its score is synthetic. It shows how quotes, driver fees and delivery events connect without needing credentials or network access.

## Play an actual practice week

Create a team at [the challenge registration page](https://spread.bahnexpress.com/join), then set the server address and your team key:

```bash
export SPREAD_URL=https://spread.bahnexpress.com
export SPREAD_KEY="<your team key>"
python dispatch.py --level 4 --seed cheap-drive-1
```

Change the fixed amounts in euros, with at most two decimal places:

```bash
python dispatch.py --level 4 --seed cheap-drive-1 --dealer-price 350 --driver-fee 180
```

Level 4 is the default because dealer quotes compete on price there. At levels 1–3 every quote wins at the first option's list price, so those levels cannot demonstrate the effect of changing our dealer price. Level 8 is available with `--level 8`, but scarcity and additional constraints make the constant-price baseline deliberately unsophisticated.

Each invocation creates an **ordinary practice world**, never a ranking run or a final. Completed worlds remain available for inspection and do not occupy unfinished-world slots. On an error or Ctrl-C, the runner **preserves its practice world by default** for debugging. An unfinished world may hold one of the team's eight unfinished-world slots. Inspect it before explicitly cleaning it up through the API. If you deliberately want this invocation's failed practice world deleted, pass `--delete-on-error`. This option does not affect completed worlds. A lost create response can leave a world whose ID the process never received.

## Inspect a run

The terminal shows requests, accepted quotes, posted driver fees, bookings, delivery events and the final score. Full events and action results are written as JSON lines under `runs/`. Use `--log runs/my-run.jsonl` to choose a fresh path; existing log files are not overwritten. All amounts inside API payloads and logs are integer cents, and times are integer world minutes.

New runs capture:

- `run`: world ID, seed, level and fixed prices. `mode=demo` always means synthetic data.
- `snapshot`: initial and end state, including score and world `endsAt` when available.
- `map`, `roster`, `reveal`: complete returned payloads when the SDK exposes them and the server permits access. Failed optional reads produce a sanitized `capability_unavailable` record.
- `action_intent`: batch ID, world minute, method, parameters and actions, flushed and fsynced **before** each mutation call. This also captures sends made internally by the official starter. Large outboxes are split into calls of at most 50 actions so each return is journaled separately.
- `advance_batch` and `act_result`: the full SDK return, flushed and fsynced **before** desk processing. A handler crash cannot discard later events in an already saved batch.
- `daily_score`, `score`, `run_end`: recorded checkpoints and the loop reaching its known endpoint.

Capture is at the pinned SDK boundary, not a packet recorder. The SDK can filter repeated event sequences and retry transport calls internally. A process crash before a completed journal write, disk failure, an interrupted response, or a lost server response can still leave missing information. An intent without its result means **unknown server outcome**, not a rejected action. Do not blindly replay it. The runner does not implement automatic resume or exactly-once delivery. HTTP headers, API keys and raw exception strings are not journaled; credential-shaped fields/text are redacted before capture.

## Analyze an existing week offline

```bash
python week_report.py runs/my-run.jsonl
python week_report.py runs/my-run.jsonl --output runs/my-week.html
```

Open the generated HTML directly in your browser. No server, key, Spread installation, CDN, map tiles, telemetry or internet connection is needed. The report generator uses Python's standard library. Output files must be fresh; the CLI refuses to overwrite an existing report or input. The report-generator version is read from the root `VERSION` file at import time and appears in each report and CLI output. Keep that file; its version is independent of the Alpha/Beta/Gamma/Delta strategy names.

The report includes financial and score charts, every observed request and quote, wins/losses, original notes and options, order/leg histories and windows, gigs/stops/fee changes, driver activity, incidents, the complete ledger, and a searchable raw explorer. Entity IDs open histories. Tables support sorting, pagination, text search, entity filters, world-day and clock filters, and exports of all filtered rows across pages. Clock ranges spanning midnight are supported. Entity-time filters match any captured activity for that entity. Overview charts always cover the full source. Days after Sunday retain distinct day numbers, including the delivery tail beyond the request week.

The layout is built for a whole week at real volume. A provenance strip shows byte retention, line validity, endpoint verification and reconciliation status on every page. The overview adds a hoverable cumulative ledger chart, money in and out per world day, recorded score checkpoints and a day-by-hour request arrival heatmap; selecting a day or an hour opens the matching ledger or timeline rows. Explorer tables show active filters as removable chips, a per-day row distribution that also filters, the current sort and sticky dense headers. Any row opens its history in a side drawer that keeps back navigation between linked orders, gigs and drivers and groups activity by day. Press `/` to search. The report follows the system light or dark theme, with a manual toggle stored only in the browser. Previews are in [docs/screenshots](screenshots/README.md).

**Original source is preserved byte for byte inside the HTML**, with SHA-256 provenance and an exact JSONL download. Complete analysis JSON and filtered JSON downloads keep unknown fields. Invalid UTF-8, malformed/partial lines, blank lines and duplicate object keys stay inspectable through exact byte ranges. Displayed invalid UTF-8 uses replacement characters; the binary download does not. The generator refuses credential-shaped input rather than embedding secrets or silently deleting fields. If refused, keep the original privately and deliberately prepare a sanitized copy for reporting. Do not import arbitrary credential-bearing logs.

The report reads both the older `run` / `event` / `action_result` / `daily_score` / `score` format and new batch captures. Exact duplicate event sequences count once in derived views while all original copies remain in raw records. Conflicting sequence payloads are shown and excluded from derived totals. Gaps, malformed records, pending intents and missing final observations lower confidence. A numerically matching ledger is not proof that a whole simulated week was captured. Only an end snapshot reaching `endsAt` verifies that endpoint. Missing map, roster and reveal are labeled unavailable. Missing quote records are not labeled unquoted unless a captured reveal confirms it.

Reconciliation compares signed ledger totals with recorded final margin and revenue. Posted and booked fees are not charged a second time. Direct order net uses only ledger lines naming that order. Gig-only/shared and unattributed costs stay separate. Gig totals can overlap directly attributed order entries and must not be added to order totals. Reliability and ranking are displayed from the recorded score rather than reverse-engineered from incomplete observations.

**Treat the HTML and its downloads as private run data**: they include the complete source, not just a dashboard. Keep them under ignored `runs/`. Share only deliberately. No real trace or generated real report belongs in a commit.

The pre-Alpha fixed-price prototype subclasses the official starter's `Desk`, reusing its basic windows, retry, expiration and trade-in handling. The client is pinned because this starter class is an implementation detail rather than a guaranteed stable API. Notes still use the starter's limited keyword parser. That baseline does not add capacity selection, robust multilingual parsing, ranking mode or final mode; Beta ranking runs use `scripts/board.py`.

Keep the team key outside Git. The application reads environment variables directly; it does not automatically load `.env` files. Run traces and local environments are ignored by Git.

## Compare two models across all levels

Here, a **model** is a dispatch strategy plus its settings. With `SPREAD_KEY` set locally, one command compares our fixed-price model with the official starter:

```bash
python compare.py run
```

The default suite runs **both models at levels 1–8 on the same ten seeds**: 160 ordinary practice weeks, run sequentially. It prints a Markdown leaderboard to stdout and saves `leaderboard.md`, machine-readable `results.json`, and a JSONL trace per world in a fresh `runs/comparison-<time>/` directory. Progress goes to stderr, so stdout can also be redirected to a Markdown file. This uses actual Spread practice worlds, not the scripted offline demo or official ranking rounds.

For a quick all-level comparison with one paired seed:

```bash
python compare.py run --seeds smoke-1 --output runs/smoke-comparison
```

For a short level-8 screening experiment, run paired seeds concurrently:

```bash
python compare.py run --model-a models/alpha.json --model-b models/starter.json \
  --levels 8 --seeds screen-1 screen-2 --workers 8 --fast \
  --output runs/quick-screen
```

`--workers` defaults to 1 and accepts up to 8. Each worker has its own process,
SDK connection and world; the requested count is reduced to the number of free
team slots observed before starting. Other processes can still race for those
slots. The server's team-wide rate limit remains in effect. GitHub practice
comparisons request eight workers while keeping full captures.

`--fast` removes HTTP stops for declared bookkeeping events, while retaining
every event and the handler clock at the original stops. The built-in starter,
fixed model, Alpha and Beta opt in; custom subclasses keep all wakes unless they
explicitly declare `passive_wake_events` on their own class. Fast mode skips
daily score reads and end roster/reveal downloads. It retains all actions,
event batches, durable journaling, the final score and the endpoint snapshot.
Use normal mode for complete diagnostics, or fetch a completed world's reveal
later. A passive handler that queues actions stops the run instead of silently
delaying them.

The SDK wrapper requests gzip responses, reuses connections and caches only the
public map. Alpha reuses the initial snapshot/map/roster already captured by
the runner. Per-week `seconds` and transport `timing` in `results.json` show
request counts, API/transport time, transferred bytes and observed rate limits.
`--no-compression` allows a transport comparison. The wrapper retains the
official SDK's request validation, rate-limit waiting and retry behavior.

Measure public API latency from a candidate host without credentials or new
practice worlds:

```bash
python performance.py --samples 8
```

The command alternates compressed and uncompressed map reads over a warm
connection. It measures that host's network path, not the duration of a week.
Moving the runner near the official server remains a useful next experiment
when round-trip time dominates; more machines do not increase the team limit.

For a focused experiment with explicit model definitions:

```bash
python compare.py run --model-a models/fixed.json --model-b models/starter.json \
  --levels 4 8 --seeds validation-1 validation-2 validation-3 \
  --output runs/fixed-vs-starter
```

The report includes:

- Overall and per-level leaderboards: qualified weeks, mean gross margin, revenue, on-time share, undelivered share and won orders.
- Paired wins and losses, plus margin, revenue and delivery-rate differences in a consistent **B − A** direction.
- Signed ledger totals, deadline warnings, drops, no-shows, failed-visit reasons and rejected actions.
- Suggested next experiments based on qualification failures, observed costs and the largest per-level margin gap. Level 8 gets its own recommendation because it is the final's difficulty.
- Code revision, dirty-tree flag, exact configurations and seeds for reproduction; raw results retain individual scores, world IDs and trace paths.

The comparison ranks **qualification count first, then mean gross margin across all sampled weeks**. It uses each world's official `ranked` flag; a high average delivery rate cannot hide failed weeks. Neither model is recommended if neither qualifies. Overall results cover the requested levels equally; use level 8 and separate held-out seeds when selecting the final strategy. Ten seeds are an initial comparison, not proof that a model will win on unseen weeks. Weekly delivery percentages are averaged per week, not pooled across orders.

To compare two fixed-price variants, copy [models/fixed.json](../models/fixed.json), give the copy a different `name`, and change its euro amounts:

```json
{
  "name": "Fixed €350 / €180",
  "factory": "fixed",
  "settings": {"dealer_price": "350", "driver_fee": "180"}
}
```

For a future strategy, set `factory` to `your_module:your_factory`. The factory receives `(world, level, now, journal, **settings)` and must return a subclass of `dispatch.JournalDesk` (or `FixedDesk`), calling the inherited `handle` and `read_results` methods so diagnostics remain complete. `JournalDesk` is the official starter with logging; it adds no pricing changes. Factories are trusted local Python code imported from the project/Python path. Both models use the same practice clock and wake events. Keep credentials in the environment, outside model JSON.

Regenerate the report later without a team key or new simulations:

```bash
python compare.py report runs/fixed-vs-starter/results.json
python compare.py report runs/fixed-vs-starter/results.json --output comparison.md
```

Existing output directories and report files are never overwritten during a new suite. Results are checkpointed after every run. On a worker failure the suite starts no more worlds and finishes those already running before reporting the failure. Ctrl-C requests that active workers stop between API calls. Failed worlds are preserved for debugging by default and may hold unfinished slots. Use `--delete-on-error` to opt into deleting only this invocation's failed worlds; completed worlds remain inspectable. Cleanup failures retain world IDs in results. A lost response can still leave an unknown world or outcome. Incomplete or mismatched pairs cannot produce a leaderboard.

To continue a suite without replaying its completed weeks, repeat the same
command and output directory with `--resume`. Code revision and Python source
hashes, model settings, server, fast mode, levels and seeds must match. The
worker count can change. Failed attempts receive fresh trace filenames, and
their prior traces and world IDs remain in the checkpoint; resume does not
delete or blindly replay an unfinished world. Only one controller can write a
given output directory at a time (the output lock uses POSIX file locking).
If code or selections change, use a fresh output directory.

## Checks

```bash
python -m unittest discover -s tests -v
```

The standard-library suite covers dispatch behavior, capture-before-processing, starter-internal sends, lost responses, exact-byte preservation, unknown/malformed/partial records, duplicate/conflicting sequences, shared-cost reconciliation, incomplete runs, credential refusal and script injection.

Optional browser checks exercise actual report controls, history drawer navigation, filter chips, day distribution and heatmap drilldown, theme switching, pagination, filters, sorting, exact source downloads, JSON exports, captured map rendering, XSS and mobile overflow using synthetic fixtures. They require a local Chromium installation managed by Playwright:

```bash
python -m pip install -r requirements-dev.txt
# Keep all downloaded environments, caches and test artifacts inside this repository.
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/browsers"
export TMPDIR="$PWD/.cache/tmp"
mkdir -p "$TMPDIR"
python -m playwright install chromium
python tests/check_browser.py
# Optionally validate the known completed level-4 trace locally as well:
python tests/check_browser.py --real-trace runs/<completed-level-4-trace>.jsonl
```

`tests/make_browser_fixture.py` also writes a clearly labeled synthetic report under ignored `.cache/`. `tests/browser_checks.js` and `tests/real_browser_checks.js` can be evaluated in that report through an existing browser automation session. No browser test starts a server or a simulator world.

The checks cover exact currency parsing, constant prices across delivery options and deadline warnings, rejected trade-in splitting, manual-licence retry handling, action rejection logging and the offline request-to-ledger flow. Comparison tests use scripted worlds to verify all-level pairing, both models' traces, qualification-first ranking, delta signs, ties, incomplete-result rejection, output preservation, failed-world retention and opt-in failure/interrupt cleanup. They make no claims about simulator performance.
