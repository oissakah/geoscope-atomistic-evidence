"""Replay frozen small-model answers with token-level log-probabilities; no gold labels."""
import argparse,json,os,hashlib,sys,importlib.metadata as md
from pathlib import Path
from hpc.confidence_common import checked_inputs,build_record,append_durable,atomic
from hpc.external_preflight import model_prompt
from hpc.external_stage import load

def run():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True,choices=['qwen','phi','smol']);p.add_argument('--shard',type=int,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parent.parent
    _,s,requests,older=checked_inputs(root,a.model,a.shard)
    man=Path(os.environ['MODEL_MANIFEST']);pin=json.loads((root/'frozen/EXTERNAL_INPUT_PINS.json').read_text())
    from hpc.external_stage import sha
    if sha(man)!=pin['original_model_manifest_sha256']:raise RuntimeError('Model manifest drift')
    model_dir=Path(json.loads(man.read_text())['models'][a.model]['local_path'])
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():raise RuntimeError('CUDA BF16 GPU is required')
    tokenizer=AutoTokenizer.from_pretrained(model_dir,local_files_only=True,trust_remote_code=False)
    if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
    model=AutoModelForCausalLM.from_pretrained(model_dir,local_files_only=True,trust_remote_code=False,
      use_safetensors=True,dtype=torch.bfloat16,attn_implementation='sdpa',device_map={'':'cuda:0'})
    model.eval();torch.manual_seed(20261022);torch.cuda.manual_seed_all(20261022)
    torch.backends.cuda.matmul.allow_tf32=False
    outf=root/f'outputs/confidence/{a.model}/confidence_shard_{a.shard:02d}.jsonl'
    meta=outf.with_suffix(outf.suffix+'.run_metadata.json')
    report={'backend':'transformers','transformers':md.version('transformers'),
      'torch':md.version('torch'),'model':a.model,'shard':a.shard,'shard_sha256':s['sha256'],
      'reference_sha256':hashlib.sha256((root/f'reference/{a.model}/predictions_shard_{a.shard:02d}.jsonl').read_bytes()).hexdigest(),
      'generation':'greedy_original_prompt','max_new_tokens':160,'dtype':'bfloat16','seed':20261022}
    if meta.exists() and json.loads(meta.read_text())!=report:raise RuntimeError('Replay metadata drift')
    atomic(meta,report)
    old=load(outf) if outf.exists() else [];known={x['request_id'] for x in old}
    if len(old)!=len(known) or known-{x['request_id'] for x in requests}:raise RuntimeError('Duplicate or foreign replay outputs')
    eos=model.generation_config.eos_token_id
    eos_ids=set(eos if isinstance(eos,(tuple,list)) else [eos] if eos is not None else [])
    for r in requests:
        if r['request_id'] in known:continue
        prompt=model_prompt(tokenizer,r,a.model)
        inputs=tokenizer(prompt,add_special_tokens=False,return_tensors='pt')
        n=int(inputs['input_ids'].shape[1]);original=older[r['request_id']]
        if n>6144 or n!=original['input_tokens']:raise RuntimeError('Prompt token drift: '+r['request_id'])
        inputs={k:v.to('cuda:0') for k,v in inputs.items()}
        with torch.inference_mode():
            output=model.generate(**inputs,max_new_tokens=160,do_sample=False,num_beams=1,
                pad_token_id=tokenizer.pad_token_id,return_dict_in_generate=True,output_scores=True)
            ids=output.sequences[0,n:].tolist();scores=output.scores
            if len(ids)!=len(scores):raise RuntimeError('Missing model token scores')
            logprobs=[float(torch.log_softmax(step[0].float(),dim=-1)[tid].item()) for step,tid in zip(scores,ids)]
        rec=build_record(r,original,ids,logprobs,tokenizer,a.model,{'input_tokens':n,
          'replay_truncated':len(ids)==160 and bool(ids) and ids[-1] not in eos_ids})
        append_durable(outf,rec);known.add(r['request_id'])
        print(a.model,a.shard,r['case_id'],rec['status'],rec['decision_token_geomean'],flush=True)
    print('REPLAY COMPLETE',a.model,a.shard,len(known),flush=True)
if __name__=='__main__':run()
