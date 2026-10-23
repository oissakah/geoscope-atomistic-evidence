"""External benchmark 32B token lengths using the previously completed v1.4 GPU environment."""
from pathlib import Path
import json,os,subprocess,sys,shlex
from hpc.large_external_common import source_large
from hpc.external_stage import sha

def main():
    root=Path('.').resolve();prev,model,pin=source_large(root)
    old=prev/'outputs/large_environment.sh'
    if not old.exists():raise RuntimeError('Missing v1.4 environment file')
    py=os.environ.get('LARGE_GPU_PYTHON')
    if not py or not Path(py).is_file():raise RuntimeError('Source v1.4 outputs/large_environment.sh before preparing large model')
    code=r"""
import json,sys,importlib.metadata as md
from pathlib import Path
from transformers import AutoTokenizer
from hpc.large_external_common import prompt
from hpc.external_stage import load
root=Path(sys.argv[1]);model=Path(sys.argv[2]);maxinput=int(sys.argv[3])
rs=load(root/'outputs/model_only/requests_PUBLIC_ONLY.jsonl')
tk=AutoTokenizer.from_pretrained(model,local_files_only=True,trust_remote_code=False)
lens=[len(tk(prompt(tk,r),add_special_tokens=False)['input_ids']) for r in rs]
rpt={'status':'PASS' if max(lens)<=maxinput else 'FAIL','model':'Qwen3-32B-AWQ','n_requests':len(rs),
'max_tokens':max(lens),'min_tokens':min(lens),'over_limit':sum(x>maxinput for x in lens),
'versions':{k:md.version(k) for k in ('torch','vllm','transformers')},'python':sys.executable}
(root/'outputs/large_preflight.json').write_text(json.dumps(rpt,indent=2)+'\n')
print('LARGE MODEL PREFLIGHT',rpt,flush=True)
if rpt['status']!='PASS' or rpt['versions']['vllm']!='0.11.2':sys.exit(8)
"""
    env={**os.environ,'PYTHONPATH':str(root)+os.pathsep+os.environ.get('PYTHONPATH','')}
    rc=subprocess.run([py,'-c',code,str(root),str(model),'6144'],cwd=root,env=env).returncode
    if rc:raise RuntimeError('Large model tokenizer or backend preflight failed: '+str(rc))
    # Preserve the *virtualenv entry point*: .venv/bin/python is often a symlink
    # to the shared system Python. Path.resolve() follows that symlink and removes
    # the venv context, so batch imports then fail despite a passing preflight.
    launch_python=str(Path(py).absolute())
    report=json.loads((root/'outputs/large_preflight.json').read_text())
    if str(Path(report['python']).absolute())!=launch_python:
        raise RuntimeError('GPU Python interpreter differs from passing 32B preflight: '
                           +str(report['python'])+' versus '+launch_python)
    with (root/'outputs/large_environment.sh').open('w') as f:
        f.write('export LARGE_GPU_PYTHON='+shlex.quote(launch_python)+'\n')

    print('REUSING PINNED LARGE MODEL',pin['repo_revision'],'and original AWQ backend')
if __name__=='__main__':main()
