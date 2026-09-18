#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check target symbols by an actual Orbis intermediate-ELF link, never a host run.

LLVM's check_library_exists otherwise only archives the probe when a cross
profile uses CMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY, producing false
positives for unavailable target libraries. Emit an initial cache with genuine
link results; keep the SDK and each subprocess invocation isolated.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess

CHECKS = {
    'LIBCXX_HAS_GCC_S_LIB': ('gcc_s', '__gcc_personality_v0'),
    'LIBCXX_HAS_GCC_LIB': ('gcc', '__gcc_personality_v0'),
    'LIBCXX_HAS_PTHREAD_LIB': ('pthread', 'pthread_create'),
    'LIBCXX_HAS_RT_LIB': ('rt', 'clock_gettime'),
    'LIBCXX_HAS_ATOMIC_LIB': ('atomic', '__atomic_fetch_add_8'),
    'LIBCXXABI_HAS_C_LIB': ('c', 'fopen'),
    'LIBCXXABI_HAS_GCC_S_LIB': ('gcc_s', '__gcc_personality_v0'),
    'LIBCXXABI_HAS_GCC_LIB': ('gcc', '__aeabi_uldivmod'),
    'LIBCXXABI_HAS_DL_LIB': ('dl', 'dladdr'),
    'LIBCXXABI_HAS_PTHREAD_LIB': ('pthread', 'pthread_once'),
    'LIBCXXABI_HAS_CXA_THREAD_ATEXIT_IMPL': ('c', '__cxa_thread_atexit_impl'),
    'LIBUNWIND_HAS_C_LIB': ('c', 'fopen'),
    'LIBUNWIND_HAS_GCC_S_LIB': ('gcc_s', '__gcc_personality_v0'),
    'LIBUNWIND_HAS_GCC_LIB': ('gcc', '__absvdi2'),
    'LIBUNWIND_HAS_DL_LIB': ('dl', 'dladdr'),
    'LIBUNWIND_HAS_PTHREAD_LIB': ('pthread', 'pthread_once'),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, default=os.environ.get('OO_PS4_TOOLCHAIN'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cc', default='clang')
    parser.add_argument('--ld', default='ld.lld')
    args = parser.parse_args()
    if args.sdk is None:
        parser.error('--sdk or OO_PS4_TOOLCHAIN is required')
    sdk = args.sdk.resolve(strict=True)
    for name in ('include/stdio.h', 'lib/crt1.o', 'link.x'):
        if not (sdk/name).is_file():
            parser.error(f'Incomplete SDK: {name}')
    args.output.mkdir(parents=True, exist_ok=True)
    results = {}

    def check(name: str, library: str, symbol: str) -> bool:
        folder = args.output/name
        folder.mkdir(exist_ok=False)
        source = folder/'probe.c'
        # Never executed: only requires the linker's definition of the symbol.
        source.write_text(f'extern void {symbol}(void);\nint main(void) {{ {symbol}(); return 0; }}\n')
        obj, elf = folder/'probe.o', folder/'probe.elf'
        cc = [args.cc, '--target=x86_64-pc-freebsd12-elf', f'--sysroot={sdk}',
              '-fPIC', '-fno-builtin', '-march=btver2', '-DPS4=1', '-c', str(source), '-o', str(obj)]
        subprocess.run(cc, check=True, capture_output=True, text=True, timeout=30)
        ld = [args.ld, '-m', 'elf_x86_64', '-pie', '--script', str(sdk/'link.x'),
              '--eh-frame-hdr', str(obj), str(sdk/'lib/crt1.o'), '-o', str(elf),
              f'-L{sdk/"lib"}', '--start-group', f'-l{library}', '-lc', '-lkernel',
              str(sdk/'lib/libclang_rt.builtins-x86_64.a'), '--end-group']
        linked = subprocess.run(ld, capture_output=True, text=True, timeout=30)
        success = linked.returncode == 0 and elf.is_file() and elf.stat().st_size > 0
        results[name] = {'library': library, 'symbol': symbol, 'links': success,
                         'command': ld, 'returncode': linked.returncode}
        (folder/'link.log').write_text(linked.stdout+linked.stderr)
        return success

    # Ensure the probe mechanism can both succeed and fail before trusting it.
    if not check('CONTROL_PRESENT', 'c', 'puts'):
        raise RuntimeError('Known-present libc control did not link; inspect link.log')
    if check('CONTROL_ABSENT', 'c', 'so_definitely_missing_runtime_symbol_8193'):
        raise RuntimeError('Missing symbol linked; cannot trust these checks')
    cache = ['# Actual target ELF links; not runtime evidence.']
    for name, (library, symbol) in CHECKS.items():
        available = check(name, library, symbol)
        cache.append(f'set({name} {"ON" if available else "OFF"} CACHE BOOL "Orbis link probe" FORCE)')
    (args.output/'sdk-link-checks.cmake').write_text('\n'.join(cache)+'\n')
    (args.output/'sdk-link-checks.json').write_text(json.dumps(results, indent=2)+'\n')
    for name, result in results.items():
        print(f'{name}={result["links"]}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
