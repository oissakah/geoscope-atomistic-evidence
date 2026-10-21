#!/usr/bin/env python3
"""Verify the original final ZIP and reproduce every frozen score, CPU only."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'lib'))
from finalstudy.evaluation import evaluate, write_reports

EXPECTED_SHA256 = '20e6b415c0ab6b3d239138664301d5da1567c052d6770afa63e4c023a89c8b26'


def load_verified(path):
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError('Input differs from the reviewed first-attempt final archive')
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or sum(i.file_size for i in z.infolist()) > 128 * 1024**2:
            raise ValueError('Duplicate or oversized archive')
        for info in z.infolist():
            p = PurePosixPath(info.filename)
            if (p.is_absolute() or '..' in p.parts or '\\' in info.filename or ':' in info.filename
                    or info.is_dir() or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError('Unsafe archive member')
        manifests = [n for n in names if n.endswith('/SHA256SUMS.json')]
        if len(manifests) != 1:
            raise ValueError('Expected one manifest')
        prefix = manifests[0].removesuffix('SHA256SUMS.json')
        hashes = json.loads(z.read(manifests[0]))
        if set(names) != {prefix + n for n in hashes} | {manifests[0]}:
            raise ValueError('Missing or untracked member')
        for name, expected in hashes.items():
            if hashlib.sha256(z.read(prefix + name)).hexdigest() != expected:
                raise ValueError('Checksum mismatch: ' + name)
        # Only explicitly named JSON data are read; no archived code is imported.
        data = {name: json.loads(z.read(prefix + name)) for name in
                ('summary.json', 'evaluation.json', 'run_config.json', 'benchmark_audit.json')}
        for name in ('cases_public.jsonl', 'cases_gold_DO_NOT_SEND_TO_MODELS.jsonl',
                     'predictions_qwen.jsonl', 'predictions_phi.jsonl', 'predictions_smol.jsonl'):
            data[name] = [json.loads(line) for line in z.read(prefix + name).splitlines()]
    return data, len(hashes)


def write_csv(path, records):
    keys = list(dict.fromkeys(k for row in records for k in row))
    with path.open('w', newline='', encoding='utf8') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(records)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=ROOT / 'evidence/final_results_original.zip')
    parser.add_argument('--output-folder', type=Path, default=ROOT / 'recomputed')
    args = parser.parse_args(argv)
    data, verified = load_verified(args.evidence)
    public = data['cases_public.jsonl']
    gold = data['cases_gold_DO_NOT_SEND_TO_MODELS.jsonl']
    predictions = sum((data[f'predictions_{key}.jsonl'] for key in ('qwen', 'phi', 'smol')), [])
    counts = Counter((r['model_key'], r['condition'], r['case_id']) for r in predictions)
    expected = {(key, condition, c['case_id']) for key in ('qwen', 'phi', 'smol')
                for condition in ('direct', 'select_evidence') for c in public}
    if set(counts) != expected or any(n != 1 for n in counts.values()):
        raise ValueError('Expected all 10560 unique first-attempt requests')
    config = data['run_config.json']
    result = evaluate(public, gold, predictions, seed=config['seed'],
                      bootstrap_samples=config['bootstrap_samples'])
    if result != data['evaluation.json']:
        raise ValueError('Recomputed evaluation differs from the frozen result')
    out = args.output_folder
    out.mkdir(parents=True, exist_ok=True)
    write_reports(result, out)
    primary = [r for r in result['paired_comparisons'] if r['control'] == 'run_only']
    compact = [{k: v for k, v in s.items() if k != 'breakdowns'} for s in result['summaries']]
    report = dict(review_date='2026-10-21', original_archive_sha256=EXPECTED_SHA256,
                  verified_files=verified, all_scores_exactly_reproduced=True,
                  case_variants=len(public), source_groups=result['source_groups'],
                  original_selected_source_groups=60,
                  expected_requests=len(expected), recorded_requests=len(predictions),
                  truncated_responses=sum(bool(r.get('truncated')) for r in predictions),
                  missing_requests=0, duplicate_requests=0,
                  original_automated_status=data['summary.json']['status'],
                  reviewed_completion='ALL_FROZEN_FIRST_ATTEMPTS_RECORDED_AND_REVIEWED',
                  retry_required=False, original_summary_modified=False,
                  scientific_scope='Controlled same-domain evidence/operation selection and selective verification; no new reasoning-algorithm or chemical-accuracy claim',
                  labels=dict(Counter(r['expected'] for r in gold)),
                  summaries=compact, primary_comparisons=primary)
    (out / 'reviewed_summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    for field in ('presentation', 'family'):
        rows = []
        for s in result['summaries']:
            for name, values in s['breakdowns'][field].items():
                rows.append(dict(model_key=s['model_key'], method=s['method'], **{field: name},
                                 **{k: v for k, v in values.items() if not isinstance(v, (dict, list))}))
        write_csv(out / f'{field}_scores.csv', rows)
    print(json.dumps({k: v for k, v in report.items() if k not in ('summaries', 'primary_comparisons')}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
