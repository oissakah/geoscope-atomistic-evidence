import copy
from collections import Counter, defaultdict
from decimal import Decimal
import json
import unittest

from finalstudy.benchmark import (build_benchmark, parse_payload, oracle,
    enumerate_proofs, licensed_relation, interval_for, judge_interval)


def sources(n=2):
    records=[]
    for group in range(n):
        defs={}
        for metric,mask,aligned in (("mobile_rmsd",[3,4,5,6],False),
            ("adsorbate_frame_rmsd",[4,5,6],False),("internal_rmsd",[4,5,6],True),
            ("anchor_rmsd",[0,1,2],False)):
            defs[metric+"_A"]=dict(atom_indices=mask,pbc=[True,True,True],
                frame="independent molecular centroids" if aligned else "shared stored slab coordinate frame",
                alignment="proper Kabsch rotation plus translation; no reflection" if aligned else "none",
                periodic_treatment="connected bond-graph unwrapping before alignment; no MIC on fitted residuals" if aligned else "minimum-image displacement independently per matched atom",
                weighting="equal weight per selected atom")
        for origin in ("measured_endpoint_pair","synthetic_control"):
            records.append(dict(pair_id=f"PRIVATE_pair_{group}_{origin}",group_id=f"PRIVATE_group_{group}",
                split="pilot_development",origin=origin,metric_definitions=copy.deepcopy(defs),
                measurements=dict(mobile_rmsd_A=.65+group*.01 if origin=="measured_endpoint_pair" else .606217782649107,
                    adsorbate_frame_rmsd_A=.7+group*.01 if origin=="measured_endpoint_pair" else .7,
                    internal_rmsd_A=.13+group*.01 if origin=="measured_endpoint_pair" else 1e-16),
                geometry_audit=dict(anchor_rmsd_A=0.),provenance=dict(secret="DO_NOT_LEAK",expected="LABEL_LEAK")))
    return records


class BenchmarkTests(unittest.TestCase):
    def test_complete_counts_balanced_direct_bound_and_group_retention(self):
        public,gold,audit=build_benchmark(sources(20))
        self.assertEqual(len(public),640)
        self.assertEqual(audit["n_base_cases"],320)
        self.assertEqual(audit["by_label"],{"SUPPORTED":200,"CONTRADICTED":200,"INSUFFICIENT_EVIDENCE":240})
        self.assertEqual(audit["by_presentation"],{"report":320,"structured":320})
        self.assertEqual(audit["n_source_groups"],20)
        self.assertFalse(audit["source_groups_replaced"])
        self.assertFalse(audit["internal_from_mic_adsorbate_bound_enabled"])
        self.assertEqual(audit["skipped_cases"],[])
        self.assertEqual(set(Counter(p['group_id'] for p in public).values()),{32})

    def test_every_gold_lists_all_conclusive_licensed_proofs(self):
        public,gold,_=build_benchmark(sources(3))
        multiple=0
        for p,g in zip(public,gold):
            proofs=enumerate_proofs(p['model_payload'])
            self.assertEqual(proofs,g['valid_proofs'])
            self.assertEqual(oracle(p['model_payload'])['verdict'],g['expected'])
            if g['expected']=='INSUFFICIENT_EVIDENCE':
                self.assertEqual(proofs,[])
                self.assertEqual(oracle(p['model_payload']),dict(verdict='INSUFFICIENT_EVIDENCE',evidence_ids=[],operation='none'))
            else:
                self.assertTrue(proofs)
                self.assertEqual({proof['verdict'] for proof in proofs},{g['expected']})
                multiple += len(proofs)>1
        self.assertGreater(multiple,0)

    def test_missing_same_pair_target_does_not_automatically_mean_insufficient(self):
        public,gold,_=build_benchmark(sources())
        for p,g in zip(public,gold):
            parsed=parse_payload(p['model_payload'])
            if p['family'] in ('missing_mobile_bound','missing_adsorbate_bound'):
                self.assertNotEqual(g['expected'],'INSUFFICIENT_EVIDENCE')
                self.assertTrue(all(proof['operation']!='value' for proof in g['valid_proofs']))
                samepair=[r for r in parsed['measurements'] if r['pair_id']==parsed['pair_id']]
                self.assertEqual(len(samepair),1)
            elif p['family'] in ('missing_mobile_ambiguous','missing_adsorbate_ambiguous'):
                self.assertEqual(g['expected'],'INSUFFICIENT_EVIDENCE')
                samepair=[r for r in parsed['measurements'] if r['pair_id']==parsed['pair_id']]
                self.assertEqual(len(samepair),1)
                operation='mobile_lower' if p['family']=='missing_mobile_ambiguous' else 'adsorbate_upper'
                lo,hi=interval_for(parsed,samepair[0],operation)
                self.assertLess(lo,parsed['threshold_A'])
                if hi is not None:self.assertLess(parsed['threshold_A'],hi)
                self.assertIsNone(judge_interval(lo,hi,parsed['threshold_A'],parsed['operator']))

    def test_masks_alignment_run_and_periodicity_are_independent_constraints(self):
        public,_,_=build_benchmark(sources(1))
        p=next(p for p in public if p['family']=='direct_scope' and p['target_metric']=='internal_rmsd' and p['presentation']=='structured')
        parsed=parse_payload(p['model_payload'])
        row=next(r for r in parsed['measurements'] if licensed_relation(parsed,r,'value'))
        for change in ('mask','alignment','pbc','frame','pair','weight'):
            altered=copy.deepcopy(row)
            if change=='mask':altered['definition']['atom_indices']=parsed['atom_sets']['mobile']
            elif change=='alignment':altered['definition']['alignment']='none'
            elif change=='pbc':altered['definition']['pbc']=[False,False,False]
            elif change=='frame':altered['definition']['frame']='other frame'
            elif change=='pair':altered['pair_id']='P_deadbeef'
            else:altered['definition']['weighting']='mass weighted'
            with self.subTest(change=change):
                self.assertFalse(licensed_relation(parsed,altered,'value'))
                with self.assertRaises(ValueError):interval_for(parsed,altered,'value')
                if change!='pair':
                    self.assertEqual(interval_for(parsed,altered,'value',validate_scope=False)[0],Decimal(str(row['value'])))

    def test_unit_conversion_and_both_styles_have_equivalent_mathematical_truth(self):
        public,gold,_=build_benchmark(sources(3))
        bases=defaultdict(list)
        for p,g in zip(public,gold):
            bases[p['base_case_id']].append((p,g))
            if p['family']=='unit_conversion':
                parsed=parse_payload(p['model_payload'])
                self.assertTrue(all(r['unit']=='nm' for r in parsed['measurements']))
                self.assertEqual(oracle(p['model_payload'])['verdict'],g['expected'])
        for variants in bases.values():
            self.assertEqual(len(variants),2)
            (p,a),(q,b)=variants
            self.assertEqual(a['expected'],b['expected'])
            x,y=parse_payload(p['model_payload']),parse_payload(q['model_payload'])
            self.assertEqual(x['threshold_A'],y['threshold_A'])
            self.assertEqual([r['value'] for r in x['measurements']],[r['value'] for r in y['measurements']])
            self.assertNotEqual(x['pair_id'],y['pair_id'])

    def test_no_internal_from_mic_bound_is_licensed(self):
        public,_,_=build_benchmark(sources(1))
        p=next(p for p in public if p['target_metric']=='internal_rmsd' and p['family']=='direct_scope')
        parsed=parse_payload(p['model_payload'])
        wrong=next(r for r in parsed['measurements'] if r['pair_id']==parsed['pair_id'] and r['definition']['alignment']=='none')
        for op in ('value','mobile_lower','adsorbate_upper','none'):
            self.assertFalse(licensed_relation(parsed,wrong,op))
        with self.assertRaises(ValueError):interval_for(parsed,wrong,'internal_upper')

    def test_internal_missing_uses_only_independent_anchors(self):
        public,gold,_=build_benchmark(sources())
        for p,g in zip(public,gold):
            if p['family']=='missing_internal_anchor_only':
                parsed=parse_payload(p['model_payload'])
                same=[r for r in parsed['measurements'] if r['pair_id']==parsed['pair_id']]
                self.assertEqual(len(same),1)
                self.assertEqual(same[0]['definition']['atom_indices'],parsed['atom_sets']['anchors'])
                self.assertEqual(g['expected'],'INSUFFICIENT_EVIDENCE')
                self.assertGreater(parsed['threshold_A'],0)

    def test_judge_interval_exact_endpoint_rules(self):
        D=Decimal
        self.assertEqual(judge_interval(D(1),D(2),D(2),'<='),'SUPPORTED')
        self.assertIsNone(judge_interval(D(1),D(2),D(1),'<='))
        self.assertEqual(judge_interval(D(1),D(2),D('.5'),'<='),'CONTRADICTED')
        self.assertEqual(judge_interval(D(1),None,D(1),'>='),'SUPPORTED')
        self.assertIsNone(judge_interval(D(1),None,D(2),'>='))
        self.assertEqual(judge_interval(D(0),D(1),D(2),'>='),'CONTRADICTED')

    def test_all_binary_contrast_pairs_opposite_and_each_variant_retained(self):
        public,gold,_=build_benchmark(sources(3))
        contrasts=defaultdict(list)
        for p,g in zip(public,gold):
            if p['contrast_group_id']:
                contrasts[(p['contrast_group_id'],p['presentation'])].append(g['expected'])
        self.assertEqual(len(contrasts),3*5*2)
        self.assertTrue(all(sorted(v)==['CONTRADICTED','SUPPORTED'] for v in contrasts.values()))

    def test_zero_values_are_skipped_explicitly_without_source_replacement(self):
        data=sources(1)
        data[0]['measurements']['internal_rmsd_A']=0
        public,gold,audit=build_benchmark(data)
        self.assertEqual(len(public),28)
        self.assertEqual(audit['n_source_groups'],1)
        self.assertEqual(audit['skipped_base_cases'],2)
        self.assertEqual(audit['by_label'],{'SUPPORTED':8,'CONTRADICTED':8,'INSUFFICIENT_EVIDENCE':12})
        for metric in data[0]['measurements']:data[0]['measurements'][metric]=0
        public,_,audit=build_benchmark(data)
        self.assertEqual(len(public),4)
        self.assertEqual(audit['skipped_base_cases'],14)
        self.assertEqual(audit['retained_source_group_ids'],['PRIVATE_group_0'])

    def test_metadata_leakage_short_ids_and_quantity_defined_in_both_styles(self):
        public,_,_=build_benchmark(sources(3))
        seen_ids=set();seen_pairs=set()
        for p in public:
            text=json.dumps(p['model_payload'])
            for bad in ('PRIVATE_','DO_NOT_LEAK','LABEL_LEAK','synthetic_control','rigid_translation','valid_proofs','expected','group_id'):
                self.assertNotIn(bad,text)
            parsed=parse_payload(p['model_payload'])
            self.assertRegex(parsed['pair_id'],r'^P_[0-9a-f]{8}$')
            self.assertNotIn(parsed['pair_id'],seen_pairs);seen_pairs.add(parsed['pair_id'])
            for r in parsed['measurements']:
                self.assertRegex(r['evidence_id'],r'^E_[0-9a-f]{8}$')
                self.assertNotIn(r['evidence_id'],seen_ids);seen_ids.add(r['evidence_id'])
            self.assertIn('square root of the mean squared coordinate-residual norm',text)
            if p['presentation']=='report':
                for bad in ('metric_id','display_name','mobile_rmsd','internal_rmsd','anchor_rmsd','RMSD'):
                    self.assertNotIn(bad,p['model_payload']['evidence_report'])

    def test_deterministic_no_mutation_and_split_guard(self):
        data=sources(2);before=copy.deepcopy(data)
        result=build_benchmark(data)
        self.assertEqual(before,data)
        self.assertEqual(result,build_benchmark(data[::-1]))
        with self.assertRaises(ValueError):build_benchmark(data,split='heldout')
        for p in data:p['split']='protected_candidate'
        heldout=build_benchmark(data,split='heldout')
        self.assertTrue(all(p['split']=='heldout' for p in heldout[0]))


if __name__=='__main__':unittest.main()
