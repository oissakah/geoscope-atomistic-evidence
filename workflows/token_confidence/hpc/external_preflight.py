"""Check original three pinned small models and all 1536 tokenizer lengths; no gold."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,shlex
from hpc.external_stage import sha,load

def model_prompt(tokenizer,req,key):
    kw={'tokenize':False,'add_generation_prompt':True}
    if key=='smol':
        kw['enable_thinking']=False
        kw['strftime_now']=lambda fmt: '20 October 2026' if fmt=='%d %B %Y' else (_ for _ in ()).throw(ValueError('unexpected date format'))
    return tokenizer.apply_chat_template(req['messages'],**kw)

def check_small(root):
    root=Path(root)
    pins=json.loads((root/'frozen/EXTERNAL_INPUT_PINS.json').read_text()); stage=root/'outputs/model_only'
    man=json.loads((stage/'stage_manifest.json').read_text())
    if man['status']!='PASS_PUBLIC_ONLY' or man['n_requests']!=1536 or man['n_groups']!=48:raise RuntimeError('Incorrect stage')
    prev=Path(os.environ.get('GEOSCOPE_MM_PARENT','/lustre/work/ock/oissakah10/GeoScope_Phase4_v1_3_ock_multimodel'))
    conf=prev/'outputs/gpu_environment.sh'
    if not conf.exists():raise RuntimeError('Missing completed v1.3 GPU environment: '+str(conf))
    # The content of this known one-source shell file is sourced by the caller,
    # not evaluated inside this Python process.
    py=Path(os.environ.get('GEOSCOPE_GPU_PYTHON',''))
    manifest=Path(os.environ.get('MODEL_MANIFEST',''))
    if not py.is_file() or not manifest.is_file():raise RuntimeError('Need GEOSCOPE_GPU_PYTHON and MODEL_MANIFEST from completed v1.3')
    if sha(manifest)!=pins['original_model_manifest_sha256']:raise RuntimeError('Original model manifest drift')
    entries=json.loads(manifest.read_text())['models']
    for key in ('qwen','phi','smol'):
        e=entries[key];d=Path(e['local_path'])
        if not (d/'config.json').is_file():raise RuntimeError('Model absent: '+key+' '+str(d))
        if key=='qwen' and d.name!=pins['legacy_qwen_snapshot']:raise RuntimeError('Changed baseline Qwen revision')
        idx=d/'model.safetensors.index.json'
        if idx.exists():
            names=set(json.loads(idx.read_text())['weight_map'].values())
            if any(not (d/n).is_file() for n in names):raise RuntimeError('Incomplete checkpoint: '+key)
        elif not (d/'model.safetensors').is_file():raise RuntimeError('No weights for '+key)
    cmd=[str(py),'-c',r"""
import json,sys,importlib.metadata as md,torch
from pathlib import Path
from transformers import AutoTokenizer
from hpc.external_preflight import model_prompt
from hpc.external_stage import load
root=Path(sys.argv[1]);m=json.loads(Path(sys.argv[2]).read_text());max_input=int(sys.argv[3])
rs=load(root/'outputs/model_only/requests_PUBLIC_ONLY.jsonl')
versions={k:md.version(k) for k in ('torch','transformers','numpy','accelerate')}
if versions['torch'].split('+')[0]!='2.13.0' or versions['transformers']!='5.3.0' or versions['accelerate']!='1.12.0' or versions['numpy']!='2.3.5' or torch.version.cuda!='12.6':
 raise RuntimeError('Original v1.3 inference environment drift: '+str(versions))
for key in ('qwen','phi','smol'):
 d=Path(m['models'][key]['local_path']); tk=AutoTokenizer.from_pretrained(d,local_files_only=True,trust_remote_code=False)
 lengths=[]
 for r in rs:
  prompt=model_prompt(tk,r,key)
  lengths.append(len(tk(prompt,add_special_tokens=False)['input_ids']))
 report={'model':key,'n_requests':len(rs),'max_tokens':max(lengths),'min_tokens':min(lengths),
         'over_limit':sum(x>max_input for x in lengths),'max_allowed':max_input,'status':'PASS' if max(lengths)<=max_input else 'FAIL'}
 (root/'outputs'/('token_preflight_'+key+'.json')).write_text(json.dumps(report,indent=2)+'\n')
 print('TOKEN CHECK',key,report,flush=True)
 if report['status']!='PASS':sys.exit(11)
""",str(root),str(manifest),str(pins['max_input'])]
    proc=subprocess.run(cmd,env={**os.environ,'PYTHONPATH':str(root)+os.pathsep+os.environ.get('PYTHONPATH','')},cwd=root)
    if proc.returncode:raise RuntimeError('Small-model tokenizer preflight failed: '+str(proc.returncode))
    rpt={'status':'PASS','python':str(py.resolve()),'model_manifest':str(manifest.resolve()),
         'manifest_sha256':sha(manifest),'stage_sha256':man['input_sha256'],'models':['qwen','phi','smol']}
    (root/'outputs/small_preflight.json').write_text(json.dumps(rpt,indent=2,sort_keys=True)+'\n')
    (root/'outputs/small_environment.sh').write_text('export GEOSCOPE_GPU_PYTHON='+shlex.quote(str(py.resolve()))+'\n'+
         'export MODEL_MANIFEST='+shlex.quote(str(manifest.resolve()))+'\n')
    print('SMALL MODEL PREFLIGHT PASS')
if __name__=='__main__':check_small(Path('.').resolve())
