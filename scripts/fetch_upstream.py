#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fetch the pinned public Suyu source. Never reset an existing worktree."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'deps.lock.json').read_text())['suyu']

def verify(source: Path) -> None:
    data = (source / LOCK['emitter_path']).read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if blob != LOCK['emitter_git_blob']:
        raise ValueError('Emitter differs from audited Git blob; do not mix ABI revisions')

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination', type=Path, default=ROOT / 'vendor/suyu')
    p.add_argument('--check', action='store_true', help='Offline verification only')
    p.add_argument('--submodules', action='store_true', help='Fetch dependencies for later full-core work')
    args = p.parse_args()
    try:
        if not args.check:
            if args.destination.exists():
                raise ValueError('Destination exists; use --check or choose a new directory')
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', 'clone', '--filter=blob:none', '--no-checkout',
                            LOCK['repository'], str(args.destination)], check=True)
            subprocess.run(['git', '-C', str(args.destination), 'fetch', '--depth', '1',
                            'origin', LOCK['commit']], check=True)
            subprocess.run(['git', '-C', str(args.destination), 'checkout', '--detach',
                            LOCK['commit']], check=True)
            if args.submodules:
                subprocess.run(['git', '-C', str(args.destination), 'submodule', 'update',
                                '--init', '--recursive'], check=True)
        verify(args.destination)
        print(f'Audited emitter verified: {LOCK["commit"]}')
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        p.exit(1, f'upstream error: {exc}\n')

if __name__ == '__main__':
    raise SystemExit(main())
