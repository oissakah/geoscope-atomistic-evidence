# Sources and acknowledgments

This package contains original project analysis, the user's preserved model-output archive and derived benchmark evidence. No model weights or model environments are redistributed. Original project code has not been assigned a new blanket license by this review.

The original OC20 structures and metadata are attributed to the Open Catalyst Project and its dataset authors. Its [official dataset repository](https://github.com/Open-Catalyst-Project/Open-Catalyst-Dataset/blob/main/README.md) identifies OC20/OC22 datasets as CC BY 4.0. Preserve that attribution and identify project modifications, including UMA relaxations, measurement extraction, synthetic translations and templated claims.

The atomistic endpoint generator uses the pinned UMA `uma-s-1p2p1` checkpoint. Acknowledge [UMA: A Family of Universal Models for Atoms](https://arxiv.org/abs/2506.23971). The [FAIRChem repository](https://github.com/facebookresearch/fairchem) distinguishes its code license from model/checkpoint licenses. The [UMA license at the pinned revision](https://huggingface.co/facebook/UMA/blob/9f578aa4bda5d1723b0cb0c4a5d2c115728a5b2e/LICENSE) is the relevant source for checkpoint terms; it is not replaced by a project-code license.

Language-model repositories and exact revisions are preserved in the original manifest:

- [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), revision `cdbee75f17c01a7cc42f958dc650907174af0554`.
- [microsoft/Phi-4-mini-instruct](https://huggingface.co/microsoft/Phi-4-mini-instruct), revision `cfbefacb99257ffa30c83adab238a50856ac3083`.
- [HuggingFaceTB/SmolLM3-3B](https://huggingface.co/HuggingFaceTB/SmolLM3-3B), revision `a07cc9a04f16550a088caea529712d1d335b0ac1`.

Inference used the recorded Transformers, PyTorch and Accelerate environment. Atomic analysis used ASE. Figure generation uses Matplotlib and NumPy; the figure requirements record the local plotting versions. A publication should acknowledge these software projects and cite their preferred references.

The observed run used UNL Swan and NVIDIA L40S hardware. Use the institution's applicable acknowledgment wording when preparing the manuscript. No allocation identifier, funding award, author identity or institutional approval has been invented here.

Upstream documentation was checked on 21 October 2026. The URLs above provide source attribution and pointers, not a replacement for the original pinned artifacts and licenses.
