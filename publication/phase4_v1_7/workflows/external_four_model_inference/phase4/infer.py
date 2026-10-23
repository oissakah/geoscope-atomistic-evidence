"""Local-only Hugging Face GPU generation for Phase 4 prospective requests.

The script never downloads weights, never alters a model, and writes *all*
attempts including truncated/invalid outputs. All system specs and hashes
must be recorded separately for the final experiment.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
from .pipeline import read_jsonl,write_jsonl,save_json


def sha(b):return hashlib.sha256(b).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--requests',required=True)
    p.add_argument('--responses',required=True)
    p.add_argument('--model-path')
    p.add_argument('--model-manifest')
    p.add_argument('--model-key',choices=['qwen','phi','smol'])
    p.add_argument('--sampling',choices=['greedy','sample'],default='greedy')
    p.add_argument('--max-new-tokens',type=int,default=160)
    p.add_argument('--max-input-tokens',type=int,default=6144)
    p.add_argument('--temperature',type=float,default=0.6)
    p.add_argument('--top-p',type=float,default=0.95)
    p.add_argument('--seed',type=int,default=20261022)
    p.add_argument('--policies',nargs='*',choices=['initial','fresh_resample','generic_feedback','specific_feedback'])
    a=p.parse_args()
    if bool(a.model_manifest) != bool(a.model_key):
        raise SystemExit('Pass both --model-manifest and --model-key, or neither.')
    if a.model_manifest:
        entry=json.loads(Path(a.model_manifest).read_text())['models'][a.model_key]
        model_path=entry['local_path']
        if a.model_path and Path(a.model_path).resolve() != Path(model_path).resolve():
            raise SystemExit('Explicit model path differs from locked manifest')
    else:
        if not a.model_path:raise SystemExit('Pass --model-path or a pinned manifest/key.')
        model_path=a.model_path
    if a.max_new_tokens<=0 or a.max_input_tokens<=0:raise ValueError('Invalid token budget')
    requests=read_jsonl(a.requests)
    if a.policies: requests=[r for r in requests if r['policy'] in a.policies]
    if not requests:raise SystemExit('No requests selected')
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer
    if not torch.cuda.is_available():raise SystemExit('A CUDA GPU allocation is required for model inference')
    torch.manual_seed(a.seed);torch.cuda.manual_seed_all(a.seed)
    torch.backends.cuda.matmul.allow_tf32=False
    tokenizer=AutoTokenizer.from_pretrained(model_path,local_files_only=True,trust_remote_code=False)
    if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model=AutoModelForCausalLM.from_pretrained(model_path,local_files_only=True,
        trust_remote_code=False,use_safetensors=True,dtype=dtype,
        attn_implementation='sdpa',device_map={'':'cuda:0'})
    model.eval()
    existing=[]
    out=Path(a.responses)
    if out.exists():existing=read_jsonl(out)
    oldids={x['request_id'] for x in existing}
    extra=oldids-{x['request_id'] for x in requests}
    if extra:raise ValueError('Existing response file contains requests outside selected set')
    versions={}
    for key in ('transformers','torch','tokenizers','safetensors'):
        try:versions[key]=importlib.metadata.version(key)
        except importlib.metadata.PackageNotFoundError:versions[key]=None
    runmeta=dict(model_path=str(Path(model_path).resolve()),model_key=a.model_key,
        request_file_sha256=sha(Path(a.requests).read_bytes()),
        model_manifest_sha256=sha(Path(a.model_manifest).read_bytes()) if a.model_manifest else None,
        sampling=a.sampling,seed=a.seed,temperature=a.temperature,top_p=a.top_p,
        max_input_tokens=a.max_input_tokens,max_new_tokens=a.max_new_tokens,
        torch_dtype=str(dtype),gpu=torch.cuda.get_device_name(0),versions=versions,
        no_network=True,no_input_truncation=True)
    meta=out.with_suffix(out.suffix+'.run_metadata.json')
    if meta.exists() and json.loads(meta.read_text())!=runmeta:
        raise ValueError('Resume metadata differs; use new output for changed settings')
    save_json(meta,runmeta)
    def template_date(fmt):
        if fmt!='%d %B %Y':raise ValueError('Unexpected dynamic template time')
        return '20 October 2026'
    eos=model.generation_config.eos_token_id
    eos_ids=set(eos if isinstance(eos,(tuple,list)) else ([eos] if eos is not None else []))
    for request in requests:
        if request['request_id'] in oldids:continue
        kwargs={'tokenize':False,'add_generation_prompt':True}
        if a.model_key=='smol':
            kwargs['enable_thinking']=False;kwargs['strftime_now']=template_date
        prompt=tokenizer.apply_chat_template(request['messages'],**kwargs)
        tokens=tokenizer(prompt,add_special_tokens=False,return_tensors='pt')
        n=int(tokens['input_ids'].shape[1])
        if n > a.max_input_tokens:
            rec=dict(request_id=request['request_id'],case_id=request['case_id'],policy=request['policy'],
                     raw_output='',status='error',error='INPUT_TOKEN_LIMIT_EXCEEDED',truncated=False,
                     input_tokens=n,output_tokens=0)
        else:
            tokens={k:v.to('cuda:0') for k,v in tokens.items()}
            cfg=dict(max_new_tokens=a.max_new_tokens,do_sample=a.sampling=='sample',num_beams=1,
                     pad_token_id=tokenizer.pad_token_id)
            if a.sampling=='sample':cfg.update(temperature=a.temperature,top_p=a.top_p)
            try:
                with torch.inference_mode(): generated=model.generate(**tokens,**cfg)
                ids=generated[0,n:].tolist()
                truncated=len(ids)==a.max_new_tokens and (not ids or ids[-1] not in eos_ids)
                rec=dict(request_id=request['request_id'],case_id=request['case_id'],policy=request['policy'],
                         raw_output=tokenizer.decode(ids,skip_special_tokens=True),status='ok',
                         truncated=truncated,input_tokens=n,output_tokens=len(ids))
            except (RuntimeError,ValueError) as ex:
                rec=dict(request_id=request['request_id'],case_id=request['case_id'],policy=request['policy'],
                         raw_output='',status='error',error=type(ex).__name__+': '+str(ex)[:300],
                         truncated=False,input_tokens=n,output_tokens=0)
        # Append each completed response as one durable JSONL record instead of
        # rewriting the whole file after every GPU generation.
        out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('a',encoding='utf-8') as handle:
            handle.write(json.dumps(rec,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')
            handle.flush()
            os.fsync(handle.fileno())
        existing.append(rec);oldids.add(request['request_id'])
        print(request['case_id'],request['policy'],rec['status'],rec['output_tokens'],flush=True)
    print('Recorded',len(existing),'responses at',out)

if __name__=='__main__':main()
