"""Scientific behavior checks for the frozen case constructor (stdlib only)."""

import copy
import json
import math
import unittest

from geomscope.cases import FAMILIES, build_cases


def pair_record(pair_id="outlier", *, mobile=1.004740, adsorbate=1.02, internal=0.007734):
    definitions = {}
    for metric in ("mobile_rmsd", "adsorbate_frame_rmsd", "internal_rmsd"):
        definitions[metric] = {
            "atom_subset": [0, 1, 2, 3] if metric == "mobile_rmsd" else [1, 2, 3],
            "frame": "surface-anchored frame" if metric != "internal_rmsd" else "adsorbate-local frame",
            "alignment": "Kabsch proper rotation" if metric == "internal_rmsd" else "none",
            "pbc": "minimum-image displacement after correspondence is fixed",
        }
    return {
        "pair_id": pair_id, "system_id": "surface_with_adsorbate", "group_id": "system_group_1",
        "split": "test", "origin": "measured_endpoint_pair",
        "measurements": {"mobile_rmsd_A": mobile, "adsorbate_frame_rmsd_A": adsorbate,
                         "internal_rmsd_A": internal},
        "metric_definitions": definitions,
        "provenance": {"workflow_a": "workflow-A", "workflow_b": "workflow-B",
                       "source_hashes": {"endpoint_a": "hash-a", "endpoint_b": "hash-b"},
                       "gold_label": "DO_NOT_COPY"},
        "force_converged": True, "reference_energy": -123.0,
        "gold_label": "DO_NOT_COPY", "rationale": "DO_NOT_COPY",
    }


class BuildCasesTests(unittest.TestCase):
    def setUp(self):
        self.record = pair_record()
        self.public, self.gold, self.summary = build_cases([self.record], [0.1])
        self.gold_by_id = {item["case_id"]: item for item in self.gold}

    def case(self, family, target="mobile_rmsd"):
        return next(item for item in self.public if item["family"] == family and item["target"]["metric_id"] == target)

    def test_five_families_and_unique_deterministic_ids(self):
        self.assertEqual(len(self.public), 15)
        self.assertEqual(set(self.summary["by_family"]), set(FAMILIES))
        self.assertEqual(len({item["case_id"] for item in self.public}), 15)
        self.assertEqual((self.public, self.gold, self.summary), build_cases([self.record], [0.1]))
        self.assertEqual(self.summary["by_label"], {
            "CONTRADICTED": 6, "INSUFFICIENT_EVIDENCE": 6, "SUPPORTED": 3,
        })
        self.assertTrue(all(item["split"] == "test" for item in self.public + self.gold))

    def test_evidence_removal_and_no_answer_leakage(self):
        relevant = self.case("missing_relevant_measurement")
        irrelevant = self.case("missing_irrelevant_measurement")
        retained = lambda case: {m["metric_id"] for m in case["model_payload"]["evidence_packet"]["measurements"]}
        self.assertNotIn("mobile_rmsd", retained(relevant))
        self.assertIn("mobile_rmsd", retained(irrelevant))
        self.assertEqual(self.gold_by_id[relevant["case_id"]]["expected"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(self.gold_by_id[relevant["case_id"]]["required_evidence_ids"], [])
        self.assertEqual(self.gold_by_id[irrelevant["case_id"]]["expected"], "CONTRADICTED")
        public_text = json.dumps(self.public)
        self.assertNotIn("DO_NOT_COPY", public_text)
        for case in self.public:
            payload = json.dumps(case["model_payload"])
            for forbidden in ("expected", "rationale", "required_evidence_ids", "CONTRADICTED", "SUPPORTED",
                              "INSUFFICIENT_EVIDENCE", "contrast_group_id", "force_converged", "reference_energy"):
                self.assertNotIn(forbidden, payload)
            self.assertEqual(set(case["model_payload"]), {"claim", "evidence_packet"})
            self.assertNotIn("expected", case)

    def test_unit_conversion_changes_measurements_not_physical_verdict(self):
        case = self.case("unit_conversion", "internal_rmsd")
        packet = case["model_payload"]["evidence_packet"]
        self.assertEqual(case["target"]["threshold"], 0.1)
        self.assertEqual(case["target"]["unit"], "angstrom")
        for m in packet["measurements"]:
            self.assertEqual(m["unit"], "nm")
            self.assertEqual(m["definition"]["units"], "nm")
            self.assertTrue(math.isclose(m["value"] * 10, self.record["measurements"][m["metric_id"] + "_A"]))
        self.assertEqual(self.gold_by_id[case["case_id"]]["expected"], "SUPPORTED")
        self.assertEqual(self.gold_by_id[case["case_id"]]["required_evidence_ids"], ["outlier::internal_rmsd"])

    def test_natural_outlier_requires_opposite_answers(self):
        mobile = self.case("metric_scope", "mobile_rmsd")
        internal = self.case("metric_scope", "internal_rmsd")
        self.assertEqual(self.gold_by_id[mobile["case_id"]]["expected"], "CONTRADICTED")
        self.assertEqual(self.gold_by_id[internal["case_id"]]["expected"], "SUPPORTED")
        self.assertEqual(self.summary["n_contrast_groups"], 1)
        self.assertEqual(set(self.summary["contrast_groups"][0]["case_ids"]), {mobile["case_id"], internal["case_id"]})
        self.assertNotIn("contrast_group_id", mobile)
        # Equal-sided measurements must never be altered to manufacture a contrast.
        _, _, no_contrast = build_cases([pair_record(internal=0.8)], [0.1])
        self.assertEqual(no_contrast["n_contrast_groups"], 0)

    def test_wrong_run_cannot_borrow_values_from_another_pair(self):
        case = self.case("wrong_run")
        packet = case["model_payload"]["evidence_packet"]
        self.assertNotEqual(packet["pair_id"], case["target"]["pair_id"])
        self.assertTrue(all(m["pair_id"] == packet["pair_id"] for m in packet["measurements"]))
        self.assertTrue(all(m["evidence_id"].startswith(packet["pair_id"] + "::") for m in packet["measurements"]))
        self.assertNotIn("source_hashes", packet["provenance"])
        self.assertEqual(self.gold_by_id[case["case_id"]]["expected"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(case["origin"], "synthetic_control")
        self.assertEqual(case["source_origin"], "measured_endpoint_pair")
        self.assertEqual(case["condition_kind"], "synthetic_pair_identity_reassignment")
        self.assertNotIn("condition_kind", case["model_payload"])
        self.assertEqual(self.summary["by_origin"], {"measured_endpoint_pair": 12, "synthetic_control": 3})
        self.assertEqual(self.summary["by_source_origin"], {"measured_endpoint_pair": 15})

    def test_manipulations_and_template_risk_are_audit_only(self):
        self.assertTrue(self.summary["template_shortcut_risk"])
        for case in self.public:
            self.assertEqual(case["evidence_packet_modified"], case["family"] != "metric_scope")
            self.assertFalse(case["source_coordinates_modified"])
            self.assertNotIn("source_origin", case["model_payload"])
            self.assertNotIn("condition_kind", case["model_payload"])
            self.assertNotIn(case["target"]["metric_id"], case["model_payload"]["claim"])

    def test_threshold_margin_is_inclusive_and_applied_per_target(self):
        records = [pair_record(mobile=0.105, adsorbate=0.095, internal=0.007)]
        public, _, summary = build_cases(records, [0.1], margin_A=0.005)
        self.assertEqual(len(public), 5)
        self.assertTrue(all(case["target"]["metric_id"] == "internal_rmsd" for case in public))
        self.assertEqual(len(summary["skipped_near_threshold"]), 2)
        self.assertEqual(summary["n_contrast_groups"], 0)

    def test_does_not_mutate_input_and_ignores_root_answer_fields(self):
        original = copy.deepcopy(self.record)
        build_cases([self.record], [0.1])
        self.assertEqual(self.record, original)
        changed = copy.deepcopy(self.record)
        changed["force_converged"] = False
        changed["reference_energy"] = 10000
        self.assertEqual(build_cases([self.record], [0.1]), build_cases([changed], [0.1]))

    def test_missing_physical_definition_and_conflicting_group_splits_rejected(self):
        missing = copy.deepcopy(self.record)
        del missing["metric_definitions"]["mobile_rmsd"]["pbc"]
        with self.assertRaisesRegex(ValueError, "explicit pbc"):
            build_cases([missing], [0.1])
        different_split = pair_record("another_pair")
        different_split["split"] = "train"
        with self.assertRaisesRegex(ValueError, "more than one split"):
            build_cases([self.record, different_split], [0.1])

    def test_geometry_definition_aliases_and_correspondence_survive(self):
        record = copy.deepcopy(self.record)
        for metric_id in list(record["metric_definitions"]):
            definition = record["metric_definitions"].pop(metric_id)
            definition["atom_indices"] = definition.pop("atom_subset")
            definition["periodic_treatment"] = definition.pop("pbc")
            definition["units"] = "Angstrom"
            definition["correspondence"] = "fixed global atom indices; no permutation"
            definition["weighting"] = "equal per atom"
            record["metric_definitions"][metric_id + "_A"] = definition
        public, _, _ = build_cases([record], [0.1])
        for case in public:
            for measurement in case["model_payload"]["evidence_packet"]["measurements"]:
                definition = measurement["definition"]
                self.assertIn("atom_subset", definition)
                self.assertIn("pbc", definition)
                self.assertEqual(definition["correspondence"], "fixed global atom indices; no permutation")
                self.assertEqual(definition["weighting"], "equal per atom")

    def test_pbc_flags_do_not_hide_periodic_algorithm(self):
        record = copy.deepcopy(self.record)
        for metric_id, definition in record["metric_definitions"].items():
            definition["pbc"] = [True, True, False]
            definition["atom_indices"] = copy.deepcopy(definition["atom_subset"])
            definition["periodic_treatment"] = (
                "connected bond-graph unwrapping before alignment; no MIC on fitted residuals"
                if metric_id == "internal_rmsd" else
                "minimum-image displacement independently per matched atom"
            )
        public, _, _ = build_cases([record], [0.1])
        case = next(case for case in public if case["family"] == "metric_scope")
        for measurement in case["model_payload"]["evidence_packet"]["measurements"]:
            source = record["metric_definitions"][measurement["metric_id"]]
            definition = measurement["definition"]
            self.assertEqual(definition["pbc"], [True, True, False])
            self.assertEqual(definition["periodic_treatment"], source["periodic_treatment"])
            self.assertEqual(definition["atom_indices"], source["atom_indices"])

    def test_invalid_values_and_duplicate_ids_rejected(self):
        for bad_value in (float("nan"), float("inf"), -1.0, True):
            record = pair_record(mobile=bad_value)
            with self.assertRaises(ValueError):
                build_cases([record], [0.1])
        with self.assertRaisesRegex(ValueError, "duplicate pair_id"):
            build_cases([self.record, self.record], [0.1])
        with self.assertRaisesRegex(ValueError, "must not repeat"):
            build_cases([self.record], [0.1, 0.10])

    def test_reordering_inputs_does_not_change_result(self):
        other = pair_record("another_pair")
        self.assertEqual(build_cases([self.record, other], [0.1, 0.2]),
                         build_cases([other, self.record], [0.2, 0.1]))


if __name__ == "__main__":
    unittest.main()
