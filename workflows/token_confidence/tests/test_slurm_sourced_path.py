"""Catch relative-$0 path bugs under SLURM's copied slurm_script launcher."""
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class SlurmSourcingTests(unittest.TestCase):
    def test_absolute_dependency_in_large_sbatch(self):
        code = (ROOT / 'hpc/run_confidence_large.sbatch').read_text()
        self.assertIn('"$PHASE4_DIR/hpc/check_environment.sh"', code)
        self.assertIn('"$PHASE4_DIR/hpc/require_python312_headers.sh"', code)
        self.assertLess(code.index('require_python312_headers.sh'), code.index('hpc.run_large_confidence'))

    def test_environment_file_uses_bash_source_not_zero(self):
        code = (ROOT / 'hpc/check_environment.sh').read_text()
        self.assertIn('BASH_SOURCE[0]', code)
        self.assertNotIn('dirname "$0"', [line for line in code.splitlines() if line.strip().startswith('cd ')][0])

    def test_sourced_environment_preserves_root_under_spooled_slurm_script(self):
        # No model downloads, CUDA, torch or Slurm required: a no-op Python
        # shim lets the production environment gate execute its shell logic.
        with tempfile.TemporaryDirectory() as td:
            t = pathlib.Path(td)
            mock_python = t / 'python-shim'
            mock_python.write_text('#!/bin/sh\ncat >/dev/null\nexit 0\n')
            mock_python.chmod(0o755)
            parent = t / 'previous_v16'; (parent / 'outputs').mkdir(parents=True)
            (parent / 'outputs' / 'manifest.json').write_text('{}')
            contents = (f'export GEOSCOPE_GPU_PYTHON="{mock_python}"\n'
                        f'export LARGE_GPU_PYTHON="{mock_python}"\n'
                        f'export MODEL_MANIFEST="{parent / "outputs" / "manifest.json"}"\n')
            for name in ('small_environment.sh', 'large_environment.sh'):
                (parent / 'outputs' / name).write_text(contents)
            spool = t / 'var' / 'spool' / 'slurmd' / 'job123'
            spool.mkdir(parents=True)
            job = spool / 'slurm_script'
            job.write_text('''#!/usr/bin/env bash
set -Eeuo pipefail
cd "$PHASE4_DIR"
source "$PHASE4_DIR/hpc/check_environment.sh"
[[ "$PWD" == "$PHASE4_DIR" ]]
[[ -f "$PHASE4_DIR/hpc/require_python312_headers.sh" ]]
echo SLURM_SOURCE_ROOT_PASS
''')
            env = os.environ.copy()
            env.update({'PHASE4_DIR': str(ROOT), 'GEOSCOPE_V16_PARENT': str(parent)})
            result = subprocess.run(['bash', str(job)], cwd=t, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + '\n' + result.stderr)
            self.assertIn('SLURM_SOURCE_ROOT_PASS', result.stdout)

if __name__ == '__main__':
    unittest.main()
