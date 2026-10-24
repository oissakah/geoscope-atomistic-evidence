"""Separate source-to-benchmark gate using original pinned GeoScope scorer."""
from pathlib import Path
import argparse,json
from .freeze_benchmark import benchmark_and_requests,write_json

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--sources',default='outputs/external_oc20_source/source_pair_records_PRIVATE.jsonl');
 ap.add_argument('--out',default='outputs/external_oc20_benchmark');ap.add_argument('--repo-root',required=True)
 args=ap.parse_args();src=Path(args.sources);out=Path(args.out)
 integrity=src.parent/'SOURCE_GATE_STATUS.json'
 status=json.loads(integrity.read_text())
 if status['status']!='OC20_EXTERNAL_SOURCE_GATE_PASS_NO_GPU_RUN' or status['source_groups']!=48:raise RuntimeError('OC20 source gate not frozen')
 sources=[json.loads(x) for x in src.read_text().splitlines() if x.strip()]
 if len(sources)!=96 or len({s['group_id'] for s in sources})!=48:raise RuntimeError('Source identities mismatch')
 n,balance,audit=benchmark_and_requests(sources,out,args.repo_root)
 write_json(out/'BUILD_STATUS.json',{'status':'EXTERNAL_BENCHMARK_BUILT_SEALED_NOT_YET_INFERRED',
 'case_count':n,'source_groups':48,'source_split':'OC20 IS2RE/IS2RS val_ood_both relaxation trajectories',
 'expected_labels_PRIVATE':balance,'provenance':'official MD5-verified external OC20 coordinates',
 'caution':'Gold stays in SEAL_OFFLINE; only initial_requests_PUBLIC_ONLY.jsonl to GPU'})
 print('EXTERNAL_BENCHMARK_READY',n,'questions, 48 groups, sealed gold separate')
if __name__=='__main__':main()
