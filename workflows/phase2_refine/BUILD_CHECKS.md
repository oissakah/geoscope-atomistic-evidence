# Local checks

Checked on 20 October 2026 before delivery:

- 57 tests pass, including the new output contract, fence-only handling, selector schema, paired arithmetic/guard behavior, rejection without oracle rescue, fabricated-ID errors, missing requests, frozen inputs, failed setup and return-ZIP collection.
- Actual reviewed parent evidence regenerates the same 320 public cases, gold labels and audit metadata. All 63 parent member checksums and the pinned parent archive SHA256 pass.
- CPU collection rehearsals retain all 2,880 expected requests when outputs are deliberately absent. A separate fixture with correct selections and judgments verifies the complete 15-combination scoring path. These are machinery checks, not model-performance results.
- Python compilation, static Bash parsing of all five shell/Slurm scripts, Linux text encoding/line endings and delivery-ZIP integrity pass.

The environment/model checkpoints have already run successfully in the prior Swan trial. The revised prompts and selection pipeline have not been evaluated on a GPU locally. They must still be run and reviewed on Swan. No weights, environment, credentials, mock outputs or rehearsal results are included in the delivery ZIP.
