#!/usr/bin/env python3
"""Verify package SHA256 checksums with standard-library Python on Linux or macOS."""
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def verify(root=ROOT):
    root = root.resolve()
    failures = []
    count = 0
    for line in (root / 'SHA256SUMS').read_text().splitlines():
        match = re.fullmatch(r'([a-f0-9]{64})  (.+)', line)
        if not match:
            raise ValueError('Hibas SHA256SUMS sor.')
        digest, name = match.groups()
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError('A fajl a csomagon kivulre mutat.')
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            failures.append(name)
            continue
        if actual != digest:
            failures.append(name)
        count += 1
    if not count or failures:
        raise ValueError('Hianyzo vagy eltero csomagfajlok: ' + ', '.join(failures))
    print('PASS: ' + str(count) + ' csomagfajl SHA256 ellenorzese sikeres.')


if __name__ == '__main__':
    try:
        verify()
    except (OSError, ValueError) as error:
        raise SystemExit('HIBA: ' + str(error))
