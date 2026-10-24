"""Frozen 20-system ALCHEMI atomic-geometry diagnostics.

Reads only existing structures and the fixed v0.9 candidate list. All geometric
results here are recomputations and descriptive comparisons, NOT model outputs or
certification of chemically independent systems.

Requires NumPy (already available in Swan Python 3.9). Does not use ASE or GPU.
"""
from __future__ import annotations
import argparse,collections,csv,hashlib,json,math,itertools,os,shlex
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from .source_identity import property_slots,parse_comment,sha_file,dump,unique_index,csv_rows,same_cell

LIMIT_ATOMS=10000
TOL=1e-5
COVALENT_RADII={'H':0.31,'C':0.76,'N':0.71,'O':0.66,'F':0.57,'P':1.07,'S':1.05,
 'B':0.85,'Cl':1.02,'Br':1.20,'I':1.39,'Si':1.11,'Li':1.28,'Na':1.66,'K':2.03,
 'Cu':1.32,'Ni':1.24,'Fe':1.32,'Pt':1.36,'Pd':1.39,'Co':1.26,'Zn':1.22}

def read_selected_extxyz(path,wanted):
 """Strictly parse selected frames, keeping all atom data only for the pinned IDs."""
 out={}; index=0
 with Path(path).open('r',encoding='utf8') as fh:
  while True:
   line=fh.readline()
   if not line:break
   if not line.strip():continue
   n=int(line.strip()); head=fh.readline()
   if not head or not 0<n<=LIMIT_ATOMS:raise ValueError('Bad EXTXYZ frame count/boundary')
   h=parse_comment(head); slots,num=property_slots(h.get('Properties',''))
   sid=h.get('sid');sys=h.get('system_id')
   if not sid or not sys:raise ValueError('Missing source identity in EXTXYZ')
   cell=np.array([float(x) for x in h.get('Lattice','').split()],float)
   if cell.size!=9 or not np.all(np.isfinite(cell)):raise ValueError('Bad cell')
   cell=cell.reshape(3,3)
   if abs(float(np.linalg.det(cell)))<1e-8:raise ValueError('Singular cell')
   pbc=h.get('pbc','').split()
   if len(pbc)!=3 or set(pbc)-{'T','F'}:raise ValueError('Invalid pbc')
   symbols=[];positions=[];mask=[];tags=[]
   for k in range(n):
    data=fh.readline().split()
    if len(data)!=num:raise ValueError(f'Bad atomic properties sid={sid}, index={k}')
    def take(key):a,b,_=slots[key];return data[a:b]
    symbols.append(take('species')[0]); xyz=[float(x) for x in take('pos')]
    if not all(math.isfinite(x) for x in xyz):raise ValueError('Nonfinite position')
    positions.append(xyz)
    m=take('move_mask')[0]
    if m not in ('T','F','True','False','1','0'):raise ValueError('Invalid move mask')
    mask.append(m in ('T','True','1'))
    tags.append(int(take('tags')[0]))
   if sid in wanted:
    if sid in out:raise ValueError('Duplicate sid='+sid)
    digest=hashlib.sha256(json.dumps([symbols,positions],separators=(',',':')).encode()).hexdigest()
    out[sid]={'sid':sid,'system_id':sys,'frame_index':index,'symbols':symbols,'positions':positions,
     'move_mask':mask,'tags':tags,'cell':cell.tolist(),'pbc':[p=='T' for p in pbc],
     'positions_sha256':digest}
   index+=1
 return out,index

def metric(displacements,chosen):
 if not chosen:return None
 norm=np.linalg.norm(np.asarray(displacements,float)[list(chosen)],axis=1)
 return {'rmsd_A':float(np.sqrt(np.mean(norm**2))), 'max_displacement_A':float(np.max(norm))}

def minimum_image_displacements(x,y,cell,pbc):
 """Search nearest lattice offsets around fractional rounded displacement.

 For skew cells this is an approximation to the closest lattice vector, and
 the output is ALWAYS labeled diagnostic, not a general PBC guarantee.
 """
 cell=np.asarray(cell,float); d=np.asarray(y,float)-np.asarray(x,float)
 frac=d @ np.linalg.inv(cell)
 shift=np.rint(frac).astype(int)
 for i,active in enumerate(pbc):
  if not active:shift[:,i]=0
 choices=[(-1,0,1) if v else (0,) for v in pbc]
 best=None; best_norm=None
 for vec in itertools.product(*choices):
  trial=d-(shift+np.array(vec,dtype=int))@cell
  norm=np.sum(trial**2,axis=1)
  if best is None:
   best=trial.copy();best_norm=norm
  else:
   pick=norm<best_norm
   best[pick]=trial[pick];best_norm[pick]=norm[pick]
 return best

def bonds(pos,sym,indices,cell,pbc):
 """Heuristic covalent-bond graph for diagnostics (not a chemical topology oracle)."""
 g=set(); unknown=[]; pos=np.asarray(pos,float)
 for a,b in itertools.combinations(indices,2):
  if sym[a] not in COVALENT_RADII or sym[b] not in COVALENT_RADII:
   unknown.extend([sym[a],sym[b]]);continue
  dr=minimum_image_displacements(pos[[a]],pos[[b]],cell,pbc)[0]
  r=float(np.linalg.norm(dr))
  if r <= 1.25*(COVALENT_RADII[sym[a]]+COVALENT_RADII[sym[b]]) and r>0.20:
   g.add((a,b))
 return g,sorted(set(unknown))

def connected(indices,graph):
 if len(indices)<2:return bool(indices)
 edges=collections.defaultdict(set)
 for a,b in graph:edges[a].add(b);edges[b].add(a)
 seen={indices[0]};stack=[indices[0]]
 while stack:
  for v in edges[stack.pop()]:
   if v not in seen:seen.add(v);stack.append(v)
 return len(seen)==len(indices)

def unwrap_positions(pos,indices,edges,cell,pbc):
 pos=np.asarray(pos,float)
 seen={indices[0]:pos[indices[0]]};stack=[indices[0]]
 edge_map=collections.defaultdict(set)
 for i,j in edges:edge_map[i].add(j);edge_map[j].add(i)
 while stack:
  i=stack.pop()
  for j in edge_map[i]:
   if j not in seen:
    shift=minimum_image_displacements(pos[[i]],pos[[j]],cell,pbc)[0]
    seen[j]=seen[i]+shift;stack.append(j)
 return np.array([seen[i] for i in indices]) if len(seen)==len(indices) else None

def kabsch_rmsd(x,y):
 x=np.asarray(x,float);y=np.asarray(y,float)
 if x.shape!=y.shape or x.ndim!=2 or x.shape[1]!=3 or not len(x):raise ValueError('Invalid shape')
 xc=x-x.mean(axis=0);yc=y-y.mean(axis=0)
 u,s,vt=np.linalg.svd(xc.T@yc)
 r=u@vt
 if np.linalg.det(r)<0:
  u[:,-1]*=-1
  r=u@vt
 return float(np.sqrt(np.mean(np.sum((xc@r-yc)**2,axis=1))))

def compare_pair(a,b,table):
 sid=a['sid']
 if sid!=b['sid'] or a['system_id']!=b['system_id']:raise ValueError('Source ID mismatch')
 for key in ('symbols','move_mask','tags','pbc'):
  if a[key]!=b[key]:raise ValueError(f'{sid}: atomic metadata {key} mismatch')
 if not same_cell(sum(a['cell'],[]),sum(b['cell'],[])):
  raise ValueError(f'{sid}: geometry cells differ')
 symbols=a['symbols']; n=len(symbols)
 ix={'all':list(range(n)),
     'mobile':[j for j,v in enumerate(a['move_mask']) if v],
     'adsorbate':[j for j,t in enumerate(a['tags']) if t==2],
     'fixed':[j for j,v in enumerate(a['move_mask']) if not v]}
 if not ix['mobile'] or not ix['adsorbate'] or not ix['fixed']:
  raise ValueError('Missing required atom masks')
 direct=np.array(b['positions'],float)-np.array(a['positions'],float)
 mic=minimum_image_displacements(a['positions'],b['positions'],a['cell'],a['pbc'])
 values={}
 for family,displacements in [('direct',direct),('minimum_image_diagnostic',mic)]:
  values[family]={kind:metric(displacements,atoms) for kind,atoms in ix.items()}
 comparison={}
 for kind in ('all','mobile','adsorbate'):
  for source,reported in [('rmsd_A','rmsd_'+kind+'_A'),('max_displacement_A','max_displacement_'+kind+'_A')]:
   expected=float(table[reported]);got=values['direct'][kind][source]
   micvalue=values['minimum_image_diagnostic'][kind][source]
   tolerance=max(1e-4,1e-3*abs(expected))
   comparison[reported]={'reported_A':expected,'recomputed_direct_A':got,
                          'recomputed_mic_diagnostic_A':micvalue,
                          'direct_matches_within_tolerance':abs(got-expected)<=tolerance,
                          'mic_matches_within_tolerance':abs(micvalue-expected)<=tolerance,
                          'direct_abs_error_A':abs(got-expected), 'tolerance_A':tolerance}
 ads=ix['adsorbate']; ba,unk1=bonds(a['positions'],symbols,ads,a['cell'],a['pbc'])
 bb,unk2=bonds(b['positions'],symbols,ads,b['cell'],b['pbc'])
 ca,cb=connected(ads,ba),connected(ads,bb)
 internal={'method':'heuristic-bond-unwrapped_Kabsch_diagnostic','value_A':None,
           'connected_b1':ca,'connected_inflight':cb,'bond_graph_matches':ba==bb,
           'n_bonds_b1':len(ba),'n_bonds_inflight':len(bb),
           'unknown_covalent_radii':sorted(set(unk1+unk2))}
 if len(ads)==1:internal['value_A']=0.0
 elif ca and cb and not internal['unknown_covalent_radii']:
  x=unwrap_positions(a['positions'],ads,ba,a['cell'],a['pbc'])
  y=unwrap_positions(b['positions'],ads,bb,b['cell'],b['pbc'])
  if x is not None and y is not None:internal['value_A']=kabsch_rmsd(x,y)
 warnings=[]
 if not all(p['direct_matches_within_tolerance'] for p in comparison.values()):warnings.append('stored_geometry_values_do_not_match_direct_coordinates')
 if not all(p['mic_matches_within_tolerance'] for p in comparison.values()):warnings.append('MIC_diagnostic_differs_from_stored_geometry_values')
 if not internal['bond_graph_matches']:warnings.append('heuristic_adsorbate_bond_graph_changed')
 if not ca or not cb:warnings.append('adsorbate_heuristic_bond_graph_disconnected')
 if internal['unknown_covalent_radii']:warnings.append('unknown_covalent_radii')
 if values['direct']['fixed']['max_displacement_A']>0.02:warnings.append('fixed_atom_drift_gt_0p02_A')
 return {'sid':sid,'system_id':a['system_id'],'n_atoms':n,'counts':{k:len(v) for k,v in ix.items()},
     'metrics':values,'stored_geometry_comparison':comparison,'internal_alignment_diagnostic':internal,
     'warnings':warnings,'source_structure_hashes':{'b1':a['positions_sha256'],'inflight':b['positions_sha256']}}

def safe_source_path(base,value):
 p=Path(value).resolve();b=Path(base).resolve()
 if os.path.commonpath([str(p),str(b)])!=str(b):raise ValueError('Source path outside permitted Swan work root')
 if not p.is_file():raise FileNotFoundError(str(p))
 return p

def run(base,out,frozen):
 base=Path(base).resolve();out=Path(out).resolve();frozen=Path(frozen).resolve()
 manifest=json.loads((frozen/'v09_prospective_holdout_manifest.json').read_text())
 summary=json.loads((frozen/'v09_identity_summary.json').read_text())
 paths=json.loads((frozen/'v09_source_files_sha256.json').read_text())
 selected=manifest['candidates']
 if len(selected)!=20 or len({r['sid'] for r in selected})!=20 or len({r['system_id'] for r in selected})!=20:
  raise RuntimeError('FROZEN HOLDOUT MISMATCH — expected exactly 20 distinct source IDs and systems')
 if manifest['label']!='PRELIMINARY_ELIGIBILITY_ONLY_NOT_FINAL_PHYSCHEM_VALIDATED':
  raise RuntimeError('Unexpected parent screening status')
 if summary['counts']['heldout_selected_systems']!=20:
  raise RuntimeError('Frozen parent summary conflicts with manifest')
 required=['b1_xyz','inflight_xyz','geometry_comparison','manifest','initial','endpoint_b1','endpoint_inflight','b1_csv','inflight_csv','original_phase3_source']
 if set(paths)!=set(required):raise RuntimeError('Changed pinned source file inventory')
 verified={}
 for key in required:
  p=safe_source_path(base,paths[key]['path']);observed=sha_file(p)
  if observed!=paths[key]['sha256']:raise RuntimeError(f'PINNED SHA256 MISMATCH: {key} at {p}')
  verified[key]=str(p)
 dump(out/'source_hash_verification.json',{'status':'PASS','verified_sha256':{k:paths[k]['sha256'] for k in required}})
 wants={r['sid'] for r in selected}
 x,nx=read_selected_extxyz(verified['b1_xyz'],wants)
 y,ny=read_selected_extxyz(verified['inflight_xyz'],wants)
 if nx!=500 or ny!=500 or set(x)!=wants or set(y)!=wants:raise RuntimeError('EXTXYZ selected-id mismatch')
 tab=unique_index(csv_rows(Path(verified['geometry_comparison'])),'geometry_comparison')
 main=unique_index(csv_rows(Path(verified['manifest'])),'manifest')
 items=[];sample=[];warn=collections.Counter()
 for r in selected:
  sid=r['sid'];a=x[sid];b=y[sid]
  if a['frame_index']!=r['b1_frame_index'] or b['frame_index']!=r['inflight_frame_index']:
   raise RuntimeError('Frame index mismatch sid='+sid)
  if a['positions_sha256']!=r['b1_positions_sha256'] or b['positions_sha256']!=r['inflight_positions_sha256']:
   raise RuntimeError('Coordinate identity changed sid='+sid)
  if main[sid]['system_id']!=r['system_id']:raise RuntimeError('Manifest system ID mismatch '+sid)
  row=compare_pair(a,b,tab[sid]);row['mpid']=main[sid].get('mpid');row['adsorbate']=main[sid].get('adsorbate');row['miller_idx']=main[sid].get('miller_idx')
  for w in row['warnings']:warn[w]+=1
  items.append(row)
  # Preserve exact selected coordinates for independent review; not distributed publicly.
  sample.append({'sid':sid,'system_id':r['system_id'],'mpid':row['mpid'],'adsorbate':row['adsorbate'],'b1':a,'inflight':b})
 out.mkdir(parents=True,exist_ok=True)
 with (out/'physical_audit_rows.jsonl').open('w') as fh:
  for r in items:fh.write(json.dumps(r,sort_keys=True,allow_nan=False)+'\n')
 with (out/'selected_atomic_pairs.jsonl').open('w') as fh:
  for r in sample:fh.write(json.dumps(r,sort_keys=True,allow_nan=False)+'\n')
 comparison=collections.Counter()
 for row in items:
  for name,v in row['stored_geometry_comparison'].items():
   if v['direct_matches_within_tolerance']:comparison[name]+=1
  if row['internal_alignment_diagnostic']['value_A'] is not None:comparison['internal_rmsd_diagnostic_available']+=1
 report={'status':'PHYSICAL_DIAGNOSTICS_COMPLETE_REVIEW_REQUIRED',
  'generated_utc':datetime.now(timezone.utc).isoformat(),
  'selected_unique_systems':len(items),'selected_unique_mpids':len({r['mpid'] for r in items}),
  'selected_unique_adsorbates':len({r['adsorbate'] for r in items}),
  'selected_source_group_ids':len({r['system_id'] for r in items}),
  'selected_atomic_configuration_pairs':len(items),'warnings_by_type':dict(warn),
  'recomputed_direct_metric_match_count':dict(comparison),
  'records_with_no_warnings':sum(not r['warnings'] for r in items),
  'parent_eligibility':summary['counts'],
  'limitations':['Previously untested system IDs from same parent collection; not an external dataset',
    'B1 vs inflight methods are alternative relaxations of same starting configurations, not DFT reference truth',
    'Periodic minimum-image calculation uses local lattice search and is diagnostic for skewed cells',
    'Heuristic bond graphs and aligned RMSDs are not authoritative topology determinations',
    'No new inference or method tuning, and no independent human-reviewed validation'],
  'next_gate':'Review reported-vs-recomputed metrics, warnings, topology, PBC treatment, source diversity, and provenance before constructing benchmark.'}
 dump(out/'physical_audit_summary.json',report)
 return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--base',default='/lustre/work/ock/oissakah10');p.add_argument('--out',default='outputs/physical_validation');a=p.parse_args()
 frozen=Path(__file__).resolve().parent.parent/'frozen'
 print(json.dumps(run(a.base,a.out,frozen),indent=2))
if __name__=='__main__':main()
