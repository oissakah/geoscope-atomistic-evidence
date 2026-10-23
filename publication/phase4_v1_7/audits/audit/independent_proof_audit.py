#!/usr/bin/env python3
"""Independent arithmetic/definition checker on structured presentations.
Never imports or calls GeoScope proof enumeration. Does not parse report prose:
paired report gold consistency is checked by matching base_case_id.
"""
import collections,math,re,json,zipfile
from pathlib import Path
Z=zipfile.ZipFile(Path(__file__).resolve().parents[1]/'source_archives'/'GeoScope_Phase4_v1_6_OC20_FOURMODEL_results_20261023T165627Z.zip')
cs=json.loads(Z.read('SEALED_REVIEW_ONLY/public_cases.json'));ref={x['case_id']:x for x in json.loads(Z.read('SEALED_REVIEW_ONLY/gold_proofs_SEALED.json'))}


def independent_witnesses(c):
 payload=c['model_payload'];p=payload['evidence_packet'];claim=payload['claim'];pair=re.search(r'endpoint pair (P_[a-z0-9]+)',claim).group(1)
 m=re.search(r'is at (most|least) ([0-9.eE+-]+) (angstrom|nm)',claim)
 if not m:raise ValueError(claim)
 is_at_most=m.group(1)=='most';threshold=float(m.group(2))*(10 if m.group(3)=='nm' else 1)
 target=c['target_metric'];sets=p['atom_sets']; allowed={'mobile_rmsd':('mobile','shared stored slab coordinate frame','none'), 'adsorbate_frame_rmsd':('adsorbate','shared stored slab coordinate frame','none'), 'internal_rmsd':('adsorbate','independent molecular centroids','proper Kabsch rotation plus translation; no reflection')}
 target_ix,target_frame,target_align=allowed[target]
 witnesses=[]
 for ev in p['measurements']:
  if ev['pair_id']!=pair or ev['metric_id'] not in allowed:continue
  ix,frame,align=allowed[ev['metric_id']];d=ev['definition']
  if d['atom_indices']!=sets[ix] or d['frame']!=frame or d['alignment']!=align or d['weighting']!='equal weight per selected atom':continue
  if ev['unit'] not in ('angstrom','nm'):continue
  v=float(ev['value'])*(10 if ev['unit']=='nm' else 1)
  if not math.isfinite(v):continue
  if ev['metric_id']==target:
   operation='value';lower=upper=v
  elif target=='mobile_rmsd' and ev['metric_id']=='adsorbate_frame_rmsd':
   if not set(sets['adsorbate']).issubset(set(sets['mobile'])):continue
   operation='mobile_lower';lower=v*math.sqrt(len(sets['adsorbate'])/len(sets['mobile']));upper=float('inf')
  elif target=='adsorbate_frame_rmsd' and ev['metric_id']=='mobile_rmsd':
   if not set(sets['adsorbate']).issubset(set(sets['mobile'])):continue
   operation='adsorbate_upper';lower=0.;upper=v*math.sqrt(len(sets['mobile'])/len(sets['adsorbate']))
  else:continue
  # no equality tie cases expected by benchmark threshold design
  verdict=None
  if is_at_most:
   if upper<=threshold:verdict='SUPPORTED'
   elif lower>threshold:verdict='CONTRADICTED'
  else:
   if lower>=threshold:verdict='SUPPORTED'
   elif upper<threshold:verdict='CONTRADICTED'
  if verdict:witnesses.append((ev['evidence_id'],operation,verdict))
 return sorted(witnesses)

struct=[c for c in cs if c['presentation']=='structured']
errors=[];bybase=collections.defaultdict(list)
for c in cs:bybase[c['base_case_id']].append(c)
for c in struct:
 found=independent_witnesses(c);expected=sorted((x['evidence_ids'][0],x['operation'],x['verdict']) for x in ref[c['case_id']]['valid_proofs'])
 if found!=expected:errors.append({'case_id':c['case_id'],'found':found,'expected':expected,'family':c['family']})
for base,items in bybase.items():
 assert len(items)==2
 a,b=items;pa=ref[a['case_id']];pb=ref[b['case_id']]
 assert pa['expected']==pb['expected'] and sorted((p['operation'],p['verdict']) for p in pa['valid_proofs'])==sorted((p['operation'],p['verdict']) for p in pb['valid_proofs'])
result={'independent_arithmetic_rule_engine':'standalone proof enumeration on structured payloads; no GeoScope function imports', 'structured_cases_checked':len(struct),'structured_cases_proof_exact_matches':len(struct)-len(errors),'mismatches':errors[:25], 'paired_report_cases_same_gold_by_base':len(bybase), 'limitations':['Independent checker shares the same declared physical axioms; not ground truth external to the benchmark.','Report text not independently parsed or proof-enumerated, although paired proof-key correspondence was verified.','Floating-point near-equality boundaries not specially tested.']}
(Path(__file__).resolve().parents[1]/'audit_results'/'INDEPENDENT_PROOF_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='mismatches'},indent=2));print('first errors',errors[:2])
if errors:raise SystemExit(1)
