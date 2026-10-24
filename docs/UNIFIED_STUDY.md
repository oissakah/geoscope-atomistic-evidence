# GeoScope: one physical-evidence question, two complementary collections

**Central question.** Can language models select atomistic measurements and operations that physically justify a conclusion about simulated structures?

GeoScope evaluates *licensed proofs*: an evidence selection is valid only if its source comparison, selected atoms, coordinate frame, alignment, periodic convention, weighting, and permitted mathematical operation support the scientific claim. It does not discover or optimize catalysts.

## Research design

| Component | UMA-relaxed OC20-Dense collection | External OC20 DFT-trajectory collection |
|---|---|---|
| Atomic systems | 55 qualified source groups | 48 qualified source groups |
| Questions | 1,760 variants; 1,100 answerable | 1,536 variants per model; 960 answerable |
| Models | Qwen3-4B, Phi-4-mini, SmolLM3-3B | Same three plus Qwen3-32B-AWQ |
| Role in one study | Test progressively stricter evidence checks, accepted coverage, direct-versus-proof-aware accuracy | Test persistent errors across a different source collection, output formatting, error types, operation diagnosis, and token confidence |
| Scoring contract | Permits one enclosing JSON code fence | Strict unfenced JSON, plus separately reported fence-normalization diagnostic |

The analyses answer one scientific question under different evaluation conditions. The numerical scores must not be pooled as if they were a direct replication of the same experiment.

## Unified findings

- The original comparison-ID check accepted 393 Qwen numerical responses; full-definition checking accepted 312 valid proofs, rejecting 81 additional invalid acceptances without losing the 312 licensed proofs.
- On the external answerable questions, Qwen3-32B-AWQ produced 567/960 (59.1%) licensed proofs after removing only outer Markdown fences. Its **strict-JSON score remained 0**, because all original outputs were fenced.
- No model gave a qualifying scientific abstention on the 576 insufficient-evidence external questions per model under the frozen output contract.
- Among 601 Qwen3-32B selections with decision-token confidence above 0.99, 185 were scientifically invalid.

## What the publication revision changes

The canonical scientific narrative proceeds through: physical measurement definitions; why identity-only checks fail; verdict-versus-proof reliability; persistence across source collections; sensitivity to presentation and operation; and limits of model confidence. One shared-framework Figure 1 now links the two collections. Original and external outcomes remain separately reported under their frozen rules.

**This is an editorial publication unification, not a new inference run.** A matched external replication of the original comparison-ID/full-definition ablation has not been performed. The deterministic rule-only oracle solves the controlled benchmark under the specified evidence/rules; no superiority of an LLM hybrid is claimed.

## Provenance and limits

The original evidence archive, frozen workflows, original raw model outputs, and independent Phase 4 audits must remain unchanged. Geometry reproducibility does not establish catalytic activity, global adsorption minima, or unseen-by-LLM-pretraining conditions. Independent expert chemical review, some parent input archives, and main/SI authorship reconciliation remain outstanding.

See the [55-system report](../FINAL_REPORT.md), [data card](../DATA_CARD.md), [Phase 4 audit status](../publication/phase4_v1_7/FREEZE_AUDIT_STATUS.md), and [external publication record](../publication/phase4_v1_7/README.md). The complete revised LaTeX files and shared Figure 1 are staged in the companion repository overlay archive, to be applied to this branch before it is merge-ready.
