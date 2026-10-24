import unittest,tarfile,tempfile,io,gzip,json
from pathlib import Path
from unittest.mock import patch
from phase4.oc20_archive_inventory import inspect,magic_name,type_name,EXPECTED_MD5
class ArchiveInventoryTests(unittest.TestCase):
    def test_suffix_and_magic(self):
        self.assertEqual(type_name('chunk.tar.gz'),'.tar.gz')
        self.assertEqual(type_name('x.traj.gz'),'.traj.gz')
        self.assertEqual(magic_name(b'\x1f\x8babc'),'gzip')
    def test_nested_tar_metadata_without_extracting(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); buf=io.BytesIO()
            with tarfile.open(fileobj=buf,mode='w:gz') as inner:
                d=b'abc';info=tarfile.TarInfo('sample.traj');info.size=len(d);inner.addfile(info,io.BytesIO(d))
            path=base/'fixture.tar'
            with tarfile.open(path,'w') as outer:
                data=buf.getvalue(); info=tarfile.TarInfo('part-000.tar.gz');info.size=len(data);outer.addfile(info,io.BytesIO(data))
            import hashlib
            with patch('phase4.oc20_archive_inventory.EXPECTED_MD5',hashlib.md5(path.read_bytes()).hexdigest()):
                report=inspect(path,base/'out')
            self.assertEqual(report['top_level_entries'],1)
            self.assertEqual(report['extension_counts']['.tar.gz'],1)
            self.assertEqual(report['sample_nested_contents'][0]['children'][0]['name'],'sample.traj')
            self.assertEqual(report['status'],'FORMAT_INVENTORY_ONLY_NO_GEOMETRY_NO_BENCHMARK')
    def test_wrong_md5_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'a.tar'
            with tarfile.open(path,'w'):pass
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                inspect(path,Path(tmp)/'out')
