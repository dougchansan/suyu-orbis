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

CHANGES = {'libcxx/include/__locale_dir/locale_base_api.h': ('c360e4d8315c264c11b590ce341cb0e563df5fdb28f633c732cffed6b4cde1bc',
                                                   [('#  elif defined(__FreeBSD__)\n',
                                                     '// Orbis adaptation 2026-09-18: musl does not provide '
                                                     'FreeBSD xlocale.\n'
                                                     '#  elif defined(__FreeBSD__) && '
                                                     '!_LIBCPP_HAS_MUSL_LIBC\n')]),
 'libcxx/src/atomic.cpp': ('13f0d72dfab9efca36f61104474c1b422cd147ba30db8e85cecb30576a381f2f',
                           [('#elif defined(__FreeBSD__)\n',
                             '// Orbis adaptation 2026-09-18: use the upstream timed-backoff baseline.\n'
                             '#elif defined(__FreeBSD__) && !defined(PS4)\n'),
                            ('#elif defined(__FreeBSD__) && __SIZEOF_LONG__ == 8\n',
                             '#elif defined(__FreeBSD__) && !defined(PS4) && __SIZEOF_LONG__ == 8\n')]),
 'libcxx/include/__config': ('52f130285c64cdc1e2604a73a0bfcd8a6c18c5870c1cd3ded9bff7b941fb4218',
                             [('#  if defined(__APPLE__) || defined(__FreeBSD__) || defined(__NetBSD__) || '
                               'defined(__OpenBSD__) ||                     \\\n',
                               '#  if defined(PS4)\n'
                               '// Orbis musl has no arc4random; retain upstream checked /dev/urandom '
                               'reads.\n'
                               '#    define _LIBCPP_USING_DEV_RANDOM\n'
                               '#  elif defined(__APPLE__) || defined(__FreeBSD__) || defined(__NetBSD__) || '
                               'defined(__OpenBSD__) ||                     \\\n'),
                              ('#  if defined(__APPLE__) || defined(__FreeBSD__)\n'
                               '#    define _LIBCPP_HAS_DEFAULTRUNELOCALE\n',
                               '#  if (defined(__APPLE__) || defined(__FreeBSD__)) && '
                               '!_LIBCPP_HAS_MUSL_LIBC\n'
                               '#    define _LIBCPP_HAS_DEFAULTRUNELOCALE\n'),
                              ('#  if defined(__APPLE__) || defined(__FreeBSD__)\n'
                               '#    define _LIBCPP_WCTYPE_IS_MASK\n',
                               '#  if (defined(__APPLE__) || defined(__FreeBSD__)) && '
                               '!_LIBCPP_HAS_MUSL_LIBC\n'
                               '#    define _LIBCPP_WCTYPE_IS_MASK\n')]),
 'libcxx/include/__cxx03/__config': ('8ee9c1ea4fc470cf26be1e66bfc031971688226195dc4bb8b7e04b5587322ce4',
                                     [('#  if defined(__APPLE__) || defined(__FreeBSD__) || '
                                       'defined(__NetBSD__) || defined(__OpenBSD__) ||                     '
                                       '\\\n',
                                       '#  if defined(PS4)\n'
                                       '// Orbis musl has no arc4random; retain upstream checked '
                                       '/dev/urandom reads.\n'
                                       '#    define _LIBCPP_USING_DEV_RANDOM\n'
                                       '#  elif defined(__APPLE__) || defined(__FreeBSD__) || '
                                       'defined(__NetBSD__) || defined(__OpenBSD__) ||                     '
                                       '\\\n'),
                                      ('#  if defined(__APPLE__) || defined(__FreeBSD__)\n'
                                       '#    define _LIBCPP_HAS_DEFAULTRUNELOCALE\n',
                                       '#  if (defined(__APPLE__) || defined(__FreeBSD__)) && '
                                       '!_LIBCPP_HAS_MUSL_LIBC\n'
                                       '#    define _LIBCPP_HAS_DEFAULTRUNELOCALE\n'),
                                      ('#  if defined(__APPLE__) || defined(__FreeBSD__)\n'
                                       '#    define _LIBCPP_WCTYPE_IS_MASK\n',
                                       '#  if (defined(__APPLE__) || defined(__FreeBSD__)) && '
                                       '!_LIBCPP_HAS_MUSL_LIBC\n'
                                       '#    define _LIBCPP_WCTYPE_IS_MASK\n')]),
 'libcxx/src/filesystem/operations.cpp': ('c2ff243df7206f32aaffed77ed18e1b5a0cf96ecb641bfe65dd935adea52b6e8',
                                          [('#elif defined(__FreeBSD__)\n',
                                            '#elif defined(__FreeBSD__) && !defined(PS4)\n'),
                                           ('#if __has_include(<sys/sendfile.h>)\n',
                                            '// Orbis has a different sendfile ABI; use upstream checked '
                                            'fstream copying.\n'
                                            '#if __has_include(<sys/sendfile.h>) && !defined(PS4)\n')]),
 'libcxxabi/src/cxa_thread_atexit.cpp': ('4bd45f3f5027b7d4d682fa1a6c8430298cf988b829f3a38b190618fca4c07fb1',
                                         [('  extern "C"\n#ifndef HAVE___CXA_THREAD_ATEXIT_IMPL',
                                           '// Orbis SDK has no __cxa_thread_atexit_impl and its SELF '
                                           'converter rejects\n'
                                           '// unresolved weak imports. Select the existing pthread-key '
                                           'implementation.\n'
                                           '#if !defined(PS4)\n'
                                           '  extern "C"\n'
                                           '#ifndef HAVE___CXA_THREAD_ATEXIT_IMPL'),
                                          ('  int __cxa_thread_atexit_impl(Dtor, void*, void*);\n',
                                           '  int __cxa_thread_atexit_impl(Dtor, void*, void*);\n'
                                           '#endif // !PS4\n'),
                                          ('    if (__cxa_thread_atexit_impl) {\n'
                                           '      return __cxa_thread_atexit_impl(dtor, obj, dso_symbol);\n'
                                           '    } else {\n',
                                           '#if !defined(PS4)\n'
                                           '    if (__cxa_thread_atexit_impl) {\n'
                                           '      return __cxa_thread_atexit_impl(dtor, obj, dso_symbol);\n'
                                           '    } else\n'
                                           '#endif\n'
                                           '    {\n')])}

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
