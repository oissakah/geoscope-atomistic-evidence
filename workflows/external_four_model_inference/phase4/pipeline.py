"""The three IO helpers imported by original v0.3 infer.py. No benchmark, gold or oracle access."""
from pathlib import Path
import json

def read_jsonl(path):
    seen=set(); items=[]
    for line in Path(path).read_text().splitlines():
        if not line.strip(): continue
        obj=json.loads(line)
        if not isinstance(obj,dict) or not obj.get('request_id'):
            raise ValueError('Every line needs a request_id')
        if obj['request_id'] in seen: raise ValueError('Duplicate request_id: '+obj['request_id'])
        seen.add(obj['request_id']);items.append(obj)
    return items

def write_jsonl(path,items):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w') as stream:
        for obj in items:
            stream.write(json.dumps(obj,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')

def save_json(path,content):
    path=Path(path);path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text(json.dumps(content,indent=2,sort_keys=True,allow_nan=False)+'\n')
