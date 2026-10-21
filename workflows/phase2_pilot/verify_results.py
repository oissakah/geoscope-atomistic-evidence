#!/usr/bin/env python3
"""Verify a Phase 2 results ZIP without extracting or executing its contents."""
import argparse
import hashlib
import json
from pathlib import PurePosixPath
import zipfile

def verify(path):
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):
            raise ValueError('Duplicate ZIP member')
        for name in names:
            p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name:
                raise ValueError('Unsafe ZIP member path')
        manifest=[name for name in names if name.endswith('/SHA256SUMS.json')]
        if len(manifest)!=1:
            raise ValueError('Expected one checksum manifest')
        prefix=manifest[0].removesuffix('SHA256SUMS.json')
        hashes=json.loads(z.read(manifest[0]))
        if {prefix+name for name in hashes}|set(manifest)!=set(names):
            raise ValueError('Untracked or missing files')
        for name,expected in hashes.items():
            if hashlib.sha256(z.read(prefix+name)).hexdigest()!=expected:
                raise ValueError('Checksum mismatch: '+name)
        summary=json.loads(z.read(prefix+'summary.json'))
        return dict(verified_files=len(hashes),status=summary['status'],phase3_ready=summary['phase3_ready'])

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip_path')
    print(json.dumps(verify(parser.parse_args().zip_path),indent=2))
