# GeoScope Phase 4 v1.7 — Predeclared token-confidence replay (frozen protocol)

**Design limitation:** This OC20 benchmark and its four-model accuracy results have already been inspected. We are fixing the confidence metrics before collecting token probabilities, but this is a **supplementary retrospective benchmark analysis**, not an untouched prospective external validation. Strong deployment-level confidence claims will need another independent, previously uninspected source collection.

**Question:** Are token-level probabilities associated with physically correct evidence-and-operation selections? Can they rank correct above incorrect selections on independently sourced OC20 systems?

## Prespecified dataset and models

- Existing OC20 `val_ood_both` external benchmark: **48 distinct source groups**, **1,536 requests**, **960 answerable** and **576 insufficient-evidence**; same structured/report pairs; no new generated scientific prompts.
- Four *identical pinned checkpoints and prompt templates*: Qwen3-4B-Instruct-2507, Phi-4-mini-instruct, SmolLM3-3B, Qwen3-32B-AWQ (4-bit), same original BF16/HF small-model and vLLM/AWQ large-model runtimes.
- Greedy generation; 160 new-token limit, 6,144 input tokens, fixed original seed 20261022. **Only change** to inference is returning selected-token log probabilities. No finetuning, no extra ground-truth instruction, no change to output-format handling.
- Original, already collected model responses are included as an **immutable gold-free reference** (checksum-verified). A replay must have identical decoded output to attach its token scores to the earlier answer. Report all divergences. Never silently replace the original answer. If match coverage is incomplete, headline conclusions must be conditional on the matched subset and report selection bias.

## Frozen endpoint and confidence metrics

Outcome: `normalized_correct_proof` from frozen v1.6 offline scoring, on **960 answerable** cases. Strict-format proof correctness is reported separately. Inadequate scientific abstentions on the other 576 cases must be reported separately and not folded into proof accuracy.

**Primary predictor:** geometric mean of conditional probabilities of generated tokens overlapping the model's **single selected measurement evidence ID and operation name** (not JSON punctuation), after reproducing the original greedy output exactly. This is `exp(mean(log p(token_t | preceding context)))` on decision-token positions. A response with multiple evidence IDs, no operation, or unstable decoded-token offsets has **no prespecified decision confidence** and its absence is recorded. This avoids selecting only correctly formatted examples without noting exclusion.

**Secondary predictors:** separate evidence-ID token probability, operation-string token probability, all-generated-token geometric mean, and minimum generated-token probability. All are conditional, token-level likelihoods. They are **not**, on their own, a mathematically justified P(scientific answer correct), especially for random identifier strings, varying output lengths, models with different tokenizers, or unnormalized scores. Cross-model raw probability magnitudes are not directly comparable.

**Primary validation statistic:** within-model AUROC for the binary scientific proof outcome, grouped bootstrap (48 system IDs) for uncertainty, with AUC=0.5 as chance. Report correct-answer rate for top 10%, 25%, 50%, 75% and 100% highest-confidence retained cases (risk–coverage). Report high-confidence wrong examples. Evaluate structured and written reports separately. Avoid within-external-set threshold selection and calibration fitting.

Optional plots show confidence score quantiles vs observed accuracy, but these are **diagnostic reliability curves, not probability calibration curves**. Do not call a token geometric mean a probability of scientific correctness, and do not report its ECE/Brier score as evidence of genuine calibration without independently fitting and validating an outcome-probability mapping.

**Future calibration if useful:** train a per-model correctness predictor using only the *previous* ALCHEMI/GeoScope 564-request development collection, respecting source groups, freeze it, and then evaluate on OC20 without refitting. Any such result must be its own clearly labeled experiment and account for distribution shift.

## Experimental invariants and validity gates

1. Public request bytes, per-group shard memberships, all 6,144 baseline answers, and pinned checkpoints must pass SHA256 and source-ID checks.
2. GPU runner and output bundle must not contain `gold_proofs`, true scientific labels, or answer lists. Gold/proof audit only joins confidence results *after* the experiment is complete.
3. Replay exact-string match, original prompt token count, no truncation differences, and checkpoint identity are independently checked and recorded.
4. Each response must yield finite log probabilities for its selected generated tokens; negative log probabilities never converted into implied calibrated probabilities of correctness.
5. Frozen confidence definitions, outcome and analyses cannot be changed after seeing how each model fares.

Relevant methods literature:
- Jiang et al. (2021), **How Can We Know When Language Models Know? On the Calibration of Language Models for Question Answering**, TACL 9:962–977, https://aclanthology.org/2021.tacl-1.57/.
- Nakkiran et al. (2026), **Trained on Tokens, Calibrated on Concepts: The Emergence of Semantic Calibration in LLMs**, ICLR 2026, https://proceedings.iclr.cc/paper_files/paper/2026/hash/39b228b1a83232b14a1c81b0ed5a7a05-Abstract-Conference.html.
- vLLM SamplingParams documented `logprobs` includes the sampled token: https://docs.vllm.ai/en/stable/api/vllm/sampling_params/.

**Status:** locally tested package; NONE of the 6,144 confidence replays have been executed on Swan yet. No claim about predictive strength or calibration is made in advance.
