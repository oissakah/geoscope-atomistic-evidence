"""Offline-only ZIP collector. Gold joins the results only AFTER inference for scoring."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,os,zipfile
from hpc.external_stage import sha,load

def main():
    root=Path(__file__).resolve().parent.parent
    pins=json.loads((root/'frozen/EXTERNAL_INPUT_PINS.json').read_text())
    stage=json.loads((root/'outputs/model_only/stage_manifest.json').read_text())
    assert stage['n_requests']==pins['expected_requests']==1536 and stage['n_groups']==48
    files={};results={};total=0
    for folder in ('frozen','source','outputs/gpu','outputs/logs'):
        directory=root/folder
        if directory.exists():
            for p in directory.rglob('*'):
                if not p.is_file():continue
                # Only one public file in source; NEVER copy potential sealed additions.
                if folder=='source' and p.name not in ('requests_PUBLIC_ONLY.jsonl','case_to_group_PUBLIC.json'):continue
                files[str(p.relative_to(root))]=p
    for p in (root/'outputs').glob('*.json'):
        files[str(p.relative_to(root))]=p
    files['outputs/model_only/stage_manifest.json']=root/'outputs/model_only/stage_manifest.json'
    for key in ('qwen','phi','smol','qwen32b'):
        got=[];duplicated=[];foreign=[];expected={r['request_id'] for s in stage['shards'] for r in load(root/'outputs/model_only'/s['file'])}
        for s in stage['shards']:
            p=root/f'outputs/gpu/{key}/predictions_shard_{s["shard"]:02d}.jsonl'
            if p.exists():
                rows=load(p);got.extend(rows)
                allowed={r['request_id'] for r in load(root/'outputs/model_only'/s['file'])}
                foreign.extend(r['request_id'] for r in rows if r['request_id'] not in allowed)
        seen=Counter(r['request_id'] for r in got)
        duplicated=[k for k,v in seen.items() if v>1]
        errors=sum(r.get('status')!='ok' for r in got)
        truncated=sum(bool(r.get('truncated')) for r in got)
        results[key]={'responses':len(got),'unique_ids':len(seen),'expected':1536,
           'duplicates':len(duplicated),'foreign':len(foreign),'errors':errors,'truncated':truncated,
           'status':'COMPLETE' if len(got)==len(seen)==1536 and not foreign and not errors else 'INCOMPLETE'}
        total+=len(got)
    source=Path(os.environ.get('GEOSCOPE_OC20_SOURCE','/lustre/work/ock/oissakah10/GeoScope_Phase4_v1_5_OC20_external_gate'))/'outputs/external_oc20_benchmark'
    for src,dst in [('public_cases.json','SEALED_REVIEW_ONLY/public_cases.json'),
                    ('benchmark_audit.json','SEALED_REVIEW_ONLY/benchmark_audit.json'),
                    ('SEAL_OFFLINE/gold_proofs_SEALED.json','SEALED_REVIEW_ONLY/gold_proofs_SEALED.json'),
                    ('BUILD_STATUS.json','SEALED_REVIEW_ONLY/BUILD_STATUS.json')]:
        p=source/src
        if p.exists():
            if sha(p)!=pins['model_only'][src]:raise RuntimeError('Sealed source checksum changed: '+src)
            files[dst]=p
        else:print('SOURCE FOR OFFLINE REVIEW NOT FOUND:',p)
    for n in ('VERSION','README.md','EXPERIMENT_PROTOCOL.md','HPC_RUNBOOK.md'):
        files[n]=root/n
    base=Path('/lustre/work/ock/oissakah10')
    if not base.exists():base=root
    dest=base/('GeoScope_Phase4_v1_6_OC20_FOURMODEL_results_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.zip')
    checks={}
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for n,p in sorted(files.items()):
            blob=p.read_bytes();z.writestr(n,blob);checks[n]=hashlib.sha256(blob).hexdigest()
        z.writestr('COLLECTION_STATUS.json',json.dumps(results,indent=2,sort_keys=True))
        z.writestr('COLLECTION_SHA256.json',json.dumps(checks,indent=2,sort_keys=True))
    with zipfile.ZipFile(dest) as z:assert z.testzip() is None
    print('RESULT ZIP:',dest)
    print('STATUS:',json.dumps(results,indent=2))
if __name__=='__main__':main()
