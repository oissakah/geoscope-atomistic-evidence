#!/usr/bin/env python3
"""Verify the distributed repository's reviewed file contents, standard library only."""
from pathlib import Path, PurePosixPath
import hashlib
import json

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'SHA256SUMS.json').read_text(encoding='utf8'))
for name, expected in manifest.items():
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe manifest path')
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing or unsafe file: ' + name)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Checksum mismatch: ' + name)
print(f'All {len(manifest)} distributed files verified.')
