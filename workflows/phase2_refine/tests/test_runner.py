"""Orchestration and return-ZIP checks without network or real models."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import run_phase2 as runner
from verify_results import verify
from test_benchmark import sources


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.out=self.base/'results'/'fixture'
        self.out.mkdir(parents=True)
        self.config=dict(runner.DEFAULT_CONFIG,bootstrap_samples=100)
        runner.support.save_json(self.out/'run_config.json',self.config)

    def prepared(self):
        with patch.object(runner,'parent_data',return_value=(sources(20),{'mock_only':True})):
            public,gold=runner.build_data(self.out,self.base/'fixture.zip',self.config)
        runner.support.save_json(self.out/'model_manifest.json',{'mock_only':True})
        runner.support.snapshot(self.out)
        runner.freeze(self.out)
        runner.support.stage(self.out,'prepare','COMPLETE')
        return public,gold

    def test_collection_missing_models_retains_all_denominators(self):
        self.prepared()
        result=runner.collect(self.out,self.base/'fixture.zip',self.config)
        self.assertEqual(result['status'],'PARTIAL_MODEL_RESULTS')
        self.assertEqual(result['expected_model_requests'],2880)
        self.assertEqual(result['successful_model_requests'],0)
        evaluation=runner.support.load_json(self.out/'evaluation.json')
        self.assertEqual(len(evaluation['summaries']),15)
        for summary in evaluation['summaries']:
            if summary['model_key'] in runner.MODEL_KEYS:
                self.assertEqual(summary['strict_accuracy'],0)

    def test_unknown_case_or_condition_cannot_fake_completed_run(self):
        self.prepared()
        fake=[dict(case_id='unknown_'+str(i),condition='invented',model_key='qwen',status='ok',raw_output='{}')
              for i in range(640)]
        runner.support.jsonl(self.out/'predictions_qwen.jsonl',fake)
        with self.assertRaisesRegex(ValueError,'Unexpected case/condition'):
            runner.collect(self.out,self.base/'fixture.zip',self.config)

    def test_all_expected_model_records_complete(self):
        public,gold=self.prepared()
        by_id={g['case_id']:g for g in gold}
        for key in runner.MODEL_KEYS:
            rows=[]
            for case in public:
                g=by_id[case['case_id']]
                for condition in runner.CONDITIONS:
                    answer=dict(evidence_ids=g['required_evidence_ids'])
                    if condition != 'select_evidence':
                        answer['verdict']=g['expected']
                    rows.append(dict(case_id=case['case_id'],condition=condition,model_key=key,status='ok',
                        raw_output=json.dumps(answer)))
            runner.support.jsonl(self.out/f'predictions_{key}.jsonl',rows)
        result=runner.collect(self.out,self.base/'fixture.zip',self.config)
        self.assertEqual(result['status'],'READY_FOR_DEVELOPMENT_REVIEW')
        self.assertEqual(result['successful_model_requests'],2880)
        self.assertFalse(result['protected_test_evaluated'])
        evaluation=runner.support.load_json(self.out/'evaluation.json')
        for item in evaluation['summaries']:
            if item['model_key'] in runner.MODEL_KEYS:
                self.assertEqual(item['strict_accuracy'],1)
                self.assertEqual(item['joint_accuracy'],1)

    def test_frozen_manifest_change_prevents_model_load(self):
        self.prepared()
        runner.support.save_json(self.out/'model_manifest.json',{'changed':True})
        with patch('phase2.models.run_model') as model:
            with self.assertRaisesRegex(ValueError,'Prepared input changed'):
                runner.run(self.out,'qwen',self.config)
            model.assert_not_called()

    def test_partial_last_line_is_visible_and_middle_corruption_rejected(self):
        path=self.base/'predictions.jsonl'
        path.write_text('{"case_id":"one"}\n{"case_id":',encoding='utf-8')
        rows,warning=runner.read_jsonl(path,allow_partial_last=True)
        self.assertEqual(rows,[{'case_id':'one'}])
        self.assertIn('incomplete final',warning)
        path.write_text('{broken}\n{}\n',encoding='utf-8')
        with self.assertRaises(json.JSONDecodeError):
            runner.read_jsonl(path,allow_partial_last=True)

    def test_setup_failure_still_returns_verified_diagnostic(self):
        config=self.base/'pilot.json'
        runner.support.save_json(config,self.config)
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            code=runner.main(['collect','--parent-zip',str(self.base/'not_required_for_diagnostic.zip'),
                '--run-id','fixture','--output-root',str(self.out.parent),'--cache-dir',str(self.base/'cache'),
                '--config',str(config)])
        self.assertEqual(code,0)
        checked=verify(self.out.parent/'return_zips/fixture_phase2_results.zip')
        self.assertEqual(checked['status'],'PREPARATION_FAILED_OR_INTERRUPTED')
        self.assertFalse(checked['phase3_ready'])

    def test_reprepare_cannot_replace_existing_frozen_data(self):
        self.prepared()
        before=(self.out/'prepared_sha256.json').read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            code=runner.main(['prepare','--parent-zip',str(self.base/'unused.zip'),
                '--run-id','fixture','--output-root',str(self.out.parent),'--cache-dir',str(self.base/'cache')])
        self.assertEqual(code,1)
        self.assertEqual((self.out/'prepared_sha256.json').read_bytes(),before)
        self.assertEqual(runner.support.load_json(self.out/'stage_prepare.json')['state'],'COMPLETE')


if __name__=='__main__':
    unittest.main()
