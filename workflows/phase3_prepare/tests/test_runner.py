"""Source-checkpoint orchestration tests; no network, UMA or LLM inference."""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import run_phase3 as runner
from verify_results import verify


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.out=self.base/'results/fixture';self.out.mkdir(parents=True)

    def parent(self,extra=None):
        payload={'summary.json':json.dumps({'fixture':True}).encode(),
                 'code_snapshot/danger.py':b'raise RuntimeError("NEVER EXECUTE ATTACHMENTS")'}
        if extra:payload.update(extra)
        hashes={n:hashlib.sha256(v).hexdigest() for n,v in payload.items()}
        path=self.base/'fixture.zip'
        with zipfile.ZipFile(path,'w') as z:
            for n,data in payload.items():z.writestr('fixture/'+n,data)
            z.writestr('fixture/SHA256SUMS.json',json.dumps(hashes))
        return path,hashlib.sha256(path.read_bytes()).hexdigest()

    def frozen(self):
        for name in ('selection.json','split_manifest.json','model_manifest.json',
                     'language_model_manifest_RESERVED.json','parent_provenance.json','candidate_membership.json'):
            runner.support.save_json(self.out/name,{'mock_only':True})
        runner.support.save_json(self.out/'run_config.json',runner.DEFAULTS)
        runner.support.snapshot(self.out);runner.freeze(self.out)
        runner.support.stage(self.out,'prepare','COMPLETE')

    def test_parent_read_verifies_bytes_and_never_returns_or_executes_code(self):
        path,sha=self.parent()
        parent=runner.read_parent(path,sha)
        self.assertEqual(parent['verified_files'],2)
        self.assertEqual(set(parent['data']),{'summary.json'})
        with self.assertRaisesRegex(ValueError,'different'):
            runner.read_parent(path,'0'*64)

    def test_parent_traversal_rejected_even_with_valid_checksums(self):
        path,sha=self.parent({'../outside.json':b'{}'})
        with self.assertRaisesRegex(ValueError,'Unsafe'):
            runner.read_parent(path,sha)

    def test_candidate_membership_is_frozen(self):
        self.frozen()
        runner.support.save_json(self.out/'candidate_membership.json',{'changed':True})
        with self.assertRaisesRegex(ValueError,'Prepared source input changed'):
            runner.verify_frozen(self.out)

    def test_run_refuses_unprepared_or_changed_data_before_gpu(self):
        with patch('phase3.sources.run_batch') as called:
            with self.assertRaisesRegex(RuntimeError,'did not complete'):
                runner.run_batch(self.out,0,runner.DEFAULTS)
            called.assert_not_called()
        self.frozen()
        runner.support.save_json(self.out/'selection.json',{'changed':True})
        with patch('phase3.sources.run_batch') as called:
            with self.assertRaisesRegex(ValueError,'changed'):
                runner.run_batch(self.out,0,runner.DEFAULTS)
            called.assert_not_called()

    def test_frozen_configuration_cannot_be_changed(self):
        path=self.base/'config.json'
        runner.support.save_json(path,dict(runner.DEFAULTS,max_steps=601))
        with self.assertRaisesRegex(ValueError,'frozen'):
            runner.config_from(path)

    def test_collect_preparation_failure_returns_checksum_verified_diagnostic(self):
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            code=runner.main(['collect','--run-id','fixture','--refinement-zip',str(self.base/'notneeded.zip'),
                             '--geometry-zip',str(self.base/'notneeded2.zip'),'--output-root',str(self.out.parent),
                             '--cache-dir',str(self.base/'cache')])
        self.assertEqual(code,0)
        checked=verify(self.out.parent/'return_zips/fixture_phase3_prepare_results.zip')
        self.assertEqual(checked['status'],'PREPARATION_FAILED_OR_INTERRUPTED')
        self.assertFalse(checked['language_model_inference_enabled']);self.assertFalse(checked['phase3_complete'])

    def test_reprepare_preserves_frozen_inputs(self):
        self.frozen();before=(self.out/'prepared_sha256.json').read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            code=runner.main(['prepare','--run-id','fixture','--refinement-zip','unused','--geometry-zip','unused',
                             '--output-root',str(self.out.parent),'--cache-dir',str(self.base/'cache')])
        self.assertEqual(code,1);self.assertEqual((self.out/'prepared_sha256.json').read_bytes(),before)

    def test_collect_keeps_partial_physical_results_without_enabling_models(self):
        self.frozen()
        with patch('phase3.sources.measure_sources',return_value=dict(status='PARTIAL_NEEDS_PHYSICAL_REVIEW',
                  selected_systems=60,measured_pairs=17)) as called:
            result=runner.collect(self.out,runner.DEFAULTS)
        called.assert_called_once()
        self.assertEqual(result['selected_systems'],60);self.assertEqual(result['measured_pairs'],17)
        self.assertIn('no language-model inference',result['next_action'])
