# GeoScope evidence and figure-data review resolution (24 October 2026)

This package resolves all findings that could be checked against **files actually recovered**. It does **not** invent missing external per-question or per-token records, silently decide authorship, or assert that unperformed chemistry review has taken place. The main GitHub branch remains code-focused; the paper and figures are in this separate publication package.

## Data provenance / what was independently recovered

1. `figure_data/verified_UMA/` contains **actual source-derived rows** exported from `evidence/final_results_original.zip`. It is not digitized from a figure: 55 real measured systems, 55 synthetic controls, 1,760 cases with model-facing packets and frozen gold proofs, 10,560 first-attempt model responses, original case-level scores, summaries, comparisons and original ZIP hash. The verified original ZIP SHA-256 is `20e6b415c0ab6b3d239138664301d5da1567c052d6770afa63e4c023a89c8b26`; all 69 internal member digests matched. The original study's full frozen scores matched the archived evaluation in GitHub Actions.
2. `figure_data/frozen_figure_inputs/` contains the **18 exact existing per-figure CSV inputs**, unchanged from the preserved publication branch. Their evidence quality differs: Figure 4 has 48 individual OC20 metric rows; several other files have aggregates, transcribed counts, or results derived from plots. Never treat every one of these CSVs as original per-case raw data.
3. `figure_data/external_geometry_audit/coordinate_checks.csv` contains 144 independently recorded numerical coordinate-comparison checks (three metric types for 48 systems), as previously archived. These are archived audit outcomes, **not** the raw endpoint coordinates themselves.
4. `figure_data/corrected_figure_inputs/` contains a **new 55-row Figure S1 data CSV** derived from actual UMA measurements, a transparent Figure S11 table with UMA three-model values (312, 121, 168 out of 1,100) and external four-model values (245, 97, 143, 567 out of 960), and Figure 7's high-confidence error rates explicitly declaring the Phi 0/0 subgroup **undefined (N/A)**. The original internal-holdout Figure S11 CSV is preserved under `*_LEGACY_DO_NOT_CONFUSE.csv` and has not been recast as a 55-system UMA experiment.

## Corrected figures (all vector PDFs plus SVG and 300-DPI PNG)

- `corrected_figures/figure_S01.*`: real 55-system A-vs-I scatter. The equality line is descriptive, not a licensed inequality between different measurement definitions. Median A/I = 3.269877922; 16/55 source systems have A/I > 10.
- `corrected_figures/figure_S11.*`: explicit separate panels for original 55-system UMA and external 48-system OC20 evaluations, with no fictitious UMA 32B result. The two evaluation protocols are different; no direct source-transfer or model-size effect is asserted.
- `corrected_figures/figure_07.*`: Phi's high-confidence error rate correctly reads **N/A (0/0)**, not 0%; other groups retain the frozen numerator/denominator (594/800, 21/29, 185/601).

## Manuscript copy changes

`manuscript/` has a rebuilt 17-page main manuscript and 12-page Supplementary Information, preserving other figure files. It updates Figures 7, S1, S11; corrects SI section labels to S1-S5; updates the corresponding figure captions; removes a stale claim that the original 55-source measurements/model outputs are unavailable; clarifies the joint strict-format/scientific abstention endpoint; fixes `collection\\'s`; clarifies that GitHub is currently **private**, not publicly available; and expands the draft AI-assistance disclosure to match the actual activity. **Authors must review and approve the AI statement** before submission.

## Reviewer issues that remain unresolved

| Item | Why it cannot be closed using current records |
| --- | --- |
| Main/SI author discrepancy | Main has Obed Issakah and Janghoon Ock; SI additionally has Md Khirul Alam Titu, Srivathsan Badrinarayanan and Ravi F. Saraf. Only the authors can confirm correct list/order/contributions. No authors were added or removed here. |
| Full external 48-system per-question outputs, gold proof witnesses, group bootstrap | Source archives identified in `publication/phase4_v1_7/audits/audit/freeze_audit.py` are not in the connected repository. The 18 figure CSVs are not substitutes for these raw input tables. |
| Format-normalized scientific abstention decomposition | Cannot compute strict vs normalized parsing/true insufficiency without per-response external raw outputs and gold sets. Continue to report 0/576 per model only as a **joint strict-format plus justification** endpoint. |
| Full model/backend and token-span reconstruction | Exact model revision, vLLM/Transformers and token-span data need external frozen run archives; underlying raw token log-probability vectors were not archived. |
| Expert chemistry audit | Blinded review packet is prepared, but no independent expert has completed the adjudication. |
| Public release | The linked GitHub repository is **private** as observed through the connected GitHub repository metadata on 24 October 2026. Do not call it publicly available without changing the repo's visibility and testing unauthenticated access. |
| Original atom coordinates / whole trajectory rerun | The 55 system-level scalar measurements are recovered, but recomputing them directly from structures still requires separately preserved coordinate/trajectory parent archives and pinned UMA/OC20 sources. |

## Next archive inputs required

To close the external evidence gap, obtain the original `GeoScope_Phase4_v1_5_OC20_external_gate_results_20261023T142306Z.zip`, `GeoScope_Phase4_v1_6_OC20_FOURMODEL_results_20261023T165627Z.zip`, `GeoScope_Phase4_v1_6_FOURMODEL_EXTERNAL_ANALYSIS.zip`, `GeoScope_Phase4_v1_7_CONFIDENCE_results_20261023T200515Z.zip`, and `GeoScope_Phase4_v1_7_FOURMODEL_CONFIDENCE_ANALYSIS.zip` from their original Swan collection/storage. Their exact hashes are recorded in the preserved GitHub publication draft's frozen audit manifest. Upload them or their validated archival collection for an independent per-case and confidence reconstruction.

## Validation

- Frozen 55-group case score rerun: **GitHub Actions PASS**.
- Recovered 55-system median ratio: **PASS** (3.269877922).
- Recovered 55-system ratios above 10: **PASS** (16).
- External 48-source geometry table: **48 rows**, coordinate audit: **144 rows**.
- Corrected supplementary Figure S11 UMA model roster: **3 models; no fabricated 32B UMA bar**.
- Phi high-confidence empty subgroup: **N/A**.
- Rebuilt LaTeX: `main.pdf` **17 pages**, `supplementary.pdf` **12 pages**; no unresolved references/citations detected in logs.

