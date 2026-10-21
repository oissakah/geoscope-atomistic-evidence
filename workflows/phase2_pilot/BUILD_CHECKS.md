# Local build checks

Checked on 20 October 2026 before delivery:

- 47 unit and integration tests passed without model downloads. These cover benchmark balance and scope, unambiguous quantity definitions, evidence citations, strict scoring, malformed/missing responses, model interface mocks, frozen inputs, resume identity, failed setup and return-ZIP collection.
- The actual reviewed Phase 1 continuation ZIP passed its pinned whole-archive SHA256 and all 228 file checksums. It generated 320 development variants from 20 groups; the scope baseline matched all labels and citations.
- A CPU collection rehearsal using that actual evidence and deliberately absent model outputs retained all 1,920 expected requests as missing, reported partial results and produced a checksum-verified return ZIP. This was a local machinery check, not language-model performance evidence.
- All Python files compile. All five shell/Slurm files pass static Bash parsing. Delivery text uses UTF-8 without a byte-order mark and Linux line endings; ZIP paths, permissions and integrity were checked.

Full model downloads, native Slurm execution and language-model inference have not been run locally. Those require validation on Swan. Local tests do not establish GPU compatibility, model scores or scientific novelty. No mock model output or local rehearsal result is included in this package.
