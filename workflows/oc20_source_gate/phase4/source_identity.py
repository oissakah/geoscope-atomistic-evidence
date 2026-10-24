"""GeoScope Phase 4: read-only, conservative ALCHEMI source-identity join.

The prior v0.7 row-by-row pairing was INVALID because EXTXYZ ordering differs.
Match original configuration ID (sid), and verify system_id, atom identities,
cell/PBC, mobile/adsorbate flags, endpoint provenance and source-group exclusion.
No gold proof or label content is read from Phase 3; only system IDs are accessed.

Candidate selection is deterministic and does not use RMSD or magnitude of
model error. This audit does NOT certify independent observations or reconstruct
per-atom geometries. This is a prerequisite, not final held-out evaluation.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, shlex, collections
from pathlib import Path
from datetime import datetime, timezone

AL='alchemi-uma-catalysis-milestone2'
SEED='GeoScope-Phase4-frozen-holdout-v0.8.0-20261022'
REQUIRED_PROPS=('species','pos','move_mask','tags')
SOURCE_TABLES={
 'b1_csv': 'results/production_500/geometry_validation/b1_geometry_results.csv',
 'inflight_csv': 'results/production_500/geometry_validation/inflight_b04_geometry_results.csv',
 'geometry_comparison': 'results/production_500/geometry_validation/geometry_comparison.csv',
 'b1_xyz': 'results/production_500/geometry_validation/b1_final_structures.extxyz',
 'inflight_xyz': 'results/production_500/geometry_validation/inflight_b04_final_structures.extxyz',
}

def sha_file(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def dump(p,data):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(data,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def csv_rows(path):
 with path.open('r',encoding='utf-8-sig',newline='') as f:
  return list(csv.DictReader(f))

def jsonl_rows(path, only=None):
 out=[]
 with path.open('r',encoding='utf8') as f:
  for i,line in enumerate(f,1):
   if not line.strip():continue
   x=json.loads(line)
   if not isinstance(x,dict):raise ValueError(f'{path}: line {i} not an object')
   out.append({k:x.get(k) for k in only} if only is not None else x)
 return out

def unique_index(rows, path, key='sid'):
 lookup={}
 for i,row in enumerate(rows):
  v=str(row.get(key) or '').strip()
  if not v:raise ValueError(f'{path}: missing {key} on row {i}')
  if v in lookup:raise ValueError(f'{path}: duplicate {key}={v}')
  lookup[v]=row
 return lookup

def parse_comment(line):
 return dict(item.split('=',1) for item in shlex.split(line.strip()) if '=' in item)

def property_slots(spec):
 toks=spec.split(':');out={};offset=0
 if len(toks)%3:raise ValueError('invalid EXTXYZ Properties')
 for i in range(0,len(toks),3):
  name,typ,count=toks[i:i+3];count=int(count)
  if count<1 or name in out:raise ValueError('bad or repeated EXTXYZ property')
  out[name]=(offset,offset+count,typ)
  offset+=count
 if any(x not in out for x in REQUIRED_PROPS):raise ValueError('missing atomic metadata fields')
 if out['species'][1]-out['species'][0]!=1 or out['pos'][1]-out['pos'][0]!=3:raise ValueError('bad species or pos widths')
 return out,offset

def extxyz_frames(path):
 """Parse full ordered species, pos, move_mask, tags; retain only hashes and summary."""
 rows=[]
 with path.open('r',encoding='utf8') as f:
  while True:
   line=f.readline()
   if not line:break
   if not line.strip():continue
   n=int(line.strip());head=f.readline()
   if not head or n<1 or n>100000:raise ValueError('bad EXTXYZ frame boundary')
   h=parse_comment(head);slots,num=property_slots(h.get('Properties',''))
   sid=h.get('sid');sys=h.get('system_id')
   if not sid or not sys:raise ValueError('missing sid/system_id in EXTXYZ')
   raw_lattice=h.get('Lattice')
   cell=[float(x) for x in raw_lattice.split()] if raw_lattice else []
   if len(cell)!=9 or not all(math.isfinite(v) for v in cell):raise ValueError('missing/invalid cell')
   a,b,c=cell[0:3],cell[3:6],cell[6:9]
   volume=(a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0]))
   if abs(volume)<1e-8:raise ValueError('singular cell')
   pbc=h.get('pbc','').strip().split()
   if len(pbc)!=3 or any(p not in ('T','F') for p in pbc):raise ValueError('invalid PBC')
   symbols=[];masks=[];tags=[];positions=[]
   for j in range(n):
    line=f.readline()
    if not line:raise ValueError('unexpected end of EXTXYZ atom block')
    fields=line.split()
    if len(fields)!=num:raise ValueError(f'atomic field count mismatch: {path} sid {sid} line {j}')
    def take(k):
     i,e,_=slots[k];return fields[i:e]
    symbols.append(take('species')[0])
    pos=[float(v) for v in take('pos')]
    if not all(math.isfinite(x) for x in pos):raise ValueError('nonfinite coordinates')
    positions.append(pos)
    mask=take('move_mask')[0]
    if mask not in ('T','F','True','False','1','0'):raise ValueError('bad move_mask')
    masks.append(mask in ('T','True','1'))
    tags.append(int(take('tags')[0]))
   sid=str(sid);sys=str(sys)
   h_atom=hashlib.sha256(json.dumps([symbols,masks,tags],separators=(',',':')).encode()).hexdigest()
   h_xyz=hashlib.sha256(json.dumps([symbols,positions],separators=(',',':')).encode()).hexdigest()
   rows.append({'sid':sid,'system_id':sys,'frame_index':len(rows),'n_atoms':n,
      'species_order_sha256':hashlib.sha256(' '.join(symbols).encode()).hexdigest(),
      'atom_metadata_sha256':h_atom,'positions_sha256':h_xyz,
      'n_mobile':sum(masks),'n_tags_2':sum(t==2 for t in tags),
      'n_tags_nonzero':sum(t!=0 for t in tags),
      'cell':cell,'pbc':pbc,'volume_A3':abs(volume),
      'tags_distribution':dict(collections.Counter(str(t) for t in tags))})
 return rows

def same_cell(a,b,tol=1e-5):
 return len(a)==len(b)==9 and all(abs(x-y)<=tol for x,y in zip(a,b))

def bool_true(s):return str(s).lower() in ('true','1','yes')

def finite_float(s):
 try:
  v=float(s);return v if math.isfinite(v) else None
 except (ValueError,TypeError):return None

def stable_select(rows,minimum=20):
 """Select one configuration per distinct system_id without reading error magnitudes."""
 bysys=collections.defaultdict(list)
 for x in rows:bysys[x['system_id']].append(x)
 def h(*v):return hashlib.sha256((SEED+'|'+ '|'.join(map(str,v))).encode()).hexdigest()
 choices=[]
 for sys,grp in bysys.items():
  one=min(grp,key=lambda x:(h(sys,x['sid']),x['sid']))
  choices.append(one)
 choices.sort(key=lambda x:(h(x['system_id']),x['system_id']))
 return choices[:minimum]

PUBLICATION_MEMBERS={
 'manifest':'full500_manifest.csv',
 'initial':'initial_structures.jsonl',
 'endpoint_b1':'b1/endpoints.jsonl',
 'endpoint_inflight':'inflight_b4/endpoints.jsonl',
}

def choose_pinned_publication(runs, expected, diagnostics_path=None):
 """Require exactly one run matching *all four* hashes from the v0.7 audit.

 We deliberately do not select the newest/first directory, or combine records
 from different publication runs. Diagnostic output can be uploaded on failure.
 """
 report={'selection_policy':'unique publication directory whose four files match the pinned v0.7 SHA256 fingerprints',
         'required_input_keys':sorted(PUBLICATION_MEMBERS), 'candidates':[],'selected':None}
 matches=[]
 for root in sorted(map(Path,runs)):
  item={'directory':str(root),'matched_keys':[],'missing_keys':[],'mismatched_keys':[], 'observed_sha256':{}}
  if not root.is_dir():
   item['missing_keys']=sorted(PUBLICATION_MEMBERS)
  else:
   for key,subpath in PUBLICATION_MEMBERS.items():
    p=root/subpath
    if not p.is_file(): item['missing_keys'].append(key);continue
    got=sha_file(p)
    item['observed_sha256'][key]=got
    if got==expected.get(key):item['matched_keys'].append(key)
    else:item['mismatched_keys'].append(key)
  item['matched_keys'].sort();item['missing_keys'].sort();item['mismatched_keys'].sort()
  report['candidates'].append(item)
  if len(item['matched_keys'])==len(PUBLICATION_MEMBERS) and not item['missing_keys'] and not item['mismatched_keys']:
   matches.append(root)
 if len(matches)==1:
  report['status']='PINNED_RUN_UNIQUELY_IDENTIFIED';report['selected']=str(matches[0])
 elif not matches:
  report['status']='NO_PINNED_RUN_MATCH'
 else:
  report['status']='AMBIGUOUS_PINNED_RUN_MATCH'
 report['matching_candidate_count']=len(matches)
 if diagnostics_path is not None:dump(diagnostics_path,report)
 if len(matches)!=1:
  raise RuntimeError('Publication-run identity failed: '+report['status']+
    f' (candidates={len(report["candidates"])}, exact_matches={len(matches)}). '
    +'Inspect outputs/source_identity/publication_run_selection.json; refuses to mix or guess source datasets.')
 return matches[0]

def choose_pinned_phase3(sources, expected_sha, diagnostics_path=None):
 report={'selection_policy':'unique Phase 3 source file matching pinned v0.7 SHA256', 'candidates':[],'selected':None}
 matches=[]
 for p in sorted(map(Path,sources)):
  sha=sha_file(p) if p.is_file() else None
  report['candidates'].append({'path':str(p),'observed_sha256':sha,'sha256_match':sha==expected_sha})
  if sha==expected_sha:matches.append(p)
 report['matching_candidate_count']=len(matches)
 if len(matches)==1:
  report['status']='PINNED_PHASE3_SOURCE_IDENTIFIED';report['selected']=str(matches[0])
 else:report['status']='PINNED_PHASE3_SOURCE_AMBIGUOUS_OR_MISSING'
 if diagnostics_path is not None:dump(diagnostics_path,report)
 if len(matches)!=1:
  raise RuntimeError('Pinned original Phase 3 source selection failed: '+report['status']+
     '. Inspect outputs/source_identity/phase3_source_selection.json.')
 return matches[0]

def audit(base,out,minimum=20,pinned_inputs=None):
 base=Path(base).resolve();out=Path(out).resolve();al=base/AL
 geom=al/'results/production_500/geometry_validation'
 if pinned_inputs is None:
  pinned_inputs=Path(__file__).resolve().parent.parent/'frozen/v07_input_hashes.json'
 pinned=json.loads(Path(pinned_inputs).read_text())
 if set(pinned)!=set(SOURCE_TABLES)|set(PUBLICATION_MEMBERS)|{'original_phase3_source'}:
  raise RuntimeError('Unexpected pinned input keys; refusing unreviewed dataset')
 pub_candidates=sorted((al/'results').glob('publication_phase1e_context_order1_*'))
 pub=choose_pinned_publication(pub_candidates,pinned,out/'publication_run_selection.json')
 old_candidates=sorted((al/'geom_scope_phase1_uma/results_phase3_final').glob('final_study_*/source_pair_measurements.jsonl'))
 old=choose_pinned_phase3(old_candidates,pinned['original_phase3_source'],out/'phase3_source_selection.json')
 paths={k:al/p for k,p in SOURCE_TABLES.items()}
 paths.update({'original_phase3_source':old,'manifest':pub/'full500_manifest.csv',
  'initial':pub/'initial_structures.jsonl','endpoint_b1':pub/'b1/endpoints.jsonl',
  'endpoint_inflight':pub/'inflight_b4/endpoints.jsonl'})
 for name,p in paths.items():
  if not p.is_file():raise FileNotFoundError(f'{name}: {p}')
 fingerprints={name:{'path':str(p),'sha256':sha_file(p),'bytes':p.stat().st_size} for name,p in paths.items()}
 if pinned_inputs is not None:
  if set(pinned)!=set(fingerprints):raise RuntimeError('PINNED INPUT KEYS CHANGED — refuses unreviewed source tree')
  wrong={name:{'wanted':sha,'observed':fingerprints[name]['sha256']} for name,sha in pinned.items() if fingerprints[name]['sha256']!=sha}
  if wrong:raise RuntimeError('PINNED INPUT SHA256 MISMATCH: '+json.dumps(wrong,sort_keys=True))
 structures={name:unique_index(extxyz_frames(paths[name]),name) for name in ('b1_xyz','inflight_xyz')}
 tables={name:unique_index(csv_rows(paths[name]),name) for name in ('b1_csv','inflight_csv','geometry_comparison','manifest')}
 init=unique_index(jsonl_rows(paths['initial'],only=('sid','system_id','config_id','sample_idx','coordinate_sha256')), 'initial')
 ends={name:unique_index(jsonl_rows(paths[name],only=('sid','system_id','config_id','sample_idx','n_atoms','n_mobile','initial_coordinate_sha256','coordinate_sha256','force_threshold_eV_A','fixed_drift_A')),name) for name in ('endpoint_b1','endpoint_inflight')}
 # Only read Phase 3 system IDs; do not parse earlier gold or proof labels.
 prior_rows=jsonl_rows(paths['original_phase3_source'],only=('system_id',))
 if not prior_rows or any(not x['system_id'] for x in prior_rows):raise RuntimeError('Original Phase 3 system IDs unavailable. No nonoverlap claim possible.')
 old_systems={str(x['system_id']) for x in prior_rows}
 allkeys=set().union(*(set(d) for d in [*structures.values(),*tables.values(),init,*ends.values()]))
 rejected=collections.Counter();joined=[];eligible=[]
 for sid in sorted(allkeys):
  sources={**structures,**tables,'initial':init,**ends}
  missing=[name for name,index in sources.items() if sid not in index]
  present=[x[sid] for x in sources.values() if sid in x]
  systems={str(x.get('system_id')) for x in present if x.get('system_id')}
  reasons=[]
  if missing:reasons.append('missing_join_members')
  if len(systems)!=1:reasons.append('conflicting_system_ids')
  sys=next(iter(systems)) if len(systems)==1 else None
  if sys in old_systems:reasons.append('original_phase3_system_overlap')
  if not missing:
   x=structures['b1_xyz'][sid];y=structures['inflight_xyz'][sid]
   if x['n_atoms']!=y['n_atoms'] or x['species_order_sha256']!=y['species_order_sha256']:reasons.append('atom_order_mismatch')
   if x['atom_metadata_sha256']!=y['atom_metadata_sha256']:reasons.append('atom_masks_or_tags_mismatch')
   if not same_cell(x['cell'],y['cell']):reasons.append('cell_mismatch')
   if x['pbc']!=y['pbc']:reasons.append('pbc_mismatch')
   if not x['n_mobile'] or not x['n_tags_2']:reasons.append('empty_mobile_or_adsorbate_mask')
   for name in ('b1_csv','inflight_csv'):
    r=tables[name][sid]
    if str(r.get('n_atoms')) !=str(x['n_atoms']):reasons.append(name+'_n_atoms_conflict')
    if not bool_true(r.get('converged')):reasons.append(name+'_not_converged')
    force=finite_float(r.get('final_fmax_eV_A'))
    if force is None:reasons.append(name+'_missing_force')
    elif force>=0.05:reasons.append(name+'_force_ge_0p05')
   for name in ('initial','endpoint_b1','endpoint_inflight'):
    if str((init if name=='initial' else ends[name])[sid].get('system_id'))!=sys:
     reasons.append(name+'_system_conflict')
   b1,i=ends['endpoint_b1'][sid],ends['endpoint_inflight'][sid]
   if str(b1.get('config_id'))!=str(i.get('config_id')) or str(b1.get('config_id'))!=str(init[sid].get('config_id')):reasons.append('config_id_mismatch')
   if not b1.get('initial_coordinate_sha256') or b1.get('initial_coordinate_sha256')!=i.get('initial_coordinate_sha256'):
    reasons.append('initial_hash_mismatch_or_missing')
   if init[sid].get('coordinate_sha256') and b1.get('initial_coordinate_sha256')!=init[sid].get('coordinate_sha256'):
    reasons.append('initial_record_hash_conflict')
   if str(b1.get('n_atoms'))!=str(x['n_atoms']) or str(i.get('n_atoms'))!=str(x['n_atoms']):reasons.append('endpoint_atom_count_conflict')
   if str(b1.get('n_mobile'))!=str(x['n_mobile']) or str(i.get('n_mobile'))!=str(x['n_mobile']):reasons.append('endpoint_mobile_count_conflict')
   if str(tables['geometry_comparison'][sid].get('n_atoms'))!=str(x['n_atoms']):reasons.append('geometry_comparison_n_atoms_conflict')
  reasons=sorted(set(reasons))
  for reason in reasons:rejected[reason]+=1
  row={'sid':sid,'system_id':sys,'status':'PRELIMINARY_CANDIDATE' if not reasons else 'NOT_CANDIDATE',
       'reasons':reasons,'is_old_group':sys in old_systems,'missing_members':missing}
  if not missing:
   row.update({'config_id':ends['endpoint_b1'][sid].get('config_id'),
    'b1_frame_index':structures['b1_xyz'][sid]['frame_index'],
    'inflight_frame_index':structures['inflight_xyz'][sid]['frame_index'],
    'n_atoms':structures['b1_xyz'][sid]['n_atoms'],
    'n_mobile':structures['b1_xyz'][sid]['n_mobile'],
    'n_adsorbate_tag2':structures['b1_xyz'][sid]['n_tags_2'],
    'initial_coordinate_sha256':ends['endpoint_b1'][sid].get('initial_coordinate_sha256'),
    'b1_positions_sha256':structures['b1_xyz'][sid]['positions_sha256'],
    'inflight_positions_sha256':structures['inflight_xyz'][sid]['positions_sha256'],
    'convergence':{k:{'converged':tables[k][sid].get('converged'),
     'final_fmax_eV_A':tables[k][sid].get('final_fmax_eV_A')} for k in ('b1_csv','inflight_csv')}})
  joined.append(row)
  if not reasons:eligible.append(row)
 selected=stable_select(eligible,minimum)
 dump(out/'source_files_sha256.json',fingerprints)
 (out/'identity_joined_rows.jsonl').parent.mkdir(parents=True,exist_ok=True)
 with (out/'identity_joined_rows.jsonl').open('w') as f:
  for x in joined:f.write(json.dumps(x,sort_keys=True)+'\n')
 dump(out/'prospective_holdout_manifest.json',{
   'label':'PRELIMINARY_ELIGIBILITY_ONLY_NOT_FINAL_PHYSCHEM_VALIDATED',
   'selection_seed':SEED,'selection_policy':'hash-order distinct system_id; within-system hash-order sid; no RMSD or model outcomes used',
   'target_system_count':minimum,'selection_count':len(selected),
   'locked_policy':'GeoScope v0.5 operation-only repair (not applied to sources)',
   'candidates':selected})
 source_key_sets=[set(v) for v in [*structures.values(),*tables.values(),init,*ends.values()]]
 status='IDENTITY_JOIN_FAILURE' if (not all(len(v)==500 for v in [*structures.values(),*tables.values(),init,*ends.values()]) or any(keys!=source_key_sets[0] for keys in source_key_sets[1:])) else ('CANDIDATES_PENDING_PHYSICS_VALIDATION' if len(selected)>=minimum else 'INSUFFICIENT_CANDIDATES')
 counts={'all_source_keys':len(allkeys),'b1_frames':len(structures['b1_xyz']),
  'inflight_frames':len(structures['inflight_xyz']),
  'source_id_sets_match':len(set(structures['b1_xyz']) & set(structures['inflight_xyz'])),
  'unique_candidate_systems':len({x['system_id'] for x in eligible}),
  'preliminary_candidate_configurations':len(eligible),
  'prior_phase3_records':len(prior_rows),'prior_phase3_unique_systems':len(old_systems),
  'alchemi_unique_systems':len({x['system_id'] for x in joined if x['system_id']}),
  'source_keys_overlapping_old_phase3':sum(x['is_old_group'] for x in joined),
  'heldout_selected_systems':len(selected),
  'full_atomic_geometry_validated':False,'final_independence_certified':False}
 summary={'status':status,'generated_utc':datetime.now(timezone.utc).isoformat(),
  'counts':counts,'rejection_reasons':dict(sorted(rejected.items())),
  'independence_scope':'No system_id overlap with prior Phase 3; all data remain from original parent ALCHEMI collection',
  'limitations':['Source join and convergence/mask checks only; per-atom correspondence, topology and unwrapping need separate audits',
     'Source IDs and initial coordinate hashes are checked from same ALCHEMI namespace; coordinate fingerprint cross-study remains to validate',
     'Prior Phase 3 records are read only for system_id; no sealed target labels were read',
     'Prospective sample is not certified until full physical audit',
     'No new inference, no DFT, no UMA, no change to frozen repair'],
  'input_sha256s':{k:v['sha256'] for k,v in fingerprints.items()}}
 dump(out/'identity_summary.json',summary)
 return summary

def main():
 p=argparse.ArgumentParser();p.add_argument('--base',default='/lustre/work/ock/oissakah10');p.add_argument('--out',default='outputs/source_identity');p.add_argument('--min-systems',type=int,default=20)
 args=p.parse_args()
 if args.min_systems<20:raise ValueError('Holdout goal must be at least 20')
 r=audit(args.base,args.out,args.min_systems,Path(__file__).resolve().parent.parent/'frozen/v07_input_hashes.json')
 print(json.dumps({k:r[k] for k in ('status','counts','rejection_reasons')},indent=2))
 if r['status']!='CANDIDATES_PENDING_PHYSICS_VALIDATION':raise SystemExit('Source audit not eligible for physical-validation stage; review JSON')
 print('PASS: preliminary prospective source identities only; NO independent physical source certified.')
if __name__=='__main__':main()
