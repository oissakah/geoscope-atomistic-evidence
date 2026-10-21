# Phase 2 development review

Reviewed 20 October 2026. Run: `phase2_pilot_20261020T171803Z_2789668_14528`.

**The computation completed successfully. Continue within Phase 2 to clarify the scoring contract and separate evidence selection from numerical comparison before preparing the protected final test.**

All 1,920 requests completed: 640 each for Qwen, Phi and SmolLM. There were no missing or duplicate requests, generation failures, input overflows or truncated outputs. All 63 returned-file checksums passed; all 19 recorded source files match the delivered package. Prepared-input hashes, model-file manifest hashes, run identities and request signatures check out. The trusted local builder exactly reproduces all 320 public cases, gold labels and benchmark audit metadata. Independent rescoring exactly reproduces every archived evaluation field.

The task contains 160 base cases in two presentations, derived from 20 source systems. These remain correlated development examples, not 320 independent physical experiments or a protected test set.

The original strict parser rejects any Markdown wrapper. Phi wrapped all 640 answers in JSON fences; SmolLM wrapped all 320 direct answers and 224 of its 320 checklist answers. Removing exactly one enclosing fence makes all 1,920 outputs parseable under the original JSON schema. No verdict, identifier, number or citation list is repaired. This is an explicitly post hoc diagnostic; the original primary scores remain unchanged.

| Model | Prompt | Original strict verdict accuracy | Verdict accuracy after fence-only removal | Verdict plus exact evidence after fence-only removal |
|---|---|---:|---:|---:|
| Qwen | Direct | 61.56% (197/320) | 61.56% | 35.00% (112/320) |
| Qwen | Checklist | 56.25% (180/320) | 56.25% | 39.06% (125/320) |
| Phi | Direct | 0% | 39.38% (126/320) | 13.13% (42/320) |
| Phi | Checklist | 0% | 39.38% (126/320) | 13.75% (44/320) |
| SmolLM | Direct | 0% | 39.06% (125/320) | 3.13% (10/320) |
| SmolLM | Checklist | 14.38% (46/320) | 39.06% (125/320) | 3.13% (10/320) |

The direct Qwen result has an exploratory source-group bootstrap interval of 56.25–66.56% for verdict accuracy. The checklist changes Qwen verdict accuracy by -5.31 percentage points and joint accuracy by +4.06 points. Their exploratory paired intervals are [-9.38, -1.56] and [+0.62, +7.50] points, respectively, from 1,000 whole-group resamples. They are development diagnostics without multiplicity adjustment. They do not establish population-level model rankings or a general effect of checklists.

The citation instruction was weaker than the exact-set scoring rule: it asked for evidence that justified the verdict but did not explicitly demand exactly one minimal citation, or an empty list for insufficient evidence. Correct verdicts with additional context citations therefore receive joint-score penalties that cannot all be interpreted as scientific misunderstanding. For Qwen direct, 85 correct verdicts fail the exact-set requirement; 77 outputs include the required decisive record plus additional citations. On truly insufficient cases, listing mismatched records might reasonably explain the absence of relevant evidence under the old instruction. These counts overlap; they are not separate error totals. The next prompt must state the citation contract explicitly before new outputs are generated.

Substantive mistakes remain even after accounting for formatting and citation ambiguity:

- Qwen direct has 45 wrong verdicts with exactly the correct single measurement citation; the checklist has 42. This observation separates at least some failures from choosing a wrong evidence ID, although it does not reveal the model's internal reasoning.
- One example cites 0.1059552265 nm and claims it is at most 0.7946641986 angstrom. The supplied value is 1.059552265 angstrom, so the claim is contradicted. Both Qwen prompts answer supported while citing the correct record.
- Qwen direct supplies one citation from the wrong comparison in 46 cases, and one citation for a different physical quantity from the correct comparison in 13 cases. Some of these are insufficiency answers with explanatory citations, so they are evidence-selection observations rather than 59 proven numerical substitutions.
- Qwen's direct verdict accuracy differs across matched presentations: 78/160 (48.75%) structured and 119/160 (74.38%) prose. Only 68/160 matched base cases have both verdicts correct. Both presentations carry equivalent numerical facts, but their wording and identifiers differ by design; this is presentation sensitivity, not proof that prose is generally better.
- After fence removal, SmolLM never correctly identifies insufficient evidence and accepts 185/200 unsupported claims under direct prompting. Its direct accuracy is close to the always-supported reference of 120/320 (37.5%). It should not be described as robust on this task.

The transparent deterministic scope selector scores 320/320 for verdict and evidence. The structure-only heuristic scores 200/320 (62.5%) verdict accuracy and the first-number control 156/320 (48.75%). Qwen's 61.56% direct verdict score does not exceed the structure-only reference on this pilot, while its joint score is higher. A high checker score on these fully specified templates is an expected control result, not a novel-method demonstration.

The next package retains the same cases, source groups, measurements and model checkpoints. It introduces an explicit minimal-citation rule, prospectively accepts a single enclosing JSON fence while reporting bare-JSON compliance separately, and adds selection-only requests. The same selected record feeds an arithmetic-only calculator and a calculator with physical-definition/run validation. The guard never replaces a bad selection with an oracle selection; rejecting a relevant answer is counted as false abstention. This comparison will help determine whether any improvement comes from selecting evidence, doing arithmetic or enforcing measurement meaning.

The original three phases remain intact. Phase 1 is complete; Phase 2 continues with this targeted refinement; Phase 3 will require a frozen final protocol and new protected source groups. Before publication, broaden the physical-definition/reference controls, address ordinary field/run-ID matching and long-identifier copying, compare strong verification baselines, and preserve the original coordinate/chemical interpretation limits. These results justify further development, not a claim of first-ever novelty, catalyst performance or general scientific competence.

Archive SHA256: `81658b921794ff7d46dee07e1ef71e823605c2b2ef9c6927dc9dd7e6bf6bec66`.
