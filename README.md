<p align="center">
  <img src="assets/cheap-drive.svg" width="240" height="240" alt="Cheap-Drive: a red car with flames behind it">
</p>

# Cheap-Drive

Cheap-Drive is a project dedicated to tackling the Bahn Express challenge at [spread.bahnexpress.com](https://spread.bahnexpress.com/how).

## Challenge resources

- [How it works](https://spread.bahnexpress.com/how) — challenge overview and instructions.
- [Judging](https://spread.bahnexpress.com/judging) — judging criteria for submissions.
- [Leaderboard](https://spread.bahnexpress.com/leaderboard) — challenge standings.

Our implementation uses **Python** and the official Spread client. See [AI overview.md](AI%20overview.md) for observations, priorities and project decisions.

## Current approach

We are prioritizing a working prototype and strategy experiments. **We do not optimize compute time or compute cost at this stage; we will address that later.**

The first prototype uses constant prices:

- Quote **€100 per order** for every offered delivery option, regardless of distance or the reference prices.
- Pay **€150 per car** to a driver. A combined two-car trade-in gig pays €300; each car posted separately pays €150.
- Keep driver fees constant, including after deadline warnings. No automatic increases, direct offers or adaptive pricing.

Both amounts are configurable. These defaults demonstrate the API flow; they are not a recommended competitive policy.

## Setup

Python 3.9 or later is supported by the official kit. We use Python 3.12 for GitHub practice runs and check 3.9, 3.12 and 3.14 in CI. From the repository root, create a local environment and install the official client:

```bash
bash scripts/setup.sh
source .venv/bin/activate
python -m unittest discover -s tests -v
python dispatch.py --demo
```

The setup command checks installed dependencies and verifies the kit's SHA-256 against `requirements.txt`. It uses Python's built-in `venv`, falling back to `uv` if installed when Python cannot bootstrap pip. If neither works, install your Python's venv support (for example, `python3-venv` on Debian/Ubuntu) or [uv](https://docs.astral.sh/uv/getting-started/installation/), then rerun it. Select a particular installed interpreter with `PYTHON=python3.12 bash scripts/setup.sh`. Setup and offline checks require no team key; installation requires network access to download the kit.

The team's API key is already configured as the `SPREAD_KEY` repository secret for GitHub Actions. Agents must not ask the user to provide, paste, recreate or re-add it for normal setup or testing. Use the existing `.github/workflows/practice.yml` (**Practice comparison**) for authorized live validation; it injects `${{ secrets.SPREAD_KEY }}` into the run.

GitHub secrets do not automatically populate local terminals, and their plaintext values cannot be retrieved from GitHub. An unset local `SPREAD_KEY` does not mean the repository secret is missing. For local work, use the key if already supplied in the environment; otherwise run offline tests and `python dispatch.py --demo`, and use Actions for authorized live runs. Never print, log or commit credentials. Report actual Actions credential failures with the workflow error instead of asking for the key because it is unavailable locally.

For local live runs where the key is already available to you, optionally copy `.env.example` to `.env`, fill in the key locally and load it with `set -a; source .env; set +a`. The `.env` file is ignored by Git. Local setup, offline tests and the demo need no key.

## GitHub setup and practice runs

The **Checks** workflow installs the kit, runs the offline tests and exercises the demo on each pull request and push to `main`. It needs no secrets.

The team key is already saved under [Settings → Secrets and variables → Actions → Repository secrets](https://github.com/KotvicCodes/Cheap-Drive/settings/secrets/actions). No credential setup is needed for this repository's practice workflow:

| Secret | Required | Value |
| --- | --- | --- |
| `SPREAD_KEY` | Yes, for live practice; already configured | The team's existing API key, injected by the practice workflow. |
| `SPREAD_URL` | No | Server address; defaults to `https://spread.bahnexpress.com`. |

Open **Actions → Practice comparison → Run workflow**. Select a level or `all` and a shared seed. The default runs both existing models at all eight levels on one seed: **16 ordinary practice weeks**. A single level runs two weeks.

To verify credentials and live execution before merging a repository branch, add the **run-practice** label to its pull request. This runs both models at level 4 on seed `github-pr-smoke-1` (two ordinary practice weeks). Remove and reapply the label to request another run. Fork pull requests are excluded. Runs start only when manually dispatched or labeled; adding a secret or pushing a commit does not start practice.

The workflow shows the leaderboard in its run summary and uploads `leaderboard.md`, `results.json` and the JSONL traces as a **practice-comparison** artifact retained for 14 days. Failed runs also upload any partial results and traces that were written. Download results before they expire. Practice jobs run sequentially within the workflow, but local runs and other users still share the team's unfinished-world slots and rate limit. A forced cancellation or timeout may leave an unfinished world; check the world IDs in the traces if you need to clean one up.

## Try it without a team key

```bash
python dispatch.py --demo
python dispatch.py --demo --dealer-price 400 --driver-fee 175
```

The demo feeds a scripted request, win, booking and delivery through our actual dispatch loop. It is **not the Spread simulator** and its score is synthetic. It shows how quotes, driver fees and delivery events connect without needing credentials or network access.

## Play an actual practice week

Use the GitHub practice workflow above with the saved repository secret. For a local live run, if the team key is already available to you, set the server address and key in your local shell:

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

Each invocation creates an **ordinary practice world**, never a ranking run or a final. Completed worlds remain available for inspection and do not occupy unfinished-world slots. On an error or Ctrl-C, the runner attempts to delete its own practice world to free its slot; it reports the world ID if cleanup fails.

## Inspect a run

The terminal shows requests, accepted quotes, posted driver fees, bookings, delivery events and the final score. Full events and action results are written as JSON lines under `runs/`. Use `--log runs/my-run.jsonl` to choose a fresh path; existing log files are not overwritten. All amounts inside API payloads and logs are integer cents, and times are integer world minutes.

Look for these trace records:

- `run`: world ID, seed, level and the chosen fixed prices.
- `event`: the raw event, including order wins/losses, bookings, drops, failed visits and account entries.
- `action_result`: the action and its individual API result, including rejection reasons.
- `daily_score` and `score`: the daily and final outcomes.

The prototype subclasses the official starter's `Desk`, reusing its basic windows, retry, expiration and trade-in handling. The client is pinned because this starter class is an implementation detail rather than a guaranteed stable API. Notes still use the starter's limited keyword parser. This prototype does not yet add capacity selection, robust multilingual parsing, ranking mode or final mode.

Keep the team key outside Git. The application reads environment variables directly; it does not automatically load `.env` files. Run traces and local environments are ignored by Git.

## Compare two models across all levels

Here, a **model** is a dispatch strategy plus its settings. With `SPREAD_KEY` set as above, one command compares our fixed-price model with the official starter:

```bash
python compare.py run
```

The default suite runs **both models at levels 1–8 on the same ten seeds**: 160 ordinary practice weeks, run sequentially. It prints a Markdown leaderboard to stdout and saves `leaderboard.md`, machine-readable `results.json`, and a JSONL trace per world in a fresh `runs/comparison-<time>/` directory. Progress goes to stderr, so stdout can also be redirected to a Markdown file. This uses actual Spread practice worlds, not the scripted offline demo or official ranking rounds.

For a quick all-level comparison with one paired seed:

```bash
python compare.py run --seeds smoke-1 --output runs/smoke-comparison
```

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

To compare two fixed-price variants, copy [models/fixed.json](models/fixed.json), give the copy a different `name`, and change its euro amounts:

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

Existing output directories and report files are never overwritten. Results are checkpointed after every run. On an error or Ctrl-C, the suite stops, saves the failure and attempts to delete only its current practice world; completed worlds remain inspectable. If cleanup fails, it reports the world ID. Incomplete or mismatched pairs cannot produce a leaderboard; rerun the suite into a fresh output directory after fixing the failure.

## Checks

```bash
python -m unittest discover -s tests -v
```

The checks cover exact currency parsing, constant prices across delivery options and deadline warnings, rejected trade-in splitting, manual-licence retry handling, action rejection logging and the offline request-to-ledger flow. Comparison tests use scripted worlds to verify all-level pairing, both models' traces, qualification-first ranking, delta signs, ties, incomplete-result rejection, output preservation and failure/interrupt cleanup. They make no claims about simulator performance.

## Project icon

[The red-car SVG](assets/cheap-drive.svg) is the reusable project icon. It is a standalone vector with an accessible title and description.
