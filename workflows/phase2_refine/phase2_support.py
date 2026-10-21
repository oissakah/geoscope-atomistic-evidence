"""Small standard-library helpers for Phase 2 provenance and return archives."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
RESULT_BYTES_LIMIT=512*1024*1024


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def jsonl(path, records):
    Path(path).write_text("".join(json.dumps(r, allow_nan=False) + "\n" for r in records), encoding="utf-8")


def safe_text(value):
    return re.sub(r"hf_[A-Za-z0-9]{12,}", "[REDACTED_HF_TOKEN]", str(value))


class Tee:
    def __init__(self, terminal, log):
        self.terminal, self.log = terminal, log
    def write(self, text):
        self.terminal.write(text)
        self.log.write(safe_text(text))
        self.log.flush()
        return len(text)
    def flush(self):
        self.terminal.flush()
        self.log.flush()


def environment():
    packages = {}
    for name in ("numpy", "torch", "transformers", "accelerate", "huggingface-hub", "tokenizers", "safetensors"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                packages=packages, slurm={key: os.environ.get(key) for key in
                ("SLURM_JOB_ID", "SLURM_JOB_PARTITION", "SLURM_CPUS_PER_TASK")})


def source_files():
    files = [p for p in ROOT.iterdir() if p.is_file() and p.suffix in {".py", ".sh", ".sbatch", ".md"}]
    for folder in ("src", "tests"):
        files.extend(p for p in (ROOT / folder).rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(files)


def snapshot(out):
    hashes = {}
    for source in source_files():
        relative = source.relative_to(ROOT)
        target = out / "code_snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[relative.as_posix()] = digest(source)
    save_json(out / "code_sha256.json", hashes)


def stage(out, mode, state, **extra):
    save_json(out / f"stage_{mode}.json", dict(stage=mode, state=state, time_unix=time.time(), **extra))


def archive(out, output_root):
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS.json")
    if any(p.is_symlink() for p in files):
        raise ValueError("Result directory contains a symlink; refusing to follow it into the return ZIP")
    if sum(p.stat().st_size for p in files) > RESULT_BYTES_LIMIT:
        raise ValueError("Results exceed the 512 MiB bounded return size; preserve run directory and inspect logs")
    save_json(out / "SHA256SUMS.json", {p.relative_to(out).as_posix(): digest(p) for p in files})
    folder = output_root / "return_zips"
    folder.mkdir(exist_ok=True)
    target = folder / f"{out.name}_phase2_results.zip"
    temporary = target.with_suffix(".zip.part")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as z:
        for path in files + [out / "SHA256SUMS.json"]:
            z.write(path, (Path(out.name) / path.relative_to(out)).as_posix())
    temporary.replace(target)
    print(f"Return ZIP: {target}")
    return target


def diagnostic_archive(out, output_root, error):
    """Replace any earlier-stage ZIP with a bounded, explicitly failed artifact."""
    summary = load_json(out / "summary.json")
    summary.setdefault("scientific_status_before_packaging", summary.get("status"))
    summary.update(status="PACKAGING_FAILED", packaging_error=safe_text(error),
                   return_archive_kind="bounded_diagnostic", full_results_remain_on_disk=True)
    save_json(out / "summary.json", summary)
    payload = {}
    inventory = []
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(out).as_posix()
        inventory.append(dict(path=relative, bytes=path.stat().st_size, symlink=path.is_symlink()))
        if path.is_symlink() or path.name == "SHA256SUMS.json":
            continue
        allowed = path.parent == out and path.suffix in {".json", ".txt", ".log"}
        allowed = allowed or path.parent == out / "slurm_logs"
        if allowed and len(payload) < 50:
            with path.open("rb") as stream:
                # Logs are bounded tails; JSON manifests are included only whole.
                if path.stat().st_size > 512 * 1024:
                    if path.suffix != ".log":
                        continue
                    stream.seek(path.stat().st_size - 512 * 1024)
                payload[relative] = stream.read()
    payload["summary.json"] = (out / "summary.json").read_bytes()
    payload["diagnostic_inventory.json"] = json.dumps(dict(files=inventory[:2000],
        inventory_truncated=len(inventory) > 2000, full_file_count=len(inventory)), indent=2).encode()
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
    payload["SHA256SUMS.json"] = json.dumps(hashes, indent=2).encode()
    folder = output_root / "return_zips"
    folder.mkdir(exist_ok=True)
    target = folder / f"{out.name}_phase2_results.zip"
    temporary = target.with_suffix(".zip.part")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as z:
        for relative, data in payload.items():
            z.writestr(f"{out.name}/{relative}", data)
    temporary.replace(target)
    print(f"Diagnostic return ZIP: {target}")
    return target
