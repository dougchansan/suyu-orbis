#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile original AArch64 test programs through the real pinned Suyu emitter."""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
from pathlib import Path
from fetch_upstream import verify
from import_modules import import_modules
ROOT = Path(__file__).resolve().parents[1]

def run(*args: str) -> None:
    subprocess.run(list(args), check=True)

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suyu', type=Path, default=ROOT/'vendor/suyu')
    p.add_argument('--work', type=Path, default=ROOT/'build/upstream-fixture')
    p.add_argument('--cxx', default=os.environ.get('CXX', 'c++'))
    args = p.parse_args()
    try:
        verify(args.suyu)
        work = args.work.resolve()
        if work.exists() and any(work.iterdir()):
            raise ValueError('Choose an empty --work directory (no destructive cleanup)')
        work.mkdir(parents=True, exist_ok=True)
        exe = work / ('emit-fixture.exe' if os.name == 'nt' else 'emit-fixture')
        run(args.cxx, '-std=c++20', '-O1', '-I', str(args.suyu/'src/core/recompiler'),
            str(ROOT/'tests/upstream_fixture.cpp'), '-o', str(exe))
        run(str(exe), str(work/'exefs'))
        import_modules(work/'exefs', work/'bundle')
        run('cmake', '-S', str(ROOT), '-B', str(work/'host'), '-G', 'Ninja',
            '-DCMAKE_BUILD_TYPE=Release', f'-DSO_MODULE_BUNDLE={work / "bundle"}',
            '-DSO_BUILD_UPSTREAM_FIXTURE=ON')
        run('cmake', '--build', str(work/'host'), '--parallel', '2')
        run('ctest', '--test-dir', str(work/'host'), '--output-on-failure')
        run(sys.executable, str(ROOT/'scripts/audit_binary.py'),
            str(work/'host/suyu-orbis-upstream-smoke'))
        print('Real-emitter HOST synthetic integration passed. No PS4/game claim.')
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        p.exit(1, f'upstream test error: {exc}\n')

if __name__ == '__main__':
    raise SystemExit(main())
