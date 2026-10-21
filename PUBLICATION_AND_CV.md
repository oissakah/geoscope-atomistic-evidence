# Publication and CV notes

## Working identity

Working title: **GeoScope: Physical-definition checking in atomistic evidence selection**.

Project category: a controlled scientific-AI reliability benchmark and reproducible empirical study. The computation is complete; no publication, peer review or public data deposition is claimed.

The central question is whether a scientific number supports a claim when its atom selection, coordinate convention or licensed mathematical relation differs. The controlled comparison tests physical-definition validation beyond ordinary endpoint-pair identity checking, using the same model selections.

## Contribution that the data support

1. An audited construction connecting UMA-relaxed OC20-Dense endpoints to 1,760 evidence/claim variants from 55 new groups, with a separate 20-group development history.
2. Explicit exact-value and subset-bound proofs, including cases where a missing measurement remains inferable and cases where evidence is genuinely insufficient.
3. A comparison of arithmetic-only, run-ID and physical-definition checks on identical selections, with failures retained and rejection separated from scientific insufficiency.
4. A reproducible account of the coverage cost: Qwen full validation filters 81 additional invalid acceptances, retains all 312 licensed correct numerical answers, and covers only 28.36% of answerable cases.

The empirical value lies in characterizing evidence-selection failures and a verification tradeoff. A perfect deterministic oracle and a formally safe checker are part of the result. They are not competing claims of a new learned reasoning algorithm.

## Related work checked on 21 October 2026

This is a focused comparison, not a proof that no similar work exists. Broad scientific context verification, absence detection and tool-based reasoning are established topics. Do not describe this project as the first scientific context-understanding benchmark.

| Primary source | Existing contribution relevant here | How to position this project |
|---|---|---|
| [SciCUEval, Scientific Data (2026)](https://www.nature.com/articles/s41597-026-06594-9) | Evaluates scientific information identification, absence detection, integration and context-aware inference across multiple domains and formats. | Acknowledge substantial conceptual overlap. Focus the proposed distinction on physically specified RMSD evidence, formal single-record proofs and matched run-ID versus definition checks. |
| [SciBench](https://arxiv.org/abs/2307.10635) | Benchmarks college-level scientific problem solving in mathematics, chemistry and physics. | Distinguish evidence/definition compatibility from general scientific exercise solving; make no broad priority claim. |
| [Toolformer](https://arxiv.org/abs/2302.04761) | Studies learning when and how to call tools, including calculators. | Tool-assisted arithmetic is established. The question here concerns whether the selected measurement licenses the calculation. |
| [GSM-Symbolic](https://machinelearning.apple.com/research/gsm-symbolic) | Uses controlled symbolic variants to study mathematical-reasoning robustness. | Acknowledge precedent for template-controlled reasoning tests. Physical source provenance and measurement semantics supply the proposed domain-specific angle. |
| [OC20 dataset paper](https://arxiv.org/abs/2010.09990) | Supplies the catalyst/adsorbate data foundation. | Credit the original dataset; this study does not generate new DFT ground truth. |
| [UMA paper](https://arxiv.org/abs/2506.23971) | Supplies the universal atomistic modeling method used for endpoint generation. | Credit the pretrained potential; this study does not train a new interatomic potential. |

The suggested distinction above is an interpretation of the current artifact and these sources. A submission's related-work section should compare task construction, evidence requirements, controls and statistical units explicitly. The available evidence does not justify a first-ever claim or a guarantee of journal acceptance.

## Manuscript writing plan

- **Introduction:** motivate why two numbers with the same units can represent different physical quantities. Acknowledge scientific context-understanding and tool-reasoning precedents before defining the narrow RMSD setting.
- **Methods:** describe the original 60-source pool, five exclusions, 55 accepted groups, 20 development groups, UMA checkpoint, coordinate conventions, synthetic distractors, subset bounds and proof enumeration. State that source geometry was reviewed before final inference.
- **Evaluation:** describe the exact frozen model revisions, independent direct/selection conditions, three same-selection checks, deterministic oracle, strict output contract and 160-token cap. Declare Qwen primary and the other models secondary.
- **Results:** lead with the Qwen run-ID versus full-definition comparison: 81 invalid acceptances removed, 312 valid answers retained, 5.45 percentage-point answerable-coverage cost. Decompose wrong verdicts and coincidentally correct but unlicensed answers. Use all three supplied figures.
- **Discussion:** explain that the checker filters invalid proofs rather than repairing evidence selection. Interpret the oracle and low coverage directly. Discuss difficult formatting and operation compliance as components of this protocol.
- **Limitations:** disclose only three compact models, same-domain sources, correlated templates, non-preregistered development, uneven chemical attrition, retained chemical flags, SmolLM truncations and no DFT validation.
- **Availability:** provide the exact original evidence archive, CPU reproduction script, code hash manifest, case generator, scoring rules and source pointers. Obtain a public repository/deposition identifier only when actually deposited.

No additional GPU experiment is required to report this frozen study honestly. A stronger future method would need a separate protocol and fresh evaluation groups. Do not improve final scores by repairing outputs, extending the cap, dropping failed cases or tuning on the inspected final set.

## CV wording available now

**Scientific AI reliability with UMA and OC20-Dense — Research project, 2026**

- Built a reproducible scientific-evidence benchmark with 1,760 claim variants from 55 qualified atomistic systems and evaluated three open-weight language models on UNL Swan.
- Compared arithmetic, run-identity and physical-definition verification; for Qwen, full validation filtered 81 additional invalid acceptances while retaining 312 licensed correct numerical answers at 28.4% answerable coverage.
- Implemented audited source qualification, formal measurement-bound proofs, failure-inclusive scoring and source-group uncertainty analysis; packaged raw outputs, reproducible analysis and scientific figures.

Compact alternative:

Developed a UMA/OC20-Dense benchmark for scientific evidence selection, evaluating three language models over 10,560 requests and quantifying how physical-definition checking filters unsupported answers at a measurable coverage cost.

Use a project/research heading now. Add a paper title, author list, repository link or preprint identifier only after those exist. Do not label the work published, accepted or peer reviewed at this stage.
