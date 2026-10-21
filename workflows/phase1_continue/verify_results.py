#!/usr/bin/env python3
"""Verify a Phase 1 return ZIP without extracting or executing its contents."""
import argparse
import hashlib
import json
from pathlib import PurePosixPath
import zipfile


def verify(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Archive has duplicate member names")
        for name in names:
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name:
                raise ValueError("Archive contains a nonportable or unsafe member path")
        bad = z.testzip()
        if bad:
            raise ValueError(f"Corrupt ZIP member: {bad}")
        manifests = [name for name in names if name.endswith("/SHA256SUMS.json")]
        if len(manifests) != 1:
            raise ValueError("Expected one Phase 1 checksum manifest (small preflight ZIPs use a different schema)")
        prefix = manifests[0].removesuffix("SHA256SUMS.json")
        hashes = json.loads(z.read(manifests[0]))
        for relative, expected in hashes.items():
            actual = hashlib.sha256(z.read(prefix + relative)).hexdigest()
            if actual != expected:
                raise ValueError(f"Checksum mismatch: {relative}")
        tracked = {prefix + relative for relative in hashes} | {manifests[0]}
        if tracked != set(names):
            raise ValueError("Archive has missing or untracked members")
        summary = json.loads(z.read(prefix + "summary.json"))
        return {"verified_files": len(hashes), "status": summary["status"], "phase2_ready": summary["phase2_ready"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path")
    print(json.dumps(verify(parser.parse_args().zip_path), indent=2))
