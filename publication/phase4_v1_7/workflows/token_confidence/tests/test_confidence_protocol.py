import unittest,hashlib,json,tempfile
from pathlib import Path
from hpc.confidence_common import checked_inputs,group_token_spans,geometric,metrics,verify_stage,build_record
from hpc.external_stage import stage
ROOT=Path(__file__).resolve().parents[1]
class DummyTokenizer:
    all_special_ids=[0]
    def decode(self,ids,skip_special_tokens=True,clean_up_tokenization_spaces=True):
        return ''.join(chr(i) for i in ids if not (skip_special_tokens and i==0))
class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stage(ROOT)
    def test_original_stage(self):
        m=verify_stage(ROOT)
        self.assertEqual(m['n_requests'],1536);self.assertEqual(m['n_groups'],48)
    def test_all_frozen_predictions(self):
        for model in ['qwen','phi','smol','qwen32b']:
            for shard in range(12):
                _,_,req,old=checked_inputs(ROOT,model,shard)
                self.assertEqual(len(req),128);self.assertEqual(len(old),128)
    def test_no_sealed_answers(self):
        self.assertFalse(list(ROOT.rglob('*gold_proofs*')))
        self.assertFalse(list(ROOT.rglob('*SEALED_REVIEW_ONLY*')))
    def test_decision_span(self):
        tk=DummyTokenizer();txt='```json\\n{"evidence_ids":["E_0123abcd"],"operation":"mobile_lower"}\\n```'
        # Actual newline escapes are valid text elements either way.
        r=metrics([ord(i) for i in txt],[-0.1]*len(txt),tk)
        self.assertTrue(r['has_single_decision_span'])
        self.assertAlmostEqual(r['decision_token_geomean'],__import__('math').exp(-.1))
    def test_ambiguous_evidence_not_scored_as_decision(self):
        tk=DummyTokenizer();txt='{"evidence_ids":["E_0123abcd","E_ab12cd34"],"operation":"value"}'
        r=metrics([ord(i) for i in txt],[-0.2]*len(txt),tk)
        self.assertFalse(r['has_single_decision_span'])
        self.assertIsNone(r['decision_token_geomean'])
    def test_length_invariant(self):
        tk=DummyTokenizer()
        self.assertAlmostEqual(geometric([-0.2]*3),geometric([-0.2]*30))
    def test_special_token_ignored(self):
        tk=DummyTokenizer();txt='{"evidence_ids":["E_0123abcd"],"operation":"value"}'
        r=metrics([ord(i) for i in txt]+[0],[-0.1]*len(txt)+[-5],tk)
        self.assertEqual(r['n_scored_tokens'],len(txt))
    def test_checksum_tampering(self):
        from hpc.external_stage import sha
        import json
        x=json.loads((ROOT/'frozen/BASELINE_RESPONSE_SHA256.json').read_text())
        self.assertEqual(sha(ROOT/'reference/qwen/predictions_shard_00.jsonl'),x['qwen']['00'])
    def test_swan_partition(self):
        for n in ('small','large'):
            t=(ROOT/f'hpc/run_confidence_{n}.sbatch').read_text()
            self.assertIn('#SBATCH --partition=ock',t)
            self.assertIn('--gres=gpu:1',t)
    def test_sampled_token_logprobs(self):
        s=(ROOT/'hpc/run_large_confidence.py').read_text()
        self.assertIn('logprobs=1',s);self.assertIn('dist.get(token)',s)
    def test_source_ids_not_in_gold(self):
        self.assertEqual(set(json.loads((ROOT/'frozen/BASELINE_STAGE_MANIFEST.json').read_text())['shards'][0]['groups']),
             set(json.loads((ROOT/'outputs/model_only/stage_manifest.json').read_text())['shards'][0]['groups']))
    def test_offline_score_auc(self):
        from hpc.analyze_confidence import roc_auc
        self.assertEqual(roc_auc([(0.1,0),(0.9,1)]),1.0)
        self.assertEqual(roc_auc([(0.1,1),(0.9,0)]),0.0)
        self.assertEqual(roc_auc([(0.5,1),(0.5,0)]),0.5)
if __name__=='__main__':unittest.main()
