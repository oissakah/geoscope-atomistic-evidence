"""Analytic fixtures only. Protected source-group performance is never read."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from decimal import Decimal

from finalstudy import benchmark as b
from finalstudy.evaluation import parse_response, derive_prediction, evaluate, write_reports

PAIR = "P_11111111"
OTHER = "P_22222222"
E1, E2 = "E_11111111", "E_22222222"
SETS = {"mobile": [0, 1, 2, 3], "adsorbate": [0], "anchors": [4, 5, 6]}


def measurement(eid=E1, value=2, metric="mobile_rmsd", pair=PAIR, unit="angstrom", **definition_changes):
    internal = metric == "internal_rmsd"
    definition = dict(atom_indices=SETS["mobile"] if metric == "mobile_rmsd" else SETS["adsorbate"],
                      frame="independent molecular centroids" if internal else "shared stored slab coordinate frame",
                      alignment="proper Kabsch rotation plus translation; no reflection" if internal else "none",
                      periodic_treatment="connected bond-graph unwrapping before alignment; no MIC on fitted residuals" if internal else "minimum-image displacement independently per matched atom",
                      pbc=[True, True, True], weighting="equal weight per selected atom")
    definition.update(definition_changes)
    return dict(evidence_id=eid, pair_id=pair, value=value, unit=unit, definition=definition)


def case(cid="c", group="g", target="mobile_rmsd", threshold=3, operator="<=", measurements=None, presentation="structured", base=None, contrast=None):
    packet = dict(atom_sets=copy.deepcopy(SETS), pbc=[True, True, True], measurements=measurements if measurements is not None else [measurement()],
                  quantity_convention=b.QUANTITY_CONVENTION, permitted_relations=b.PERMITTED_RELATIONS)
    claim = f"For endpoint pair {PAIR}, the {b.NAMES[target]}, with equal atom weights and the supplied atom sets, is {'at most' if operator == '<=' else 'at least'} {threshold} angstrom."
    payload = {"claim": claim, "evidence_packet": packet} if presentation == "structured" else {"claim": claim, "evidence_report": b._render_report(packet)}
    return dict(case_id=cid, group_id=group, model_payload=payload, family="analytic", presentation=presentation,
                target_metric=target, base_case_id=base, contrast_group_id=contrast)


def answer(c, expected="SUPPORTED", proofs=None):
    return {"case_id": c["case_id"], "expected": expected,
            "valid_proofs": proofs if proofs is not None else [dict(verdict=expected, evidence_ids=[E1], operation="value")]}


def prediction(c, selector=False, ids=None, operation="value", verdict="SUPPORTED", model="qwen", **extra):
    ids = [E1] if ids is None else ids
    response = dict(evidence_ids=ids, operation=operation)
    if not selector:response["verdict"] = verdict
    return dict(case_id=c["case_id"], model_key=model, condition="select_evidence" if selector else "direct", status="ok", raw_output=json.dumps(response), **extra)


def summary(result, method, model="qwen"):
    return next(s for s in result["summaries"] if s["model_key"] == model and s["method"] == method)


class ParserTests(unittest.TestCase):
    def test_bare_and_whole_fences_including_inline_closing(self):
        raw=json.dumps(dict(verdict="SUPPORTED", evidence_ids=[E1], operation="value"))
        for text in [raw, " \n"+raw+"\n", "```json\n"+raw+"```", "```\n"+raw+"\n```", "```json\r\n"+raw+"\r\n```"]:
            self.assertEqual(parse_response(text)["evidence_ids"], [E1])
        self.assertEqual(parse_response('{"evidence_ids":[],"operation":"none"}', selector=True), {"evidence_ids": [], "operation": "none"})

    def test_no_repair_extra_fields_duplicates_fences_or_coercion(self):
        raw='{"verdict":"SUPPORTED","evidence_ids":["E_11111111"],"operation":"value"}'
        bad=[None, [], "", raw+" commentary", "prefix "+raw, "```JSON\n"+raw+"```", "```json\n```json\n"+raw+"\n```\n```",
             raw[:-1]+',"reason":"x"}', raw.replace('"SUPPORTED"','"supported"'),raw.replace('["E_11111111"]','["E_11111111","E_11111111"]'),
             raw.replace('["E_11111111"]','"E_11111111"'),raw.replace('["E_11111111"]','[1]'),raw.replace('"value"','"VALUE"'),
             raw.replace('"value"','"none"'),raw.replace('["E_11111111"]','[]'),raw.replace('"operation":"value"','"operation":"value","operation":"none"'),
             raw.replace('"SUPPORTED"','NaN')]
        for text in bad:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):parse_response(text)
        with self.assertRaises(ValueError):parse_response(raw,selector=True)


class DerivationTests(unittest.TestCase):
    def test_same_selector_three_branches_and_wrong_pair(self):
        c=case(measurements=[measurement(pair=OTHER)]);p=prediction(c,selector=True)
        traces=[derive_prediction(c,p,m) for m in ("arithmetic_only","run_only","full_definition")]
        self.assertEqual([t["disposition"] for t in traces],["ACCEPT_NUMERIC","REJECT_CONTRACT","REJECT_CONTRACT"])
        self.assertEqual(len({t["raw_output_sha256"] for t in traces}),1)
        self.assertEqual(len({tuple(t["evidence_ids"]) for t in traces}),1)

    def test_run_only_cannot_detect_alignment_mismatch(self):
        c=case(measurements=[measurement(alignment="proper Kabsch rotation plus translation; no reflection")]);p=prediction(c,selector=True)
        self.assertEqual(derive_prediction(c,p,"run_only")["disposition"],"ACCEPT_NUMERIC")
        self.assertEqual(derive_prediction(c,p,"full_definition")["disposition"],"REJECT_CONTRACT")

    def test_no_selection_and_unresolved_are_not_scientific_insufficiency(self):
        c=case(target="mobile_rmsd",threshold=3,measurements=[measurement(value=4,metric="adsorbate_frame_rmsd")])
        p=prediction(c,selector=True,operation="mobile_lower")
        unresolved=derive_prediction(c,p,"full_definition")
        self.assertEqual(unresolved["interval_A"][0],"2.0")
        self.assertEqual(unresolved["disposition"],"REJECT_UNRESOLVED")
        self.assertIsNone(unresolved["verdict"])
        empty=derive_prediction(c,prediction(c,selector=True,ids=[],operation="none"),"full_definition")
        self.assertEqual(empty["disposition"],"REJECT_NO_SELECTION")
        self.assertIsNone(empty["verdict"])

    def test_units_and_both_licensed_bounds(self):
        lower=case(target="mobile_rmsd",threshold=1,measurements=[measurement(value=.4,unit="nm",metric="adsorbate_frame_rmsd")])
        lowertrace=derive_prediction(lower,prediction(lower,selector=True,operation="mobile_lower"),"full_definition")
        self.assertEqual(lowertrace["verdict"],"CONTRADICTED")
        self.assertEqual(Decimal(lowertrace["interval_A"][0]),Decimal(2))
        upper=case(target="adsorbate_frame_rmsd",threshold=5,measurements=[measurement(value=.2,unit="nm")])
        uppertrace=derive_prediction(upper,prediction(upper,selector=True,operation="adsorbate_upper"),"full_definition")
        self.assertEqual(uppertrace["verdict"],"SUPPORTED")
        self.assertEqual(Decimal(uppertrace["interval_A"][1]),Decimal(4))

    def test_unknown_identifier_and_status_precedence(self):
        c=case()
        for selector,method in [(False,"direct"),(True,"full_definition")]:
            self.assertEqual(derive_prediction(c,prediction(c,selector=selector,ids=["invented"]),method)["disposition"],"INVALID_IDENTIFIER")
        p=prediction(c,selector=True,truncated=True)
        self.assertEqual(derive_prediction(c,p,"full_definition")["disposition"],"INVALID_TRUNCATED")
        p=prediction(c,selector=True);p["status"]="error"
        self.assertEqual(derive_prediction(c,p,"full_definition")["disposition"],"INVALID_EXECUTION")

    def test_public_only_interface_never_searches_for_substitute(self):
        c=case(measurements=[measurement(pair=OTHER),measurement(eid=E2)])
        with patch.object(b,"enumerate_proofs",side_effect=AssertionError("no oracle search")):
            trace=derive_prediction(c,prediction(c,selector=True),"full_definition")
        self.assertEqual(trace["disposition"],"REJECT_CONTRACT")
        self.assertEqual(trace["evidence_ids"],[E1])
        self.assertNotIn("expected",trace)
        self.assertNotIn("valid_proofs",trace)


class EvaluationTests(unittest.TestCase):
    def test_alternate_valid_proof_and_fixed_absent_models(self):
        c=case(measurements=[measurement(),measurement(eid=E2,value=.2,unit="nm")])
        a=answer(c,proofs=[dict(verdict="SUPPORTED",evidence_ids=[eid],operation="value") for eid in [E1,E2]])
        ps=[prediction(c,ids=[E2]),prediction(c,selector=True,ids=[E2])]
        result=evaluate([c],[a],ps,bootstrap_samples=20)
        self.assertEqual(len(result["summaries"]),13)
        self.assertEqual(summary(result,"direct")["scientific_threeway_accuracy_with_proof"],1)
        self.assertEqual(summary(result,"full_definition")["answerable_correct_verdict_and_proof_rate"],1)
        self.assertEqual(summary(result,"direct","phi")["scientific_threeway_accuracy_with_proof"],0)
        self.assertEqual(summary(result,"direct","phi")["answerable_missing"],1)
        self.assertEqual(summary(result,"oracle","payload_oracle")["scientific_threeway_accuracy_with_proof"],1)

    def test_guard_rejection_does_not_gain_insufficiency_credit(self):
        c=case(measurements=[]);a=answer(c,"INSUFFICIENT_EVIDENCE",[])
        ps=[prediction(c,ids=[],operation="none",verdict="INSUFFICIENT_EVIDENCE"),prediction(c,selector=True,ids=[],operation="none")]
        result=evaluate([c],[a],ps,bootstrap_samples=0)
        direct=summary(result,"direct");guard=summary(result,"full_definition")
        self.assertEqual(direct["scientific_threeway_accuracy_with_proof"],1)
        self.assertIsNone(guard["scientific_threeway_accuracy_with_proof"])
        row=next(r for r in result["rows"] if r["model_key"]=="qwen" and r["method"]=="full_definition")
        self.assertFalse(row["label_correct"])
        self.assertFalse(row["scientific_threeway_correct"])
        self.assertEqual(guard["numeric_acceptances"],0)
        self.assertIsNone(guard["conditional_accepted_correctness_with_proof"])

    def test_wrong_definition_prevention_and_coverage_cost(self):
        bad=case(cid="bad",group="g1",measurements=[measurement(alignment="wrong")])
        good=case(cid="good",group="g2")
        # Bad source scope leaves no proof; a separate genuine witness makes
        # the claim answerable, but the selector is not allowed to replace E1.
        bad["model_payload"]["evidence_packet"]["measurements"].append(measurement(eid=E2))
        gold=[answer(bad,proofs=[dict(verdict="SUPPORTED",evidence_ids=[E2],operation="value")]),answer(good)]
        result=evaluate([bad,good],gold,[prediction(c,selector=True) for c in [bad,good]],bootstrap_samples=100)
        run=summary(result,"run_only");full=summary(result,"full_definition")
        self.assertEqual(run["answerable_coverage"],1)
        self.assertEqual(run["answerable_correct_verdict_and_proof_rate"],.5)
        self.assertEqual(run["bad_fraction_of_accepted_numeric"],.5)
        self.assertEqual(full["answerable_coverage"],.5)
        self.assertEqual(full["conditional_accepted_correctness_with_proof"],1)
        primary=next(x for x in result["paired_comparisons"] if x["model_key"]=="qwen" and x["control"]=="run_only")
        self.assertEqual(primary["bad_numeric_acceptances_prevented"],1)
        self.assertEqual(primary["lost_answerable_numeric_acceptances"],1)
        self.assertEqual(primary["lost_control_correct_numeric_answers"],0)
        self.assertEqual(primary["prevention_per_all_cases"],.5)
        self.assertEqual(primary["lost_answerable_coverage"],.5)
        self.assertEqual(primary["bootstrap"]["intervals"]["prevention_per_all_cases"],[0,1])

    def test_unsafe_numeric_acceptance_on_insufficient_not_safe_abstention(self):
        c=case(measurements=[measurement(pair=OTHER)]);a=answer(c,"INSUFFICIENT_EVIDENCE",[])
        ps=[prediction(c),prediction(c,selector=True)]
        result=evaluate([c],[a],ps,bootstrap_samples=0)
        self.assertEqual(summary(result,"direct")["unsafe_acceptance_on_insufficient_rate"],1)
        self.assertEqual(summary(result,"arithmetic_only")["unsafe_acceptance_on_insufficient_rate"],1)
        self.assertEqual(summary(result,"run_only")["unsafe_acceptance_on_insufficient_rate"],0)
        self.assertIsNone(summary(result,"run_only")["scientific_threeway_accuracy_with_proof"])

    def test_errors_duplicates_missing_and_truncation_stay_in_denominator(self):
        cs=[case(cid=str(i),group="g"+str(i%2)) for i in range(5)];gs=[answer(c) for c in cs]
        ps=[prediction(c) for c in cs[:4]]
        ps.append(prediction(cs[0]))
        ps[1]["truncated"]=True
        ps[2]["status"]="error"
        ps[3]["raw_output"]="not JSON"
        ps.append(dict(case_id="unknown",model_key="qwen",condition="direct",status="ok",raw_output="{}"))
        result=evaluate(cs,gs,ps,bootstrap_samples=0)
        s=summary(result,"direct")
        self.assertEqual(s["cases"],5)
        self.assertEqual(s["format_valid_responses"],0)
        self.assertEqual(s["scientific_threeway_label_accuracy"],0)
        self.assertEqual(s["answerable_invalid"],5)
        counts=next(c for c in result["completeness"] if c["model_key"]=="qwen" and c["condition"]=="direct")
        self.assertEqual((counts["missing_cases"],counts["duplicate_cases"],counts["truncated_cases"],counts["execution_error_cases"],counts["invalid_format_cases"]),(1,1,1,1,1))
        self.assertEqual(len(result["unexpected_predictions"]),1)

    def test_paired_cases_and_whole_group_bootstrap_are_deterministic(self):
        cs=[];gs=[];ps=[]
        for group in ["g1","g2"]:
            for expected,threshold in [("SUPPORTED",3),("CONTRADICTED",1)]:
                for style in ["structured","report"]:
                    c=case(cid=group+expected+style,group=group,threshold=threshold,presentation=style,base=group+expected,contrast=group+"pair")
                    cs.append(c);gs.append(answer(c,expected));ps.append(prediction(c,selector=True) if group=="g1" else prediction(c,selector=True,ids=[],operation="none"))
        one=evaluate(cs,gs,ps,seed=7,bootstrap_samples=500)
        two=evaluate(list(reversed(cs)),list(reversed(gs)),list(reversed(ps)),seed=7,bootstrap_samples=500)
        s=summary(one,"full_definition");self.assertEqual(s["bootstrap"],summary(two,"full_definition")["bootstrap"])
        self.assertEqual(s["answerable_correct_verdict_and_proof_rate"],.5)
        self.assertEqual(s["bootstrap"]["intervals"]["answerable_correct_verdict_and_proof_rate"],[0,1])
        self.assertEqual(s["paired_cases"]["eligible_contrast_pairs"],4)
        self.assertEqual(s["paired_cases"]["contrast_both_correct_with_proof"],2)
        self.assertEqual(s["paired_cases"]["answerable_representation_pairs"],4)
        self.assertEqual(s["paired_cases"]["representation_both_correct_with_proof_answerable"],2)

    def test_reports_are_json_finite_and_no_inputs_mutated(self):
        c=case();a=answer(c);ps=[prediction(c),prediction(c,selector=True)];before=copy.deepcopy(([c],[a],ps))
        result=evaluate([c],[a],ps,bootstrap_samples=0)
        self.assertEqual(([c],[a],ps),before)
        with tempfile.TemporaryDirectory() as folder:
            write_reports(result,folder)
            self.assertEqual({p.name for p in Path(folder).iterdir()},{"evaluation.json","method_scores.csv","case_scores.csv","completeness.csv","paired_comparisons.json"})
            self.assertEqual(json.loads((Path(folder)/"evaluation.json").read_text())["source_groups"],1)

    def test_no_predictions_still_produces_full_fixed_denominators(self):
        c=case();result=evaluate([c],[answer(c)],[],bootstrap_samples=0)
        self.assertEqual(len(result["rows"]),13)
        self.assertEqual(len(result["completeness"]),6)
        self.assertTrue(all(x["expected_cases"]==1 for x in result["completeness"]))
        self.assertTrue(all(x["missing_cases"]==1 for x in result["completeness"]))


if __name__=="__main__":unittest.main()
