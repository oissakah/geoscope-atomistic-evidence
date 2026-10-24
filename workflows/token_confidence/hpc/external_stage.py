"""Fail-closed external benchmark staging without private cases, labels, or proofs."""
from pathlib import Path
from collections import Counter
import json,hashlib,os

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return [json.loads(s) for s in Path(p).read_text().splitlines() if s.strip()]
def stage(root=Path('.'),nshards=12):
    root=Path(root).resolve(); pins=json.loads((root/'frozen/EXTERNAL_INPUT_PINS.json').read_text())
    src=root/'source/requests_PUBLIC_ONLY.jsonl'; gids=root/'source/case_to_group_PUBLIC.json'
    assert sha(src)==pins['staged_requests_sha256']==pins['model_only']['initial_requests_PUBLIC_ONLY.jsonl']
    assert sha(gids)==pins['case_to_group_sha256']
    reqs=load(src); mapping=json.loads(gids.read_text())
    assert len(reqs)==pins['expected_requests'] and len({r['request_id'] for r in reqs})==len(reqs)
    assert len(mapping)==len(reqs) and set(mapping)=={r['case_id'] for r in reqs}
    groups=set(mapping.values());assert len(groups)==pins['expected_groups']
    for r in reqs:
        assert set(r)=={'attempt','case_id','messages','policy','request_id'}
        assert r['attempt']==0 and r['policy']=='initial'
        assert len(r['messages'])==1 and r['messages'][0]['role']=='user'
        txt=r['messages'][0]['content'].lower()
        assert not any(t in txt for t in ('gold_proofs_sealed','expected_label','gold_labels_private','seal_offline'))
    if nshards!=12:raise RuntimeError('Shard number is frozen at 12')
    group_sizes=Counter(mapping.values());bins=[[] for _ in range(nshards)];loads=[0]*nshards
    for g,n in sorted(group_sizes.items(),key=lambda x:(-x[1],x[0])):
        i=min(range(nshards),key=lambda j:(loads[j],j));bins[i].append(g);loads[i]+=n
    bygroup={g:i for i,b in enumerate(bins) for g in b}
    records=[[] for _ in bins]
    for r in reqs:records[bygroup[mapping[r['case_id']]]].append(r)
    out=root/'outputs/model_only';out.mkdir(parents=True,exist_ok=True)
    allfile=out/'requests_PUBLIC_ONLY.jsonl'
    if allfile.exists() and sha(allfile)!=sha(src):raise RuntimeError('Staged public inputs drift')
    allfile.write_bytes(src.read_bytes())
    meta=[]
    for i,lst in enumerate(records):
        p=out/f'requests_shard_{i:02}.jsonl'
        b=(''.join(json.dumps(x,sort_keys=True,ensure_ascii=False)+'\n' for x in lst)).encode()
        if p.exists() and p.read_bytes()!=b:raise RuntimeError('Staged shard drift: '+str(p))
        p.write_bytes(b)
        meta.append({'shard':i,'file':p.name,'count':len(lst),'sha256':sha(p),'groups':sorted(bins[i])})
    manifest={'n_requests':len(reqs),'n_groups':len(groups),'n_shards':nshards,'input_sha256':sha(src),
              'shards':meta,'sealed_gold_staged':False,'source_gold_sha256':pins['model_only']['SEAL_OFFLINE/gold_proofs_SEALED.json'],
              'source_public_sha256':pins['model_only']['public_cases.json'],'status':'PASS_PUBLIC_ONLY'}
    f=out/'stage_manifest.json'
    if f.exists() and json.loads(f.read_text())!=manifest:raise RuntimeError('Staging metadata drift')
    f.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    assert sum(x['count'] for x in meta)==1536
    assert len(set(g for x in meta for g in x['groups']))==48
    print('PUBLIC_ONLY STAGE PASS:',len(reqs),'requests,',len(groups),'source groups, 12 shards, counts',loads)
    return manifest
if __name__=='__main__':stage()
