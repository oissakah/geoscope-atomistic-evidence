import unittest,math,numpy as np
from phase4.external_oc20 import candidate_metrics,record_pair,pair_from_ase,composition_cluster,sha,SELECT_N,SOURCE_MD5,SOURCE_URL
from phase4.geometry_validation import minimum_image_displacements
class FakeAtoms:
 def __init__(self,positions,tags,symbols,cell=None):
  self._pos=np.array(positions,dtype=float);self._tags=tags;self._sy=symbols
  self.cell=type('Cell',(),{'array':np.diag([10.,10.,20.]) if cell is None else np.array(cell)})()
  self.constraints=[]
 def get_positions(self):return self._pos
 def get_chemical_symbols(self):return self._sy
 def get_tags(self):return self._tags
 def get_pbc(self):return np.array([True,True,False])
class ExternalTests(unittest.TestCase):
 def setUp(self):
  # Two OH adsorbate atoms, surface mobile, stationary anchor. Rigid 0.2-A move.
  self.sym=['Cu','Cu','Cu','Cu','O','H']
  self.tags=[0,0,1,1,2,2]
  self.x=np.array([[1,1,0],[5,5,0],[1,2,2],[5,2,2],[1,2,4],[1,2,4.97]],float)
 def test_48_frozen(self):self.assertEqual(SELECT_N,48);self.assertEqual(SOURCE_MD5,'bc74b6474a13542cc56eaa97bd51adfc')
 def test_geometry_pair_recomputed(self):
  y=self.x.copy();y[2:]+=np.array([0.2,0,0])
  p=pair_from_ase(FakeAtoms(self.x,self.tags,self.sym),FakeAtoms(y,self.tags,self.sym),'fake_1')
  real,synthetic=candidate_metrics(p)
  self.assertAlmostEqual(real['adsorbate_frame_rmsd_A'],.2,places=7)
  self.assertAlmostEqual(real['internal_rmsd_A'],0.,places=7)
  self.assertAlmostEqual(real['anchor_rmsd_A'],0.,places=7)
  self.assertNotAlmostEqual(synthetic['adsorbate_frame_rmsd_A'],real['adsorbate_frame_rmsd_A'])
  self.assertEqual(len(composition_cluster(p)),20)
  records=record_pair(p,real,synthetic)
  self.assertEqual(len(records),2);self.assertEqual(records[0]['split'],'heldout')
  self.assertIn('synthetic',records[1]['origin'])
  self.assertTrue(all('system_id_PRIVATE' in x for x in records))
  self.assertTrue(all('metric_definitions' in x for x in records))
 def test_anchor_drift_refused(self):
  y=self.x.copy();y[0,0]+=.1
  with self.assertRaisesRegex(ValueError,'anchor_motion'):
   pair_from_ase(FakeAtoms(self.x,self.tags,self.sym),FakeAtoms(y,self.tags,self.sym),'fake_2')
 def test_changed_identity_refused(self):
  y=self.x.copy();s=self.sym.copy();s[-1]='O'
  with self.assertRaisesRegex(ValueError,'atom_identity'):
   pair_from_ase(FakeAtoms(self.x,self.tags,self.sym),FakeAtoms(y,self.tags,s),'fake_3')
 def test_single_atom_rejected(self):
  t=self.tags.copy();t[-1]=1
  with self.assertRaisesRegex(ValueError,'single_atom'):
   pair_from_ase(FakeAtoms(self.x,t,self.sym),FakeAtoms(self.x,t,self.sym),'fake_4')
 def test_tag0_anchor_drift_conservative(self):
  y=self.x.copy();y[1,1]+=.0003
  with self.assertRaisesRegex(ValueError,'tag0_not_stationary'):
   pair_from_ase(FakeAtoms(self.x,self.tags,self.sym),FakeAtoms(y,self.tags,self.sym),'fake_5')
 def test_original_geometry_has_fixed_protocol(self):
  from phase4.freeze_benchmark import FRAME,MIC,IPERIODIC
  self.assertEqual(FRAME,'shared stored slab coordinate frame')
  self.assertIn('minimum-image',MIC)
  self.assertIn('unwrapping',IPERIODIC)
if __name__=='__main__':unittest.main()
