import unittest,hashlib,tempfile,pathlib
from phase4.external_oc20 import md5_file,SOURCE_MD5
class Integrity(unittest.TestCase):
 def test_md5_stream(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'test';p.write_bytes(b'data');self.assertEqual(md5_file(p),hashlib.md5(b'data').hexdigest())
 def test_official_pin_not_all_zeros(self):self.assertEqual(len(SOURCE_MD5),32);self.assertNotEqual(SOURCE_MD5,'0'*32)
