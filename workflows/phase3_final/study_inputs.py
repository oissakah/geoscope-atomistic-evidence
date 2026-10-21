"""Read pinned source data without extracting or executing archived programs."""
from __future__ import annotations
import hashlib
import json
import stat
import zipfile
from pathlib import Path,PurePosixPath

SOURCE_SHA256='5e9d6067e2855255a52f03bb8ae94509a79ae7af03ae4b43a93114ed5ec34bf7'
DEVELOPMENT_SHA256='8e8e77cc36b6f1dde2ab282bfb4f79f5c00d9f5333eff0fc0d9e593781727b86'


def read_verified(path,expected):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>128*1024*1024:
        raise ValueError('Reviewed input ZIP is missing or too large')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    if digest.hexdigest()!=expected:raise ValueError('Input ZIP differs from the reviewed archive')
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or len(names)>4000 or sum(i.file_size for i in z.infolist())>128*1024*1024:
            raise ValueError('Duplicate or oversized archive')
        for info in z.infolist():
            p=PurePosixPath(info.filename)
            if (p.is_absolute() or '..' in p.parts or '\\' in info.filename or ':' in info.filename
                or info.is_dir() or stat.S_ISLNK(info.external_attr>>16)):
                raise ValueError('Unsafe archive member')
        manifests=[n for n in names if n.endswith('/SHA256SUMS.json')]
        if len(manifests)!=1:raise ValueError('Expected one checksum manifest')
        prefix=manifests[0].removesuffix('SHA256SUMS.json')
        if '/' in prefix.rstrip('/'):raise ValueError('Expected one top-level run folder')
        hashes=json.loads(z.read(manifests[0]))
        if {prefix+n for n in hashes}|{manifests[0]}!=set(names):raise ValueError('Missing or untracked member')
        for name,sha in hashes.items():
            if hashlib.sha256(z.read(prefix+name)).hexdigest()!=sha:raise ValueError('Archive member checksum mismatch: '+name)
        payload={}
        allowed={'summary.json','source_pair_measurements.jsonl','pair_measurements.jsonl',
                 'model_manifest.json','language_model_manifest_RESERVED.json','split_manifest.json',
                 'diversity_inventory.json','measurement_rejections.json','source_metrics.json'}
        for name in allowed:
            if prefix+name in names:
                raw=z.read(prefix+name)
                payload[name]=[json.loads(x) for x in raw.splitlines()] if name.endswith('.jsonl') else json.loads(raw)
        return payload,dict(run_id=prefix.rstrip('/'),archive_sha256=expected,verified_files=len(hashes))


def load_inputs(source_zip,development_zip,gate_path):
    source,sprov=read_verified(source_zip,SOURCE_SHA256)
    development,dprov=read_verified(development_zip,DEVELOPMENT_SHA256)
    gate=json.loads(Path(gate_path).read_text(encoding='utf8'))
    summary=source['summary.json']
    if (summary.get('selected_systems')!=60 or summary.get('measured_pairs')!=55
        or summary.get('synthetic_pairs')!=55 or summary.get('outcome_counts')!={'converged':58,'nonconverged':2}
        or summary.get('model_evaluation_started') or summary.get('gold_labels_created')):
        raise ValueError('Source archive differs from the reviewed 55-of-60 physical qualification')
    if development['summary.json'].get('successful_model_requests')!=2880:
        raise ValueError('Development archive differs from the reviewed refinement')
    final_pairs=source['pair_measurements.jsonl'];dev_pairs=development['source_pair_measurements.jsonl']
    final_groups={r['group_id'] for r in final_pairs};dev_groups={r['group_id'] for r in dev_pairs}
    if len(final_pairs)!=110 or len(final_groups)!=55 or len(dev_groups)!=20 or final_groups&dev_groups:
        raise ValueError('Wrong source counts or overlap with development')
    accepted={r['pair_id']:r for r in gate.get('accepted',[])}
    real=[r for r in final_pairs if r['origin']=='measured_endpoint_pair']
    if len(accepted)!=55 or set(accepted)!={r['pair_id'] for r in real}:
        raise ValueError('Physical qualification IDs differ from the frozen gate')
    for row in real:
        qualified=accepted[row['pair_id']]
        hashes=row['provenance']['source_hashes']
        if (qualified['group_id']!=row['group_id'] or hashes['initial']!=qualified['initial_sha256']
            or hashes['final']!=qualified['final_sha256']):
            raise ValueError('Qualified source hashes or identity mismatch')
    model=source['language_model_manifest_RESERVED.json']
    if model!=development['model_manifest.json']:raise ValueError('Reserved language-model manifest differs from development')
    return final_pairs,dev_pairs,model,dict(source=sprov,development=dprov,
        final_source_groups=sorted(final_groups),development_source_groups=sorted(dev_groups),
        selected_source_denominator=60,qualified_source_groups=55,
        exclusions=source['measurement_rejections.json'],diversity=source['diversity_inventory.json'],
        study_scope='New source-system groups after geometry-only qualification; same dataset domain; no chemical-family or UMA-training independence claim')
