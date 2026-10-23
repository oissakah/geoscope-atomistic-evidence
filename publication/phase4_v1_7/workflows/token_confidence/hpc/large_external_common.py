"""Use the original completed 32B model snapshot/pin and backend on an external stage."""
from pathlib import Path
import os,json
from hpc.external_stage import load,sha
from hpc.external_preflight import model_prompt as small_prompt
MODEL_REPO='Qwen/Qwen3-32B-AWQ'

def source_large(root):
    root=Path(root).resolve()
    prev=Path(os.environ.get('GEOSCOPE_32B_PARENT','/lustre/work/ock/oissakah10/GeoScope_Phase4_v1_4_ock_qwen32b_awq'))
    pin=json.loads((prev/'models/model_pin.json').read_text())
    model=prev/'models/qwen3_32b_awq'
    if pin['repo_id']!=MODEL_REPO or len(pin['repo_revision'])!=40 or pin['quantization']!='AWQ_INT4':raise RuntimeError('Large checkpoint pin drift')
    for name, expected in pin['file_sha256'].items():
        if sha(model/name)!=expected:raise RuntimeError('Large checkpoint file drift: '+name)
    return prev,model,pin

def prompt(tokenizer,r):
    return tokenizer.apply_chat_template(r['messages'],tokenize=False,add_generation_prompt=True,enable_thinking=False)

def checked_shard(root,index):
    root=Path(root).resolve();m=json.loads((root/'outputs/model_only/stage_manifest.json').read_text())
    if m['n_requests']!=1536 or m['n_groups']!=48 or m['n_shards']!=12 or m['sealed_gold_staged']!=False:raise RuntimeError('Stage drift')
    if not (0<=index<12):raise RuntimeError('Out-of-range external shard')
    s=m['shards'][index];p=root/'outputs/model_only'/s['file'];rs=load(p)
    if sha(p)!=s['sha256'] or len(rs)!=s['count']:raise RuntimeError('Shard hash/count drift')
    return m,s,rs
