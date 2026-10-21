"""Frozen parser and selection/calculation controls for development only."""
from __future__ import annotations
import copy
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from .benchmark import parse_payload, _matches_definition, _verdict
from .evaluation import parse_prediction, _unique_object, _reject_constant
from .models import MODEL_KEYS, _manifest_entry, _verify_files, _save_json

PARENT_SHA256 = '81658b921794ff7d46dee07e1ef71e823605c2b2ef9c6927dc9dd7e6bf6bec66'
FENCE = re.compile(r'\A\s*```(?:json)?[ \t]*\r?\n(.*?)\r?\n```\s*\Z', re.DOTALL)


def unwrap(text):
    if not isinstance(text, str):
        raise ValueError('Output must be text')
    found = FENCE.fullmatch(text)
    return (found.group(1), True) if found else (text, False)


def parse_response(text, *, selector=False, allow_fence=True):
    """Accept bare JSON or one entire-output fence. Never repair content."""
    if allow_fence:
        text, _ = unwrap(text)
    if selector:
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        if not isinstance(value, dict) or set(value) != {'evidence_ids'}:
            raise ValueError('Selector must contain exactly evidence_ids')
        ids = parse_prediction(json.dumps(dict(verdict='SUPPORTED', evidence_ids=value['evidence_ids'])))['evidence_ids']
        if len(ids) > 1:
            raise ValueError('Selector must choose zero or one measurement')
        return {'evidence_ids': ids}
    value = parse_prediction(text)
    wanted = 0 if value['verdict'] == 'INSUFFICIENT_EVIDENCE' else 1
    if len(value['evidence_ids']) != wanted:
        raise ValueError('Verdict and minimal-citation contract disagree')
    return value


def selected_calculation(payload, ids, *, validate_scope):
    """Calculate only the selected record; never search for a better selection."""
    parsed = parse_payload(payload)
    if not ids:
        return {'verdict': 'INSUFFICIENT_EVIDENCE', 'evidence_ids': []}, 'no_selection'
    if len(ids) != 1:
        raise ValueError('Need at most one selected ID')
    choices = [r for r in parsed['measurements'] if r['evidence_id'] == ids[0]]
    if len(choices) != 1:
        raise ValueError('Selected identifier is not a unique visible measurement')
    row = choices[0]
    if validate_scope and (row['pair_id'] != parsed['pair_id'] or not
            _matches_definition(row, parsed['metric_id'], parsed['atom_sets'])):
        return {'verdict': 'INSUFFICIENT_EVIDENCE', 'evidence_ids': []}, 'scope_rejected'
    return {'verdict': _verdict(row['value'], row['unit'], parsed['threshold_A'], parsed['operator']),
            'evidence_ids': [row['evidence_id']]}, 'calculated'


def derive_predictions(public, predictions):
    """Make scored copies while keeping the raw output files unchanged."""
    cases = {r['case_id']: r for r in public}
    results = []
    diagnostics = defaultdict(Counter)
    for raw in predictions:
        if raw['case_id'] not in cases:
            raise ValueError('Unknown case in derived predictions')
        condition = raw['condition']
        if condition == 'baseline':
            results.append(copy.deepcopy(raw))
            continue
        if condition not in {'direct', 'scope_checklist', 'select_evidence'}:
            raise ValueError('Unknown refinement condition')
        selector = condition == 'select_evidence'
        counts = diagnostics[raw['model_key'] + '/' + condition]
        counts['expected'] += 1
        parsed = None
        if raw.get('status') == 'ok':
            counts['generation_ok'] += 1
            try:
                parse_response(raw['raw_output'], selector=selector, allow_fence=False)
                counts['bare_json_contract_valid'] += 1
            except (ValueError, TypeError, KeyError):
                pass
            try:
                parsed = parse_response(raw['raw_output'], selector=selector)
                counts['normalized_contract_valid'] += 1
                counts['enclosing_fence_removed'] += unwrap(raw['raw_output'])[1]
            except (ValueError, TypeError, KeyError):
                counts['invalid_contract'] += 1
        else:
            counts['execution_missing_or_failed'] += 1
        derived_conditions = ('selector_arithmetic', 'selector_guard') if selector else (condition,)
        for derived_condition in derived_conditions:
            row = {k: copy.deepcopy(v) for k,v in raw.items() if k != 'raw_output'}
            row['condition'] = derived_condition
            row['processing_policy'] = 'phase2_refinement_v1: entire-output fence only, exact schema and minimal citations'
            row['source_condition'] = condition
            if parsed is None:
                row.update(status='invalid_contract' if raw.get('status') == 'ok' else raw.get('status','missing'),
                           raw_output='', tool_action='not_calculated')
            else:
                try:
                    if selector:
                        value, action = selected_calculation(cases[row['case_id']]['model_payload'], parsed['evidence_ids'],
                                                            validate_scope=derived_condition == 'selector_guard')
                        counts[derived_condition + '/' + action] += 1
                    else:
                        value, action = parsed, 'direct_answer'
                    row.update(status='ok', raw_output=json.dumps(value), tool_action=action)
                    row['selected_evidence_ids'] = parsed['evidence_ids']
                except (ValueError, TypeError, KeyError) as exc:
                    row.update(status='invalid_selection', raw_output='', tool_action='invalid_identifier', error=str(exc))
                    counts[derived_condition + '/invalid_identifier'] += 1
            results.append(row)
    return results, {k:dict(v) for k,v in sorted(diagnostics.items())}


def reuse_models(parent_zip, out_dir):
    """Reuse exact successful checkpoints, without accessing the network."""
    parent_zip = Path(parent_zip)
    if hashlib.sha256(parent_zip.read_bytes()).hexdigest() != PARENT_SHA256:
        raise ValueError('Reviewed Phase 2 parent ZIP differs')
    with zipfile.ZipFile(parent_zip) as z:
        names = [n for n in z.namelist() if n.endswith('/model_manifest.json')]
        if len(names) != 1:
            raise ValueError('Expected exactly one parent model manifest')
        manifest = json.loads(z.read(names[0]))
    if manifest.get('schema_version') != 1 or set(manifest.get('models',{})) != set(MODEL_KEYS):
        raise ValueError('Parent model manifest does not match the reviewed model set')
    for key in MODEL_KEYS:
        _manifest_entry(manifest['models'][key], key)
        _verify_files(manifest['models'][key])
    _save_json(Path(out_dir)/'model_manifest.json', manifest)
    return manifest
