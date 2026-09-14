#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Cross-build a diagnostic ELF and eboot; does not install or launch on a PS4."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from doctor import inspect
ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixture-bundle', type=Path,
                   help='Only the two synthetic modules from test_upstream.py')
    args=p.parse_args()
    report=inspect(True)
    if not report['ready']:
        print(json.dumps(report, indent=2)); return 1
    sdk=Path(os.environ['OO_PS4_TOOLCHAIN']).resolve()
    host={'Linux':'linux', 'Darwin':'macos'}[platform.system()]
    target='suyu-orbis-upstream-smoke' if args.fixture_bundle else 'suyu-orbis-probe'
    build=ROOT/'build/orbis'
    out=ROOT/'out/orbis'/target
    def run(*command: str) -> None:
        subprocess.run(list(command), check=True, cwd=ROOT)
    try:
        run('cmake', '--preset', 'orbis',
            f'-DSO_MODULE_BUNDLE={args.fixture_bundle.resolve() if args.fixture_bundle else ""}',
            f'-DSO_BUILD_UPSTREAM_FIXTURE={"ON" if args.fixture_bundle else "OFF"}')
        run('cmake', '--build', str(build), '--target', target, '--parallel', '2')
        elf=build/(target+'.elf')
        if not elf.is_file(): raise ValueError(f'Expected ELF not produced: {elf}')
        run(sys.executable, str(ROOT/'scripts/audit_binary.py'), str(elf))
        out.mkdir(parents=True, exist_ok=True)
        eboot=out/'eboot.bin'
        # Remove only this script's prior conversion output: a failed converter
        # must not make a stale eboot appear to be the newly built executable.
        eboot.unlink(missing_ok=True)
        run(str(sdk/'bin'/host/'create-fself'), '-in='+str(elf),
            '-out='+str(out/(target+'.oelf')), '--eboot', str(eboot),
            '--paid', '0x3800000000000011')
        if not eboot.is_file() or eboot.stat().st_size == 0:
            raise ValueError('create-fself did not produce a nonempty eboot')
        evidence={'target':target, 'elf':str(elf), 'eboot':str(eboot),
                  'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),
                  'eboot_sha256':hashlib.sha256(eboot.read_bytes()).hexdigest(),
                  'cross_compiled':True, 'ps4_run':False, 'game_run':False,
                  'renderer':'none', 'sdk':str(sdk)}
        (out/'build_report.json').write_text(json.dumps(evidence, indent=2)+'\n')
        print(json.dumps(evidence, indent=2))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        p.exit(1, f'Orbis build error: {exc}\n')
if __name__ == '__main__':
    raise SystemExit(main())
