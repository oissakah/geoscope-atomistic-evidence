# Prospective frozen OC20 external four-model protocol

- Source: official OC20 IS2RE/IS2RS `val_ood_both` compressed per-system trajectories, hash verified in v1.5.2; model-input requests exactly hash-verified as captured in the 2026-10-23 external source-gate archive.
- 48 hash-ranked source groups, 1,536 frozen cases (480 SUPPORTED, 480 CONTRADICTED, 576 INSUFFICIENT_EVIDENCE); 768 structured/report presentation pairs, 12 group-disjoint shards of 128 cases.
- Primary response evaluation: original strict syntax and one-evidence proof protocol; secondary format-normalized analysis removes JSON fences only. Report abstention separately. All model results kept case-paired by source ID.
- Small models: exactly the original pinned BF16+SDPA Transformers 5.3.0 stack, greedy max 160 new tokens, max 6144 input tokens, no truncation, original revisions.
- Large model: originally pinned Qwen3-32B-AWQ (4-bit quantized), original vLLM 0.11.2, no thinking, greedy temp 0, 160 new tokens, max 6144 input tokens; maintain secondary classification because quantized architecture/backend differs.
- Inputs are never automatically rewritten if over the input-token limit. Must pass tokenizer preflight for all 1,536 requests.
- 12 shards per model to cap GPU-job duration; all presentations of a source group in one shard; 48 total GPU tasks across four models. Small array max 2 concurrent, large array max 1.
- Freeze outputs; no feedback-based retries, model prompt tuning, or label-guided revisions on external cases.
- Offline verifier and operation-only repair are deterministic diagnostic checks and must never be claimed as a trained model improvement or external experimental validation. OC20 is independently sourced but possible training-data exposure of language models remains unverified.
