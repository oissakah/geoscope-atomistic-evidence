"""Secondary independent RMSD assessment of molecular internal geometry.
The bond graph uses conventional covalent-radius cutoffs. Independent of GeoScope modules.
"""
from pathlib import Path
import zipfile,json,numpy as np,itertools,math
z=zipfile.ZipFile(Path(__file__).resolve().parents[1]/'source_archives'/'GeoScope_Phase4_v1_5_OC20_external_gate_results_20261023T142306Z.zip')
sources=[json.loads(x) for x in z.read('outputs/external_oc20_source/selected_atomic_pairs_PRIVATE.jsonl').splitlines()]
ref={s['sid']:s['real_metrics_A'] for s in json.loads(z.read('outputs/external_oc20_source/selected_source_audit_PRIVATE.json'))}
radii={'H':0.31,'C':0.76,'N':0.71,'O':0.66}
check=[]
for entry in sources:
 a=entry['b1'];b=entry['inflight'];x=np.array(a['positions']);y=np.array(b['positions']);cell=np.array(a['cell']);inv=np.linalg.inv(cell);axes=np.array(a['pbc'],dtype=bool)
 ids=[i for i,t in enumerate(a['tags']) if t==2]
 def near(v):
  nearest=np.rint(v@inv)*axes
  images=(v-(nearest+np.array(d))@cell for d in itertools.product(*[(-1,0,1) if flag else (0,) for flag in axes]))
  return min(images,key=lambda q:q@q)
 def graph(q):
  edges={k:[] for k in ids}
  for u,v in itertools.combinations(ids,2):
   dis=near(q[v]-q[u]); cutoff=1.25*(radii[a['symbols'][u]]+radii[a['symbols'][v]])
   if 0.20<np.linalg.norm(dis)<=cutoff:
    edges[u].append(v);edges[v].append(u)
  return edges
 ga=graph(x); gb=graph(y)
 def unwrap(q,g):
  known={ids[0]:np.asarray(q[ids[0]],float)};queue=[ids[0]]
  while queue:
   here=queue.pop(0)
   for nbr in sorted(g[here]):
    if nbr not in known:
     known[nbr]=known[here]+near(q[nbr]-q[here]);queue.append(nbr)
  return np.array([known[i] for i in ids]) if len(known)==len(ids) else None
 xa=unwrap(x,ga);yb=unwrap(y,gb)
 status='PASS' if xa is not None and yb is not None and {tuple(sorted((i,j))) for i in ga for j in ga[i]}=={tuple(sorted((i,j))) for i in gb for j in gb[i]} else 'REVIEW_BOND_GRAPH'
 if status=='PASS':
  u=xa-xa.mean(0);v=yb-yb.mean(0);left,s,right=np.linalg.svd(u.T@v)
  rot=left @ np.diag([1,1,np.linalg.det(left@right)])@right
  rms=float(np.sqrt(np.mean(np.sum((u@rot-v)**2,axis=1))))
  expected=ref[entry['sid']]['internal_rmsd_A']
  error=abs(rms-expected)
 else:rms=expected=error=None
 check.append({'sid':entry['sid'],'adsorbate_atoms':len(ids),'status':status,'computed_A':rms,'archived_A':expected,'abs_error_A':error})
print('N',len(check),'passes',sum(a['status']=='PASS' for a in check),'maxerror',max((a['abs_error_A'] for a in check if a['abs_error_A'] is not None),default=-1),'mismatches >1e-6', [a for a in check if a['abs_error_A'] and a['abs_error_A']>1e-6][:5])
(Path(__file__).resolve().parents[1]/'audit_results'/'internal_multiatom_checks.json').write_text(json.dumps(check,indent=2)+'\n')
