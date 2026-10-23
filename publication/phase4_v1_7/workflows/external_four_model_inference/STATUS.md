External OC20 source gate: PASS (48 systems). Sealed benchmark: PASS (1536 questions). No external GPU inference conducted yet.

### v1.6.1 runtime repair
OC20 1536-case Qwen/Phi/SmolLM runs completed in v1.6.0. All 12 Qwen3-32B array tasks failed during import because a resolved Python symlink bypassed the venv. v1.6.1 changes only environment handoff and batch preflight; external 32B inference still must be run on Swan.
