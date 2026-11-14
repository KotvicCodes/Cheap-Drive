# Gemini note extraction: offline research prototype

Investigated 14 November 2026, against Delta PR #11's prepared checkout.
Recommendation: proceed with independently labelled offline evaluation; a live
client or strategy change is **not warranted yet**. There is no model-quality,
latency, price or margin measurement in this work. Synthetic tests establish
adapter behavior only. Frozen Gamma, Delta settings and dispatch actions are
unchanged. No private notes/reveals were read for this research or sent outside
the workspace; only public documentation and the existing pinned dependency
were downloaded. No inference, credential lookup or new SDK dependency exists.

## What official sources establish

Direct read-only requests to `ai.google.dev` models, structured-output, API,
pricing, rate-limit and troubleshooting pages returned HTTP 403. The linked
Google-owned source repositories were readable. Findings below use those
sources, not remembered product claims. Recheck service documentation before
any live experiment; sample code is not an account-specific availability check.

1. The [official model-list notebook](https://github.com/google-gemini/cookbook/blob/6c416d766328d125774e21f282e59dfdf12049c9/quickstarts/Models.ipynb)
   lists `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite` and
   `gemini-2.5-flash-lite` in its saved output. The
   [current JSON notebook](https://github.com/google-gemini/cookbook/blob/6c416d766328d125774e21f282e59dfdf12049c9/quickstarts/JSON_mode.ipynb)
   includes `gemini-3.5-flash-lite` in its model selector, using Interactions.
   This makes 3.5 Flash-Lite a documented lightweight research candidate;
   it establishes no latency, production lifecycle status or project access.
   The [archived GenerateContent notebook](https://github.com/google-gemini/cookbook/blob/archive/generate-content-api/quickstarts/JSON_mode.ipynb)
   also explicitly includes `gemini-3.1-flash-lite` and schema-constrained JSON.
   Treat that as a secondary compatibility candidate, not a measured ranking.
2. The [official REST JSON notebook](https://github.com/google-gemini/cookbook/blob/6c416d766328d125774e21f282e59dfdf12049c9/quickstarts/rest/JSON_mode_REST.ipynb)
   still demonstrates `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`.
   The [API definition](https://github.com/googleapis/googleapis/blob/97f6460c3558c1435d7fd001a9251f8df058ae2f/google/ai/generativelanguage/v1beta/generative_service.proto)
   documents `application/json`, `responseSchema` and alternative
   `responseJsonSchema`. For the latter, omit `responseSchema`, specify the
   compatible MIME type, and use the supported JSON Schema subset. It lists
   objects, properties, required, additionalProperties, arrays/items, bounds,
   enums and anyOf; oneOf is interpreted as anyOf. No conditional schema or
   semantic entailment guarantee is assumed. Our generated schema uses this
   subset, with stricter local cross-field checks. Actual service acceptance
   of this exact schema has **not** been tested; overly complex schemas remain
   a compatibility risk. The
   [current SDK README](https://github.com/googleapis/python-genai/blob/a3d04bd5edc0e131267425506b025576de2d0242/README.md)
   says its v3 default changed to `v1`; `*-latest` aliases are v1beta-only.
   Explicitly record the API version rather than inheriting a changing default.
3. [Official HttpOptions/HttpRetryOptions](https://github.com/googleapis/python-genai/blob/a3d04bd5edc0e131267425506b025576de2d0242/google/genai/types.py)
   specify a request timeout in **milliseconds**. Retry attempts count the
   original call; 0/1 means no retry. An options object with unspecified
   attempts documents five attempts, whereas the
   [implementation](https://github.com/googleapis/python-genai/blob/a3d04bd5edc0e131267425506b025576de2d0242/google/genai/_api_client.py)
   uses one attempt when retry options are absent. It converts milliseconds
   to client seconds and rounds the server-timeout header up to seconds.
   Therefore neither retry defaults nor a server timeout protect a subsecond
   application deadline. Use an outer monotonic cutoff, explicitly one attempt,
   bounded network operations and cancellation/discard of late results. A
   cancelled request may still incur provider cost. No server response-time
   SLA or measured speed was found.
4. The same API definition exposes `usageMetadata` prompt, candidate, total,
   cached-content, thought and tool-use token counts plus `modelVersion` and
   candidate `finishReason`. Cached prompt tokens are already included in
   prompt tokens: never add them again. Do not add total to component counts,
   assume absent counts are zero, or bill only visible answer tokens. The
   prototype records observed counts even for blocked/truncated responses;
   missing usage remains unknown. Reconcile all attempts/timeouts with billing
   in a future shadow ledger. Token metadata alone is not a price invoice.

Current [pricing](https://ai.google.dev/gemini-api/docs/pricing),
[quota](https://ai.google.dev/gemini-api/docs/rate-limits) and
[model lifecycle](https://ai.google.dev/gemini-api/docs/models) pages were
inaccessible here. **No prices, quota numbers, regional availability or latency
claims are verified.** Those are explicit prerequisites to a later live trial.
There is no silent substitution of a similarly named Vertex AI offering.

## Contract and local use

`gemini_notes.py` contains the extraction instruction, strict machine-readable
schema, prompt builder, cache identity, provider-neutral JSON validator and
conservative merge. `scripts/benchmark_gemini_notes.py` reads local JSONL only:

```bash
# This command needs only Python's standard library and notes.py.
python3 scripts/benchmark_gemini_notes.py contract

# The benchmark also uses the repository's existing pinned spread dependency.
.venv/bin/python scripts/benchmark_gemini_notes.py benchmark \
  runs/gemini/private-development.jsonl \
  --responses runs/gemini/private-responses.jsonl \
  --model gemini-3.5-flash-lite --enable-assisted
```

Omit `--enable-assisted` to retain deterministic Delta throughout. Nothing
imports this adapter from a desk, dispatch loop or model factory. The CLI never
emits note prose, evidence, request IDs, provider strings or labels. Store all
fixtures, raw responses, timings, account metadata and reports under ignored
`runs/`; do not commit them. The examples below are formats, not real data or
an independently adjudicated corpus.

Each fixture line has exactly `id`, `note` (original string), `arrived_at`
(world-minute integer), `language` (`fi/sv/en/mixed`), `split`
(`development/holdout`), `gold` and `adjudication`. `gold` is a complete instance
of the emitted response schema, with status `extracted` and independently
adjudicated exact evidence. `adjudication` is
`{"status":"independent","reviewers":["reviewer-a","reviewer-b"],"reveal_used":false}`.
The CLI checks these declarations, not actual independence. Keep holdout files
separate; the default selected split is development.

Each cache line is `{"key":"<cache_key(text, arrival, model)>","response":{...}}`,
where `response` is a saved **REST GenerateContent** response containing one
`candidates` item, `finishReason:"STOP"`, text-only `content.parts`, and optional
`usageMetadata`/`modelVersion`. Other envelopes require an explicit normalizer;
an Interactions response cannot silently stand in for GenerateContent. Duplicate
keys are rejected. One cache row represents one attempt, not a complete billing
ledger. Prompts, schema and configured model are included in the SHA-256 key
alongside original text and arrival; cache hits are local, not Google context
caching. Preserve returned modelVersion privately; the public aggregate only
counts its presence. Unknown/version-drifted caches need invalidation, not
indefinite reuse based on an alias.

Unknown fields, duplicate JSON keys, non-finite numbers, Boolean timestamps,
invalid weekday lists, fabricated/missing spans, missing anchors, contradictory
daily windows, truncation, blocks and tools are rejected. All nondefault facts
need exact Unicode code-point spans. Absolute dates also need an arrival-day
offset and minute-of-day whose arithmetic matches the value. The 14-day
extraction horizon, 8,192-character input and 64-KiB output bounds are proposed
prototype limits, not provider or challenge guarantees. Dates/units are
structurally checked; recognizing whether a date phrase supports an offset
still requires semantic adjudication.

Negation, corrections, payment release, recurring hours, absolute promises and
pickup/delivery roles are explicit prompt requirements. `unsupported` retains
exact summer-tyre, negated, ambiguous and out-of-contract spans; these never
become an actionable tyre capability through `NoteFacts`. Unsupported recall
matches category plus exact gold span, so differing span boundaries require
adjudication rather than being treated as proof of missed meaning.

Merging preserves omitted deterministic fields and refuses supplied lower
readiness, later closing/deadlines or broader weekday sets. Flags and explicit
delivery-day protection cannot be cleared. This prevents loosening extracted
constraints; it cannot certify new restrictions or correct deterministic false
positives. For example, Gamma can flag a negated mention of manual gearboxes;
the conservative adapter intentionally retains that flag. Tightening can also
incorrectly reject profitable work. Exact evidence is not entailment, and model
confidence is not correctness. Tests deliberately show a perfectly quoted
delivery clause mislabelled as pickup passing structural validation and then
failing semantic scoring. This adapter is insufficient as a live safety proof.

## Proposed research sequence and gates

All numbers in this section are **proposals**, not observations or approved
production budgets. Freeze selection rules and numeric gates before each stage.

1. **Offline meaning first.** Compare frozen `notes.parse_note`, existing
   `delta.parse_delta_note`, and selective cached extraction over Delta. The
   frozen parser is Gamma's note arm, not a replay of Gamma's entire strategy.
   Select eligible notes by a development-only rule (documented vocabulary
   gaps/ambiguous scope); missing/ineligible caches fall back to Delta. The
   prototype does not choose which notes may be sent to a provider. No requests
   are sent by it. A future inference collection needs its own data scope.
   Use a proposed minimum 300 independently labelled notes, balanced over FI,
   SV, EN, ordinary notes, negation, typos, relative days, payment, both roles,
   private slots, plates/manual and tyres. Labels come from two human reviewers blind
   to model outputs and parser predictions, with disagreements resolved before
   scoring. Split by semantic template/request family, not random paraphrases.
   Do not select only won orders or failed visits. Reveals cover won work only:
   use them, if at all, in a separate post-label diagnostic audit; never as
   independent gold, model input, selector feature or holdout tuning feedback.
   Lock a separate holdout before prompts/selection are tuned.
   Report exact field-value coverage/precision, exact-note accuracy, omitted or
   loosened gold constraints, wrong restrictions, unsupported-fact recall and
   fallback reasons by language/category. The CLI emits aggregate three-arm
   counts and raw-candidate diagnostics; stratification requires separate
   predeclared fixture files. Candidate diagnostics include structurally valid
   extractions rejected by the conservative merge. Proposed advance gate:
   at least +10 percentage points coverage on the frozen eligible holdout,
   no loss of exact-note accuracy overall or in a language stratum, and zero
   new safety-critical role, negation, date, explicit-window or capability errors.
   Zero observed errors is not zero risk; report sample size and uncertainty.
2. **Shadow latency/cost second.** Only after the offline gate, add an isolated
   nonblocking transport and reverify model access, schema support, lifecycle,
   project quota, data handling and current pricing. Keep all actions on Delta.
   Measure receipt-to-validated-result p50/p95/p99 and worst tails, rate-limit
   and timeout frequency, burst behavior, cache-hit rates, late-result discard,
   total requests/tokens and externally billed currency. Include cold starts,
   failures and all retry attempts; a cache replay is not a latency experiment.
   Freeze the model identifier, API version, prompt/schema hashes, generation
   settings and observed modelVersion. Repeat a fixed private sample to assess
   nondeterminism even with low temperature; version drift forces requalification.
3. **Paired practice last, if justified.** Freeze both implementations and the
   eligible-note rule; use isolated shared screening seeds with fixed cached
   outputs to separate semantic effects from provider randomness. Inspect
   every week's qualification (at least one won order, at least 90% on time),
   paired margin, worst on-time rate, failed visits and missed quotes. Proposed
   screen gate: all weeks qualify, no new deadline/visit safety regression,
   and positive paired mean in-game margin; select nothing from a fresh
   confirmation block. In-game gross margin and external API expenditure are
   separate ledgers; report both and their economic combination explicitly.
   These proposed positive-mean/qualification checks are diagnostic only. Any
   Delta promotion must still meet the unchanged main plan gates, including
   worst on time ≥93%, mean gain ≥€500/week, ≥6/8 positive weeks, long lateness
   ≤5%, service comparison and undelivered-share limits. No weaker Gemini-only
   promotion gate is introduced. Neither an offline score nor a practice replay
   establishes final-clock safety.

## Proposed final-clock envelope, not implemented here

Normal daytime quotes have only **4.5 wall seconds total**. No blocking provider
call belongs in dispatch, quoting or recovery. A proposed async worker may
start on price-request receipt, while deterministic planning proceeds. Admit at
most two in-flight calls, no waiting queue, one attempt each; overflow immediately
falls back. A proposed extraction cutoff is the earlier of receipt +800 ms
and conservatively projected `respondBy` minus 1,500 ms. Reserve 50 ms inside
that cutoff for decoding/validation. These are unmeasured starting budgets;
the true clock mapping, scheduler/transport jitter and burst measurements must
justify them. Old/replayed events or uncertain final-clock projection immediately
fall back. The caller never waits for a result: use only a complete validated
result available before planning seals its action and strictly before the
cutoff; later completion cannot amend an already committed quote.

Cancel expired work, discard partial/late/stale text, and invalidate on note or
arrival changes. Bound local cache size/TTL, worker memory and input/output
tokens; do not assume SHA keys anonymize short notes. Proposed shadow caps are
100 attempts/session and 250,000 conservatively reserved total tokens, plus an
operator-configured currency ceiling based on verified current pricing. Reserve
worst-case input/schema plus capped output/thought usage before launch; release
only after accounting is reconciled. Missing usage consumes the reservation.
Do not add retries inside the quote budget. HTTP timeouts, safety blocks,
schema failures, quota exhaustion, changed versions and any budget/cutoff miss
use deterministic fallback. These guards and live transport are deliberately
unimplemented until offline evidence warrants them.
