#!/usr/bin/env bash
#SBATCH --job-name=geo-ext-sm
#SBATCH --partition=ock
#SBATCH --gres=gpu:1
#SBATCH --constraint=gpu_l40s
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --array=0-35%2
#SBATCH --output=outputs/logs/extsmall_%A_%a.out
set -Eeuo pipefail
: "${PHASE4_DIR:?Missing root}"
cd "$PHASE4_DIR"
source outputs/small_environment.sh
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
idx="${SLURM_ARRAY_TASK_ID:?missing index}"
if (( idx < 12 ));then key=qwen;shard="$idx";elif (( idx < 24 ));then key=phi;shard=$((idx-12));else key=smol;shard=$((idx-24));fi
printf -v part '%02d' "$shard"
requests="$PWD/outputs/model_only/requests_shard_${part}.jsonl"
responses="$PWD/outputs/gpu/${key}/predictions_shard_${part}.jsonl"
"$GEOSCOPE_GPU_PYTHON" - "$key" "$requests" "$shard" <<'PY_CHECK'
import json,sys,hashlib,pathlib,torch
key,path,shard=sys.argv[1:]
assert torch.cuda.is_available() and torch.cuda.is_bf16_supported(),'L40S bf16 is required'
r=pathlib.Path('.');m=json.loads((r/'outputs/model_only/stage_manifest.json').read_text())
s=m['shards'][int(shard)];assert s['file']==pathlib.Path(path).name
assert hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()==s['sha256']
p=json.loads((r/'outputs/small_preflight.json').read_text()); assert p['status']=='PASS'
assert p['stage_sha256']==m['input_sha256']
assert hashlib.sha256(pathlib.Path(p['model_manifest']).read_bytes()).hexdigest()==p['manifest_sha256']
assert json.loads((r/('outputs/token_preflight_'+key+'.json')).read_text())['status']=='PASS'
print('GPU',torch.cuda.get_device_name(0),'MODEL',key,'SHARD',shard)
PY_CHECK
"$GEOSCOPE_GPU_PYTHON" -m phase4.infer --requests "$requests" --responses "$responses" \
  --model-manifest "$MODEL_MANIFEST" --model-key "$key" \
  --sampling greedy --max-new-tokens 160 --max-input-tokens 6144 --seed 20261022
