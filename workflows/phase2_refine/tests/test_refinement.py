"""Checks for the changed parser and selection/calculation boundary."""
import json
import unittest
from phase2.refinement import parse_response, selected_calculation, derive_predictions
from phase2.benchmark import build_benchmark, parse_payload
from test_benchmark import sources


class RefinementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public,cls.gold,_=build_benchmark(sources(20))
        cls.answers={r['case_id']:r for r in cls.gold}

    def test_one_enclosing_fence_changes_no_answer_content(self):
        text='{"verdict":"SUPPORTED","evidence_ids":["E_x"]}'
        self.assertEqual(parse_response(text),parse_response('```json\n'+text+'\n```'))
        with self.assertRaises(ValueError): parse_response('```json\n'+text+'\n```',allow_fence=False)
        for wrong in ['Here is the answer: '+text, '```json\n'+text+'\n```\nExtra explanation',
                      text+text, text.replace('"SUPPORTED"','"supported"')]:
            with self.assertRaises(ValueError): parse_response(wrong)

    def test_citation_contract_is_explicit_and_enforced(self):
        for obj in [dict(verdict='SUPPORTED',evidence_ids=[]),
                    dict(verdict='CONTRADICTED',evidence_ids=['E_a','E_b']),
                    dict(verdict='INSUFFICIENT_EVIDENCE',evidence_ids=['E_a'])]:
            with self.assertRaises(ValueError): parse_response(json.dumps(obj))
        self.assertEqual(parse_response('{"verdict":"INSUFFICIENT_EVIDENCE","evidence_ids":[]}')['evidence_ids'],[])

    def test_selector_cannot_inject_a_verdict_or_duplicate_json_key(self):
        for text in ['{"verdict":"SUPPORTED","evidence_ids":[]}',
                     '{"evidence_ids":[],"evidence_ids":["E_a"]}',
                     '{"evidence_ids":["E_a","E_b"]}', '{"evidence_ids":null}',
                     '{"evidence_ids":[" E_a"]}']:
            with self.assertRaises(ValueError): parse_response(text,selector=True)

    def test_gold_selection_is_sufficient_for_both_calculators(self):
        for case in self.public:
            gold=self.answers[case['case_id']]
            for guarded in (False,True):
                result,_=selected_calculation(case['model_payload'],gold['required_evidence_ids'],validate_scope=guarded)
                self.assertEqual(result,dict(verdict=gold['expected'],evidence_ids=gold['required_evidence_ids']))

    def test_guard_rejects_wrong_pair_and_wrong_definition_without_oracle_rescue(self):
        case=next(c for c in self.public if self.answers[c['case_id']]['required_evidence_ids'])
        parsed=parse_payload(case['model_payload'])
        for record in parsed['measurements']:
            if record['evidence_id'] in self.answers[case['case_id']]['required_evidence_ids']: continue
            result,action=selected_calculation(case['model_payload'],[record['evidence_id']],validate_scope=True)
            self.assertEqual(result,dict(verdict='INSUFFICIENT_EVIDENCE',evidence_ids=[]))
            self.assertEqual(action,'scope_rejected')
            _,action=selected_calculation(case['model_payload'],[record['evidence_id']],validate_scope=False)
            self.assertEqual(action,'calculated')

    def test_fabricated_identifier_is_error_not_rewarded_abstention(self):
        with self.assertRaises(ValueError):
            selected_calculation(self.public[0]['model_payload'],['E_fabricated'],validate_scope=True)

    def test_derived_records_keep_raw_predictions_unchanged(self):
        case=self.public[0]
        raw=dict(case_id=case['case_id'],model_key='qwen',condition='select_evidence',status='ok',
                 raw_output='```json\n{"evidence_ids":[]}\n```')
        before=json.dumps(raw,sort_keys=True)
        derived,diagnostic=derive_predictions([case],[raw])
        self.assertEqual(before,json.dumps(raw,sort_keys=True))
        self.assertEqual({r['condition'] for r in derived},{'selector_arithmetic','selector_guard'})
        self.assertEqual(diagnostic['qwen/select_evidence']['normalized_contract_valid'],1)

    def test_invalid_selector_stays_error_for_both_tools(self):
        case=self.public[0]
        raw=dict(case_id=case['case_id'],model_key='qwen',condition='select_evidence',status='ok',
                 raw_output='{"evidence_ids":["invented"]}')
        derived,_=derive_predictions([case],[raw])
        self.assertTrue(all(r['status']=='invalid_selection' and r['raw_output']=='' for r in derived))

    def test_direct_multiple_citations_is_visible_contract_error(self):
        case=self.public[0]
        raw=dict(case_id=case['case_id'],model_key='qwen',condition='direct',status='ok',
                 raw_output='{"verdict":"SUPPORTED","evidence_ids":["a","b"]}')
        derived,diagnostic=derive_predictions([case],[raw])
        self.assertEqual(derived[0]['status'],'invalid_contract')
        self.assertEqual(diagnostic['qwen/direct']['invalid_contract'],1)

    def test_missing_generation_remains_missing_for_both_tools(self):
        case=self.public[0]
        raw=dict(case_id=case['case_id'],model_key='qwen',condition='select_evidence',status='missing',raw_output='')
        derived,_=derive_predictions([case],[raw])
        self.assertTrue(all(r['status']=='missing' for r in derived))
