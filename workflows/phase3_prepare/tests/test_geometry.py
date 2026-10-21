"""Analytic geometry tests; these tests run no physical calculators."""

import unittest

import numpy as np
from ase import Atoms

from geomscope.geometry import analyze_pair


class GeometryTests(unittest.TestCase):
    def setUp(self):
        # Four labeled vertices of a regular tetrahedron, centered at (5,5,3).
        # Each centered vertex has norm sqrt(3)/2 and edge length sqrt(2).
        self.center = np.array([5.0, 5.0, 3.0])
        self.vertices = 0.5 * np.array(
            [[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], dtype=float
        )
        anchors = [[0, 0, 0], [2, 0, 0], [0, 2, 0]]
        self.a = Atoms(
            ["Cu", "Cu", "Cu", "C", "H", "F", "Cl"],
            positions=np.vstack((anchors, self.vertices + self.center)),
            cell=[20, 20, 20],
            pbc=[True, True, False],
        )
        self.mobile = [3, 4, 5, 6]
        self.anchors = [0, 1, 2]
        self.bonds = [[3, 4], [3, 5], [3, 6]]

    def analyze(self, b, a=None, **overrides):
        arguments = dict(
            mobile_indices=self.mobile,
            adsorbate_indices=self.mobile,
            anchor_indices=self.anchors,
            adsorbate_bonds=self.bonds,
        )
        arguments.update(overrides)
        return analyze_pair(self.a if a is None else a, b, **arguments)

    def test_rigid_translation_separates_frame_and_internal_metrics(self):
        b = self.a.copy()
        b.positions[self.mobile] += [1, 0, 0]
        actual = self.analyze(b)
        self.assertAlmostEqual(actual["mobile_rmsd_A"], 1.0, places=12)
        self.assertAlmostEqual(actual["adsorbate_frame_rmsd_A"], 1.0, places=12)
        self.assertAlmostEqual(actual["internal_rmsd_A"], 0.0, places=12)
        self.assertEqual(actual["anchor_max_displacement_A"], 0.0)
        self.assertEqual(actual["metric_definitions"]["internal_rmsd_A"]["atom_indices"], self.mobile)

    def test_rigid_rotation_changes_frame_metric_but_not_internal_metric(self):
        b = self.a.copy()
        rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
        b.positions[self.mobile] = self.vertices @ rotation + self.center
        actual = self.analyze(b)
        # Every vertex changes by length 1 under this quarter-turn.
        self.assertAlmostEqual(actual["adsorbate_frame_rmsd_A"], 1.0, places=12)
        self.assertAlmostEqual(actual["internal_rmsd_A"], 0.0, places=12)
        self.assertAlmostEqual(actual["topology"]["kabsch_rotation_determinant"], 1.0, places=12)

    def test_internal_distortion_has_analytic_nonzero_rmsd(self):
        b = self.a.copy()
        b.positions[self.mobile] = 2.0 * self.vertices + self.center
        actual = self.analyze(b)
        # Isotropic expansion cannot be removed by any rigid rotation.
        self.assertAlmostEqual(actual["internal_rmsd_A"], np.sqrt(3) / 2, places=12)

    def test_mobile_and_adsorbate_masks_have_distinct_denominators(self):
        a = self.a.copy()
        a.extend(Atoms("Cu", positions=[[3, 3, 0]]))
        b = a.copy()
        b.positions[self.mobile] += [1, 0, 0]
        actual = self.analyze(b, a=a, mobile_indices=[3, 4, 5, 6, 7])
        # Four displaced adsorbate atoms and one stationary mobile-slab atom.
        self.assertAlmostEqual(actual["mobile_rmsd_A"], np.sqrt(4 / 5), places=12)
        self.assertAlmostEqual(actual["adsorbate_frame_rmsd_A"], 1.0, places=12)
        self.assertEqual(actual["metric_definitions"]["mobile_rmsd_A"]["atom_indices"], [3, 4, 5, 6, 7])

    def test_reflected_labeled_tetrahedron_is_not_superimposable(self):
        b = self.a.copy()
        reflected = self.vertices.copy()
        reflected[:, 0] *= -1
        b.positions[self.mobile] = reflected + self.center
        actual = self.analyze(b)
        # X.T X = I: enforcing a proper rotation leaves squared residual 4,
        # so the RMSD over four fixed-correspondence vertices is exactly 1.
        self.assertAlmostEqual(actual["internal_rmsd_A"], 1.0, places=12)
        self.assertAlmostEqual(actual["topology"]["kabsch_rotation_determinant"], 1.0, places=12)

    def test_triclinic_wrapping_does_not_change_observables(self):
        a = self.a.copy()
        a.set_cell([[10, 0, 0], [3, 9, 0], [0, 0, 20]])
        a.positions[self.mobile] = self.vertices + [9.7, 8.7, 3]
        b = a.copy()
        b.wrap()
        actual = self.analyze(b, a=a)
        self.assertAlmostEqual(actual["mobile_rmsd_A"], 0.0, places=11)
        self.assertAlmostEqual(actual["internal_rmsd_A"], 0.0, places=11)
        # Translation and wrapping retain exactly 0.5 A frame displacement.
        b.positions[self.mobile] += [0.3, 0.4, 0]
        b.wrap()
        moved = self.analyze(b, a=a)
        self.assertAlmostEqual(moved["adsorbate_frame_rmsd_A"], 0.5, places=11)
        self.assertAlmostEqual(moved["internal_rmsd_A"], 0.0, places=11)

    def test_anchor_motion_is_reported_without_registration_or_hidden_cutoff(self):
        b = self.a.copy()
        b.positions[:] += [0.03, 0.04, 0]
        actual = self.analyze(b)
        self.assertAlmostEqual(actual["anchor_rmsd_A"], 0.05, places=12)
        self.assertAlmostEqual(actual["anchor_max_displacement_A"], 0.05, places=12)
        self.assertAlmostEqual(actual["mobile_rmsd_A"], 0.05, places=12)
        self.assertFalse(actual["validation"]["anchor_drift_cutoff_applied"])

    def test_anchor_maximum_is_not_rmsd(self):
        b = self.a.copy()
        b.positions[0] += [0.03, 0, 0]
        actual = self.analyze(b)
        self.assertAlmostEqual(actual["anchor_rmsd_A"], 0.03 / np.sqrt(3), places=12)
        self.assertAlmostEqual(actual["anchor_max_displacement_A"], 0.03, places=12)

    def test_symbol_cell_and_pbc_mismatch_fail_closed(self):
        for alteration in ("symbol", "cell", "pbc"):
            b = self.a.copy()
            if alteration == "symbol":
                b[4].symbol = "He"
            elif alteration == "cell":
                b.cell[0, 0] += 0.01
            else:
                b.pbc[2] = True
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                self.analyze(b)

    def test_cell_tolerance_is_absolute(self):
        b = self.a.copy()
        b.cell[0, 0] += 5e-7
        self.analyze(b)
        with self.assertRaises(ValueError):
            self.analyze(b, cell_atol=1e-8)

    def test_invalid_masks_fail_closed(self):
        invalid = [
            {"mobile_indices": []},
            {"mobile_indices": [3, 3, 4, 5, 6]},
            {"mobile_indices": [3, 4, 5, 7]},
            {"mobile_indices": [True, 4, 5, 6]},
            {"mobile_indices": [3.0, 4, 5, 6]},
            {"mobile_indices": [3, 4, 5]},
            {"anchor_indices": [0, 1]},
            {"anchor_indices": [0, 1, 3]},
        ]
        for arguments in invalid:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.analyze(self.a.copy(), **arguments)

    def test_collinear_anchors_and_nonfinite_positions_are_rejected(self):
        b = self.a.copy()
        b.positions[2] = [4, 0, 0]
        with self.assertRaisesRegex(ValueError, "noncollinear"):
            self.analyze(b)
        b = self.a.copy()
        b.positions[4, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            self.analyze(b)

    def test_disconnected_duplicate_or_outside_bond_graph_rejected(self):
        invalid = [
            [[3, 4], [5, 6]],
            self.bonds + [[4, 3]],
            [[3, 4], [3, 5], [3, 0]],
        ]
        for bonds in invalid:
            with self.subTest(bonds=bonds), self.assertRaises(ValueError):
                self.analyze(self.a.copy(), adsorbate_bonds=bonds)

    def test_consistent_molecular_cycle_allowed(self):
        actual = self.analyze(self.a.copy(), adsorbate_bonds=self.bonds + [[4, 5]])
        self.assertAlmostEqual(actual["internal_rmsd_A"], 0.0, places=12)

    def test_nonzero_periodic_cycle_winding_rejected(self):
        a = self.a.copy()
        a.set_cell([10, 10, 20])
        a.pbc = [True, False, False]
        a.positions[self.mobile] = [[0, 5, 3], [3, 5, 3], [6, 5, 3], [9, 5, 3]]
        with self.assertRaisesRegex(ValueError, "cycle winding"):
            self.analyze(a.copy(), a=a, adsorbate_bonds=[[3, 4], [4, 5], [5, 6], [6, 3]])

    def test_periodic_half_cell_bond_is_rejected_as_ambiguous(self):
        a = self.a.copy()
        a.set_cell([4, 20, 20])
        a.pbc = [True, False, False]
        a.positions[3] = [0, 5, 3]
        a.positions[4] = [2, 5, 3]
        with self.assertRaisesRegex(ValueError, "unique periodic unwrapping"):
            self.analyze(a.copy(), a=a)

    def test_no_pbc_accepts_zero_cell_and_remains_analytic(self):
        a = self.a.copy()
        a.pbc = False
        a.cell = np.zeros((3, 3))
        b = a.copy()
        b.positions[self.mobile] += [3, 4, 0]
        actual = self.analyze(b, a=a)
        self.assertAlmostEqual(actual["mobile_rmsd_A"], 5.0, places=12)
        self.assertAlmostEqual(actual["internal_rmsd_A"], 0.0, places=12)
        self.assertIsNone(actual["topology"]["periodic_unique_bond_radius_lower_bound_A"])

    def test_no_calculator_calls_or_input_mutation(self):
        class BombCalculator:
            def get_property(self, *args, **kwargs):
                raise AssertionError("A calculator must not be invoked by geometry analysis")
        self.a.calc = BombCalculator()
        b = self.a.copy()
        original_a, original_b = self.a.positions.copy(), b.positions.copy()
        self.analyze(b)
        np.testing.assert_array_equal(self.a.positions, original_a)
        np.testing.assert_array_equal(b.positions, original_b)


if __name__ == "__main__":
    unittest.main()
