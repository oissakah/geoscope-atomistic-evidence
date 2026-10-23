#!/usr/bin/env python3
"""Read-only, independently authored checks on the frozen GeoScope archives.
Requires only Python and NumPy. Does not import GeoScope scientific code.
"""
from pathlib import Path
import collections,csv,datetime,hashlib,io,itertools,json,math,zipfile,re,os
import numpy as np

BASE=Path(os.environ.get('GEOSCOPE_ARCHIVE_DIR',str(Path(__file__).resolve().parents[1]/'source_archives')))
OUT=Path(__file__).resolve().parents[1]/'audit_results';OUT.mkdir(exist_ok=True)
FILES={
 'original_results':'GeoScope_Phase4_RESULTS_20261022_172058.zip',
 'original_manuscript':'GeoScope_manuscript_updated_scientific_narrative.zip',
 'alc_holdout':'GeoScope_Phase4_v1_1_benchmark_results_20261022T202908Z.zip',
 'external_source':'GeoScope_Phase4_v1_5_OC20_external_gate_results_20261023T142306Z.zip',
 'four_model_results':'GeoScope_Phase4_v1_6_OC20_FOURMODEL_results_20261023T165627Z.zip',
 'four_model_analysis':'GeoScope_Phase4_v1_6_FOURMODEL_EXTERNAL_ANALYSIS.zip',
 'confidence_results':'GeoScope_Phase4_v1_7_CONFIDENCE_results_20261023T200515Z.zip',
 'confidence_analysis':'GeoScope_Phase4_v1_7_FOURMODEL_CONFIDENCE_ANALYSIS.zip',
 'oc20_source_gate_code':'GeoScope_Phase4_v1_5_2_OC20_IS2RES_external_gate.zip',
 'four_model_code':'GeoScope_Phase4_v1_6_1_OC20_fourmodel_GPU_fix.zip',
 'confidence_final_code':'GeoScope_Phase4_v1_7_4_OC20_confidence_slurm_pathfix.zip',
}

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk)
 return h.hexdigest()

def find(z,name):
 matches=[n for n in z.namelist() if n==name or n.endswith('/'+name)]
 assert len(matches)==1,(name,matches)
 return matches[0]

manifest={}
for label,filename in FILES.items():
 p=BASE/filename;assert p.is_file()
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  manifest[label]={'filename':filename,'bytes':p.stat().st_size,'sha256':sha(p),'zip_integrity':'PASS','members':len(z.namelist())}

with zipfile.ZipFile(BASE/FILES['external_source']) as source, zipfile.ZipFile(BASE/FILES['four_model_results']) as results,zipfile.ZipFile(BASE/FILES['four_model_analysis']) as analysis, zipfile.ZipFile(BASE/FILES['confidence_results']) as conf,zipfile.ZipFile(BASE/FILES['confidence_analysis']) as confanalysis:
 provenance=json.loads(source.read(find(source,'source_integrity.json')))
 selection=json.loads(source.read(find(source,'selected_source_audit_PRIVATE.json')))
 geometry=[json.loads(s) for s in source.read(find(source,'selected_atomic_pairs_PRIVATE.jsonl')).splitlines() if s]
 pairs=[json.loads(s) for s in source.read(find(source,'source_pair_records_PRIVATE.jsonl')).splitlines() if s]
 public=json.loads(results.read('SEALED_REVIEW_ONLY/public_cases.json'))
 sealed=json.loads(results.read('SEALED_REVIEW_ONLY/gold_proofs_SEALED.json'))
 status=json.loads(results.read('SEALED_REVIEW_ONLY/BUILD_STATUS.json'))
 model_summary=list(csv.DictReader(io.StringIO(analysis.read('model_comparison.csv').decode())))
 confidence=json.loads(confanalysis.read('CONFIDENCE_ANALYSIS.json'))
 confidence_summary=list(csv.DictReader(io.StringIO(confanalysis.read('summary.csv').decode())))
 # Independently hash-check every member listed in the collection manifests.
 collection_hash_counts={}
 for label,zfile in [('four_model_results',results),('confidence_results',conf)]:
  recorded=json.loads(zfile.read('COLLECTION_SHA256.json'))
  mismatches=[name for name,expected in recorded.items() if name not in zfile.namelist() or hashlib.sha256(zfile.read(name)).hexdigest()!=expected]
  assert not mismatches, (label,mismatches[:5])
  collection_hash_counts[label]=len(recorded)
 # Consistency and provenance
 assert provenance['verified_md5']==provenance['official_md5']
 assert len(selection)==len(geometry)==48
 assert len({x['sid'] for x in geometry})==48
 assert len(pairs)==96
 assert len({x['group_id'] for x in pairs})==48
 assert len({x['pair_id'] for x in pairs})==96
 assert collections.Counter(x['origin'] for x in pairs)=={'measured_endpoint_pair':48,'synthetic_control':48}
 assert len(public)==len(sealed)==1536
 assert len({x['case_id'] for x in public})==1536
 assert len({x['group_id'] for x in public})==48
 assert collections.Counter(x['presentation'] for x in public)=={'report':768,'structured':768}
 assert collections.Counter(x['expected'] for x in sealed)=={'SUPPORTED':480,'CONTRADICTED':480,'INSUFFICIENT_EVIDENCE':576}
 assert {x['case_id'] for x in public}=={x['case_id'] for x in sealed}
 assert all((len(x['valid_proofs'])>0)==(x['expected']!='INSUFFICIENT_EVIDENCE') for x in sealed)
 pub_by={x['case_id']:x for x in public}; gold_by={x['case_id']:x for x in sealed}
 assert all(pub_by[k]['group_id']==gold_by[k]['group_id'] for k in pub_by)
 for x in sealed:
  payload=pub_by[x['case_id']]['model_payload']; ids=({m['evidence_id'] for m in payload['evidence_packet']['measurements']} if 'evidence_packet' in payload else set(re.findall(r'Evidence ID: (E_[a-z0-9]+)',payload['evidence_report'])))
  assert all(set(p['evidence_ids'])<=ids and len(p['evidence_ids'])==1 for p in x['valid_proofs'])
 # Confirm each base case is represented once per presentation
 base=collections.defaultdict(list)
 for case in public:base[case['base_case_id']].append(case)
 assert len(base)==768 and all(len(v)==2 and {x['presentation'] for x in v}=={'report','structured'} for v in base.values())
 # Read all confidence lines and verify exact matches/uniqueness from archived status
 confidence_status=json.loads(conf.read(find(conf,'COLLECTION_STATUS.json')))
 # independent coords: enumerate neighboring images around rounded fractional displacement (robust for skew cell)
 refs={x['sid']:x for x in selection}
 frame_errors=[]; bond_errors=[]; anchor_movements=[]; atom_counts=[]; reason_counts=collections.Counter()
 for pair in geometry:
  a,b=pair['b1'],pair['inflight'];sid=pair['sid'];x=np.asarray(a['positions']);y=np.asarray(b['positions']);cell=np.asarray(a['cell']);pbc=np.asarray(a['pbc'],bool)
  assert a['symbols']==b['symbols'] and a['tags']==b['tags'] and a['pbc']==b['pbc']
  assert np.allclose(cell,b['cell'],atol=1e-9)
  assert a['fixed_indices']==b['fixed_indices']
  assert a['move_mask']==b['move_mask']
  assert all(not a['move_mask'][j] for j in a['fixed_indices'])
  assert all(bool(a['move_mask'][j])!=(j in a['fixed_indices']) for j in range(len(x)))
  atom_counts.append(len(x))
  raw=y-x; frac=raw@np.linalg.inv(cell);shift=np.rint(frac)*pbc
  dr=np.zeros_like(raw)
  for i in range(len(x)):
   choices=itertools.product(*[(-1,0,1) if p else (0,) for p in pbc]);dd=[raw[i]-(shift[i]+np.asarray(c))@cell for c in choices]
   dr[i]=min(dd,key=lambda v:v@v)
  tags=np.array(a['tags']);mask=np.array(a['move_mask'],bool)
  for lab,idx,reference in [('mobile',np.flatnonzero(mask),'mobile_rmsd_A'),('adsorbate',np.flatnonzero(tags==2),'adsorbate_frame_rmsd_A'),('anchor',np.flatnonzero(~mask),'anchor_rmsd_A')]:
   assert len(idx)>0
   computed=float(np.sqrt(np.mean(np.sum(dr[idx]**2,axis=1))))
   orig=float(refs[sid]['real_metrics_A'][reference]);frame_errors.append({'sid':sid,'measurement':reference,'independent_A':computed,'archived_A':orig,'abs_error_A':abs(computed-orig)})
  anchor_movements.append(float(np.linalg.norm(dr[~mask],axis=1).max()))
  ads=np.flatnonzero(tags==2)
  if len(ads)==2:
   ia,ib=ads
   def bondlength(v):
    frac=v@np.linalg.inv(cell);center=np.rint(frac)*pbc
    return min(np.linalg.norm(v-(center+np.array(c))@cell) for c in itertools.product(*[(-1,0,1) if p else (0,) for p in pbc]))
   d0=bondlength(x[ib]-x[ia]);d1=bondlength(y[ib]-y[ia]);got=abs(d1-d0)/2
   expect=float(refs[sid]['real_metrics_A']['internal_rmsd_A'])
   bond_errors.append({'sid':sid,'independent_A':got,'archived_A':expect,'abs_error_A':abs(got-expect),'n_adsorbate':2})
 assert max(v['abs_error_A'] for v in frame_errors)<1e-6
 assert max(v['abs_error_A'] for v in bond_errors)<1e-6
 assert max(anchor_movements)<0.02
 # Model tabulations from raw per-case audit rather than summary only
 cases=list(csv.DictReader(io.StringIO(analysis.read('per_case_comparison.csv').decode())))
 assert len(cases)==6144
 model_stats={}
 for key in ('qwen','phi','smol','qwen32b'):
  a=[r for r in cases if r['model']==key]
  assert len(a)==1536 and len({r['case_id'] for r in a})==1536
  answer=[r for r in a if r['answerable']=='True']
  insuff=[r for r in a if r['answerable']=='False']
  assert len(answer)==960 and len(insuff)==576
  res={'strict_correct':sum(r['strict_correct_proof']=='True' for r in answer),
   'normalized_correct':sum(r['normalized_correct_proof']=='True' for r in answer),
   'repaired_correct':sum(r['normalized_correct_after_repair']=='True' for r in answer),
   'correct_abstention':sum(r['normalized_correct_abstention']=='True' for r in insuff)}
  row=next(x for x in model_summary if x['model_key']==key)
  for fld in res:assert res[fld]==int(row[fld if fld!='repaired_correct' else 'repaired_correct']), (key,fld,res,row)
  model_stats[key]=res
 confrows=list(csv.DictReader(io.StringIO(confanalysis.read('confidence_per_case.csv').decode())))
 assert len(confrows)==6144
 for key in model_stats:
  check=[r for r in confrows if r['model']==key]
  assert len(check)==1536 and len({r['case_id'] for r in check})==1536
  assert all(r['exact_replay']=='True' and r['baseline_raw_sha256']==r['replay_raw_sha256'] for r in check)
  cstats=next(r for r in confidence_summary if r['model']==key)
  assert sum(r['decision_token_geomean']=='' for r in check if r['answerable']=='True')==int(cstats['n_missing_answerable'])

 # Confidence: integrity and previously recorded joins
 assert confidence['all_exact_replay'] and confidence['n_joined']==6144
 assert len(confidence_summary)==4

stats={'archive_integrity':{'checked':len(manifest),'all_pass':True,'member_sha256_checks':collection_hash_counts},
 'source_provenance':{'published_dataset':'OC20 IS2RE/IS2RS val_ood_both','official_md5':provenance['official_md5'], 'official_md5_verified_by_swan':provenance['verified_md5'],'external_trajectory_tar_sha256_reported_by_swan':provenance['source_sha256'], 'local_trajectory_tar_available_for_rehash':False},
 'source_geometry':{'systems':len(geometry),'real_and_synthetic_source_records':len(pairs),'real_frame_values_recomputed':len(frame_errors),'max_frame_rmsd_absolute_error_angstrom':max(x['abs_error_A'] for x in frame_errors),'two_atom_internal_rmsd_values_recomputed':len(bond_errors),'max_two_atom_internal_error_angstrom':max(x['abs_error_A'] for x in bond_errors),'non_two_atom_internal_rmsd_independently_recomputed':0,'maximum_fixed_atom_displacement_angstrom':max(anchor_movements),'atom_count_min_max':[min(atom_counts),max(atom_counts)],'human_review':'NOT_DONE'},
 'benchmark':{'source_groups':48,'source_pairs':96,'questions':len(public),'base_cases':len(base),'presentations':dict(collections.Counter(x['presentation'] for x in public)),'labels':dict(collections.Counter(x['expected'] for x in sealed)), 'sealed_valid_proof_reference_checks':'VALID_REFERENCES_AND_LABEL_CONSISTENCY_ONLY','independent_full_physics_enumeration':False},
 'models_recomputed_from_case_audit':model_stats,
 'confidence':{'replays':6144,'exact_matches':6144,'AUROC_outcomes_prior_scoring':{k:confidence['models'][k]['score_analysis']['decision_token_geomean']['all']['auc'] if 'decision_token_geomean' in confidence['models'][k]['score_analysis'] else None for k in confidence['models']}},
 'publication_freeze_scope':'LOCAL_SNAPSHOT_OF_UPLOADED_ARCHIVES; no writes to Swan, GitHub, upstream model weights or original manuscript'}

(OUT/'FROZEN_ARCHIVE_MANIFEST.json').write_text(json.dumps({'freeze_date_utc':'2026-10-23','files':manifest},indent=2,sort_keys=True)+'\n')
(OUT/'INDEPENDENT_AUDIT_SUMMARY.json').write_text(json.dumps(stats,indent=2,sort_keys=True)+'\n')
with (OUT/'coordinate_checks.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,frame_errors[0].keys());w.writeheader();w.writerows(frame_errors)
with (OUT/'two_atom_internal_checks.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,bond_errors[0].keys());w.writeheader();w.writerows(bond_errors)
# 48 groups, 2 paired presentations for blinded expert review, deterministic hashed choice
blinded=[];golditems=[]
bygroup=collections.defaultdict(list)
for baseid,prs in base.items():bygroup[prs[0]['group_id']].append((baseid,prs))
for group_id,pools in sorted(bygroup.items()):
 baseid,prs=min(pools,key=lambda r:hashlib.sha256((group_id+'|review|'+r[0]).encode()).digest())
 for case in sorted(prs,key=lambda c:c['presentation']):
  row={'case_id':case['case_id'],'group_id':case['group_id'],'base_case_id':baseid,'presentation':case['presentation'],'claim':case['model_payload']['claim'], 'public_evidence':(case['model_payload']['evidence_packet'] if 'evidence_packet' in case['model_payload'] else case['model_payload']['evidence_report']),'review_questions':['Which atom subset and endpoint pair are required?','Are units, alignment, periodicity and frame compatible?','Is any conclusive licensed proof possible?','If so, record exact evidence ID, operation and verdict; otherwise explain why absent.'],'reviewer_verdict':'','reviewer_evidence_id':'','reviewer_operation':'','reviewer_reason':'','reviewer_confidence':'','reviewer_id':''}
  blinded.append(row)
  golditems.append({'case_id':case['case_id'],'expected':gold_by[case['case_id']]['expected'],'valid_proofs':gold_by[case['case_id']]['valid_proofs']})
assert len(blinded)==96 and len(golditems)==96
(OUT/'EXPERT_REVIEW_BLINDED.jsonl').write_text(''.join(json.dumps(c,sort_keys=True)+'\n' for c in blinded))
(OUT/'EXPERT_REVIEW_SEALED_REFERENCE.jsonl').write_text(''.join(json.dumps(c,sort_keys=True)+'\n' for c in golditems))
print(json.dumps(stats,indent=2)[:3000])
