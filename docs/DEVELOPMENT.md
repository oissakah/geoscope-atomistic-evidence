# Development and verification

The repository preserves a completed, frozen first-attempt computational study.
Its original evidence archive, raw responses, source conventions, inference
settings and scoring rules define the reported result. Workflow rejection is
distinct from a scientific insufficiency verdict. Malformed and truncated
outputs remain in the denominators.

## CPU verification

Python 3.12 and its standard library are sufficient for these checks:

```bash
python verify_repository.py
python reproduce_analysis.py --output-folder /tmp/geoscope-recomputed
PYTHONPATH=workflows/phase3_final/src python -m unittest discover -s workflows/phase3_final/tests -v
```

The final workflow contains 57 CPU tests covering benchmark construction,
licensed interval proofs, selective evaluation, mocked model boundaries and
runner failure paths. They do not require ASE, PyTorch, a GPU or downloaded
model weights. Earlier physical-source workflows have separate dependencies and
are not part of this CPU-only test command.

Score reproduction verifies the pinned final evidence ZIP and all of its member
hashes, then reads explicitly named JSON data. It does not import or execute
programs from that archive. The trusted local scorer must reproduce every
reported evaluation field exactly before writing derived reports. Use an output
directory outside the tracked study files.

Continuous integration runs those same checks on Ubuntu with Python 3.12. It
uses the official `actions/checkout` and `actions/setup-python` actions pinned
to full commits, grants only read access to repository contents, and has a
15-minute job limit. It does not run Swan jobs, download research datasets or
model weights, publish files, or upload build artifacts. Action setup and
repository checkout use the runner's ordinary GitHub network access.

The action pins were verified against the official release pages:

- [checkout v6.0.3](https://github.com/actions/checkout/releases/tag/v6.0.3),
  commit `df4cb1c069e1874edd31b4311f1884172cec0e10`.
- [setup-python v6.3.0](https://github.com/actions/setup-python/releases/tag/v6.3.0),
  commit `ece7cb06caefa5fff74198d8649806c4678c61a1`.

## Preserve the reported experiment

The unpacked workflow folders under `workflows/` preserve the delivered source
for inspection and testing. Their companion delivery ZIPs and the original
final results ZIP remain immutable historical artifacts. Do not edit an
archive, replace failed responses, alter the final parser, extend the inference
budget or change protected-case membership to improve the reported scores.

Maintenance changes to documentation, repository verification or CI should
remain distinguishable from the frozen scientific source. If a genuine scoring
defect is discovered, document the correction and its effect explicitly while
retaining the original result and code. Do not silently overwrite the first
attempts or their checksum trail.

Any new method, prompt, output contract or inference budget belongs to a
separately identified experiment. The current final groups have already been
inspected; tuning on them makes them development data. Evaluate improvements
on fresh held-out groups with the new protocol fixed before inspecting its
outputs. Keep scientific conclusions within the same-domain, controlled-task
scope described in `DATA_CARD.md` and `FINAL_REPORT.md`.

## Credentials and model files

Research inference requires separately obtained model access and an appropriate
compute environment. Keep authentication tokens, credential stores, local
environments, downloaded checkpoints and private keys outside the repository.
Recorded Swan paths and source identifiers are provenance metadata, not login
credentials. The evidence ZIP intentionally retains the original run metadata;
it contains no model weights.
