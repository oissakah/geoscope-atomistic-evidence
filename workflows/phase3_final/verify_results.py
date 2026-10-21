#!/usr/bin/env python3
"""Verify the final results ZIP without extracting or executing its contents."""
import argparse
import hashlib
import json
import zipfile
from pathlib import PurePosixPath

def verify(path):
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate ZIP member')
        for n in names:
            p=PurePosixPath(n)
            if p.is_absolute() or '..' in p.parts or '\\' in n or ':' in n:raise ValueError('Unsafe ZIP member')
        manifests=[n for n in names if n.endswith('/SHA256SUMS.json')]
        if len(manifests)!=1:raise ValueError('Expected one checksum manifest')
        prefix=manifests[0].removesuffix('SHA256SUMS.json');hashes=json.loads(z.read(manifests[0]))
        if {prefix+n for n in hashes}|{manifests[0]}!=set(names):raise ValueError('Missing or untracked member')
        for n,h in hashes.items():
            if hashlib.sha256(z.read(prefix+n)).hexdigest()!=h:raise ValueError('Checksum mismatch: '+n)
        summary=json.loads(z.read(prefix+'summary.json'))
        return dict(verified_files=len(hashes),status=summary['status'],phase3_complete=summary['phase3_complete'],
                    final_review_required=summary['final_review_required'])

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('zip_path')
    print(json.dumps(verify(parser.parse_args().zip_path),indent=2))
