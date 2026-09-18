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
 'libcxx/src/chrono.cpp': ('9f5acabff11905fd20100c6fb7afa3450b1e9dc5b2279302a5a544e55defe361',
                           [('#include "include/apple_availability.h"\n#include <time.h> // clock_gettime and CLOCK_{MONOTONIC,REALTIME,MONOTONIC_RAW}\n',
                             '#include "include/apple_availability.h"\n'
                             '#if defined(PS4)\n'
                             '#  include <orbis/libkernel.h>\n'
                             '#endif\n'
                             '#include <time.h> // clock_gettime and CLOCK_{MONOTONIC,REALTIME,MONOTONIC_RAW}\n'),
                            ('#  if defined(__APPLE__)\n',
                             '#  if defined(PS4)\n'
                             '// OpenOrbis exposes a process-time counter with an explicit frequency.\n'
                             '// Use it directly instead of relying on the FreeBSD ABI clock-id values.\n'
                             'static steady_clock::time_point __libcpp_steady_clock_now() {\n'
                             '  const auto frequency = sceKernelGetProcessTimeCounterFrequency();\n'
                             '  const auto counter = sceKernelGetProcessTimeCounter();\n'
                             '  if (frequency == 0)\n'
                             '    __throw_system_error(EINVAL, "sceKernelGetProcessTimeCounterFrequency returned zero");\n'
                             '  constexpr auto __ns_per_second = 1000000000ULL;\n'
                             '  const auto whole = counter / frequency;\n'
                             '  const auto fraction = counter % frequency;\n'
                             '  const auto ns = whole * __ns_per_second + fraction * __ns_per_second / frequency;\n'
                             '  return steady_clock::time_point(nanoseconds(static_cast<nanoseconds::rep>(ns)));\n'
                             '}\n\n'
                             '#  elif defined(__APPLE__)\n')]),
 'libcxx/src/filesystem/time_utils.h': ('b264875005a9a897e6b547d579959e7c9e808528dc3841efd9ffaaf488a4bf0d',
                                           [('#  include <unistd.h>\n#endif\n',
                                             '#  include <unistd.h>\n'
                                             '#  if defined(PS4)\n'
                                             '#    include <orbis/libkernel.h>\n'
                                             '#  endif\n'
                                             '#endif\n'),
                                            ('using TimeSpec = struct timespec;\n'
                                             'using TimeVal  = struct timeval;\n'
                                             'using StatT    = struct stat;\n',
                                             'using TimeSpec = struct timespec;\n'
                                             'using TimeVal  = struct timeval;\n'
                                             '#  if defined(PS4)\n'
                                             '// PS4 kernel stat layout is not the generic musl/FreeBSD host layout.\n'
                                             'using StatT = OrbisKernelStat;\n'
                                             '#  else\n'
                                             'using StatT = struct stat;\n'
                                             '#  endif\n')]),
 'libcxx/src/filesystem/posix_compat.h': ('98d04aa7bbaad33100e4a44905e6d8dd8233d21055c7e854c78a262230d09ba8',
                                            [('#  include <unistd.h>\n#endif\n#include <stdlib.h>\n',
                                              '#  include <unistd.h>\n'
                                              '#  if defined(PS4)\n'
                                              '#    include <orbis/libkernel.h>\n'
                                              '#  endif\n'
                                              '#endif\n#include <stdlib.h>\n'),
                                             ('using ::fstat;\n'
                                              'using ::ftruncate;\n'
                                              'using ::getcwd;\n'
                                              'using ::link;\n'
                                              'using ::lstat;\n'
                                              'using ::mkdir;\n',
                                              '#  if defined(PS4)\n'
                                              'inline int __orbis_stat_result(int result) {\n'
                                              '  if (result >= 0)\n'
                                              '    return result;\n'
                                              '  errno = static_cast<int>(static_cast<unsigned>(result) & 0xffffu);\n'
                                              '  if (errno == 0)\n'
                                              '    errno = EIO;\n'
                                              '  return -1;\n'
                                              '}\n'
                                              'inline int stat(const char* path, StatT* buf) {\n'
                                              '  return __orbis_stat_result(sceKernelStat(path, buf));\n'
                                              '}\n'
                                              'inline int fstat(int fd, StatT* buf) {\n'
                                              '  return __orbis_stat_result(sceKernelFstat(fd, buf));\n'
                                              '}\n'
                                              '// Public OpenOrbis/shadPS4 does not provide a working lstat import.\n'
                                              '// Preserve target-stat behavior for regular files/directories; symlink\n'
                                              '// metadata remains an explicit unvalidated platform capability.\n'
                                              'inline int lstat(const char* path, StatT* buf) { return stat(path, buf); }\n'
                                              '#  else\n'
                                              'using ::fstat;\n'
                                              'using ::lstat;\n'
                                              'using ::stat;\n'
                                              '#  endif\n'
                                              'using ::ftruncate;\n'
                                              'using ::getcwd;\n'
                                              'using ::link;\n'
                                              'using ::mkdir;\n'),
                                             ('using ::stat;\n'
                                              'using ::statvfs;\n',
                                              '#  if !defined(PS4)\n'
                                              'using ::stat;\n'
                                              '#  endif\n'
                                              'using ::statvfs;\n')]),
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
