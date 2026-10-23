"""Gold-free collector of replay token-confidence estimates and checksums."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import zipfile,json,hashlib,os
from hpc.external_stage import load
from hpc.confidence_common import KEYS,checked_inputs,verify_stage

def main():
    root=Path(__file__).resolve().parent.parent
    verify_stage(root)
    report={};files={}
    for key in KEYS:
        rows=[];expected=set()
        for shard in range(12):
            _,s,rs,_=checked_inputs(root,key,shard)
            expected.update(r['request_id'] for r in rs)
            p=root/f'outputs/confidence/{key}/confidence_shard_{shard:02d}.jsonl'
            if p.exists():
                files[str(p.relative_to(root))]=p
                meta=p.with_suffix(p.suffix+'.run_metadata.json')
                if meta.exists():files[str(meta.relative_to(root))]=meta
                rows+=load(p)
        seen=Counter(r['request_id'] for r in rows)
        invalid=[r for r in rows if r.get('status') not in ('ok','REPLAY_MISMATCH')]
        report[key]={'n_records':len(rows),'n_unique':len(seen),'expected':1536,
          'missing':len(expected-set(seen)),'foreign':len(set(seen)-expected),
          'duplicate':sum(v>1 for v in seen.values()),
          'exact_replay':sum(bool(r.get('exact_replay')) for r in rows),
          'replay_mismatch':sum(not r.get('exact_replay') for r in rows),
          'no_decision_span':sum(not r.get('has_single_decision_span') for r in rows),
          'invalid_record':len(invalid),
          'status':'COMPLETE' if len(rows)==len(seen)==len(expected)==1536 and not invalid and set(seen)==expected else 'INCOMPLETE'}
    for d in ['frozen','source','reference','outputs/model_only','outputs/logs']:
        for p in (root/d).rglob('*'):
            if p.is_file():files[str(p.relative_to(root))]=p
    for p in ['VERSION','EXPERIMENT_PROTOCOL.md','README.md','HPC_RUNBOOK.md','hpc/confidence_common.py','hpc/analyze_confidence.py']:
        files[p]=root/p
    dest=Path('/lustre/work/ock/oissakah10')
    if not dest.is_dir():dest=root.parent
    target=dest/('GeoScope_Phase4_v1_7_CONFIDENCE_results_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.zip')
    sums={}
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in sorted(files.items()):
            data=p.read_bytes()
            if 'gold_proofs' in name.lower() or 'SEALED_REVIEW_ONLY' in name:raise RuntimeError('Gold contamination')
            z.writestr(name,data);sums[name]=hashlib.sha256(data).hexdigest()
        z.writestr('COLLECTION_STATUS.json',json.dumps(report,sort_keys=True,indent=2))
        z.writestr('COLLECTION_SHA256.json',json.dumps(sums,sort_keys=True,indent=2))
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    print('RESULTS:',target,'STATUS:',json.dumps(report,indent=2))
if __name__=='__main__':main()
