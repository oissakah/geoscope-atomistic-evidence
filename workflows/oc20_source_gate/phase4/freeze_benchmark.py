"""Make a provenance-checked, system-ID-heldout benchmark from v1.0 geometry.

The trusted original finalstudy benchmark is imported, never modified or duplicated.
No Phase 3 gold labels are opened. Input contains 20 frozen v0.9 pairs.
Exactly two bond-disconnected sources are excluded from the FULL metric benchmark
while preserved in eligibility/attrition reports. Their original eligibility is
not revised based on model outputs. Remaining controls are synthetic adsorbate
translations, not independently relaxed or DFT-referenced structures.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, math, os, sys, zipfile
from pathlib import Path
import numpy as np
from .geometry_validation import minimum_image_displacements, bonds, connected, unwrap_positions, kabsch_rmsd

FRAME = 'shared stored slab coordinate frame'
MIC = 'minimum-image displacement independently per matched atom'
WEIGHT = 'equal weight per selected atom'
IFRAME = 'independent molecular centroids'
ALIGN = 'proper Kabsch rotation plus translation; no reflection'
IPERIODIC = 'connected bond-graph unwrapping before alignment; no MIC on fitted residuals'
REQUIRED = (
 'outputs/physical_validation/physical_audit_summary.json',
 'outputs/physical_validation/physical_audit_rows.jsonl',
 'outputs/physical_validation/selected_atomic_pairs.jsonl',
 'outputs/physical_validation/frozen_policy_verification.json',
 'outputs/physical_validation/source_hash_verification.json',
 'frozen/v09_prospective_holdout_manifest.json',
)

def sha(data):return hashlib.sha256(data).hexdigest()
def write_json(path,obj):
 path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+'\n')
def write_jsonl(path,records):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w') as f:
  for obj in records:f.write(json.dumps(obj,sort_keys=True,allow_nan=False)+'\n')
def loads_jsonl(data):return [json.loads(x) for x in data.decode().splitlines() if x.strip()]

def load_parent(parent,package):
 """Use verified loose files or a verified one-of archived parent; no guessing."""
 parent=Path(parent).resolve();expect=json.loads((package/'frozen/PARENT_V10_INPUT_SHA256.json').read_text())
 if set(expect)!=set(REQUIRED):raise RuntimeError('Tampered parent digest inventory')
 def check_content(get):
  content={n:get(n) for n in REQUIRED}
  for n,dat in content.items():
   if sha(dat)!=expect[n]:raise RuntimeError('PINNED V1.0 INPUT HASH MISMATCH: '+n)
  return content
 if all((parent/n).is_file() for n in REQUIRED):
  content=check_content(lambda n:(parent/n).read_bytes()); origin='directory'
 else:
  matches=[]
  for archive in sorted(parent.glob('GeoScope_Phase4_v1_0_physics_results_*.zip')):
   if not zipfile.is_zipfile(archive):continue
   with zipfile.ZipFile(archive) as z:
    if not all(n in z.namelist() for n in REQUIRED):continue
    try: result=check_content(lambda n:z.read(n))
    except RuntimeError:continue
    matches.append((str(archive),result))
  if len(matches)!=1:raise RuntimeError('Expected exactly one digest-matched v1.0 archive (or intact loose outputs), found '+str(len(matches)))
  origin=matches[0][0];content=matches[0][1]
 return {
  'summary':json.loads(content[REQUIRED[0]]),
  'rows':loads_jsonl(content[REQUIRED[1]]),
  'pairs':loads_jsonl(content[REQUIRED[2]]),
  'policy':json.loads(content[REQUIRED[3]]),
  'source_hash':json.loads(content[REQUIRED[4]]),
  'holdout':json.loads(content[REQUIRED[5]]),
  'origin':origin,'parent_hashes':expect,
 }

def definition(indices,pbc,internal=False):
 return {'atom_indices':sorted(indices),'frame':IFRAME if internal else FRAME,
         'alignment':ALIGN if internal else 'none',
         'periodic_treatment':IPERIODIC if internal else MIC,
         'weighting':WEIGHT,'pbc':list(pbc)}

def masks(p):
 b=p['b1']; a=[j for j,t in enumerate(b['tags']) if t==2]
 m=[j for j,v in enumerate(b['move_mask']) if v]
 f=[j for j,v in enumerate(b['move_mask']) if not v]
 if not a or not m or not f or not set(a)<set(m) or set(a)&set(f):raise RuntimeError('Invalid atom masks')
 return m,a,f

def compute_metrics(x,y,p):
 """Independent computations from coordinates for both measured and control pairs."""
 b=p['b1']; m,a,f=masks(p)
 cell=np.asarray(b['cell'],float);pbc=b['pbc']
 residual=minimum_image_displacements(x,y,cell,pbc)
 def val(ix):
  d=residual[ix];return float(np.sqrt(np.mean(np.sum(d*d,axis=1))))
 internal=0.0 if len(a)==1 else None
 if len(a)>1:
  sy=b['symbols'];ga,unknown1=bonds(x,sy,a,cell,pbc);gb,unknown2=bonds(y,sy,a,cell,pbc)
  if unknown1 or unknown2 or ga!=gb or not connected(a,ga) or not connected(a,gb):
   raise RuntimeError('Control changed adsorbate graph or nonconnected reference')
  ux=unwrap_positions(x,a,ga,cell,pbc);uy=unwrap_positions(y,a,gb,cell,pbc)
  if ux is None or uy is None:raise RuntimeError('Cannot unwrap adsorbate')
  internal=kabsch_rmsd(ux,uy)
 return {'mobile_rmsd_A':val(m),'adsorbate_frame_rmsd_A':val(a),
         'internal_rmsd_A':float(internal),'anchor_rmsd_A':val(f)}

def records_from_parent(d):
 summary=d['summary']; rows=d['rows']; pairs=d['pairs']; frozen=d['holdout']; policy=d['policy']
 if summary.get('status')!='PHYSICAL_DIAGNOSTICS_COMPLETE_REVIEW_REQUIRED':raise RuntimeError('Unexpected physical validation status')
 if len(rows)!=20 or len(pairs)!=20 or len(frozen.get('candidates',[]))!=20:raise RuntimeError('Frozen 20-system holdout not intact')
 if policy.get('status')!='PASS' or d['source_hash'].get('status')!='PASS':raise RuntimeError('Parent source/policy audit missing')
 rowmap={x['sid']:x for x in rows}; pairmap={x['sid']:x for x in pairs}; candidates=frozen['candidates']
 if len(rowmap)!=20 or len(pairmap)!=20 or len({x['system_id'] for x in candidates})!=20:raise RuntimeError('Duplicate or missing identifiers')
 if set(rowmap)!=set(pairmap) or set(rowmap)!={x['sid'] for x in candidates}:raise RuntimeError('Prospective holdout identity mismatch')
 sources=[];status=[]
 for candidate in candidates:
  sid=candidate['sid'];row=rowmap[sid];p=pairmap[sid]
  if row['system_id']!=candidate['system_id'] or p['system_id']!=candidate['system_id'] or candidate['is_old_group']:
   raise RuntimeError('Group identity or original evaluation overlap: '+sid)
  for role in ('b1','inflight'):
   if p[role]['positions_sha256']!=candidate[role+'_positions_sha256']:
    raise RuntimeError('Pinned coordinates altered: '+sid)
  if row['counts']['fixed']<1 or row['metrics']['direct']['fixed']['max_displacement_A']>1e-8:
   raise RuntimeError('Unexpected fixed-atom motion: '+sid)
  if any(not v['direct_matches_within_tolerance'] for v in row['stored_geometry_comparison'].values()):
   raise RuntimeError('Invalid parent geometry: '+sid)
  if row['warnings']:
   status.append({'sid':sid,'system_id':row['system_id'],'status':'EXCLUDED_FROM_FULL_METRIC_BENCHMARK',
                  'warnings':row['warnings'],'preserved_for_frame_only_analysis':True})
   continue
  if not row['internal_alignment_diagnostic']['bond_graph_matches'] or row['internal_alignment_diagnostic']['value_A'] is None:
   raise RuntimeError('No validated internal metric: '+sid)
  m,a,f=masks(p);b=p['b1']; i=p['inflight'];x=np.asarray(b['positions'],float);y=np.asarray(i['positions'],float)
  if b['pbc']!=i['pbc'] or b['symbols']!=i['symbols'] or b['tags']!=i['tags'] or b['move_mask']!=i['move_mask']:
   raise RuntimeError('Inconsistent atom metadata: '+sid)
  original=compute_metrics(x,y,p)
  for key,ref in [('mobile_rmsd_A',row['metrics']['minimum_image_diagnostic']['mobile']['rmsd_A']),
                  ('adsorbate_frame_rmsd_A',row['metrics']['minimum_image_diagnostic']['adsorbate']['rmsd_A']),
                  ('internal_rmsd_A',row['internal_alignment_diagnostic']['value_A'])]:
   if abs(original[key]-ref)>2e-8:raise RuntimeError('Parent diagnostic does not reproduce: '+sid+' '+key)
  # Prospective fixed construction: 0.35-A rigid +x shift of the second endpoint's adsorbate.
  # No new simulation run, no force claim; this is a DISTRACTOR not a chemical validation result.
  shifted=y.copy();shifted[a,:]+=np.array([0.35,0.,0.])
  synthetic=compute_metrics(x,shifted,p)
  defs={'mobile_rmsd_A':definition(m,b['pbc']),
        'adsorbate_frame_rmsd_A':definition(a,b['pbc']),
        'internal_rmsd_A':definition(a,b['pbc'],internal=True),
        'anchor_rmsd_A':definition(f,b['pbc'])}
  group='holdout_system_'+hashlib.sha256(row['system_id'].encode()).hexdigest()[:16]
  for name,metric in [('measured_endpoint_pair',original),('synthetic_control',synthetic)]:
   pid='v11pair_'+hashlib.sha256((sid+'|'+name).encode()).hexdigest()[:24]
   sources.append({'group_id':group,'pair_id':pid,'split':'heldout','origin':name,
                   'measurements':{k:metric[k] for k in ('mobile_rmsd_A','adsorbate_frame_rmsd_A','internal_rmsd_A')},
                   'metric_definitions':defs,'geometry_audit':{'anchor_rmsd_A':metric['anchor_rmsd_A']},
                   'phase4_origin':'REAL_ALCHEMI_IN_COLLECTION_HELDOUT_WITH_ARTIFICIAL_DISTRACTOR',
                   'system_id_PRIVATE':row['system_id'],'sid_PRIVATE':sid})
  status.append({'sid':sid,'system_id':row['system_id'],'status':'FULL_METRIC_BENCHMARK_CANDIDATE',
                 'warnings':[],'n_adsorbate':len(a),'singleton_internal_trivial':len(a)==1,
                 'real_metrics':original,'synthetic_metrics':synthetic})
 if len(sources)!=36 or len([x for x in status if x['status']=='FULL_METRIC_BENCHMARK_CANDIDATE'])!=18:
  raise RuntimeError('Unexpected source attrition: requires 18 full-metric groups')
 return sources,status

def benchmark_and_requests(sources,out,repo_root):
 lib=Path(repo_root).resolve()/'lib'
 if not (lib/'finalstudy/benchmark.py').is_file():raise RuntimeError('Pinned original GeoScope source not found')
 sys.path.insert(0,str(lib))
 from finalstudy import benchmark, protocol
 from hashlib import sha256
 # Original constructor, original claims and original licensed proof oracle.
 public,gold,audit=benchmark.build_benchmark(sources,seed=20261022,split='heldout')
 if len({c['case_id'] for c in public})!=len(public) or len(public)!=len(gold):raise RuntimeError('Case identity collision')
 gs={x['case_id']:x for x in gold}
 for case in public:
  correct=benchmark.oracle(case['model_payload'])['verdict']
  if correct!=gs[case['case_id']]['expected']:raise RuntimeError('Sealed scoring mismatch')
  if set(case['model_payload']) not in ({'claim','evidence_packet'},{'claim','evidence_report'}):raise RuntimeError('Leaked data in model payload')
  serialized=json.dumps(case['model_payload'],sort_keys=True)
  if 'system_id_PRIVATE' in serialized or 'sid_PRIVATE' in serialized or 'gold_proofs' in serialized:raise RuntimeError('Private source metadata leaked into model payload')
  # The only content shared with GPU inference is model payload + fixed selector prompt.
 req=[]
 for case in public:
  cid=case['case_id'];rid='p4_'+sha256((cid+'|initial|0').encode()).hexdigest()[:24]
  prompt=protocol.PROMPTS['select_evidence']+'\n\n'+json.dumps(case['model_payload'],sort_keys=True,separators=(',',':'),ensure_ascii=False)
  req.append({'request_id':rid,'case_id':cid,'policy':'initial','attempt':0,
              'messages':[{'role':'user','content':prompt}]})
 if len({r['request_id'] for r in req})!=len(req):raise RuntimeError('Request identity collision')
 write_json(out/'public_cases.json',public)
 write_json(out/'SEAL_OFFLINE/gold_proofs_SEALED.json',gold)
 write_json(out/'benchmark_audit.json',audit)
 write_jsonl(out/'initial_requests_PUBLIC_ONLY.jsonl',req)
 lengths=[len(x['messages'][0]['content']) for x in req]
 write_json(out/'request_character_audit.json',{'n':len(lengths),'max_characters':max(lengths),
      'min_characters':min(lengths),'median_characters':sorted(lengths)[len(lengths)//2],
      'note':'Character counts are not token counts; enforce 6144-token no-truncation preflight before GPU.'})
 tally=collections.Counter(x['expected'] for x in gold)
 write_json(out/'label_balance_PRIVATE.json',{'labels':dict(tally),'request_count':len(req),'source_groups':len({s['group_id'] for s in sources}),
           'warning':'PRIVATE gold and label balance; do not copy to model inference environment'})
 return len(req),dict(tally),audit

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--parent',default='/lustre/work/ock/oissakah10/GeoScope_Phase4_v1_0')
 ap.add_argument('--repo-root',default=None)
 ap.add_argument('--out',default='outputs/heldout_benchmark')
 args=ap.parse_args()
 package=Path(__file__).resolve().parent.parent
 out=Path(args.out);out.mkdir(exist_ok=True,parents=True)
 d=load_parent(args.parent,package)
 records,status=records_from_parent(d)
 write_json(out/'source_pair_records_PRIVATE.json',records)
 write_json(out/'source_eligibility_audit.json',status)
 write_json(out/'input_integrity.json',{'status':'PASS','parent_origin':d['origin'],
            'input_sha256':d['parent_hashes'],'original_holdout_count':20,
            'full_metric_source_groups':18,'excluded_full_metric_sources':2,
            'role':'Previously unused system IDs from original ALCHEMI collection, NOT external validation'})
 print('PARENT VALIDATED; 20 selected groups, 18 full-metric, 2 frame-only diagnostics')
 if args.repo_root:
  n,balance,audit=benchmark_and_requests(records,out,args.repo_root)
  write_json(out/'build_status.json',{'status':'BENCHMARK_BUILT_NOT_YET_INFERRED','public_requests':n,
                                     'gold_labels_PRIVATE':balance,'source_groups':18,
                                     'note':'Heldout in-collection. All data/labels frozen before new model run.'})
  print('BENCHMARK READY; requests',n,'groups',audit.get('n_source_groups'),'labels kept private')
 else:
  write_json(out/'build_status.json',{'status':'RECORDS_PREPARED_ORIGINAL_BENCHMARK_REQUIRED','source_groups':18})
  print('Source records ready. Supply --repo-root to construct benchmark.')
if __name__=='__main__':main()
