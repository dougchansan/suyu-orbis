#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Symbol-level no-JIT guardrail, NOT proof of all execution/memory behavior."""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
FORBIDDEN = re.compile(r'Dynarmic::|ArmDynarmic|dlopen|dlsym|LoadLibrary[AW]?|GetProcAddress|\b__jit_debug_register_code\b')
def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('binary', type=Path)
    p.add_argument('--nm', default=shutil.which('llvm-nm') or shutil.which('nm'))
    args=p.parse_args()
    try:
        if not args.nm or not args.binary.is_file():
            raise ValueError('Need an unstripped binary and nm/llvm-nm')
        result=subprocess.run([args.nm, '-C', str(args.binary)], check=True,
                              text=True, capture_output=True)
        if not result.stdout.strip():
            raise ValueError('No symbols available; cannot audit a stripped artifact')
        hits=[line.strip() for line in result.stdout.splitlines() if FORBIDDEN.search(line)]
        print(json.dumps({'binary': str(args.binary), 'scope': 'symbol_guardrail_only',
                          'passed': not hits, 'forbidden_symbols': hits}, indent=2))
        return 1 if hits else 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        p.exit(1, f'audit error: {exc}\n')
if __name__ == '__main__':
    raise SystemExit(main())
