# Delivery validation

Prepared locally on 20 October 2026. These are software checks, not final model-performance results.

- All 57 CPU unit tests passed: 12 benchmark tests, 21 model/protocol tests, 16 evaluation tests and eight orchestration tests.
- The pinned source and development archives were read as data, with every member checksum verified. Their 55 qualified final groups and 20 development groups are disjoint, and the reserved language-model manifest is unchanged.
- The revised constructor passed the 20-group development regression before generating the final 55-group cases. The actual final inputs produce exactly 1,760 variants: 550 supported, 550 contradicted and 660 insufficient. All groups are retained, no cases are skipped, and every gold verdict agrees with the public-payload oracle.
- A CPU collection rehearsal used all 1,760 actual case packets with synthetic responses only. Completely absent models retained all 10,560 request denominators and all 13 method/model summaries. A perfect-proof fixture then checked 10,560 synthetic responses and 22,880 derived rows, inclusive fence parsing, separate rejection/insufficiency accounting and all 1,000 source-group bootstrap iterations.
- The rehearsal produced a return ZIP with 47 verified member checksums. The archive correctly retained `phase3_complete=false` and `final_review_required=true`. Synthetic outputs remain outside this delivery and must never be reported as model results.
- Delivery validation compiles every Python file, parses the five Bash/Slurm scripts and their three embedded Python blocks, checks UTF-8/LF formatting, and verifies archive paths, permissions, unique members and ZIP integrity. The ZIP SHA256 is supplied separately.

No language model was loaded, no UMA calculation was run and no GPU/Slurm execution was performed locally. The new frozen model protocol still requires its first execution on Swan. All raw first-attempt outputs, including failures, must be returned for review before publication conclusions are drawn.
