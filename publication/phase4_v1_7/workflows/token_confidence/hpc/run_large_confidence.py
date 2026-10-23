"""Replay frozen Qwen-32B-AWQ via original vLLM backend with sampled-token logprobs."""
import argparse,os,json,hashlib,importlib.metadata as md
from pathlib import Path
from hpc.confidence_common import checked_inputs,build_record,append_durable,atomic
from hpc.external_stage import load,sha
from hpc.large_external_common import source_large,prompt

def run():
    ap=argparse.ArgumentParser();ap.add_argument('--shard',type=int,required=True);args=ap.parse_args()
    root=Path(__file__).resolve().parent.parent
    _,s,requests,older=checked_inputs(root,'qwen32b',args.shard)
    _,model,pin=source_large(root)
    import torch
    from transformers import AutoTokenizer
    from hpc.gpu_check import validate_single_l40s
    validate_single_l40s(torch.cuda)
    tokenizer=AutoTokenizer.from_pretrained(model,local_files_only=True,trust_remote_code=False)
    from vllm import LLM,SamplingParams
    outf=root/f'outputs/confidence/qwen32b/confidence_shard_{args.shard:02d}.jsonl'
    meta=outf.with_suffix(outf.suffix+'.run_metadata.json')
    report={'backend':'vllm','vllm':md.version('vllm'),'model_repo':pin['repo_id'],
      'model_revision':pin['repo_revision'],'shard':args.shard,'shard_sha256':s['sha256'],
      'reference_sha256':sha(root/f'reference/qwen32b/predictions_shard_{args.shard:02d}.jsonl'),
      'quantization':'AWQ_INT4','dtype':'half','temperature':0.0,'max_new_tokens':160,'seed':20261022}
    if meta.exists() and json.loads(meta.read_text())!=report:raise RuntimeError('Replay metadata drift')
    atomic(meta,report)
    old=load(outf) if outf.exists() else [];known={r['request_id'] for r in old}
    if len(old)!=len(known) or known-{r['request_id'] for r in requests}:raise RuntimeError('Duplicate or foreign replay outputs')
    pending=[r for r in requests if r['request_id'] not in known]
    if not pending:print('REPLAY SHARD COMPLETE, SKIPPING MODEL LOAD',args.shard);return
    llm=LLM(model=str(model),tokenizer=str(model),trust_remote_code=False,quantization='awq',
      dtype='half',tensor_parallel_size=1,max_model_len=6400,gpu_memory_utilization=0.85,
      enforce_eager=True,seed=20261022,disable_log_stats=True)
    params=SamplingParams(temperature=0.0,top_p=1.0,max_tokens=160,seed=20261022,logprobs=1)
    for r in pending:
        p=prompt(tokenizer,r);n=len(tokenizer(p,add_special_tokens=False)['input_ids'])
        original=older[r['request_id']]
        if n!=original['input_tokens'] or n>6144:raise RuntimeError('Large prompt token drift')
        output=llm.generate([p],params,use_tqdm=False)[0]
        if len(output.outputs)!=1:raise RuntimeError('Unexpected sample count')
        o=output.outputs[0];ids=list(o.token_ids)
        if not o.logprobs or len(o.logprobs)!=len(ids):raise RuntimeError('Missing generated token probabilities')
        lp=[]
        for token,dist in zip(ids,o.logprobs):
            point=dist.get(token)
            if point is None:raise RuntimeError('Sampled token logprob not present')
            lp.append(float(point.logprob))
        rec=build_record(r,original,ids,lp,tokenizer,'qwen32b',{'input_tokens':n,
             'replay_truncated':o.finish_reason=='length'})
        append_durable(outf,rec);known.add(r['request_id'])
        print('qwen32b',args.shard,r['case_id'],rec['status'],rec['decision_token_geomean'],flush=True)
    print('REPLAY COMPLETE qwen32b',args.shard,len(known),flush=True)
if __name__=='__main__':run()
