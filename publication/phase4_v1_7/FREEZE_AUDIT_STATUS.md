# GeoScope Phase 4 v1.7 — Publication freeze status (2026-10-23)

## Completed in this local snapshot

1. Archived 11 original inputs/results/scripts/manuscript ZIPs byte-for-byte without modifying their contents, with SHA256 hashes recorded in `audit_results/FROZEN_ARCHIVE_MANIFEST.json`.
2. ZIP CRC/integrity checks passed for all 11 inputs; 173 + 230 listed member SHA256 digests independently checked against the corresponding collected GPU result archives.
3. Checked 48 distinct external OC20 physical systems, 96 real+synthetic evidence source records, 768 paired base cases, 1,536 sealed questions (480 supported / 480 contradicted / 576 insufficient), and model/case unique IDs.
4. Independently recomputed 144 fixed/mobile/adsorbate frame RMSDs from saved coordinates and all 48 adsorbate internal Kabsch RMSDs using a separate implementation. Values match archived measurements within numerical precision. The geometric bond cutoff is still a shared *assumption*, not independent chemical truth.
5. Independently enumerated all 768 structured public-case proof sets from physical metadata and mathematical inequalities (no GeoScope evaluator imports): 768 exact matches. Paired reports have identical target verdicts and operation-class witnesses for 768 matched base cases, but their prose parsing was **not** independently audited.
6. Recounted strict, normalized, repaired and abstention results from all 6,144 case-level output rows; values match the frozen analysis. Confirmed all 6,144 replay-output digests match originals and that confidence scores agree with frozen summary.
7. Wrote and compiled a new 18-page LaTeX manuscript draft and an editable Word conversion, using seven main figures and two external-validation tables. Original 55-group result and newer 48-system OC20 validation are separate experimental cohorts.

## Outstanding before claiming an independent SCIENTIFIC validation or submission-ready reproducibility

- A human domain expert must independently review chemical bond definitions, physical proof assumptions, and the blinded 96-question reviewer packet. No expert review has yet been performed.
- For the original 55-group manuscript's 1,760-case main result, the full *original Phase 3 final-results parent archive* was not among the available mounted inputs. We preserved the earlier manuscript and its stated counts but did not re-run its original 10,560-response scoring from raw data. Obtain and pin that raw final-results archive for complete main-claim reproduction.
- The original OC20 4.4-GB trajectory tarball is not mounted; its published MD5 verification is recorded in the Swan source audit but was not independently recomputed here from that large tar file.
- Raw per-generated-token log-probability traces were not archived, so confidence-span probabilities can be joined and checked but not independently regenerated from raw token-logprob streams without another run.
- External OC20 trajectories may have appeared in language-model pretraining. Source-level externality is not a proof of model-pretraining novelty.
- Original GitHub and Swan projects have **not** been changed, pushed, or frozen remotely. This is an immutable **local package snapshot**, not a repository tag or remote storage policy.

## Scientific claims allowed now

- The original matched-checker study observed 81 further Qwen invalid acceptances excluded (from the prior draft; original full results re-run pending).
- On 48 OC20 source systems, each of four frozen models answered 1,536 cases. At 960 answerable cases/model, Qwen3-32B generated 567 valid proofs after outer-fence normalization, vs 245 for Qwen3-4B. This is *not* strict-format and *not* a controlled effect of model size.
- Zero scientifically correct abstentions from 576 insufficient-evidence questions/model under the frozen output contract.
- Qwen3-32B decision-token confidence AUROC was 0.724 on answerable cases, but 185 of 601 answerable responses above 0.99 token likelihood were scientifically wrong; raw token likelihood is not P(scientific correctness).
- Full deterministic enumeration can solve this rule-defined benchmark from structured public evidence. Oracle-assisted operation repair is diagnostic and not a deployable model-improvement claim.

## Maintainer signoff

Until expert review and missing original artifacts are addressed, treat the manuscript as a substantive **working submission draft**, not as a fully independently validated final submission. Scope any new experiment as Phase 5 or separate follow-up rather than silently changing v1.7.
