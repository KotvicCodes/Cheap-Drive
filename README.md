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

Python 3.9 or later is supported by the official kit. Create a virtual environment and install the pinned client:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

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

## Checks

```bash
python -m unittest discover -s tests -v
```

The checks cover exact currency parsing, constant prices across delivery options and deadline warnings, rejected trade-in splitting, manual-licence retry handling, action rejection logging and the offline request-to-ledger flow.

## Project icon

[The red-car SVG](assets/cheap-drive.svg) is the reusable project icon. It is a standalone vector with an accessible title and description.
