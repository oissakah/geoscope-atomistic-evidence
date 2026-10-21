#!/usr/bin/env python3
"""Freeze and run the final new-system evidence study without new UMA calls."""
from __future__ import annotations
import argparse
import contextlib
import json
import re
import sys
import traceback
import unittest
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
import study_support as support
from study_inputs import load_inputs

DEFAULTS=dict(seed=20261021,batch_size=2,max_new_tokens=160,max_input_tokens=6144,bootstrap_samples=1000)
MODEL_KEYS=('qwen','phi','smol')
CONDITIONS=('direct','select_evidence')


def config_from(path):
    config=support.load_json(path)
    if config!=DEFAULTS or any(type(config.get(k))!=type(v) for k,v in DEFAULTS.items()):
        raise ValueError('Use the supplied frozen final configuration unchanged')
    return config


def read_jsonl(path,allow_partial_last=False):
    text=Path(path).read_text(encoding='utf8');lines=text.splitlines();rows=[]
    for i,line in enumerate(lines):
        if not line.strip():continue
        try:rows.append(json.loads(line))
        except json.JSONDecodeError:
            if allow_partial_last and i==len(lines)-1 and not text.endswith('\n'):
                return rows,'One incomplete final JSONL record omitted after interruption; its case remains missing'
            raise
    return rows,None


def build_data(out,source_zip,development_zip,config):
    from finalstudy.benchmark import build_benchmark,oracle
    final_pairs,development_pairs,model,provenance=load_inputs(source_zip,development_zip,ROOT/'data/qualification_gate.json')
    # Validate the revised generator on development inputs first. No model is
    # called on either split during this preparation stage.
    dev_public,dev_gold,dev_audit=build_benchmark(development_pairs,seed=config['seed'],split='development')
    for case,answer in zip(dev_public,dev_gold):
        if case['case_id']!=answer['case_id'] or oracle(case['model_payload'])['verdict']!=answer['expected']:
            raise ValueError('Development oracle/gold disagreement blocks final evaluation')
    support.save_json(out/'development_audit.json',dev_audit)
    public,gold,audit=build_benchmark(final_pairs,seed=config['seed'],split='heldout')
    if len({c['group_id'] for c in public})!=55:
        raise ValueError('The final case set must retain all 55 qualified source groups')
    for case,answer in zip(public,gold):
        if case['case_id']!=answer['case_id'] or oracle(case['model_payload'])['verdict']!=answer['expected']:
            raise ValueError('Final oracle/gold disagreement blocks model inference')
    support.jsonl(out/'cases_public.jsonl',public)
    support.jsonl(out/'cases_gold_DO_NOT_SEND_TO_MODELS.jsonl',gold)
    support.save_json(out/'benchmark_audit.json',audit)
    support.jsonl(out/'source_pair_measurements.jsonl',final_pairs)
    support.save_json(out/'parent_provenance.json',provenance)
    support.save_json(out/'qualification_gate.json',support.load_json(ROOT/'data/qualification_gate.json'))
    support.save_json(out/'model_manifest.json',model)
    return public,gold


def freeze(out):
    names=('run_config.json','cases_public.jsonl','cases_gold_DO_NOT_SEND_TO_MODELS.jsonl',
           'benchmark_audit.json','development_audit.json','model_manifest.json','parent_provenance.json',
           'qualification_gate.json','protocol.json','code_sha256.json')
    support.save_json(out/'prepared_sha256.json',{n:support.digest(out/n) for n in names})


def verify_frozen(out):
    for name,expected in support.load_json(out/'prepared_sha256.json').items():
        if support.digest(out/name)!=expected:raise ValueError('Frozen study input changed: '+name)
    actual={p.relative_to(ROOT).as_posix():support.digest(p) for p in support.source_files()}
    if actual!=support.load_json(out/'code_sha256.json'):
        raise ValueError('Study source changed after preparation. Preserve the run; do not modify the final protocol')


def prepare(out,source_zip,development_zip,config):
    from finalstudy.models import _manifest_entry,_verify_files
    from finalstudy.protocol import PROTOCOL
    support.snapshot(out)
    support.save_json(out/'environment_prepare.json',support.environment())
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    report=unittest.TextTestRunner(verbosity=1).run(suite)
    support.save_json(out/'self_tests.json',dict(tests_run=report.testsRun,failures=len(report.failures),
                       errors=len(report.errors),success=report.wasSuccessful()))
    if not report.wasSuccessful():raise RuntimeError('Final protocol self-tests failed; no model evaluation permitted')
    public,gold=build_data(out,source_zip,development_zip,config)
    model=support.load_json(out/'model_manifest.json')
    if model.get('schema_version')!=1 or set(model.get('models',{}))!=set(MODEL_KEYS):
        raise ValueError('The final run must reuse the three reviewed model checkpoints')
    for key in MODEL_KEYS:
        _manifest_entry(model['models'][key],key);_verify_files(model['models'][key])
    support.save_json(out/'protocol.json',PROTOCOL)
    freeze(out);support.stage(out,'prepare','COMPLETE',case_variants=len(public),source_groups=55)
    return dict(status='FROZEN_PENDING_MODELS',case_variants=len(public),source_groups=55,
                expected_model_requests=len(public)*len(CONDITIONS)*len(MODEL_KEYS))


def run_model(out,key,config):
    if not (out/'stage_prepare.json').exists() or support.load_json(out/'stage_prepare.json').get('state')!='COMPLETE':
        raise RuntimeError('Preparation did not complete; collect diagnostics')
    verify_frozen(out)
    from finalstudy.models import run_model as infer
    public,_=read_jsonl(out/'cases_public.jsonl')
    rows=infer(key,support.load_json(out/'model_manifest.json'),public,out,seed=config['seed'],
               max_new_tokens=config['max_new_tokens'],batch_size=config['batch_size'],max_input_tokens=config['max_input_tokens'])
    support.stage(out,key,'COMPLETE',recorded_requests=len(rows))
    return dict(status='MODEL_JOB_FINISHED',model_key=key,recorded_requests=len(rows))


def collect_logs(out):
    if not (out/'launcher_jobs.json').exists():return
    jobs=support.load_json(out/'launcher_jobs.json');folder=Path(jobs['logs_dir'])
    for key,stem in [('prepare_job_id','prepare'),('qwen_job_id','model'),('phi_job_id','model'),
                     ('smol_job_id','model'),('collect_job_id','collect')]:
        number=str(jobs.get(key,''));source=folder/f'{stem}-{number}.log'
        if number.isdigit() and source.is_file() and not source.is_symlink():
            destination=out/'slurm_logs'/source.name;destination.parent.mkdir(exist_ok=True)
            with source.open('rb') as stream:
                stream.seek(max(0,source.stat().st_size-1024*1024));text=stream.read().decode('utf8',errors='replace')
            destination.write_text(support.safe_text(text),encoding='utf8')


def collect(out,config):
    collect_logs(out)
    if not (out/'prepared_sha256.json').exists():
        return dict(status='PREPARATION_FAILED_OR_INTERRUPTED',model_evaluation_complete=False,
                    next_action='Return this diagnostic ZIP; do not relaunch to overwrite the final run')
    verify_frozen(out)
    from finalstudy.evaluation import evaluate,write_reports
    public,_=read_jsonl(out/'cases_public.jsonl');gold,_=read_jsonl(out/'cases_gold_DO_NOT_SEND_TO_MODELS.jsonl')
    expected={(case['case_id'],condition) for case in public for condition in CONDITIONS}
    predictions=[];warnings=[];successful=0
    for key in MODEL_KEYS:
        path=out/f'predictions_{key}.jsonl'
        raw,warning=read_jsonl(path,allow_partial_last=True) if path.exists() else ([],None)
        if warning:warnings.append(dict(model_key=key,warning=warning))
        valid_identity=[]
        for row in raw:
            identity=(row.get('case_id'),row.get('condition'))
            if identity not in expected or row.get('model_key')!=key:
                warnings.append(dict(model_key=key,warning='Unexpected prediction identity retained in raw file',
                                     case_id=row.get('case_id'),condition=row.get('condition')))
            else:valid_identity.append(row)
        counts=Counter((r['case_id'],r['condition']) for r in valid_identity)
        successful+=sum(r.get('status')=='ok' and not r.get('truncated',False)
                        and counts[(r['case_id'],r['condition'])]==1 for r in valid_identity)
        predictions.extend(valid_identity)
        for case in public:
            for condition in CONDITIONS:
                if (case['case_id'],condition) not in counts:
                    predictions.append(dict(case_id=case['case_id'],condition=condition,model_key=key,
                        status='missing',raw_output='',error='No recorded response; missing case remains in denominator'))
    result=evaluate(public,gold,predictions,seed=config['seed'],bootstrap_samples=config['bootstrap_samples'])
    write_reports(result,out)
    support.save_json(out/'collection_warnings.json',warnings)
    expected_requests=len(expected)*len(MODEL_KEYS)
    return dict(status='READY_FOR_FINAL_REVIEW' if successful==expected_requests else 'PARTIAL_FINAL_RESULTS',
        case_variants=len(public),source_groups=55,original_selected_source_denominator=60,
        expected_model_requests=expected_requests,successful_model_requests=successful,
        model_evaluation_complete=successful==expected_requests,
        next_action='Upload this final results ZIP for analysis, data release and manuscript/CV conclusions; do not tune on these outcomes')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','run','collect'));parser.add_argument('--run-id',required=True)
    parser.add_argument('--source-zip',type=Path,required=True);parser.add_argument('--development-zip',type=Path,required=True)
    parser.add_argument('--model-key',choices=MODEL_KEYS)
    parser.add_argument('--output-root',type=Path,default=ROOT.parent/'results_phase3_final')
    parser.add_argument('--cache-dir',type=Path,default=ROOT.parent/'cache/llms_phase2')
    parser.add_argument('--config',type=Path,default=ROOT/'config/final.json')
    args=parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',args.run_id):parser.error('Invalid run ID')
    output_root,cache=args.output_root.resolve(),args.cache_dir.resolve()
    if cache==output_root or output_root in cache.parents:parser.error('Cache must be outside results')
    out=output_root/args.run_id;out.mkdir(parents=True,exist_ok=True)
    if args.mode=='prepare' and ((out/'stage_prepare.json').exists() or (out/'prepared_sha256.json').exists()):
        print('This final run was already prepared or attempted. Preserve it and return diagnostics; do not overwrite it.',file=sys.stderr);return 1
    stage=args.model_key if args.mode=='run' else args.mode;code=0
    try:
        config=config_from(args.config);existing=out/'run_config.json'
        if existing.exists() and support.load_json(existing)!=config:raise ValueError('Run configuration changed')
        if not existing.exists():support.save_json(existing,config)
        with (out/f'{stage}.log').open('a',encoding='utf8') as log, \
             contextlib.redirect_stdout(support.Tee(sys.stdout,log)),contextlib.redirect_stderr(support.Tee(sys.stderr,log)):
            print(f'Final frozen study: {args.mode}; run={args.run_id}; model={args.model_key}',flush=True)
            if args.mode=='collect':result=collect(out,config)
            elif args.mode=='prepare':
                support.stage(out,stage,'RUNNING');result=prepare(out,args.source_zip,args.development_zip,config)
            else:
                if args.model_key is None:raise ValueError('run requires --model-key')
                support.stage(out,stage,'RUNNING');result=run_model(out,args.model_key,config)
    except Exception as exc:
        error=support.safe_text(traceback.format_exc());(out/f'{stage}_error.txt').write_text(error,encoding='utf8')
        support.stage(out,stage,'FAILED',error=support.safe_text(exc));print(error,file=sys.stderr)
        result=dict(status='FAILED',failed_stage=stage,error=support.safe_text(exc));code=1
    result.update(phase=3,checkpoint='frozen_new_system_model_evaluation',run_id=args.run_id,
        phase3_complete=False,final_review_required=True,new_uma_calculations=False,
        contains_model_weights=False,contains_credentials=False,
        limitation='First frozen model evaluation on 55 qualified same-domain groups after geometry review; no chemical-family independence, preregistered-study or novel-algorithm claim')
    support.save_json(out/f'summary_{stage}.json',result)
    if args.mode!='run':support.save_json(out/'summary.json',result)
    if args.mode=='collect':
        try:support.archive(out,output_root)
        except Exception as exc:support.diagnostic_archive(out,output_root,exc);return 2
    return code


if __name__=='__main__':raise SystemExit(main())
