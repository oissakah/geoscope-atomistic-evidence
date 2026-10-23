"""Guard against dropping the 32B virtualenv by resolving its interpreter symlink."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class TestLargeEnvHandoff(unittest.TestCase):
    def test_absolute_keeps_symlink_entrypoint(self):
        with tempfile.TemporaryDirectory() as folder:
            executable=Path(folder)/'python'
            executable.symlink_to(Path(sys.executable))
            self.assertEqual(str(executable.absolute()),str(executable))
            self.assertNotEqual(str(executable.resolve()),str(executable))

    def test_preflight_preserves_original_interpreter(self):
        contents=(ROOT/'hpc/large_external_preflight.py').read_text()
        self.assertIn('Path(py).absolute()',contents)
        self.assertNotIn('shlex.quote(str(Path(py).resolve()))',contents)
        self.assertIn("report['python']",contents)

    def test_batch_fails_closed_on_interpreter_drift(self):
        script=(ROOT/'hpc/run_large_external.sbatch').read_text()
        self.assertIn('LARGE_BATCH_ENVIRONMENT_PASS',script)
        self.assertIn('sys.prefix==sys.base_prefix',script)
        self.assertIn('from transformers import AutoTokenizer',script)
        self.assertIn('LARGE_GPU_PYTHON',script)

if __name__=='__main__':unittest.main()
