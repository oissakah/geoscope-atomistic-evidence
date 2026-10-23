"""OC20 S2EF val_ood_both independent provenance and geometry gate.

Run on official MD5-verified tarball only. Never creates artificial 'source' structures.
All files from OC20 remain external real structures; synthetic controls are labeled.
This intentionally uses the exact v1.1 metric computation/definition functions.
"""
from __future__ import annotations
import argparse,collections,hashlib,io,json,math,os,sys,tarfile,tempfile,lzma
from pathlib import Path
import numpy as np
from .freeze_benchmark import compute_metrics, definition, benchmark_and_requests, write_json,write_jsonl
from .geometry_validation import minimum_image_displacements

SOURCE_URL='https://dl.fbaipublicfiles.com/opencatalystproject/data/is2res_val_ood_both_trajectories.tar'
SOURCE_MD5='bc74b6474a13542cc56eaa97bd51adfc'
SELECT_N=48
MAX_MEMBER_BYTES=128_000_000
MAX_UNCOMPRESSED_BYTES=256_000_000
SUFFIX='.extxyz.xz'
MAX_ATOMS=500

def sha(b):return hashlib.sha256(b).hexdigest()
def source_digests(p):
 md5=hashlib.md5();sha256=hashlib.sha256()
 with Path(p).open('rb') as f:
  for buf in iter(lambda:f.read(8*1024*1024),b''):
   md5.update(buf);sha256.update(buf)
 return md5.hexdigest(),sha256.hexdigest()

def md5_file(p):return source_digests(p)[0]

def positions_record(atoms):
 if atoms.constraints:
  from ase.constraints import FixAtoms
 else:
  FixAtoms=type("NoFixAtoms",(),{})
 positions=np.asarray(atoms.get_positions(),float)
 symbols=atoms.get_chemical_symbols();tags=[int(v) for v in atoms.get_tags()]
 cell=np.asarray(atoms.cell.array,float);pbc=atoms.get_pbc().tolist()
 if len(symbols)>MAX_ATOMS or len(symbols)<5:raise ValueError('atom_count')
 if len(tags)!=len(symbols) or len(positions)!=len(symbols):raise ValueError('record_shape')
 if not np.all(np.isfinite(positions)) or not np.all(np.isfinite(cell)) or abs(float(np.linalg.det(cell)))<1e-8:raise ValueError('cell_positions')
 explicit=[]
 for c in atoms.constraints:
  if isinstance(c,FixAtoms):explicit+=list(map(int,c.get_indices()))
  else:raise ValueError('unsupported_constraint_type')
 if explicit:
  fixed=sorted(set(explicit));basis='explicit_ASE_FixAtoms'
 else:
  # OC20 tag 0 is subsurface, not itself a documented constraint. We only
  # accept these as candidate anchors when both endpoints verify stationarity.
  fixed=[j for j,t in enumerate(tags) if t==0];basis='tag0_stationary_verified_later'
 if not fixed:raise ValueError('no_anchor_candidates')
 return {'symbols':symbols,'tags':tags,'positions':positions.tolist(), 'cell':cell.tolist(),
  'pbc':pbc,'fixed_indices':fixed,'anchor_basis':basis}

def pair_from_ase(a,b,sid):
 p=positions_record(a);q=positions_record(b)
 if p['symbols']!=q['symbols'] or p['tags']!=q['tags']:raise ValueError('atom_identity_or_tag_change')
 if p['pbc']!=q['pbc']:raise ValueError('pbc_changed')
 if not np.allclose(p['cell'],q['cell'],atol=1e-5,rtol=1e-7):raise ValueError('cell_changed')
 fixed=p['fixed_indices']
 if p['fixed_indices']!=q['fixed_indices']:raise ValueError('anchor_indices_changed')
 ads=[j for j,t in enumerate(p['tags']) if t==2]
 if len(ads)<2:raise ValueError('single_atom_or_absent_adsorbate_not_full_metric')
 if set(ads)&set(fixed):raise ValueError('adsorbate_marked_fixed')
 move=[j not in fixed for j in range(len(p['symbols']))]
 if not any(move):raise ValueError('no_mobile_atoms')
 d=minimum_image_displacements(p['positions'],q['positions'],p['cell'],p['pbc'])
 max_fixed=float(np.linalg.norm(d[fixed],axis=1).max())
 if max_fixed>0.02:raise ValueError('anchor_motion_gt_0p02_A')
 # Inferred stationary anchors require more stringent verification; conservative.
 if p['anchor_basis'].startswith('tag0') and max_fixed>1e-4:raise ValueError('tag0_not_stationary')
 p['move_mask']=move;q['move_mask']=move
 return {'sid':sid,'system_id':'OC20_'+sid,'b1':p,'inflight':q,
  'anchor_basis':p['anchor_basis'], 'max_anchor_displacement_A':max_fixed}

def composition_cluster(pair):
 # conservative inferred group for later group-aware uncertainty, not a claim
 # of matching OC20's official adsorbate/catalyst system IDs.
 from collections import Counter
 p=pair['b1'];sy=p['symbols'];tg=p['tags']
 surf=sorted(Counter(s for s,t in zip(sy,tg) if t!=2).items())
 ads=sorted(Counter(s for s,t in zip(sy,tg) if t==2).items())
 shape=np.asarray(p['cell'],float).round(2).tolist()
 return sha(json.dumps([surf,ads,shape],sort_keys=True).encode())[:20]

def candidate_metrics(pair):
 p=pair['b1'];q=pair['inflight']; x=np.asarray(p['positions'],float);y=np.asarray(q['positions'],float)
 metrics=compute_metrics(x,y,pair)
 if not all(math.isfinite(v) for v in metrics.values()):raise ValueError('nonfinite_metric')
 # Synthetic distractors have fixed predeclared construction; not real relaxation.
 ads=[j for j,t in enumerate(p['tags']) if t==2]
 shifted=y.copy();shifted[ads,:]+=np.array([0.35,0,0])
 synthetic=compute_metrics(x,shifted,pair)
 return metrics,synthetic

def record_pair(pair,metrics,synthetic):
 p=pair['b1'];pbc=p['pbc'];n=len(p['symbols']); m=[j for j,x in enumerate(p['move_mask']) if x]
 a=[j for j,x in enumerate(p['tags']) if x==2];f=[j for j in range(n) if j not in m]
 defs={k:definition(ii,pbc,internal=internal) for k,ii,internal in (
  ('mobile_rmsd_A',m,False),('adsorbate_frame_rmsd_A',a,False),('internal_rmsd_A',a,True),('anchor_rmsd_A',f,False))}
 group='oc20_external_'+sha(pair['sid'].encode())[:16]
 result=[]
 for origin,v in [('measured_endpoint_pair',metrics),('synthetic_control',synthetic)]:
  result.append({'group_id':group,'pair_id':'oc20pair_'+sha((pair['sid']+'|'+origin).encode())[:24],
   'split':'heldout','origin':origin,
   'measurements':{k:v[k] for k in ('mobile_rmsd_A','adsorbate_frame_rmsd_A','internal_rmsd_A')},
   'metric_definitions':defs,'geometry_audit':{'anchor_rmsd_A':v['anchor_rmsd_A']},
   'phase4_origin':'EXTERNAL_OC20_VAL_OOD_BOTH_REAL_DFT_FRAMES_AND_EXPLICIT_SYNTHETIC_DISTRACTOR',
   'system_id_PRIVATE':pair['system_id'],'sid_PRIVATE':pair['sid']})
 return result

def candidate_identity(member_name):
 """Only official IS2RES per-system .extxyz.xz trajectories, never S2EF shards."""
 from pathlib import PurePosixPath
 if not member_name.endswith(SUFFIX):return None
 path=PurePosixPath(member_name)
 if any(seg in ('', '.', '..') for seg in path.parts):return None
 official_id=path.name[:-len(SUFFIX)]
 if not official_id or '/' in official_id:return None
 return official_id


def load_trajectory_member(tar,member):
 """Read exactly one OC20 IS2RES trajectory, no cross-system pairing.

 Streaming LZMA into a bounded temporary extxyz avoids extracting the 35GB
 collection. The ASE reader iterates actual frames. No source data is changed.
 """
 if member.size<10 or member.size>MAX_MEMBER_BYTES:raise ValueError('compressed_trajectory_member_size')
 raw=tar.extractfile(member)
 if raw is None:raise ValueError('unreadable_member')
 compressed=raw.read(MAX_MEMBER_BYTES+1)
 if len(compressed)!=member.size or len(compressed)>MAX_MEMBER_BYTES:raise ValueError('compressed_member_short_or_oversized')
 if not compressed.startswith(b'\xfd7zXZ\x00'):raise ValueError('not_lzma_xz_file')
 chash=sha(compressed)
 with tempfile.NamedTemporaryFile(suffix='.extxyz') as f:
  total=0
  with lzma.LZMAFile(io.BytesIO(compressed)) as decompressor:
   while True:
    block=decompressor.read(1024*1024)
    if not block:break
    total+=len(block)
    if total>MAX_UNCOMPRESSED_BYTES:raise ValueError('extxyz_decompressed_size_exceeded')
    f.write(block)
  f.flush()
  from ase.io import iread
  first=last=None;nframes=0
  for atoms in iread(f.name,index=':',format='extxyz'):
   if nframes==0:first=atoms
   last=atoms
   nframes+=1
   if nframes>10000:raise ValueError('too_many_trajectory_frames')
  if nframes<2:raise ValueError('fewer_than_two_frames')
 return first,last,chash,nframes


def catalog_member_ids(tar):
 """Prospectively rank official system IDs independent of any geometry/LLM output."""
 members=[];seen=set();entries=0;duplicate=0
 for item in tar:
  entries+=1
  if not item.isfile():continue
  identity=candidate_identity(item.name)
  if identity is None:continue
  if identity in seen:
   duplicate+=1
   continue
  seen.add(identity)
  members.append((sha((identity+'|'+item.name).encode()),identity,item))
 members.sort(key=lambda x:(x[0],x[1],x[2].name))
 return members,entries,duplicate


def scan_tar(src,out,max_groups=SELECT_N,limit_members=None):
 src=Path(src).resolve();out=Path(out);out.mkdir(exist_ok=True,parents=True)
 md5,source_sha256=source_digests(src)
 if md5!=SOURCE_MD5:raise RuntimeError('STOP: official IS2RES OC20 MD5 differs; source rejected')
 # Index metadata without extracting or decompressing every trajectory. The
 # official outer .tar is not compressed and supports bounded random access.
 eligible=[];counts=collections.Counter();inspected=0
 with tarfile.open(src,'r:') as tar:
  candidates,all_entries,duplicate_ids=catalog_member_ids(tar)
  if not candidates:raise RuntimeError('STOP: official archive contains no per-system .extxyz.xz files')
  if duplicate_ids:counts['duplicate_official_system_id_skipped']+=duplicate_ids
  if limit_members is not None:
   # Debug mode always stops before benchmark creation.
   candidates=candidates[:limit_members]
  for key,sid,member in candidates:
   inspected+=1
   try:
    first,last,fdigest,nframes=load_trajectory_member(tar,member)
    pair=pair_from_ase(first,last,sid)
    real,synthetic=candidate_metrics(pair)
    entry={'selection_hash':key,'sid':sid,'path':member.name,'member_sha256':fdigest,
      'trajectory_frames':nframes,'composition_cluster':composition_cluster(pair),
      'pair':pair,'real':real,'synthetic':synthetic}
    eligible.append(entry)
    counts['accepted_candidate']+=1
   except (ValueError,RuntimeError,ArithmeticError,IOError,EOFError,lzma.LZMAError,UnicodeDecodeError) as e:
    counts[str(e)[:110]]+=1
   if inspected%25==0:print('SCREENED',inspected,'accepted',len(eligible),flush=True)
   if len(eligible)>=max_groups:break
 write_json(out/'eligibility_counts_PRESELECTION.json',{'candidate_trajectory_files':len(candidates),
  'candidate_trajectories_screened_in_hash_order':inspected,
  'archive_entries_seen':all_entries,'outcomes':dict(counts),
  'selection_note':'First 48 eligible in source-ID hash rank. Full eligible-population count is not estimated.'})
 if limit_members is not None:raise RuntimeError('DEBUG scan cannot freeze a publication benchmark')
 if len(eligible)<max_groups:raise RuntimeError('STOP: only %d eligible OC20 system trajectories; required %d; do not relax eligibility'%(len(eligible),max_groups))
 sources=[];status=[];selected_pairs=[]
 for x in eligible:
  sources.extend(record_pair(x['pair'],x['real'],x['synthetic']))
  status.append({'sid':x['sid'],'system_id':x['pair']['system_id'],'member':x['path'],
   'compressed_member_sha256':x['member_sha256'],'selection_hash':x['selection_hash'],
   'trajectory_frames':x['trajectory_frames'],'composition_cluster':x['composition_cluster'],
   'anchor_basis':x['pair']['anchor_basis'],
   'max_anchor_displacement_A':x['pair']['max_anchor_displacement_A'],
   'real_metrics_A':x['real'],'synthetic_metrics_A':x['synthetic'],
   'n_atoms':len(x['pair']['b1']['symbols']),
   'adsorbate_atoms':sum(t==2 for t in x['pair']['b1']['tags'])})
  selected_pairs.append(x['pair'])
 write_json(out/'source_integrity.json',{'status':'PASS_EXTERNAL_OC20_IS2RES_TAR_VERIFIED',
  'source_url':SOURCE_URL,'official_md5':SOURCE_MD5,'verified_md5':md5,
  'source_sha256':source_sha256,'official_split':'is2res_val_ood_both_trajectories',
  'archive_entries_seen':all_entries,'official_system_ids_catalogued':len(candidates),
  'system_trajectories_screened':inspected,'eligible_trajectories_admitted':len(status),
  'selected_unique_system_groups':len(status),
  'selection':'hash_ranked_unique_official_system_ids_first_48_passing_geometry_gate',
  'frame_policy':'first and last saved DFT trajectory frames; no convergence claim',
  'attribution':'OC20 (Chanussot et al., ACS Catalysis, 2021); CC-BY-4.0',
  'warning':'external to ALCHEMI; LLM pretraining exposure unverified; no model result'})
 write_json(out/'eligibility_counts.json',dict(counts));write_json(out/'selected_source_audit_PRIVATE.json',status)
 write_jsonl(out/'source_pair_records_PRIVATE.jsonl',sources)
 write_jsonl(out/'selected_atomic_pairs_PRIVATE.jsonl',selected_pairs)
 write_json(out/'SOURCE_GATE_STATUS.json',{'status':'OC20_EXTERNAL_SOURCE_GATE_PASS_NO_GPU_RUN',
 'source_groups':len(status),'real_pairs':len(status),'synthetic_controls':len(status),
 'expected_benchmark_source_records':len(sources),
 'next_step':'build sealed benchmark from original pinned GeoScope source, then inspect before inference'})
 print('SOURCE_GATE_PASS',len(status),'real system groups; scanned',inspected,
       'ordered candidates; selected source pairs saved',flush=True)
 return sources

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--tar',required=True);ap.add_argument('--out',default='outputs/external_oc20_source')
 ap.add_argument('--max-groups',type=int,default=SELECT_N);args=ap.parse_args()
 if args.max_groups!=SELECT_N:raise SystemExit('STOP: protocol freezes exactly 48 source groups; no edits without protocol revision')
 scan_tar(args.tar,args.out,args.max_groups)
if __name__=='__main__':main()
