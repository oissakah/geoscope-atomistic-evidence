import collections,hashlib,io,lzma,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from phase4 import external_oc20 as oc

class FormatTests(unittest.TestCase):
 def test_pinned_source_and_suffix(self):
  self.assertEqual(oc.SOURCE_MD5,'bc74b6474a13542cc56eaa97bd51adfc')
  self.assertIn('is2res_val_ood_both_trajectories.tar',oc.SOURCE_URL)
  self.assertEqual(oc.candidate_identity('1/1234.extxyz.xz'),'1234')
  self.assertIsNone(oc.candidate_identity('s2ef/0.extxyz'))
  self.assertIsNone(oc.candidate_identity('1/system.txt'))
 def test_hash_order_and_unique_ids(self):
  with tempfile.TemporaryDirectory() as d:
   file=Path(d)/'tiny.tar'
   with tarfile.open(file,'w') as archive:
    for name in ('2/2.extxyz.xz','1/1.extxyz.xz','3/1.extxyz.xz','3/system.txt'):
     contents=b'test';entry=tarfile.TarInfo(name);entry.size=len(contents)
     archive.addfile(entry,io.BytesIO(contents))
   with tarfile.open(file) as archive:
    cand,n,dup=oc.catalog_member_ids(archive)
   self.assertEqual(len(cand),2);self.assertEqual(dup,1)
   self.assertEqual([x[0] for x in cand],sorted(x[0] for x in cand))
 def test_xz_stream_frame_first_and_last(self):
  # Mock ASE external dependency but exercise actual LZMA and tar access.
  class A:pass
  payload=lzma.compress(b'first\nsecond\n')
  with tempfile.TemporaryDirectory() as d:
   source=Path(d)/'tiny.tar'
   with tarfile.open(source,'w') as archive:
    m=tarfile.TarInfo('2/99.extxyz.xz');m.size=len(payload)
    archive.addfile(m,io.BytesIO(payload))
   with tarfile.open(source) as archive:
    from unittest.mock import patch
    with patch.dict('sys.modules',{'ase':__import__('types').ModuleType('ase'), 'ase.io':__import__('types').ModuleType('ase.io')}):
     import sys
     sys.modules['ase.io'].iread=lambda path,index,format: [A(),A()]
     a,b,sha,n=oc.load_trajectory_member(archive,archive.getmember('2/99.extxyz.xz'))
   self.assertIsNot(a,b);self.assertEqual(n,2);self.assertEqual(sha,hashlib.sha256(payload).hexdigest())
 def test_s2ef_source_md5_rejected_before_data(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'junk.tar';f.write_bytes(b'not official')
   with self.assertRaisesRegex(RuntimeError,'MD5 differs'):
    oc.scan_tar(f,Path(d)/'out')
 def test_metric_definitions_still_pinned(self):
  from phase4.freeze_benchmark import FRAME,ALIGN,MIC
  self.assertEqual(FRAME,'shared stored slab coordinate frame')
  self.assertIn('Kabsch',ALIGN)
  self.assertIn('minimum-image',MIC)
if __name__=='__main__':unittest.main()
