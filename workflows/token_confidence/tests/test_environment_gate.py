"""Regression tests for Swan environment checks (no GPUs or real HF packages needed)."""
import os,sys,shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class EnvironmentGateTests(unittest.TestCase):
    def test_gate_uses_imported_versions_not_prefix(self):
        t=(ROOT/'hpc/check_environment.sh').read_text()
        self.assertNotIn('assert sys.prefix!=sys.base_prefix',t)
        self.assertIn("md.version('transformers')=='5.3.0'",t)
        self.assertIn("md.version('vllm')=='0.11.2'",t)
        self.assertIn('AutoModelForCausalLM',t)
        self.assertIn('from vllm import LLM,SamplingParams',t)

    def test_standalone_shell_syntax(self):
        p=subprocess.run(['bash','-n',str(ROOT/'hpc/check_environment.sh')],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_actual_system_python_with_equal_prefix_can_pass_mocked_packages(self):
        # In this test Python has prefix == base_prefix, the same condition
        # that previously broke the Swan preflight despite correct imports.
        # Do not use /usr/bin/python3: on Swan it may be an older Python
        # without importlib.metadata, unrelated to the v1.7 model environments.
        # Use the test runner's Python (>=3.9) and simulate equal prefixes
        # in an executable shim, so this regression runs on any host.
        python_binary=sys.executable
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);stub=base/'fake_lib';stub.mkdir()
            shim=base/'equal_prefix_python'
            code=(
                'import sys\n'
                'sys.prefix=sys.base_prefix\n'
                'exec(compile(sys.stdin.read(), "<stdin>", "exec"))\n'
            )
            shim.write_text('#!/bin/sh\nexec '+shlex.quote(python_binary)+' -c '+shlex.quote(code)+' "$@"\n')
            shim.chmod(0o755)
            (stub/'transformers.py').write_text('class AutoTokenizer: pass\nclass AutoModelForCausalLM: pass\n')
            (stub/'torch.py').write_text('__version__="2.13.0+cu126"\n')
            (stub/'vllm.py').write_text('class LLM: pass\nclass SamplingParams: pass\n')
            for name,version in [('transformers','5.3.0'),('torch','2.13.0+cu126'),('vllm','0.11.2')]:
                di=stub/(name+'-'+version+'.dist-info');di.mkdir()
                (di/'METADATA').write_text('Metadata-Version: 2.1\nName: '+name+'\nVersion: '+version+'\n')
            parent=base/'v16';(parent/'outputs').mkdir(parents=True)
            (parent/'outputs/model-manifest.json').write_text('{}')
            q=str(shim).replace('"','\\"')
            for f in ['small_environment.sh','large_environment.sh']:
                (parent/'outputs'/f).write_text(
                    'export GEOSCOPE_GPU_PYTHON="'+q+'"\n'+
                    'export LARGE_GPU_PYTHON="'+q+'"\n'+
                    'export MODEL_MANIFEST="'+str(parent/'outputs/model-manifest.json')+'"\n')
            env=os.environ.copy()
            env['GEOSCOPE_V16_PARENT']=str(parent)
            env['PYTHONPATH']=str(stub)+os.pathsep+str(ROOT)
            p=subprocess.run(['bash',str(ROOT/'hpc/check_environment.sh')],cwd=ROOT,env=env,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+'\n'+p.stderr)
            self.assertIn('ENVIRONMENTS CHECKED',p.stdout)
            self.assertIn('prefix ',p.stdout)

if __name__=='__main__': unittest.main()
