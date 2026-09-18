#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Apply reviewed platform selectors to an isolated pinned LLVM runtime checkout.

OpenOrbis targets a FreeBSD ELF ABI but supplies musl C headers, not FreeBSD
xlocale/umtx. Select upstream musl locale support and upstream atomic-wait
poll/backoff fallback; do not stub operations or claim native futex support.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path

CHANGES = {
    'libcxx/include/__locale_dir/locale_base_api.h': (
        'c360e4d8315c264c11b590ce341cb0e563df5fdb28f633c732cffed6b4cde1bc',
        [('#  elif defined(__FreeBSD__)\n',
          '// Orbis adaptation 2026-09-18: musl does not provide FreeBSD xlocale.\n'
          '#  elif defined(__FreeBSD__) && !_LIBCPP_HAS_MUSL_LIBC\n')]),
    'libcxx/src/atomic.cpp': (
        '13f0d72dfab9efca36f61104474c1b422cd147ba30db8e85cecb30576a381f2f',
        [('#elif defined(__FreeBSD__)\n',
          '// Orbis adaptation 2026-09-18: use the upstream timed-backoff baseline.\n'
          '#elif defined(__FreeBSD__) && !defined(PS4)\n'),
         ('#elif defined(__FreeBSD__) && __SIZEOF_LONG__ == 8\n',
          '#elif defined(__FreeBSD__) && !defined(PS4) && __SIZEOF_LONG__ == 8\n')]),
}

def patch(root: Path) -> None:
    pending = []
    for relative, (expected, changes) in CHANGES.items():
        file = root/relative
        current = file.read_text()
        original = current
        for old, new in reversed(changes):
            if new in original:
                original = original.replace(new, old)
        if hashlib.sha256(original.encode()).hexdigest() != expected:
            raise ValueError(f'Unreviewed LLVM source: {relative}')
        modified = original
        for old, new in changes:
            if modified.count(old) != 1:
                raise ValueError(f'Ambiguous patch location: {relative}')
            modified = modified.replace(old, new)
        pending.append((file, modified))
    for file, modified in pending:
        file.write_text(modified)
        print(f'Orbis platform selection: {file.relative_to(root)}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    patch(parser.parse_args().source.resolve(strict=True))
