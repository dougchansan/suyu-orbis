#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check host/SDK prerequisites without changing the machine."""
from __future__ import annotations
import argparse
import json
import os
import platform
import shutil
from pathlib import Path

def inspect(orbis: bool, sdk: str | None = None) -> dict:
    names = ['cmake', 'ninja', 'python3']
    if orbis:
        names += ['clang', 'clang++', 'ld.lld', 'llvm-ar', 'llvm-ranlib']
    else:
        names += ['cc']
    tools = {name: shutil.which(name) for name in names}
    missing = [name for name, path in tools.items() if not path]
    files = {}
    if orbis:
        raw = sdk if sdk is not None else os.environ.get('OO_PS4_TOOLCHAIN')
        if not raw:
            missing.append('OO_PS4_TOOLCHAIN')
        else:
            root = Path(raw).expanduser().resolve()
            for relative in ['include/stdio.h', 'include/stdint.h', 'lib/crt1.o', 'link.x']:
                files[relative] = (root / relative).is_file()
                if not files[relative]: missing.append(relative)
            for library in ['c', 'kernel']:
                present = any((root / 'lib' / f'lib{library}{ext}').is_file()
                              for ext in ['.a', '.so'])
                files[f'lib{library}'] = present
                if not present: missing.append(f'lib{library}')
            host = {'Linux': 'linux', 'Darwin': 'macos'}.get(platform.system())
            if not host:
                missing.append('Linux/WSL or macOS OpenOrbis build host')
            else:
                converter = 'create-fself-macos' if host == 'macos' else 'create-fself'
                fself = root/'bin'/host/converter
                files['create-fself'] = fself.is_file() and os.access(fself, os.X_OK)
                if not files['create-fself']: missing.append(str(fself))
    return {'mode': 'orbis' if orbis else 'host', 'ready': not missing,
            'tools': tools, 'sdk_files': files, 'missing': missing,
            'note': 'Prerequisites only; not evidence of a successful PS4 build/run'}

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--orbis', action='store_true')
    p.add_argument('--sdk')
    args=p.parse_args()
    result=inspect(args.orbis, args.sdk)
    print(json.dumps(result, indent=2))
    return 0 if result['ready'] else 1
if __name__ == '__main__':
    raise SystemExit(main())
