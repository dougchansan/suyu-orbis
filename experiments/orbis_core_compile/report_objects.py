#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Verify object coverage/ABI and retain unresolved imports; not a link/run test."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import struct
import subprocess
from verify_sources import EXPECTED_COUNT, UPSTREAM

FORBIDDEN = re.compile(r'Dynarmic::|ArmDynarmic|__jit_debug_register_code|\bdlopen\b|\bdlsym\b')

def check_elf(data: bytes) -> None:
    if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('Expected a 64-bit little-endian ELF object')
    if struct.unpack_from('<HH', data, 16) != (1, 62):
        raise ValueError('Expected ET_REL / EM_X86_64, not a host executable')

def report(build: Path, output: Path, nm: str) -> dict:
    selected = json.loads((build / 'selected-sources.json').read_text())['sources']
    commands = json.loads((build / 'compile_commands.json').read_text())
    if len(commands) != EXPECTED_COUNT or len(selected) != EXPECTED_COUNT:
        raise ValueError('Incomplete or unexpected compilation database')
    rows = []
    unresolved = set()
    defined = set()
    seen = set()
    empty_symbol_units = []
    for command in commands:
        argv = shlex.split(command['command'])
        if '-DSUYU_NO_JIT=1' not in argv or '--target=x86_64-pc-freebsd12-elf' not in argv:
            raise ValueError('Command lacks the explicit no-JIT Orbis target')
        if '-march=native' in argv:
            raise ValueError('Host ISA tuning leaked into the Orbis profile')
        file = Path(command['file'])
        matches = [name for name in selected if file.as_posix().endswith('/src/' + name)]
        if len(matches) != 1 or matches[0] in seen:
            raise ValueError('Unknown or repeated source in compilation database')
        name = matches[0]
        seen.add(name)
        if hashlib.sha256(file.read_bytes()).hexdigest() != selected[name]:
            raise ValueError(f'Source changed after configure: {name}')
        obj = Path(command['directory']) / command['output']
        data = obj.read_bytes()
        check_elf(data)
        symbols = subprocess.run([nm, '-g', '-C', str(obj)], check=True,
                                 text=True, capture_output=True).stdout
        if FORBIDDEN.search(symbols):
            raise ValueError(f'Forbidden CPU/loader symbol: {name}')
        if not symbols.strip():
            empty_symbol_units.append(name)  # Some pinned units contain static_asserts only.
        for line in symbols.splitlines():
            match = re.match(r'^\s*(?:[0-9a-fA-F]+\s+)?([A-Za-z?])\s+(.+)$', line)
            if not match:
                continue
            kind, symbol = match.groups()
            if kind == 'U':
                unresolved.add(symbol)
            elif kind in 'TDRBSAWV':
                defined.add(symbol)
        rows.append({'source': name, 'object_sha256': hashlib.sha256(data).hexdigest(),
                     'object_bytes': len(data)})
    for required in ('Core::ArmRecomp::RunThread', 'Kernel::KProcess::Run', 'Kernel::KThread::Run'):
        if not any(symbol.startswith(required + '(') for symbol in defined):
            raise ValueError(f'Missing actual kernel definition: {required}')
    remaining = sorted(unresolved - defined)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_name('remaining-undefined.txt').write_text('\n'.join(remaining) + '\n')
    result = {'passed': True, 'scope': 'Orbis translation units only',
              'upstream_commit': UPSTREAM, 'compiled_units': len(rows),
              'cpu_jit_symbol_guardrail': True, 'remaining_undefined_count': len(remaining),
              'empty_global_symbol_units': empty_symbol_units,
              'full_core_linked': False, 'orbis_scheduler_executed': False,
              'physical_ps4_tested': False, 'game_tested': False, 'objects': rows}
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'objects'}, indent=2))
    return result

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--nm', default=shutil.which('llvm-nm') or shutil.which('nm'))
    a = p.parse_args()
    try:
        if not a.nm:
            raise ValueError('nm or llvm-nm is required')
        report(a.build.resolve(strict=True), a.output.resolve(), a.nm)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        p.exit(1, f'Object gate failed: {error}\n')
