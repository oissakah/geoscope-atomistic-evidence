"""Offline-only analysis joining token confidence to separately frozen OC20 proof scoring.

USAGE python3 hpc/analyze_confidence.py RESULTS_ZIP FOURMODEL_ANALYSIS_ZIP --out DIRECTORY
No data leakage: only after all GPU confidence responses were collected.
"""
import argparse,csv,io,zipfile,json,math,random,collections,hashlib
from pathlib import Path

MODELS=('qwen','phi','smol','qwen32b')
SCORES=('decision_token_geomean','evidence_token_geomean','operation_token_geomean','all_token_geomean','min_token_prob')

def b(s):return s is True or str(s).lower()=='true'
def read_jsonl(z,name):return [json.loads(x) for x in z.read(name).decode().splitlines() if x.strip()]
def validate_collection(z):
    hashes=json.loads(z.read('COLLECTION_SHA256.json'))
    for name,expected in hashes.items():
        if hashlib.sha256(z.read(name)).hexdigest()!=expected:raise ValueError('Checksum failed: '+name)
    return json.loads(z.read('COLLECTION_STATUS.json'))

def roc_auc(items):
    """AUC with midranks for ties; returns None if one outcome class is absent."""
    n1=sum(y for _,y in items);n0=len(items)-n1
    if n1==0 or n0==0:return None
    ordered=sorted(items,key=lambda x:x[0]);wins=0;i=0;below_neg=0
    while i<len(ordered):
        j=i
        while j<len(ordered) and ordered[j][0]==ordered[i][0]:j+=1
        pos=sum(y for _,y in ordered[i:j]);neg=(j-i)-pos
        wins+=pos*below_neg+0.5*pos*neg
        below_neg+=neg;i=j
    return wins/(n1*n0)

def quantiles(arr):
    if not arr:return []
    arr=sorted(arr)
    return [arr[int((len(arr)-1)*p)] for p in (.025,.5,.975)]

def summary(rows,seed=20261023,bootstrap=500):
    if not rows:return {'n':0}
    pairs=[(r['score'],r['correct']) for r in rows];groups=collections.defaultdict(list)
    for r in rows:groups[r['group_id']].append((r['score'],r['correct']))
    n=len(rows);ordered=sorted(rows,key=lambda r:(-r['score'],r['case_id']))
    curve={}
    for pct in (0.10,0.25,0.50,0.75,1):
        k=max(1,int(math.ceil(n*pct)));curve[str(pct)]={'retained':k,'accuracy':sum(r['correct'] for r in ordered[:k])/k}
    deciles=[]
    asc=sorted(rows,key=lambda r:(r['score'],r['case_id']))
    for k in range(10):
        sample=asc[int(k*n/10):int((k+1)*n/10)]
        if sample:deciles.append({'bin':k+1,'n':len(sample),'mean_token_score':sum(r['score'] for r in sample)/len(sample),
           'observed_accuracy':sum(r['correct'] for r in sample)/len(sample)})
    group_keys=list(groups);rng=random.Random(seed);aucs=[]
    for _ in range(bootstrap):
        sampled=[v for g in rng.choices(group_keys,k=len(group_keys)) for v in groups[g]]
        auc=roc_auc(sampled)
        if auc is not None:aucs.append(auc)
    base=sum(r['correct'] for r in rows)/n
    return {'n':n,'correct':sum(r['correct'] for r in rows),'accuracy':base,
        'auc_roc':roc_auc(pairs),'group_bootstrap_auc_95_interval': [quantiles(aucs)[0],quantiles(aucs)[-1]] if aucs else None,
        'group_count':len(groups),'top_confidence_accuracy':curve,'quantile_bins':deciles,
        'high_confidence_wrong_top_decile':sum(not r['correct'] for r in ordered[:max(1,math.ceil(n*.1))])}

def main():
    p=argparse.ArgumentParser();p.add_argument('results_zip');p.add_argument('fourmodel_scoring_zip');p.add_argument('--out',default='confidence_offline_analysis');p.add_argument('--bootstrap',type=int,default=1000);args=p.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.results_zip) as z,zipfile.ZipFile(args.fourmodel_scoring_zip) as gold:
        status=validate_collection(z)
        audit=list(csv.DictReader(io.StringIO(gold.read('per_case_comparison.csv').decode())))
        key={(r['model'],r['case_id']):r for r in audit}
        assert len(audit)==6144 and len(key)==6144
        rows=[];disagreements=[];seen=set()
        for model in MODELS:
            for shard in range(12):
                file=f'outputs/confidence/{model}/confidence_shard_{shard:02d}.jsonl'
                if file not in z.namelist():continue
                for row in read_jsonl(z,file):
                    ident=(model,row['case_id'])
                    if ident in seen:raise RuntimeError('Duplicate confidence case '+str(ident))
                    seen.add(ident)
                    if ident not in key:raise RuntimeError('No frozen scoring record for '+str(ident))
                    g=key[ident]
                    rec=dict(row)
                    rec.update({'group_id':g['group_id'],'presentation':g['presentation'],'expected':g['expected'],
                      'answerable':b(g['answerable']),'strict_correct_proof':b(g['strict_correct_proof']),
                      'normalized_correct_proof':b(g['normalized_correct_proof']),
                      'normalized_correct_after_repair':b(g['normalized_correct_after_repair']),
                      'normalized_correct_abstention':b(g['normalized_correct_abstention']),
                      'baseline_scoring_status':g['status']})
                    rows.append(rec)
                    if not row['exact_replay']:disagreements.append(ident)
        # Every score in this analysis is conditional on the SAME original answer being replayed.
        results={'protocol':'GeoScope_v1.7_ORIGINAL_OC20_OUTPUT_REPLAY_CONFIDENCE',
          'inputs_status':status,'joined':len(rows),'replay_mismatch_count':len(disagreements),
          'primary_outcome':'frozen normalized_correct_proof on answerable cases',
          'primary_metric':'decision_token_geomean (evidence ID + operation string tokens)',
          'warning':'Token probabilities are NOT calibrated probabilities of scientific correctness.',
          'subgroups':{}}
        for model in MODELS:
            sub=[r for r in rows if r['model']==model];d={'n_total':len(sub),'n_exact_replay':sum(b(r['exact_replay']) for r in sub),
             'n_answerable':sum(r['answerable'] for r in sub),
             'n_confidence_eligible':sum(b(r['exact_replay']) and r['answerable'] and r['has_single_decision_span'] for r in sub),
             'by_score':{}}
            for score in SCORES:
                d['by_score'][score]={}
                for presentation in ('all','structured','report'):
                    filtered=[{'score':float(r[score]),'correct':int(r['normalized_correct_proof']),
                       'group_id':r['group_id'],'case_id':r['case_id']}
                       for r in sub if r['answerable'] and r['exact_replay'] and r[score] is not None
                       and (presentation=='all' or r['presentation']==presentation)]
                    d['by_score'][score][presentation]=summary(filtered,bootstrap=args.bootstrap)
            # Independently report token scores on correct vs incorrect proofs
            # and on missing-evidence cases. Never count a rejected proof as abstention.
            d['distribution_diagnostics']={}
            for group_name,criterion in (
                ('answerable_correct',lambda x: x['answerable'] and x['normalized_correct_proof']),
                ('answerable_wrong',lambda x: x['answerable'] and not x['normalized_correct_proof']),
                ('insufficient_evidence',lambda x: x['expected']=='INSUFFICIENT_EVIDENCE')):
                subvalues=sorted(float(x['decision_token_geomean']) for x in sub
                   if x['exact_replay'] and x['decision_token_geomean'] is not None and criterion(x))
                d['distribution_diagnostics'][group_name]={'count':len(subvalues),
                     'median_decision_score':subvalues[len(subvalues)//2] if subvalues else None,
                     'min_score':subvalues[0] if subvalues else None,
                     'max_score':subvalues[-1] if subvalues else None}
            # Missing-evidence behavior must be scored separately, even when
            # none of the models learned a valid scientific abstention.
            d['insufficient_evidence']={'n_total':sum(x['expected']=='INSUFFICIENT_EVIDENCE' for x in sub),
               'n_exact_replay':sum(x['expected']=='INSUFFICIENT_EVIDENCE' and x['exact_replay'] for x in sub),
               'n_valid_abstentions_in_original':sum(x['expected']=='INSUFFICIENT_EVIDENCE' and x['normalized_correct_abstention'] for x in sub)}
            results['subgroups'][model]=d
        (out/'CONFIDENCE_ANALYSIS.json').write_text(json.dumps(results,indent=2,sort_keys=True)+'\n')
        cols=sorted(set().union(*(r.keys() for r in rows))) if rows else []
        with (out/'confidence_per_case.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader()
            for r in rows:writer.writerow(r)
        with (out/'replay_disagreements.json').open('w') as f:json.dump(disagreements,f,indent=2)
        print(json.dumps({'joined':len(rows),'mismatches':len(disagreements),
          'primary_auc':{k:v['by_score']['decision_token_geomean']['all'].get('auc_roc') for k,v in results['subgroups'].items()},
          'status':'OFFLINE_SCORED_NO_RETRAINING'},indent=2))
if __name__=='__main__':main()
