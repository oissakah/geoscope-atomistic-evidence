# Checks performed before delivery

Date: 20 October 2026.

- 64 local automated tests passed: coordinate invariance and failure cases, deterministic case construction, source selection and archive handling, constrained ASE optimization using a labelled mock calculator, frozen input integrity, and return ZIP diagnostics/checksums.
- The real official OC20-Dense initial-coordinate archive was verified by its frozen SHA256 and parsed locally. Default selection produced 20 distinct systems, with 35–151 atoms per structure and 3–12 adsorbate atoms. All selected input hashes, atom tags and exact fixed-atom masks were checked.
- Python sources compiled successfully. All six shell/Slurm files passed a Bash grammar parser. Archive paths, UTF-8/LF text and ZIP integrity were checked.
- Mock calculators and synthetic demonstration coordinates are test fixtures. They are not UMA predictions, DFT reference results or evidence of benchmark performance.

Not executed locally: native Bash/Slurm submission, the large GPU software installation, authenticated gated model download, or CUDA/UMA inference on Swan. Those require the user's Swan run. The first three systems provide a bounded runtime smoke check before the remaining pilot systems are attempted.

The downloaded dataset archive, model weights, Python dependencies, local test results and environment are not included in this script ZIP. The scripts obtain official data and authorized model weights into a separate cache on Swan.
