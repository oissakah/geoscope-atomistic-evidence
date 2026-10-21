# Continuation package checks

Reviewed 20 October 2026 against the uploaded parent run.

- 60 local automated tests passed, covering geometry, UMA integration through labelled CPU mock calculators, corrected case construction, immutable parent archives, preservation of the 13 accepted endpoints, restoration of original initial references, partial checkpoint recovery, source/input tampering and diagnostic ZIP creation.
- The actual parent ZIP passed all 181 checksums and frozen prepared-manifest checks. A CPU-only collection rehearsal restored the 20 original systems, preserved the 13 accepted endpoint hashes and generated 780 corrected schema-2 cases in a verified return ZIP. This rehearsal performed no inference.
- An independent review of the corrected constructor against the actual measurements found zero detected errors across those 780 cases. All required evidence IDs resolve, omitted numeric values stay omitted, and neutral aliases do not repeat across cases.
- Native Bash/Slurm execution and the additional UMA optimizations require the user's Swan run. The first Phase 1 run has already established that the existing Swan environment and UMA checkpoint execute successfully on its L40S GPU.

The package carries the parent scientific review and inspection images under `parent_review/`. It contains no model weights or raw dataset archive. The original result ZIP is read as data; its archived Python source and old case files are not executed or copied into the new run.
