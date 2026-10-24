"""Version-pinned, gold-free utilities for confidence replay."""
from pathlib import Path
import hashlib,json,math,re,os
from hpc.external_stage import load,sha
KEYS=('qwen','phi','smol','qwen32b')
OPS=('adsorbate_upper','mobile_lower','value','none')

def atomic(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n');os.replace(q,p)

def verify_stage(root):
    root=Path(root)
    stage=json.loads((root/'outputs/model_only/stage_manifest.json').read_text())
    fixed=json.loads((root/'frozen/BASELINE_STAGE_MANIFEST.json').read_text())
    if stage!=fixed:raise RuntimeError('Benchmark shard manifest differs from frozen OC20 run')
    if stage['n_requests']!=1536 or stage['n_groups']!=48 or stage['n_shards']!=12:raise RuntimeError('Incorrect OC20 benchmark')
    if stage['sealed_gold_staged'] or list(root.rglob('*gold_proofs*')):raise RuntimeError('SEALED GOLD found in GPU package')
    return stage

def checked_inputs(root,key,shard):
    if key not in KEYS or shard not in range(12):raise ValueError('Invalid key/shard')
    root=Path(root);stage=verify_stage(root);s=stage['shards'][shard]
    inputs=root/'outputs/model_only'/s['file'];baseline=root/'reference'/key/f'predictions_shard_{shard:02d}.jsonl'
    pins=json.loads((root/'frozen/BASELINE_RESPONSE_SHA256.json').read_text())
    if sha(inputs)!=s['sha256'] or sha(baseline)!=pins[key][f'{shard:02d}']:raise RuntimeError('Frozen request/answer checksum drift')
    reqs=load(inputs);original=load(baseline)
    if len(reqs)!=128 or len(original)!=128:raise RuntimeError('Expected 128 per shard')
    index={r['request_id']:r for r in original}
    if len(index)!=128 or set(index)!={r['request_id'] for r in reqs}:raise RuntimeError('Missing/duplicate/foreign reference answer')
    for r in reqs:
        old=index[r['request_id']]
        if old['case_id']!=r['case_id'] or old['status']!='ok':raise RuntimeError('Bad reference record')
    return stage,s,reqs,index

def group_token_spans(token_ids,logprobs,tokenizer):
    if len(token_ids)!=len(logprobs):raise ValueError('Misaligned logits')
    valid_ids=[];valid_probs=[];bounds=[];previous=''
    for idx,(tid,lp) in enumerate(zip(token_ids,logprobs)):
        if not math.isfinite(lp) or lp>0.0001:raise ValueError('Invalid sampled-token log probability')
        if tid in tokenizer.all_special_ids:continue
        valid_ids.append(tid);valid_probs.append(float(lp))
        nxt=tokenizer.decode(valid_ids,skip_special_tokens=True,clean_up_tokenization_spaces=False)
        if not nxt.startswith(previous):
            raise ValueError('Token decoding not prefix-stable; do not infer decision-token spans')
        bounds.append((len(previous),len(nxt)))
        previous=nxt
    return previous,valid_probs,bounds

def geometric(lp):return math.exp(sum(lp)/len(lp)) if lp else None

def metrics(ids,logprobs,tokenizer):
    # UTF-8 byte fallback can make intermediate prefix decodes unstable.
    # In that case, preserve valid whole-answer confidence but mark the
    # evidence/operation span inaccessible rather than crash an HPC shard.
    try:
        text,lp,bounds=group_token_spans(ids,logprobs,tokenizer)
        span_issue=None
    except ValueError as exc:
        if 'prefix-stable' not in str(exc):raise
        lp=[float(x) for token,x in zip(ids,logprobs) if token not in tokenizer.all_special_ids]
        text=tokenizer.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False)
        bounds=[]
        span_issue='DECODE_PREFIX_UNSTABLE'
    all_mean=geometric(lp);minimum=math.exp(min(lp)) if lp else None
    # Primary semantic span: evidence identifier and operation STRING VALUES ONLY.
    # Reject ambiguous multi IDs; never score punctuation as semantic confidence.
    evidences=list(re.finditer(r'E_[0-9a-fA-F]{8}',text))
    op_matches=list(re.finditer(r'"operation"\s*:\s*"(adsorbate_upper|mobile_lower|value|none)"',text))
    decision=[];evidence=[];operation=[]
    if len(evidences)==1 and len(op_matches)==1:
        m=evidences[0];o=op_matches[0];spans={'evidence':(m.start(),m.end()),'operation':o.span(1)}
        for pos,(a,b) in enumerate(bounds):
            if a==b:continue
            for name,(left,right) in spans.items():
                if a<right and b>left:
                    (evidence if name=='evidence' else operation).append(lp[pos]);decision.append(pos)
    decision_lp=[lp[i] for i in sorted(set(decision))]
    return {'all_token_geomean':all_mean,'min_token_prob':minimum,'n_scored_tokens':len(lp),
      'decision_token_geomean':geometric(decision_lp),
      'evidence_token_geomean':geometric(evidence),'operation_token_geomean':geometric(operation),
      'n_decision_tokens':len(decision_lp),'has_single_decision_span':bool(evidence and operation),
      'decision_span_issue':span_issue,
      'decoded_text':text}

def build_record(request,old,ids,logprobs,tokenizer,backend,extra=None):
    met=metrics(ids,logprobs,tokenizer)
    raw=tokenizer.decode(ids,skip_special_tokens=True)
    exact=raw==old['raw_output']
    rec={'request_id':request['request_id'],'case_id':request['case_id'],'model':backend,
      'baseline_raw_sha256':hashlib.sha256(old['raw_output'].encode()).hexdigest(),
      'replay_raw_sha256':hashlib.sha256(raw.encode()).hexdigest(),
      'exact_replay':exact,'reference_output_tokens':old['output_tokens'],
      'replay_output_tokens':len(ids),'original_truncated':bool(old.get('truncated')),
      'all_token_geomean':met['all_token_geomean'],'min_token_prob':met['min_token_prob'],
      'decision_token_geomean':met['decision_token_geomean'],
      'evidence_token_geomean':met['evidence_token_geomean'],
      'operation_token_geomean':met['operation_token_geomean'],
      'n_scored_tokens':met['n_scored_tokens'],'n_decision_tokens':met['n_decision_tokens'],
      'has_single_decision_span':met['has_single_decision_span'],
      'decision_span_issue':met['decision_span_issue'],
      'status':'ok' if exact else 'REPLAY_MISMATCH'}
    if extra:rec.update(extra)
    return rec

def append_durable(path,rec):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as f:
        f.write(json.dumps(rec,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
