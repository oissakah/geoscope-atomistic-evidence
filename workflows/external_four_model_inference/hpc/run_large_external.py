"""Offline 32B vLLM generation on 1 of 12 frozen OC20 shards; fail closed on duplicate outputs."""
from pathlib import Path
import argparse,hashlib,importlib.metadata as md,json,os
from hpc.external_stage import sha,load
from hpc.large_external_common import source_large,checked_shard,prompt

def atomic_json(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n');os.replace(t,p)
def main():
    a=argparse.ArgumentParser();a.add_argument('--shard',type=int,required=True);args=a.parse_args()
    root=Path(__file__).resolve().parent.parent
    stage,s,reqs=checked_shard(root,args.shard)
    prev,model,pin=source_large(root)
    prep=json.loads((root/'outputs/large_preflight.json').read_text())
    if prep['status']!='PASS' or stage['input_sha256']!=json.loads((root/'frozen/EXTERNAL_INPUT_PINS.json').read_text())['staged_requests_sha256']:raise RuntimeError('Invalid preflight')
    from transformers import AutoTokenizer
    import torch
    from hpc.gpu_check import validate_single_l40s
    validate_single_l40s(torch.cuda)
    tokenizer=AutoTokenizer.from_pretrained(model,local_files_only=True,trust_remote_code=False)
    output=root/f'outputs/gpu/qwen32b/predictions_shard_{args.shard:02d}.jsonl'
    output.parent.mkdir(parents=True,exist_ok=True)
    meta=dict(backend='vllm',backend_version=md.version('vllm'),model_repo=pin['repo_id'],
       model_revision=pin['repo_revision'],model_path=str(model.resolve()),quantization='AWQ_INT4',
       thinking=False,sampling='greedy',max_new_tokens=160,max_input_tokens=6144,seed=20261022,
       input_sha256=s['sha256'],stage_sha256=stage['input_sha256'],shard=args.shard,expected=len(reqs))
    metap=Path(str(output)+'.run_metadata.json')
    if metap.exists() and json.loads(metap.read_text())!=meta:raise RuntimeError('Resume metadata drift')
    if not metap.exists():atomic_json(metap,meta)
    existing=load(output) if output.exists() else []
    known={r['request_id'] for r in existing}
    if len(known)!=len(existing) or not known<={x['request_id'] for x in reqs}:raise RuntimeError('Duplicate/foreign output')
    remaining=[r for r in reqs if r['request_id'] not in known]
    if not remaining:print('SHARD COMPLETE (already):',args.shard);return
    from vllm import LLM,SamplingParams
    llm=LLM(model=str(model),tokenizer=str(model),trust_remote_code=False,quantization='awq',
         dtype='half',tensor_parallel_size=1,max_model_len=6400,
         gpu_memory_utilization=0.85,enforce_eager=True,seed=20261022,disable_log_stats=True)
    prm=SamplingParams(temperature=0.0,top_p=1.0,max_tokens=160,seed=20261022)
    for r in remaining:
        p=prompt(tokenizer,r)
        n=len(tokenizer(p,add_special_tokens=False)['input_ids'])
        if n>6144:raise RuntimeError('Input overflow despite preflight')
        output_obj=llm.generate([p],prm,use_tqdm=False)[0]
        if len(output_obj.outputs)!=1:raise RuntimeError('Unexpected generation count')
        o=output_obj.outputs[0]
        rec={'request_id':r['request_id'],'case_id':r['case_id'],'policy':r['policy'],
             'status':'ok','raw_output':o.text,'input_tokens':n,'output_tokens':len(o.token_ids),
             'truncated':o.finish_reason=='length'}
        with output.open('a',encoding='utf-8') as f:
            f.write(json.dumps(rec,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
        print('EXTERNAL',args.shard,r['case_id'],rec['output_tokens'],flush=True)
    print('COMPLETE SHARD',args.shard)
if __name__=='__main__':main()
