"""Validate the ONE assigned L40S CUDA device using units that match hardware.

NVIDIA labels L40S as 48 GB (decimal); 45 GiB == 48.32 GB and wrongly
rejects the nominal device. Validate identity and generous real capacity,
printing an actionable diagnostic before any vLLM model loading.
"""
import json
import os

MIN_L40S_GIB = 40


def validate_single_l40s(cuda):
    report = {
        "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", "<unset>"),
        "SLURM_JOB_GPUS": os.environ.get("SLURM_JOB_GPUS", "<unset>"),
        "SLURM_STEP_GPUS": os.environ.get("SLURM_STEP_GPUS", "<unset>"),
        "SLURM_JOB_ID": os.environ.get("SLURM_JOB_ID", "<unset>"),
        "minimum_capacity_gib": MIN_L40S_GIB,
    }
    try:
        report["cuda_available"] = bool(cuda.is_available())
        report["cuda_device_count"] = int(cuda.device_count())
        if report["cuda_available"] and report["cuda_device_count"]:
            props = cuda.get_device_properties(0)
            report["gpu_name"] = str(props.name)
            report["total_bytes"] = int(props.total_memory)
            report["total_gib"] = round(int(props.total_memory) / 1024**3, 3)
            report["total_decimal_gb"] = round(int(props.total_memory) / 10**9, 3)
            report["compute_capability"] = f"{props.major}.{props.minor}"
            try:
                free_bytes, total_bytes = cuda.mem_get_info(0)
                report["free_gib_at_check"] = round(int(free_bytes) / 1024**3, 3)
            except (AttributeError, RuntimeError, TypeError) as exc:
                report["free_memory_probe_note"] = type(exc).__name__
    except Exception as exc:
        report["probe_exception"] = f"{type(exc).__name__}: {exc}"
        print("CUDA_GPU_DIAGNOSTIC:", json.dumps(report, sort_keys=True), flush=True)
        raise RuntimeError("CUDA device inspection failed; inspect CUDA_GPU_DIAGNOSTIC") from exc
    print("CUDA_GPU_DIAGNOSTIC:", json.dumps(report, sort_keys=True), flush=True)
    if not report["cuda_available"]:
        raise RuntimeError("CUDA is unavailable inside the SLURM job; inspect GPU assignment, driver and CUDA_GPU_DIAGNOSTIC")
    if report["cuda_device_count"] != 1:
        raise RuntimeError("Expected exactly one visible CUDA GPU; inspect CUDA_VISIBLE_DEVICES and SLURM GPU allocation")
    if "l40s" not in report.get("gpu_name", "").lower():
        raise RuntimeError("Wrong GPU assigned: expected NVIDIA L40S, received " + report.get("gpu_name", "unknown"))
    if report["total_bytes"] < MIN_L40S_GIB * 1024**3:
        raise RuntimeError("L40S reports unexpectedly low total memory (GiB): " + str(report["total_gib"]))
    return report


def main():
    import torch
    info = validate_single_l40s(torch.cuda)
    print("GPU_PREFLIGHT_PASS:", info["gpu_name"], info["total_gib"], "GiB", flush=True)


if __name__ == "__main__":
    main()
