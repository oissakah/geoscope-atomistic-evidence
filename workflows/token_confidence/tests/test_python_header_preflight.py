import unittest
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
class HeaderPreflightTests(unittest.TestCase):
 def test_linux_shell_parse(self):
  for p in ['hpc/require_python312_headers.sh','hpc/run_confidence_large.sbatch','hpc/submit_confidence_large_pilot.sh','hpc/submit_confidence_large_remainder.sh']:
   t=subprocess.run(['bash','-n',str(ROOT/p)],capture_output=True,text=True)
   self.assertEqual(t.returncode,0,(p,t.stderr))
 def test_exact_minor_version_and_override(self):
  s=(ROOT/'hpc/require_python312_headers.sh').read_text()
  for tok in ['3.12','GEOSCOPE_PY312_INCLUDE','Python.h','CPATH','-fsyntax-only']:
   self.assertIn(tok,s)
 def test_large_job_preflights_before_model(self):
  s=(ROOT/'hpc/run_confidence_large.sbatch').read_text()
  self.assertLess(s.index('source "$PHASE4_DIR/hpc/require_python312_headers.sh"'),s.index('-m hpc.run_large_confidence'))
 def test_pilot_only_shard_zero(self):
  s=(ROOT/'hpc/submit_confidence_large_pilot.sh').read_text()
  self.assertIn('--array=0 ',s)
  r=(ROOT/'hpc/submit_confidence_large_remainder.sh').read_text()
  self.assertIn('--array=1-11%1',r)
 def test_successful_header_gate_does_not_exit_parent_shell(self):
  import tempfile,sys,os,shutil
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);inc=d/'include'/'python3.12';inc.mkdir(parents=True)
   (inc/'Python.h').write_text('/* fake for compiler smoke test only */\n')
   py=d/'mockpy';py.write_text('#!/bin/bash\nif [[ "$1" == "-c" ]]; then echo 3.12; else echo /unused; fi\n')
   py.chmod(0o755)
   env=os.environ.copy();env.update({'LARGE_GPU_PYTHON':str(py),'GEOSCOPE_PY312_INCLUDE':str(inc),'CC':shutil.which('gcc') or 'gcc'})
   cmd='source hpc/require_python312_headers.sh; echo AFTER_GATE'
   p=subprocess.run(['bash','-c',cmd],cwd=ROOT,env=env,text=True,capture_output=True)
   self.assertEqual(p.returncode,0,p.stdout+'\n'+p.stderr)
   self.assertIn('AFTER_GATE',p.stdout)
 def test_scientific_code_and_data_not_replaced(self):
  self.assertTrue((ROOT/'frozen/BASELINE_STAGE_MANIFEST.json').is_file())
  self.assertTrue((ROOT/'hpc/analyze_confidence.py').is_file())
