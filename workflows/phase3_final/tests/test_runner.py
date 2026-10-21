"""Final orchestration checks without protected predictions or GPU calls."""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import run_final as runner
from study_inputs import read_verified
from verify_results import verify
from test_evaluation import case,answer,prediction


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.out=self.base/'results/fixture';self.out.mkdir(parents=True)
        self.config=dict(runner.DEFAULTS,bootstrap_samples=10)

    def frozen(self):
        public=[case('fixture_case',group='fixture_group')]
        gold=[answer(public[0])]
        runner.support.jsonl(self.out/'cases_public.jsonl',public)
        runner.support.jsonl(self.out/'cases_gold_DO_NOT_SEND_TO_MODELS.jsonl',gold)
        for name in ('benchmark_audit.json','development_audit.json','model_manifest.json','parent_provenance.json',
                     'qualification_gate.json','protocol.json'):
            runner.support.save_json(self.out/name,{'mock_only':True})
        runner.support.save_json(self.out/'run_config.json',self.config)
        runner.support.snapshot(self.out);runner.freeze(self.out);runner.support.stage(self.out,'prepare','COMPLETE')
        return public,gold

    def test_parent_verification_only_returns_allowed_data(self):
        path=self.base/'parent.zip'
        data={'summary.json':b'{}','code_snapshot/unsafe.py':b'raise RuntimeError("NEVER EXECUTE")'}
        hashes={n:hashlib.sha256(v).hexdigest() for n,v in data.items()}
        with zipfile.ZipFile(path,'w') as z:
            for n,v in data.items():z.writestr('fixture/'+n,v)
            z.writestr('fixture/SHA256SUMS.json',json.dumps(hashes))
        returned,provenance=read_verified(path,hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(returned,{'summary.json':{}})
        self.assertEqual(provenance['verified_files'],2)
        with self.assertRaisesRegex(ValueError,'differs'):read_verified(path,'0'*64)

    def test_missing_models_are_all_scored_with_oracle_separate(self):
        self.frozen();result=runner.collect(self.out,self.config)
        self.assertEqual(result['status'],'PARTIAL_FINAL_RESULTS')
        self.assertEqual(result['successful_model_requests'],0)
        self.assertEqual(result['expected_model_requests'],6)
        scored=runner.support.load_json(self.out/'evaluation.json')
        self.assertEqual(len(scored['summaries']),13)
        for row in scored['summaries']:
            if row['model_key'] in runner.MODEL_KEYS:
                self.assertEqual(row['answerable_correct_verdict_and_proof_rate'],0)

    def test_duplicate_or_foreign_records_cannot_fake_completeness(self):
        public,_=self.frozen()
        raw=prediction(public[0]);rows=[raw,dict(raw),dict(raw,case_id='foreign')]
        runner.support.jsonl(self.out/'predictions_qwen.jsonl',rows)
        result=runner.collect(self.out,self.config)
        self.assertEqual(result['successful_model_requests'],0)
        self.assertEqual(result['status'],'PARTIAL_FINAL_RESULTS')
        warnings=runner.support.load_json(self.out/'collection_warnings.json')
        self.assertEqual(len(warnings),1)

    def test_correct_fixture_runs_complete_without_claiming_project_completion(self):
        public,_=self.frozen()
        for model in runner.MODEL_KEYS:
            runner.support.jsonl(self.out/f'predictions_{model}.jsonl',[
                prediction(public[0],model=model),prediction(public[0],selector=True,model=model)])
        result=runner.collect(self.out,self.config)
        self.assertEqual(result['status'],'READY_FOR_FINAL_REVIEW')
        self.assertEqual(result['successful_model_requests'],6)
        scored=runner.support.load_json(self.out/'evaluation.json')
        for row in scored['summaries']:
            self.assertEqual(row['answerable_correct_verdict_and_proof_rate'],1)

    def test_frozen_cases_and_protocol_tampering_are_rejected(self):
        self.frozen();runner.support.save_json(self.out/'protocol.json',{'changed':True})
        with self.assertRaisesRegex(ValueError,'Frozen study input changed'):runner.verify_frozen(self.out)

    def test_incomplete_last_record_retains_warning(self):
        path=self.base/'rows.jsonl';path.write_text('{}\n{"case_id":',encoding='utf8')
        rows,warning=runner.read_jsonl(path,True)
        self.assertEqual(rows,[{}]);self.assertIn('incomplete',warning)
        path.write_text('{bad}\n{}\n',encoding='utf8')
        with self.assertRaises(json.JSONDecodeError):runner.read_jsonl(path,True)

    def test_failed_preparation_still_produces_verified_return_zip(self):
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            code=runner.main(['collect','--run-id','fixture','--source-zip','notneeded','--development-zip','notneeded',
                              '--output-root',str(self.out.parent),'--cache-dir',str(self.base/'cache')])
        self.assertEqual(code,0)
        checked=verify(self.out.parent/'return_zips/fixture_final_results.zip')
        self.assertEqual(checked['status'],'PREPARATION_FAILED_OR_INTERRUPTED')
        self.assertFalse(checked['phase3_complete']);self.assertTrue(checked['final_review_required'])

    def test_existing_preparation_is_never_overwritten(self):
        self.frozen();before=(self.out/'prepared_sha256.json').read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            code=runner.main(['prepare','--run-id','fixture','--source-zip','unused','--development-zip','unused',
                              '--output-root',str(self.out.parent),'--cache-dir',str(self.base/'cache')])
        self.assertEqual(code,1);self.assertEqual((self.out/'prepared_sha256.json').read_bytes(),before)
