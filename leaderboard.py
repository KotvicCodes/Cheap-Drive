"""Pure Markdown reporting for complete, paired practice comparisons."""
from __future__ import annotations

from collections import Counter
import json
import math
from statistics import mean


def cell(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(
        ">", "&gt;").replace("|", "&#124;").replace("\r", " ").replace("\n", " ")


def euros(cents, signed=False):
    return f"€{cents / 100:+,.2f}" if signed else f"€{cents / 100:,.2f}"


def table(headers, rows):
    return ["| " + " | ".join(map(cell, headers)) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *("| " + " | ".join(map(cell, row)) + " |" for row in rows), ""]


def validate(results):
    if results.get("schema_version") != 1 or results.get("mode") != "practice" or results.get("status") != "complete":
        raise ValueError("leaderboards require a complete schema-version-1 practice comparison")
    models, levels, seeds = (results[key] for key in ("models", "levels", "seeds"))
    if len(models) != 2 or models[0]["name"] == models[1]["name"]:
        raise ValueError("results must describe two distinctly named models")
    if (not levels or not seeds or len(set(levels)) != len(levels) or len(set(seeds)) != len(seeds)
            or any(level not in range(1, 9) for level in levels)):
        raise ValueError("results must contain distinct levels (1–8) and seeds")
    expected = {(model, level, seed) for model in (0, 1) for level in levels for seed in seeds}
    actual = set()
    for run in results["runs"]:
        key = (run["model"], run["level"], run["seed"])
        if run["status"] != "complete" or key in actual or key not in expected:
            raise ValueError("results contain failed, duplicate or unexpected runs")
        actual.add(key)
        score = run["score"]
        for field in ("marginCents", "revenueCents", "wonOrders", "onTimeShare", "undeliveredShare"):
            value = score[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"invalid score field: {field}")
        if (not isinstance(score["ranked"], bool) or score["wonOrders"] < 0
                or any(not 0 <= score[field] <= 1 for field in ("onTimeShare", "undeliveredShare"))):
            raise ValueError("invalid qualification or delivery score")
    if actual != expected:
        raise ValueError("incomplete pairing: each model needs every level/seed combination")


def average(runs, field):
    return mean(run["score"][field] for run in runs)


def qualified(runs):
    return sum(run["score"]["ranked"] for run in runs)


def winner(groups):
    """More qualified weeks first, then mean gross margin across all weeks."""
    if not any(qualified(group) for group in groups):
        return None
    keys = [(qualified(group), average(group, "marginCents")) for group in groups]
    return None if keys[0] == keys[1] else int(keys[1] > keys[0])


def render_markdown(results):
    validate(results)
    names = [model["name"] for model in results["models"]]
    levels, seeds, runs = results["levels"], results["seeds"], results["runs"]
    groups = [[run for run in runs if run["model"] == model] for model in (0, 1)]
    by_level = {level: [[run for run in group if run["level"] == level] for group in groups] for level in levels}
    label = lambda index: cell(names[index])
    scope = "All levels (1–8)" if set(levels) == set(range(1, 9)) else "Selected levels: " + ", ".join(map(str, levels))
    lines = ["# Model comparison leaderboard", "", f"{scope}; {len(seeds)} paired seed(s) per level; {len(runs)} practice runs.",
             "", "Local comparison of ordinary practice worlds; this is not the official Spread leaderboard.", "",
             "Ranking rule: more qualified weeks wins; if equal, higher mean gross margin across **all** weeks wins. "
             "If neither model qualifies any week, neither is recommended. Exact ties remain ties. "
             "Qualification uses the simulator's `ranked` flag, not an average delivery rate.", "",
             "All averages below are per week, including unqualified weeks. Delivery shares are mean weekly shares, "
             "not pooled order rates. These are descriptive results on the selected seeds, not statistical proof.", "",
             "## Overall leaderboard", ""]
    best = winner(groups)
    order = [best, 1 - best] if best is not None else [0, 1]
    rows = []
    for index in order:
        group = groups[index]
        rank = "—" if not any(qualified(g) for g in groups) else 1 if best is None else order.index(index) + 1
        rows.append([rank, names[index], f"{qualified(group)}/{len(group)}",
                     euros(average(group, "marginCents")), euros(average(group, "revenueCents")),
                     f"{average(group, 'onTimeShare'):.1%}", f"{average(group, 'undeliveredShare'):.1%}",
                     f"{average(group, 'wonOrders'):.1f}"])
    lines += table(["Rank", "Model", "Qualified weeks", "Mean margin", "Mean revenue", "Mean on-time", "Mean undelivered", "Mean won orders"], rows)
    if not any(qualified(group) for group in groups):
        lines += ["Neither model qualified any week. Margin alone does not establish a usable winner.", ""]
    elif best is None:
        lines += ["Overall result: tie under the stated ranking rule.", ""]
    else:
        lines += [f"Overall leader on these weeks: **{label(best)}**.", ""]

    lines += ["## Leaderboard by level", ""]
    rows = []
    for level in levels:
        pair = by_level[level]
        lead = winner(pair)
        for index, group in enumerate(pair):
            rank = "—" if not any(qualified(g) for g in pair) else 1 if lead is None or lead == index else 2
            rows.append([level, rank, names[index], f"{qualified(group)}/{len(group)}",
                         euros(average(group, "marginCents")), f"{average(group, 'onTimeShare'):.1%}",
                         f"{average(group, 'undeliveredShare'):.1%}", f"{average(group, 'wonOrders'):.1f}"])
    lines += table(["Level", "Rank", "Model", "Qualified weeks", "Mean margin", "Mean on-time", "Mean undelivered", "Mean won orders"], rows)

    lines += ["## Paired differences", "", f"All deltas are **B − A**: A = {label(0)}; B = {label(1)}. "
              "Positive margin/on-time is better; positive undelivered is worse. Shares use percentage points (pp).", "",
              "A paired win means only that model qualifies, or both qualify and it earns more margin. "
              "Weeks where neither qualifies are counted separately.", ""]
    rows = []
    for level in levels:
        pair = by_level[level]
        scores = [{run["seed"]: run["score"] for run in group} for group in pair]
        counts = Counter()
        for seed in seeds:
            a, b = (score[seed] for score in scores)
            if not a["ranked"] and not b["ranked"]:
                counts["neither"] += 1
            elif a["ranked"] != b["ranked"]:
                counts["b" if b["ranked"] else "a"] += 1
            else:
                counts["b" if b["marginCents"] > a["marginCents"] else "a" if a["marginCents"] > b["marginCents"] else "tie"] += 1
        delta = lambda field: average(pair[1], field) - average(pair[0], field)
        rows.append([level, euros(delta("marginCents"), True), euros(delta("revenueCents"), True),
                     f"{100 * delta('onTimeShare'):+.1f}", f"{100 * delta('undeliveredShare'):+.1f}",
                     f"{counts['a']} / {counts['b']} / {counts['tie']} / {counts['neither']}"])
    lines += table(["Level", "Δ mean margin", "Δ mean revenue", "Δ on-time pp", "Δ undelivered pp", "A wins / B wins / ties / neither"], rows)

    lines += ["## Diagnostics", "", "Event counts include retries and individual legs; they are not counts of unique failed orders. "
              "Signed ledger amounts are totals across all sampled weeks (negative = net expense).", ""]
    counters = []
    for group in groups:
        summary = {key: Counter() for key in ("events", "rejections", "visit_failures", "ledger")}
        for run in group:
            for key in summary:
                summary[key].update(run["diagnostics"][key])
        counters.append(summary)
    rows = [[event, *[summary["events"][event] for summary in counters]] for event in (
        "order_lost", "deadline_close", "gig_dropped", "no_show", "visit_failed", "gig_expired")]
    rows.append(["rejected actions", *[sum(summary["rejections"].values()) for summary in counters]])
    lines += table(["Event/action", *names], rows)
    for key, heading, currency in (("ledger", "Ledger category", True), ("visit_failures", "Failed-visit reason", False),
                                   ("rejections", "Rejected-action reason", False)):
        keys = sorted(set(counters[0][key]) | set(counters[1][key]))
        if keys:
            lines += table([heading, *names], [[reason, *[euros(c[key][reason]) if currency else c[key][reason]
                                                          for c in counters]] for reason in keys])

    lines += ["## Where to iterate next", ""]
    if 8 in by_level:
        lead = winner(by_level[8])
        if not any(qualified(group) for group in by_level[8]):
            lines.append("- Neither model qualifies at level 8. Prioritize capacity selection and delivery reliability before tuning margin.")
        elif lead is None:
            lines.append("- Level 8 is tied. Use additional held-out seeds to choose the final-level strategy.")
        else:
            lines.append(f"- Use **{label(lead)}** as the level 8 candidate under the stated rule; confirm on held-out weeks before adopting it.")
    else:
        lines.append("- Include level 8 before selecting a strategy for the final.")
    for index, group in enumerate(groups):
        weak = [str(level) for level in levels if qualified(by_level[level][index]) < len(seeds)]
        if weak:
            lines.append(f"- **{label(index)}** misses qualification at level(s) {', '.join(weak)}. Inspect those traces for late/undelivered work and order-selection limits.")
        for key, action in (("rejections", "Fix the rejected action"), ("visit_failures", "Investigate pickup constraints")):
            if counters[index][key]:
                reason, count = counters[index][key].most_common(1)[0]
                lines.append(f"- **{label(index)}**: {action}: {cell(reason)} ({count} occurrences).")
        expenses = [(amount, kind) for kind, amount in counters[index]["ledger"].items() if amount < 0]
        if expenses:
            amount, kind = min(expenses)
            lines.append(f"- **{label(index)}**: inspect {cell(kind)}, the largest observed net expense ({euros(amount)} total). Test one cost-control change while protecting qualification.")
    deltas = [(average(pair[1], "marginCents") - average(pair[0], "marginCents"), level) for level, pair in by_level.items()]
    delta, level = max(deltas, key=lambda item: abs(item[0]))
    if delta:
        pair = by_level[level]
        revenue_delta = average(pair[1], "revenueCents") - average(pair[0], "revenueCents")
        lines.append(f"- The largest mean margin gap is at level {level}: B − A = {euros(delta, True)}, "
                     f"with revenue {euros(revenue_delta, True)} and net costs {euros(revenue_delta - delta, True)}. "
                     "Use paired traces to test whether quoting, order volume or fulfillment costs explain the gap.")
    else:
        lines.append("- No mean margin gap was observed. Check per-seed outcomes and expand seed coverage before concluding the strategies are equivalent.")
    lines += ["- Change one policy at a time, rerun the same seeds, then validate on a separate 10–20-seed set. Averages can hide individual weeks that fail qualification.", "",
              "## Reproduction", "", f"Created: {cell(results['created_at'])}. Commit: {cell(results['code']['commit'])}; "
              f"working tree dirty: {results['code']['dirty']}.", "", "Seeds: " + ", ".join(cell(seed) for seed in seeds) + ".", "",
              "Model configurations (trusted local factories):", "", "```json",
              json.dumps(results["models"], ensure_ascii=False, indent=2).replace("`", "\\u0060"), "```", "",
              "`results.json` contains every final score, world ID, diagnostic summary and trace filename. "
              "Trace paths are relative to the results directory. Failed/incomplete suites cannot produce a leaderboard.", ""]
    return "\n".join(lines)
