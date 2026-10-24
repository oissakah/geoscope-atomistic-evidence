import unittest,json,hashlib,sys,tempfile,shutil,collections
from pathlib import Path
from hpc.external_stage import stage,load,sha
from hpc.large_external_common import checked_shard,prompt

ROOT=Path(__file__).resolve().parents[1]
class ExternalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=stage(ROOT)
    def test_count_groups(self):
        self.assertEqual(self.manifest['n_requests'],1536)
        self.assertEqual(self.manifest['n_groups'],48)
        self.assertEqual(self.manifest['n_shards'],12)
    def test_shards(self):
        self.assertEqual([s['count'] for s in self.manifest['shards']],[128]*12)
        self.assertEqual(sum(len(s['groups']) for s in self.manifest['shards']),48)
        self.assertEqual(len({g for s in self.manifest['shards'] for g in s['groups']}),48)
    def test_requests_unique(self):
        ls=load(ROOT/'source/requests_PUBLIC_ONLY.jsonl')
        self.assertEqual(len({r['request_id'] for r in ls}),1536)
    def test_no_private_stage(self):
        fs={p.name for p in (ROOT/'outputs/model_only').iterdir() if p.is_file()}
        self.assertEqual(fs, {'stage_manifest.json','requests_PUBLIC_ONLY.jsonl'}|{f'requests_shard_{i:02d}.jsonl' for i in range(12)})
        self.assertNotIn('gold',str((ROOT/'outputs/model_only').as_posix()).lower())
    def test_sealed_gold_hash_only(self):
        pin=json.loads((ROOT/'frozen/EXTERNAL_INPUT_PINS.json').read_text())
        self.assertEqual(len(pin['model_only']['SEAL_OFFLINE/gold_proofs_SEALED.json']),64)
        self.assertEqual(self.manifest['source_gold_sha256'],pin['model_only']['SEAL_OFFLINE/gold_proofs_SEALED.json'])
    def test_source_frozen(self):
        pin=json.loads((ROOT/'frozen/EXTERNAL_INPUT_PINS.json').read_text())
        self.assertEqual(sha(ROOT/'source/requests_PUBLIC_ONLY.jsonl'),pin['staged_requests_sha256'])
    def test_small_infer_reused(self):
        text=(ROOT/'phase4/infer.py').read_text()
        self.assertIn('apply_chat_template',text)
        self.assertIn('local_files_only=True',text)
        self.assertIn('sampling',text)
    def test_partition(self):
        for n in ('small','large'):
            t=(ROOT/f'hpc/run_{n}_external.sbatch').read_text()
            self.assertIn('#SBATCH --partition=ock',t)
            self.assertIn('--gres=gpu:1',t)
    def test_large_semantics(self):
        text=(ROOT/'hpc/run_large_external.py').read_text()
        self.assertIn("thinking=False",text)
        self.assertIn('temperature=0.0',text)
        self.assertIn('existing',text)
    def test_single_group_one_shard(self):
        gids=json.loads((ROOT/'source/case_to_group_PUBLIC.json').read_text())
        s={}
        for row in self.manifest['shards']:
            for r in load(ROOT/'outputs/model_only'/row['file']):
                group=gids[r['case_id']]
                if group in s:self.assertEqual(s[group],row['shard'])
                s[group]=row['shard']
        self.assertEqual(len(s),48)
if __name__=='__main__':unittest.main()
