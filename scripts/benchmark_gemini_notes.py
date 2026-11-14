"""Offline three-arm note benchmark. Inputs stay local; stdout is aggregate JSON.

Private fixtures and response caches belong under ignored runs/. No network,
credential lookup, raw-note output, or dispatch integration exists here.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.gemini_notes import (
    CALENDARS, FACT_NAMES, LOWER, PROMPT, UPPER,
    InvalidExtraction, cache_key, gemini_response_text,
    response_schema, select_cached, strict_json, validate_response,
)
from models.notes import parse_note


TOKEN_FIELDS = ('promptTokenCount', 'candidatesTokenCount', 'totalTokenCount',
                'cachedContentTokenCount', 'thoughtsTokenCount', 'toolUsePromptTokenCount')


def read_rows(path):
    with path.open(encoding='utf-8') as source:
        for line in source:
            if line.strip():
                row = strict_json(line)
                if type(row) is not dict:
                    raise InvalidExtraction('invalid_record')
                yield row


def _active(value):
    return value is not None and value is not False


def _loosened(name, predicted, gold):
    if not _active(gold):
        return False
    if not _active(predicted):
        return True
    if name in LOWER:
        return predicted < gold
    if name in UPPER:
        return predicted > gold
    if name in CALENDARS:
        return not set(predicted) <= set(gold)
    return False


def score_facts(counts, predicted, gold):
    counts['notes'] += 1
    counts['exact_notes'] += predicted == gold
    for name in FACT_NAMES:
        value, expected = getattr(predicted, name), getattr(gold, name)
        counts['gold_facts'] += _active(expected)
        counts['predicted_facts'] += _active(value)
        counts['correct_facts'] += _active(value) and value == expected
        counts['wrong_constraints'] += _active(value) and value != expected
        counts['loosened_fields'] += _loosened(name, value, expected)


def unsupported_set(items):
    return {(item['kind'], item['span']['start'], item['span']['end']) for item in items}


def validate_fixture(row):
    if not {'id', 'note', 'arrived_at', 'language', 'split', 'gold', 'adjudication'} == set(row):
        raise InvalidExtraction('invalid_fixture_keys')
    if type(row['id']) is not str or not row['id'] or row['language'] not in ('fi', 'sv', 'en', 'mixed'):
        raise InvalidExtraction('invalid_fixture_identity')
    if row['split'] not in ('development', 'holdout'):
        raise InvalidExtraction('invalid_split')
    # This checks declarations only; the research protocol must establish independence.
    judges = row['adjudication']
    if type(judges) is not dict or set(judges) != {'status', 'reviewers', 'reveal_used'}:
        raise InvalidExtraction('missing_adjudication')
    reviewers = judges['reviewers']
    if (judges['status'] != 'independent' or judges['reveal_used'] is not False
            or type(reviewers) is not list or len(reviewers) < 2
            or any(type(person) is not str or not person.strip() for person in reviewers)
            or len(set(reviewers)) != len(reviewers)):
        raise InvalidExtraction('gold_not_independent')
    # Gold uses the same strict contract/evidence/units, but is never a model input.
    gold = validate_response(json.dumps(row['gold']), row['note'], row['arrived_at'])
    if gold.abstained:
        raise InvalidExtraction('unadjudicated_gold')
    return gold


def benchmark(fixtures, caches, model, *, enabled=False, split='development'):
    # Lazy import: printing the contract and validating responses need only stdlib.
    from models.delta import parse_delta_note

    cache = {}
    for row in caches:
        if not {'key', 'response'} <= set(row) or type(row['key']) is not str:
            raise InvalidExtraction('invalid_cache_record')
        if row['key'] in cache:
            raise InvalidExtraction('duplicate_cache_key')
        cache[row['key']] = row['response']
    arms = {name: Counter() for name in ('frozen_gamma', 'deterministic_delta', 'selective_assisted')}
    reasons, versions, tokens, token_observations = Counter(), Counter(), Counter(), Counter()
    candidate_scores = Counter()
    selected, seen, usage_requests = 0, set(), 0
    missing, used_cache_keys = object(), set()
    languages = Counter()
    for row in fixtures:
        if row.get('split') not in ('development', 'holdout'):
            raise InvalidExtraction('invalid_split')
        if row['split'] != split:
            continue
        gold = validate_fixture(row)
        if row['id'] in seen:
            raise InvalidExtraction('duplicate_fixture_id')
        seen.add(row['id'])
        selected += 1
        languages[row['language']] += 1
        note, arrived = row['note'], row['arrived_at']
        gamma, delta = parse_note(note, arrived), parse_delta_note(note, arrived)
        key = cache_key(note, arrived, model)
        payload = cache.get(key, missing)
        text, provider_reason = None, None
        if enabled and payload is not missing:
            try:
                text = gemini_response_text(payload)
            except InvalidExtraction as error:
                provider_reason = str(error)
        if enabled and payload is not missing and key not in used_cache_keys:
            used_cache_keys.add(key)
            # Includes cached responses rejected for safety or truncation.
            usage = payload.get('usageMetadata') if type(payload) is dict else None
            if type(usage) is dict:
                usage_requests += 1
                for name in TOKEN_FIELDS:
                    value = usage.get(name)
                    if type(value) is int and value >= 0:
                        tokens[name] += value
                        token_observations[name] += 1
            version = payload.get('modelVersion') if type(payload) is dict else None
            if type(version) is str and version:
                # Report counts only: untrusted provider strings must not echo private content.
                versions['reported'] += 1
            else:
                versions['missing'] += 1
        choice = select_cached(note, arrived, delta, text, enabled=enabled)
        reasons[provider_reason or choice.reason] += 1
        gold_unsupported = unsupported_set(gold.unsupported)
        extracted = choice.extraction
        if extracted and not extracted.abstained:
            score_facts(candidate_scores, extracted.facts, gold.facts)
        proposed_unsupported = unsupported_set(extracted.unsupported) if extracted else set()
        for name, facts in (('frozen_gamma', gamma), ('deterministic_delta', delta), ('selective_assisted', choice.facts)):
            counts = arms[name]
            score_facts(counts, facts, gold.facts)
            predicted = proposed_unsupported if name == 'selective_assisted' else set()
            counts['unsupported_gold'] += len(gold_unsupported)
            counts['unsupported_found'] += len(predicted & gold_unsupported)
            counts['unsupported_wrong'] += len(predicted - gold_unsupported)
    if not selected:
        raise InvalidExtraction('empty_selected_split')
    # Coverage is exact field-value recall; incorrect extracted fields do not count.
    for counts in arms.values():
        counts['coverage'] = counts['correct_facts'] / counts['gold_facts'] if counts['gold_facts'] else None
        counts['precision'] = counts['correct_facts'] / counts['predicted_facts'] if counts['predicted_facts'] else None
        counts['exact_rate'] = counts['exact_notes'] / counts['notes']
    return dict(
        split=split, notes=selected, languages=dict(languages), assisted_enabled=enabled,
        arms={name: dict(counts) for name, counts in arms.items()}, selection_reasons=dict(reasons),
        cached_usage=dict(unique_attempts=len(used_cache_keys), requests_with_usage=usage_requests,
                          requests_without_usage=len(used_cache_keys) - usage_requests, observed_tokens=dict(tokens),
                          observations_per_field=dict(token_observations), model_version_presence=dict(versions)),
        candidate_diagnostics=dict(candidate_scores),
        caveats=['Labels declared independent; CLI cannot establish reviewer independence.',
                 'Cached usage only; missing usage is unknown, not zero cost.',
                 'No latency, prices, causal dispatch impact or qualification measured.'],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('contract', help='Print the public prompt and machine-readable response schema')
    run = commands.add_parser('benchmark', help='Compare private adjudicated JSONL fixtures with cached REST responses')
    run.add_argument('fixtures', type=Path)
    run.add_argument('--responses', type=Path)
    run.add_argument('--model', required=True, help='Exact configured model identifier used in cache identity')
    run.add_argument('--split', choices=('development', 'holdout'), default='development')
    run.add_argument('--enable-assisted', action='store_true', help='Default off; use cache only, never an API')
    args = parser.parse_args(argv)
    if args.command == 'contract':
        print(json.dumps(dict(system_instruction=PROMPT, response_json_schema=response_schema()), indent=2))
        return 0
    try:
        result = benchmark(read_rows(args.fixtures), read_rows(args.responses) if args.responses else [],
                           args.model, enabled=args.enable_assisted, split=args.split)
    except (InvalidExtraction, OSError, UnicodeError):
        # No tracebacks, paths, provider output or prose from private input files.
        print('Invalid or unreadable private benchmark input; no report emitted.', file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
