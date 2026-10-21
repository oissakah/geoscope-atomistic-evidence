#!/usr/bin/env python3
"""Prepare a disjoint physical source pool; language-model evaluation is disabled."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import json
import re
import stat
import sys
import traceback
import unittest
import zipfile
from pathlib import Path, PurePosixPath

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
import phase3_support as support

REFINEMENT_SHA256='8e8e77cc36b6f1dde2ab282bfb4f79f5c00d9f5333eff0fc0d9e593781727b86'
GEOMETRY_SHA256='f99604ad0d7a29dfbb123b4845a7078b84d7ca45ed1b01a09ecdf8a1fe51c326'
DEFAULTS=dict(n_systems=60,seed=20261021,max_atoms=180,min_adsorbate_atoms=3,
              max_steps=600,batch_size=20,n_batches=3,fmax=0.05,anchor_max_displacement_A=0.02)


def config_from(path):
    config=support.load_json(path)
    if config != DEFAULTS or any(type(config.get(k)) != type(v) for k,v in DEFAULTS.items()):
        raise ValueError('This source qualification protocol is frozen; use the supplied configuration unchanged')
    return config


def read_parent(path, expected_sha256):
    """Verify attached data; never extract or execute its archived programs."""
    path=Path(path)
    if not path.is_file() or path.stat().st_size>128*1024*1024 or support.digest(path)!=expected_sha256:
        raise ValueError('Parent ZIP missing, oversized or different from the reviewed archive')
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)>4000 or len(set(names))!=len(names) or sum(i.file_size for i in z.infolist())>128*1024*1024:
            raise ValueError('Duplicate or oversized parent archive')
        for info in z.infolist():
            p=PurePosixPath(info.filename)
            if (p.is_absolute() or '..' in p.parts or '\\' in info.filename or ':' in info.filename
                or info.is_dir() or stat.S_ISLNK(info.external_attr>>16)):
                raise ValueError('Unsafe parent archive path or member type')
        manifests=[n for n in names if n.endswith('/SHA256SUMS.json')]
        if len(manifests)!=1:
            raise ValueError('Expected one parent checksum manifest')
        prefix=manifests[0].removesuffix('SHA256SUMS.json')
        if '/' in prefix.rstrip('/'):
            raise ValueError('Expected one top-level parent folder')
        hashes=json.loads(z.read(manifests[0]))
        if {prefix+n for n in hashes}|{manifests[0]}!=set(names):
            raise ValueError('Missing or untracked parent archive member')
        for name,sha in hashes.items():
            if hashlib.sha256(z.read(prefix+name)).hexdigest()!=sha:
                raise ValueError('Parent member checksum mismatch: '+name)
        # Only these data records can be returned to the running pipeline.
        payload={}
        for name in ('summary.json','model_manifest.json','source_pair_measurements.jsonl','pair_measurements.jsonl'):
            if prefix+name in names:
                data=z.read(prefix+name)
                payload[name]=[json.loads(x) for x in data.splitlines()] if name.endswith('.jsonl') else json.loads(data)
        return dict(run_id=prefix.rstrip('/'),archive_sha256=expected_sha256,verified_files=len(hashes),data=payload)


def load_parents(refinement_zip,geometry_zip):
    refinement=read_parent(refinement_zip,REFINEMENT_SHA256)
    geometry=read_parent(geometry_zip,GEOMETRY_SHA256)
    summary=refinement['data']['summary.json']
    if summary.get('successful_model_requests')!=2880 or not summary.get('model_evaluation_complete'):
        raise ValueError('Reviewed refinement did not match the completed 2880-request development run')
    gs=geometry['data']['summary.json']
    if gs.get('measured_pairs')!=20 or gs.get('outcome_counts')!={'converged':20}:
        raise ValueError('Reviewed geometry pilot differs from the accepted complete 20-system run')
    development=refinement['data']['source_pair_measurements.jsonl']
    original=geometry['data']['pair_measurements.jsonl']
    groups={r['group_id'] for r in development}
    if len(groups)!=20 or groups!={r['group_id'] for r in original}:
        raise ValueError('Reviewed development source-group identity mismatch')
    model=geometry['data']['model_manifest.json']
    if model.get('revision')!='9f578aa4bda5d1723b0cb0c4a5d2c115728a5b2e':
        raise ValueError('UMA model revision differs from the reviewed geometry pilot')
    metadata={name:{k:v for k,v in parent.items() if k!='data'} for name,parent in [('refinement',refinement),('geometry',geometry)]}
    metadata['excluded_development_groups']=sorted(groups)
    return groups,model,refinement['data']['model_manifest.json'],metadata


def freeze(out):
    names=['run_config.json','selection.json','split_manifest.json','model_manifest.json',
           'language_model_manifest_RESERVED.json','parent_provenance.json','code_sha256.json']
    for name in ('candidate_membership.json','diversity_inventory.json','source_inventory.json'):
        if (out/name).is_file():names.append(name)
    support.save_json(out/'prepared_sha256.json',{n:support.digest(out/n) for n in names})


def verify_frozen(out):
    for name,sha in support.load_json(out/'prepared_sha256.json').items():
        if support.digest(out/name)!=sha:raise ValueError('Prepared source input changed: '+name)
    current={p.relative_to(ROOT).as_posix():support.digest(p) for p in support.source_files()}
    if current!=support.load_json(out/'code_sha256.json'):
        raise ValueError('Source code changed after preparation; preserve this run and choose a new run ID')


def prepare(out,cache,refinement_zip,geometry_zip,config):
    excluded,model,llm_manifest,parents=load_parents(refinement_zip,geometry_zip)
    support.snapshot(out)
    support.save_json(out/'environment_prepare.json',support.environment())
    tests=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover(str(ROOT/'tests')))
    support.save_json(out/'self_tests.json',dict(tests_run=tests.testsRun,failures=len(tests.failures),
                       errors=len(tests.errors),success=tests.wasSuccessful()))
    if not tests.wasSuccessful():raise RuntimeError('Source preparation self-tests failed')
    from geomscope.uma import _check_model
    from phase3.sources import prepare_sources
    _check_model(model,out)
    support.save_json(out/'model_manifest.json',model)
    support.save_json(out/'language_model_manifest_RESERVED.json',llm_manifest)
    support.save_json(out/'parent_provenance.json',parents)
    selected=prepare_sources(cache/'oc20dense',out,excluded,config)
    if len(selected)!=60 or {r['group_id'] for r in selected}&excluded:
        raise ValueError('Source selection does not match the disjoint 60-system protocol')
    freeze(out)
    support.stage(out,'prepare','COMPLETE',selected_systems=len(selected))
    return dict(status='PREPARED_PENDING_UMA',selected_systems=len(selected))


def run_batch(out,batch_index,config):
    if not (out/'stage_prepare.json').exists() or support.load_json(out/'stage_prepare.json').get('state')!='COMPLETE':
        raise RuntimeError('Source preparation did not complete; collect diagnostics')
    verify_frozen(out)
    from phase3.sources import run_batch as source_batch
    support.save_json(out/f'environment_uma_{batch_index}.json',support.environment())
    rows=source_batch(out,batch_index,config)
    support.stage(out,f'uma_{batch_index}','COMPLETE',recorded_systems=len(rows))
    return dict(status='UMA_BATCH_FINISHED',batch_index=batch_index,recorded_systems=len(rows))


def collect_logs(out):
    if not (out/'launcher_jobs.json').exists():return
    jobs=support.load_json(out/'launcher_jobs.json')
    folder=Path(jobs['logs_dir'])
    for key,stem in [('prepare_job_id','prepare'),('uma0_job_id','uma'),('uma1_job_id','uma'),
                     ('uma2_job_id','uma'),('collect_job_id','collect')]:
        number=str(jobs.get(key,''));source=folder/f'{stem}-{number}.log'
        if number.isdigit() and source.is_file() and not source.is_symlink():
            dest=out/'slurm_logs'/source.name;dest.parent.mkdir(exist_ok=True)
            with source.open('rb') as stream:
                stream.seek(max(0,source.stat().st_size-1024*1024))
                text=stream.read().decode('utf8',errors='replace')
            dest.write_text(support.safe_text(text),encoding='utf8')


def collect(out,config):
    collect_logs(out)
    if not (out/'prepared_sha256.json').exists():
        return dict(status='PREPARATION_FAILED_OR_INTERRUPTED',action='Return this diagnostic ZIP')
    verify_frozen(out)
    from phase3.sources import measure_sources
    result=measure_sources(out,config)
    result['next_action']='Upload ZIP for physical-data review; no language-model inference has been authorized by this checkpoint'
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','run','collect'))
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--refinement-zip',type=Path,required=True)
    parser.add_argument('--geometry-zip',type=Path,required=True)
    parser.add_argument('--batch-index',type=int,choices=(0,1,2))
    parser.add_argument('--output-root',type=Path,default=ROOT.parent/'results_phase3_prepare')
    parser.add_argument('--cache-dir',type=Path,default=ROOT.parent/'cache')
    parser.add_argument('--config',type=Path,default=ROOT/'config/sources.json')
    args=parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',args.run_id):parser.error('Invalid run ID')
    output_root,cache=args.output_root.resolve(),args.cache_dir.resolve()
    if cache==output_root or output_root in cache.parents:parser.error('Cache must be outside results')
    out=output_root/args.run_id;out.mkdir(parents=True,exist_ok=True)
    if args.mode=='prepare' and ((out/'stage_prepare.json').exists() or (out/'prepared_sha256.json').exists()):
        print('Preparation already attempted; preserve this run and start a new run ID.',file=sys.stderr);return 1
    stage=f'uma_{args.batch_index}' if args.mode=='run' else args.mode
    code=0
    try:
        config=config_from(args.config)
        existing=out/'run_config.json'
        if existing.exists() and support.load_json(existing)!=config:raise ValueError('Run configuration changed')
        if not existing.exists():support.save_json(existing,config)
        with (out/f'{stage}.log').open('a',encoding='utf8') as log, \
             contextlib.redirect_stdout(support.Tee(sys.stdout,log)),contextlib.redirect_stderr(support.Tee(sys.stderr,log)):
            print(f'Phase 3 physical-source preparation: {args.mode}; run={args.run_id}; batch={args.batch_index}',flush=True)
            if args.mode=='collect':result=collect(out,config)
            elif args.mode=='prepare':
                support.stage(out,stage,'RUNNING')
                result=prepare(out,cache,args.refinement_zip,args.geometry_zip,config)
            else:
                if args.batch_index is None:raise ValueError('run requires --batch-index')
                support.stage(out,stage,'RUNNING')
                result=run_batch(out,args.batch_index,config)
    except Exception as exc:
        error=support.safe_text(traceback.format_exc())
        (out/f'{stage}_error.txt').write_text(error,encoding='utf8')
        support.stage(out,stage,'FAILED',error=support.safe_text(exc))
        result=dict(status='FAILED',failed_stage=stage,error=support.safe_text(exc));code=1
        print(error,file=sys.stderr)
    result.update(phase=3,checkpoint='physical_source_qualification',run_id=args.run_id,
                  phase3_complete=False,phase3_ready=False,language_model_inference_enabled=False,
                  protected_model_test_evaluated=False,contains_model_weights=False,contains_credentials=False,
                  candidate_group_disjointness_verified=(result.get('status')!='FAILED' and (out/'prepared_sha256.json').exists()),
                  limitation='Fresh source-group IDs do not establish chemical-family independence; this checkpoint creates no final claims, gold labels or model scores')
    support.save_json(out/f'summary_{stage}.json',result)
    if args.mode!='run':support.save_json(out/'summary.json',result)
    if args.mode=='collect':
        try:support.archive(out,output_root)
        except Exception as exc:
            support.diagnostic_archive(out,output_root,exc);return 2
    return code


if __name__=='__main__':raise SystemExit(main())
