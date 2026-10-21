# Phase 3 source qualification: independent physical review

Run: `phase3_prepare_20261020T211054Z_234814_30462`.

Accept the 55 qualified system groups, together with their 55 synthetic controls, for the next frozen evaluation checkpoint. Preserve the five exclusions and the original 60-system denominator. No retries, longer relaxation budgets or replacement systems are needed or justified by this review.

The attachment was treated as data. No archived program was executed and UMA was not called. The audit read all saved trajectories and cached forces using ASE, compared original inputs directly with their members of the pinned official OC20-Dense archive, and independently recomputed all accepted geometric measurements. A trusted local geometry module supplied a second calculation. Initial/final top and side overlays for all 60 systems, the five excluded endpoints and both nonconverged force traces were visually inspected.

## Physical-data gate

| Check | Result |
|---|---|
| Frozen selected source groups | 60 |
| Force-converged endpoints | 58/60 |
| Qualified geometric comparisons | 55/60 (91.67%) |
| Qualified synthetic controls | 55 |
| Saved trajectory frames inspected | 11,550 |
| Finite positions, energies and full saved forces | All frames |
| Fixed-atom maximum drift | Exactly 0 Å |
| Atom identity, order, tags, cell, periodicity and fixed mask | Preserved in all frames |
| Recorded versus independently extracted final force error | Exactly 0 eV/Å |
| Maximum optimizer-log force difference | 1.555×10⁻⁶ eV/Å |
| Maximum final coordinate export difference | 4.999×10⁻⁹ Å |
| Maximum original export versus official coordinates | 5.001×10⁻⁹ Å |
| Accepted real/control metric pairs recomputed | 110 |
| Largest reported RMSD discrepancy | 2.493×10⁻¹⁵ Å |

All original selected input hashes and all 60 official archive-member hashes match. The original exports preserve official symbols, tags, cell and periodicity within coordinate-export precision. Stage initial coordinates and first trajectory coordinates match those frozen exports exactly. Every final export agrees with its final trajectory frame within export precision. All selected atom masks match tags. All accepted real comparisons retain the original official initial placement as their reference.

Every converged trajectory stops at its first frame strictly below 0.05 eV/Å. The two nonconverged runs each stop at 600 steps and never cross that threshold. Frame counts agree with recorded step counts, and every optimizer-log step index matches its trajectory frame. The small log differences are consistent with output rounding and numeric precision; they do not alter any convergence classification.

Every accepted adsorbate graph remains connected and unchanged under the declared initial 1.25-covalent-radius construction. This validates its use for the prescribed geometric unwrapping and alignment; it does not establish experimental bond orders or adsorption chemistry. The 55 synthetic controls translate only the adsorbate by +0.7 Å along stored x, preserve the selected masks and periodicity, and contain no calculator results. Their energies, forces and convergence must remain disabled.

## Five exclusions are correct

| System / placement | Outcome | Independent evidence |
|---|---|---|
| 41_1447_86 / heur24 | Nonconverged at 600 steps | Final force 0.057698 eV/Å; minimum 0.055916. C–C grows 1.520→2.390 Å and O–H grows 0.970→4.284 Å; final adsorbate graph has three components. |
| 41_2443_105 / rand2 | Nonconverged at 600 steps | Final force 0.128692 eV/Å; minimum 0.064969. Adsorbate graph remains intact, but the frozen force criterion is not met. |
| 41_3331_215 / heur29 | Converged, changed graph | O–H grows 0.970→2.887 Å, far beyond the 1.2125 Å graph cutoff; the hydrogen is disconnected from the adsorbate scaffold. |
| 41_9852_9 / heur8 | Converged, changed graph | O–H grows 0.970→3.243 Å; the hydrogen is disconnected from the adsorbate scaffold. |
| 41_3099_22 / heur17 | Converged, changed graph | C–O grows 1.420→3.026 Å, beyond the 1.775 Å graph cutoff; an OH-containing fragment separates. |

These are substantial geometry changes rather than tiny cutoff crossings. They may be dissociation or proton-transfer candidates under UMA, but that chemical interpretation has not been independently validated. They remain unsuitable for the frozen intact-adsorbate internal-shape comparison. Do not redefine their bond graph after seeing results, substitute other placements, or treat their exclusion as missing at random.

All five exclusions have formula C₂H₃O₂. The selected pool contains 25 such systems, and 20 remain qualified. This chemical concentration of attrition must be disclosed in any publication or data card.

## Descriptive chemical flags to retain

The checks below are descriptive review flags, not new exclusion criteria. They must not change the frozen 55-system cohort after the fact. Force convergence and valid RMSD measurements do not imply DFT accuracy, successful chemisorption or a physically correct reconstructed surface.

Nine qualified endpoints have an all-atom distance smaller than 0.8 times the sum of covalent radii, involving surface atoms. The strongest flag is `15_9991_19 / heur15`, where a Mo–Mo distance is 1.962 Å (ratio 0.637). The other flagged pair identities are Y–Co (`41_2717_113`), Mo–Mo (`58_3453_7`), Fe–Ta (`41_6229_3`), V–V (`41_1175_54`), W–W (`58_1664_84`), V–Fe (`41_8111_9`), Co–Y (`15_3994_47`) and Nb–Nb (`41_3960_1`). These suggest close contacts or surface reconstructions to document, not automatic proof of invalidity.

Nine qualified endpoints have minimum adsorbate–surface contact radius ratios above 1.3: `58_833_10`, `58_7014_9`, `58_4098_202`, `10_394_10`, `15_9991_19`, `11_783_2`, `15_3994_47`, `16_4335_2` and `58_2538_115`. The most remote is `11_783_2 / rand6`, with minimum adsorbate–surface distance 6.530 Å. Preserve a remote/weak-contact description and avoid calling it confirmed adsorption. Sixteen qualified systems carry at least one of these two descriptive flags; two carry both.

The qualified cohort spans nine adsorbate formulas: 20 C₂H₃O₂, 18 C₂H₈N₂, four CH₂O, four C₂HO, three C₂H₂, two CH₃O, two CH₄, one CH₃ and one CH₄O. The two largest formulas still account for 38/55 groups (69.09%). This is broader than the development pool but remains a narrow same-domain sample. Disjoint source-group IDs are not proof of independence from chemical families or UMA training data.

## Recommendation

Pass the physical evidence gate for the existing 55 qualified groups and retain all five failed denominators in provenance. Carry the chemical flags forward without adding retrospective exclusions. Freeze the exact accepted IDs and source hashes before generating protected language-model cases. The source preparation itself created no claims, gold labels or model scores, so language-model evaluation remains a separate next checkpoint.

Artifacts: `physical_review.json` and `.csv`, six `overlays_page*.png` files, `excluded_overlays.png`, `nonconverged_force_traces.png`, and cached-force series. These are review artifacts; no delivery source files were edited.
