import copy
import json
import tempfile
import unittest
from pathlib import Path

from phase2.evaluation import evaluate, parse_prediction, write_reports


E1 = "E_" + "1" * 24
E2 = "E_" + "2" * 24


def fixture():
    public, gold = [], []
    # Two source groups, each with two threshold claims rendered in two styles.
    for group in ("g1", "g2"):
        for label in ("SUPPORTED", "CONTRADICTED"):
            base = group + ":" + label
            for style in ("structured", "report"):
                cid = base + ":" + style
                payload = {"claim": {"text": "Claim"}}
                if style == "structured":
                    payload["evidence_packet"] = {"measurements": [{"evidence_id": E1}, {"evidence_id": E2}]}
                else:
                    payload["evidence_report"] = f"Evidence ID: {E1}. Endpoint pair: P_abc.\nEvidence ID: {E2}. Other measurement."
                public.append({"case_id": cid, "group_id": group, "base_case_id": base,
                               "contrast_group_id": group + ":contrast", "family": "scope", "target_metric": "internal_rmsd",
                               "presentation": style, "model_payload": payload})
                gold.append({"case_id": cid, "expected": label, "required_evidence_ids": [E1]})
    return public, gold


def prediction(answer, *, model="m", condition="direct", verdict=None, ids=None, status="ok"):
    return {"case_id": answer["case_id"], "model_key": model, "condition": condition, "status": status,
            "raw_output": json.dumps({"verdict": verdict or answer["expected"],
                                      "evidence_ids": answer["required_evidence_ids"] if ids is None else ids})}


class ParseTests(unittest.TestCase):
    def test_exact_object_whitespace(self):
        self.assertEqual(parse_prediction(' \n {"verdict":"SUPPORTED","evidence_ids":[]}\n'), {"verdict": "SUPPORTED", "evidence_ids": []})

    def test_rejects_all_nonconforming_formats(self):
        valid = '{"verdict":"SUPPORTED","evidence_ids":[]}'
        bad = [None, {}, "", "```json\n" + valid + "\n```", valid + " commentary", "commentary " + valid,
               "[" + valid + "]", '{"verdict":"supported","evidence_ids":[]}',
               '{"verdict":"SUPPORTED","evidence_ids":[],"reason":"x"}',
               '{"verdict":"SUPPORTED"}', '{"verdict":"SUPPORTED","verdict":"CONTRADICTED","evidence_ids":[]}',
               '{"verdict":"SUPPORTED","evidence_ids":["a","a"]}',
               '{"verdict":"SUPPORTED","evidence_ids":[""]}', '{"verdict":"SUPPORTED","evidence_ids":[1]}',
               '{"verdict":"SUPPORTED","evidence_ids":[" padded"]}',
               '{"verdict":"SUPPORTED","evidence_ids":"a"}', '{"verdict":[],"evidence_ids":[]}',
               '{"verdict":"SUPPORTED","evidence_ids":[NaN]}']
        for item in bad:
            with self.subTest(item=item):
                with self.assertRaises(ValueError):
                    parse_prediction(item)


class EvaluationTests(unittest.TestCase):
    def test_perfect_predictions_and_reports(self):
        public, gold = fixture()
        before = copy.deepcopy((public, gold))
        result = evaluate(public, gold, [prediction(a) for a in gold], bootstrap_samples=50)
        s = result["summaries"][0]
        self.assertEqual(s["strict_accuracy"], 1)
        self.assertEqual(s["joint_accuracy"], 1)
        self.assertEqual(s["format_rate"], 1)
        self.assertEqual(s["macro_f1_fixed_three_labels"], 2 / 3)
        self.assertEqual(s["paired"]["eligible_binary_contrast_pairs"], 4)
        self.assertEqual(s["paired"]["contrast_pair_both_labels_correct"], 1)
        self.assertEqual(s["paired"]["eligible_representation_pairs"], 4)
        self.assertEqual(s["paired"]["representation_both_joint_correct"], 1)
        self.assertEqual(s["bootstrap"]["intervals"]["strict_accuracy"], [1, 1])
        self.assertEqual((public, gold), before)
        with tempfile.TemporaryDirectory() as folder:
            write_reports(result, folder)
            self.assertEqual(json.loads((Path(folder) / "evaluation.json").read_text())["source_groups"], 2)
            self.assertEqual(len((Path(folder) / "case_scores.csv").read_text().splitlines()), 9)

    def test_partial_errors_duplicates_do_not_inflate(self):
        public, gold = fixture()
        predictions = [prediction(a) for a in gold[:5]]
        predictions.append(prediction(gold[0]))  # Duplicate invalidates the key.
        predictions[1]["status"] = "failed"
        predictions[2]["raw_output"] = "not JSON"
        predictions[2]["parsed_prediction"] = {"verdict": gold[2]["expected"], "evidence_ids": [E1]}
        predictions.append({"case_id": "unknown", "model_key": "m", "condition": "direct", "raw_output": "irrelevant"})
        result = evaluate(public, gold, predictions, bootstrap_samples=0)
        s = result["summaries"][0]
        self.assertEqual(s["cases"], 8)
        self.assertEqual(s["strict_correct"], 2)
        self.assertEqual(s["strict_accuracy"], .25)
        self.assertEqual(s["format_rate"], .25)
        self.assertEqual(s["valid_only_accuracy"], 1)
        self.assertEqual(sum(s["confusion"][label]["INVALID"] for label in s["confusion"]), 6)
        c = result["completeness"][0]
        self.assertEqual((c["missing_cases"], c["duplicate_cases"], c["extra_duplicate_records"]), (3, 1, 1))
        self.assertEqual(len(result["unknown_prediction_cases"]), 1)
        self.assertFalse(c["complete_unique_record_set"])

    def test_missing_placeholders_remain_missing(self):
        public, gold = fixture()
        result = evaluate(public, gold, [prediction(a, status="missing") for a in gold], bootstrap_samples=0)
        self.assertEqual(result["completeness"][0]["missing_cases"], 8)
        self.assertEqual(result["summaries"][0]["strict_accuracy"], 0)

    def test_citation_exact_precision_and_fabrication(self):
        public, gold = fixture()
        predictions = [prediction(a) for a in gold]
        predictions[0] = prediction(gold[0], ids=[E1, E2])
        predictions[1] = prediction(gold[1], ids=["fabricated"])
        predictions[2] = prediction(gold[2], ids=[])
        rows = {r["case_id"]: r for r in evaluate(public, gold, predictions, bootstrap_samples=0)["rows"]}
        self.assertTrue(rows[gold[0]["case_id"]]["label_correct"])
        self.assertFalse(rows[gold[0]["case_id"]]["joint_correct"])
        self.assertEqual(rows[gold[0]["case_id"]]["evidence_precision"], .5)
        self.assertFalse(rows[gold[1]["case_id"]]["citations_reference_visible"])
        self.assertEqual(rows[gold[1]["case_id"]]["evidence_precision"], 0)
        self.assertEqual(rows[gold[2]["case_id"]]["evidence_recall"], 0)

    def test_insufficient_and_error_rate_denominators(self):
        public, gold = fixture()
        gold[0]["expected"] = "INSUFFICIENT_EVIDENCE"
        gold[0]["required_evidence_ids"] = []
        predictions = [prediction(a) for a in gold]
        predictions[0] = prediction(gold[0], verdict="SUPPORTED", ids=[])
        predictions[1] = prediction(gold[1], verdict="INSUFFICIENT_EVIDENCE", ids=[])
        result = evaluate(public, gold, predictions, bootstrap_samples=0)
        s = result["summaries"][0]
        self.assertEqual(s["unsupported_claims"], 5)
        self.assertEqual(s["unsupported_acceptance_rate"], 1 / 5)
        self.assertEqual(s["decisive_claims"], 7)
        self.assertEqual(s["excess_abstention_rate"], 1 / 7)
        self.assertEqual(s["insufficiency_recall"], 0)

    def test_correct_insufficient_empty_citations(self):
        public, gold = fixture()
        gold[0].update(expected="INSUFFICIENT_EVIDENCE", required_evidence_ids=[])
        result = evaluate(public, gold, [prediction(a) for a in gold], bootstrap_samples=0)
        row = next(r for r in result["rows"] if r["case_id"] == gold[0]["case_id"])
        self.assertTrue(row["joint_correct"])
        self.assertEqual((row["evidence_precision"], row["evidence_recall"]), (1, 1))

    def test_cluster_bootstrap_is_grouped_and_deterministic(self):
        public, gold = fixture()
        predictions = [prediction(a, verdict=("INSUFFICIENT_EVIDENCE" if a["case_id"].startswith("g2") else None)) for a in gold]
        first = evaluate(public, gold, predictions, seed=13, bootstrap_samples=500)
        second = evaluate(list(reversed(public)), list(reversed(gold)), list(reversed(predictions)), seed=13, bootstrap_samples=500)
        b = first["summaries"][0]["bootstrap"]
        self.assertEqual(b, second["summaries"][0]["bootstrap"])
        self.assertEqual(b["source_groups"], 2)
        self.assertEqual(b["intervals"]["strict_accuracy"], [0, 1])
        self.assertEqual(first["summaries"][0]["strict_accuracy"], .5)

    def test_paired_difference_intervals(self):
        public, gold = fixture()
        predictions = [prediction(a, condition="direct", verdict="INSUFFICIENT_EVIDENCE") for a in gold]
        predictions += [prediction(a, condition="scope_checklist") for a in gold]
        result = evaluate(public, gold, predictions, bootstrap_samples=80)
        pair = result["paired_comparisons"][0]
        self.assertEqual(pair["direction"], "right minus left")
        self.assertEqual(pair["strict_accuracy_difference"], 1)
        self.assertEqual(pair["exploratory_95pct_intervals"]["label_correct"], [1, 1])

    def test_invariance_is_not_correctness(self):
        public, gold = fixture()
        result = evaluate(public, gold, [prediction(a, verdict="INSUFFICIENT_EVIDENCE", ids=[]) for a in gold], bootstrap_samples=0)
        paired = result["summaries"][0]["paired"]
        self.assertEqual(paired["representation_verdict_invariance"], 1)
        self.assertEqual(paired["representation_both_labels_correct"], 0)
        self.assertEqual(paired["contrast_pair_both_labels_correct"], 0)

    def test_rejects_gold_errors_and_duplicate_public_ids(self):
        for error in ("duplicate_public", "duplicate_gold", "missing_gold", "unseen_evidence", "bad_verdict"):
            public, gold = fixture()
            if error == "duplicate_public":public.append(copy.deepcopy(public[0]))
            if error == "duplicate_gold":gold.append(copy.deepcopy(gold[0]))
            if error == "missing_gold":gold.pop()
            if error == "unseen_evidence":gold[0]["required_evidence_ids"] = ["not_in_payload"]
            if error == "bad_verdict":gold[0]["expected"] = "unknown"
            with self.subTest(error=error):
                with self.assertRaises(ValueError):
                    evaluate(public, gold, [])


if __name__ == "__main__":
    unittest.main()
