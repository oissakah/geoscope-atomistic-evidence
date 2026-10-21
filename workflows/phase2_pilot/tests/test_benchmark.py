import copy
import json
import re
import unittest
from collections import Counter, defaultdict

from phase2.benchmark import QUANTITY_CONVENTION, baseline, build_benchmark, parse_payload


def sources(n=2):
    records = []
    for group in range(n):
        defs = {}
        for metric, mask, aligned in (("mobile_rmsd_A", [3, 4, 5, 6], False), ("adsorbate_frame_rmsd_A", [4, 5, 6], False), ("internal_rmsd_A", [4, 5, 6], True)):
            defs[metric] = {
                "atom_indices": mask, "atom_subset": mask, "pbc": [True, True, True],
                "frame": "independent molecular centroids" if aligned else "shared stored slab coordinate frame",
                "alignment": "proper Kabsch rotation plus translation; no reflection" if aligned else "none",
                "periodic_treatment": "connected bond-graph unwrapping before alignment; no MIC on fitted residuals" if aligned else "minimum-image displacement independently per matched atom",
                "weighting": "equal weight per selected atom",
            }
        defs["anchor_rmsd_A"] = {"atom_indices": [0, 1, 2]}
        for origin in ("measured_endpoint_pair", "synthetic_control"):
            records.append({
                "pair_id": f"private_original_system_{group}_{origin}", "group_id": f"private_group_{group}",
                "split": "pilot_development", "origin": origin,
                "measurements": {"mobile_rmsd_A": .42 + group * .01, "adsorbate_frame_rmsd_A": .7 + group * .01,
                                 "internal_rmsd_A": .13 + group * .01 if origin == "measured_endpoint_pair" else 1e-16},
                "metric_definitions": copy.deepcopy(defs),
                "provenance": {"workflow_a": "SENSITIVE", "workflow_b": "rigid_translation", "expected": "ANSWER_LEAK"},
            })
    return records


class BenchmarkTests(unittest.TestCase):
    def test_counts_balance_and_source_independence(self):
        public, gold, audit = build_benchmark(sources(20))
        self.assertEqual(len(public), 320)
        self.assertEqual(audit["n_base_cases"], 160)
        self.assertEqual(audit["by_label"], {"SUPPORTED": 120, "CONTRADICTED": 120, "INSUFFICIENT_EVIDENCE": 80})
        self.assertEqual(Counter(p["group_id"] for p in public), {f"private_group_{i}": 16 for i in range(20)})
        for labels in audit["by_family_label"].values():
            if "SUPPORTED" in labels:
                self.assertEqual(labels["SUPPORTED"], labels["CONTRADICTED"])
        self.assertEqual(audit["by_presentation"], {"report": 160, "structured": 160})
        self.assertTrue(audit["all_pilot_development"])
        self.assertTrue(all(p["split"] == "pilot_development" for p in public))

    def test_scope_baseline_matches_every_gold(self):
        public, gold, _ = build_benchmark(sources(4))
        for p, g in zip(public, gold):
            self.assertEqual(p["case_id"], g["case_id"])
            self.assertEqual(baseline(p["model_payload"]), {"verdict": g["expected"], "evidence_ids": g["required_evidence_ids"]})

    def test_both_presentations_explicitly_define_the_quantity_reduction(self):
        public, _, _ = build_benchmark(sources(2))
        self.assertIn("square root of the mean squared coordinate-residual norm", QUANTITY_CONVENTION)
        self.assertIn("after the stated alignment and periodic handling", QUANTITY_CONVENTION)
        for case in public:
            payload = case["model_payload"]
            if case["presentation"] == "structured":
                self.assertEqual(payload["evidence_packet"]["quantity_convention"], QUANTITY_CONVENTION)
            else:
                self.assertEqual(payload["evidence_report"].splitlines()[0], QUANTITY_CONVENTION)
                self.assertNotIn("RMSD", payload["evidence_report"])

    def test_deterministic_input_order_and_no_mutation(self):
        original = sources(3)
        before = copy.deepcopy(original)
        built = build_benchmark(original)
        self.assertEqual(original, before)
        self.assertEqual(built, build_benchmark(list(reversed(original))))
        self.assertNotEqual(built, build_benchmark(original, seed=7))

    def test_no_source_answer_or_transform_leaks_in_payload(self):
        public, gold, _ = build_benchmark(sources(3))
        aliases, evidence_ids = set(), set()
        for p in public:
            payload = p["model_payload"]
            text = json.dumps(payload)
            for bad in ("private_", "SENSITIVE", "ANSWER_LEAK", "rigid_translation", "synthetic_control", "SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE", "source_pair_id", "target_metric", "condition_kind"):
                self.assertNotIn(bad, text)
            parsed = parse_payload(payload)
            self.assertNotIn(parsed["pair_id"], aliases)
            aliases.add(parsed["pair_id"])
            for row in parsed["measurements"]:
                self.assertRegex(row["evidence_id"], r"^E_[0-9a-f]{24}$")
                self.assertNotIn(row["evidence_id"], evidence_ids)
                evidence_ids.add(row["evidence_id"])
            if p["presentation"] == "report":
                report = payload["evidence_report"]
                for name in ("metric_id", "display_name", "mobile_rmsd", "internal_rmsd", "adsorbate_frame_rmsd", "RMSD"):
                    self.assertNotIn(name, report)
        self.assertEqual(len(aliases), len(public))

    def test_paired_styles_share_values_but_not_ids(self):
        public, gold, _ = build_benchmark(sources(3))
        by_base = defaultdict(list)
        for p in public:
            by_base[p["base_case_id"]].append(parse_payload(p["model_payload"]))
        for variants in by_base.values():
            a, b = variants
            self.assertNotEqual(a["pair_id"], b["pair_id"])
            self.assertEqual(a["threshold_A"], b["threshold_A"])
            self.assertEqual(a["operator"], b["operator"])
            self.assertEqual([m["value"] for m in a["measurements"]], [m["value"] for m in b["measurements"]])
            self.assertTrue({m["evidence_id"] for m in a["measurements"]}.isdisjoint({m["evidence_id"] for m in b["measurements"]}))

    def test_threshold_contrasts_have_both_labels_and_same_operator(self):
        public, gold, _ = build_benchmark(sources(5))
        contrasts = defaultdict(list)
        operators = defaultdict(set)
        for p, g in zip(public, gold):
            if p["contrast_group_id"] is not None:
                contrasts[(p["contrast_group_id"], p["presentation"])].append(g["expected"])
                operators[p["contrast_group_id"]].add(p["operator"])
        self.assertTrue(all(sorted(labels) == ["CONTRADICTED", "SUPPORTED"] for labels in contrasts.values()))
        self.assertTrue(all(len(x) == 1 for x in operators.values()))

    def test_missing_values_cannot_be_recovered_from_other_target_metrics(self):
        public, gold, _ = build_benchmark(sources(2))
        for p, g in zip(public, gold):
            if p["family"] in ("missing_measurements", "wrong_run"):
                parsed = parse_payload(p["model_payload"])
                self.assertTrue(parsed["measurements"])
                self.assertFalse(any(m["pair_id"] == parsed["pair_id"] for m in parsed["measurements"]))
                self.assertEqual(g["expected"], "INSUFFICIENT_EVIDENCE")
                self.assertEqual(g["required_evidence_ids"], [])

    def test_unit_and_irrelevant_ablation_leave_target_present(self):
        public, gold, _ = build_benchmark(sources(3))
        for p in public:
            parsed = parse_payload(p["model_payload"])
            rows = parsed["measurements"]
            if p["family"] == "unit_conversion":
                self.assertEqual(len(rows), 6)
                self.assertTrue(all(x["unit"] == "nm" for x in rows))
            elif p["family"] == "missing_irrelevant_measurement":
                self.assertEqual(len(rows), 5)
                self.assertEqual(sum(m["pair_id"] == parsed["pair_id"] for m in rows), 2)
                self.assertNotEqual(baseline(p["model_payload"])["verdict"], "INSUFFICIENT_EVIDENCE")

    def test_scope_uses_definitions_not_the_explicit_metric_id(self):
        public, _, _ = build_benchmark(sources(2))
        for p in public:
            if p["presentation"] == "structured":
                payload = copy.deepcopy(p["model_payload"])
                before = baseline(payload)
                for m in payload["evidence_packet"]["measurements"]:
                    m["metric_id"] = "false_label"
                    m["display_name"] = "false_label"
                self.assertEqual(baseline(payload), before)

    def test_bad_sources_rejected_without_substitution(self):
        for mutation in ("zero_real", "missing_control", "wrong_mask", "wrong_split", "duplicate"):
            data = sources()
            if mutation == "zero_real":
                data[0]["measurements"]["internal_rmsd_A"] = 0
            elif mutation == "missing_control":
                data.pop()
            elif mutation == "wrong_mask":
                data[1]["metric_definitions"]["mobile_rmsd_A"]["atom_indices"] = [3, 4, 5]
            elif mutation == "wrong_split":
                data[0]["split"] = "test"
            else:
                data.append(copy.deepcopy(data[0]))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                build_benchmark(data)

    def test_baseline_controls_do_not_inadvertently_use_gold_or_audit(self):
        public, gold, _ = build_benchmark(sources(5))
        scores = Counter()
        for p, g in zip(public, gold):
            for method in ("scope", "value_only", "structure"):
                result = baseline(p["model_payload"], method)
                scores[method] += result["verdict"] == g["expected"]
                self.assertIn(result["verdict"], ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"))
        self.assertEqual(scores["scope"], len(public))
        self.assertLess(scores["value_only"], len(public))
        self.assertLess(scores["structure"], len(public))
        with self.assertRaises(ValueError):
            baseline(public[0]["model_payload"], "secret_gold")


if __name__ == "__main__":
    unittest.main()
