#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Extend the pinned Orbis runtime selectors with BSD-aware file removal.

Use this entry point in place of prepare_runtime.py for the current port.
Both syscall failures are propagated. No recursive delete or success stub.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from prepare_runtime import CHANGES, patch

REMOVE_OLD = 'using ::remove;\n'
REMOVE_NEW = '''#  if defined(PS4)
// SDK musl remove() retries only Linux EISDIR. Orbis also uses POSIX EPERM
// for unlink(directory). Invoke real rmdir for either directory-style error;
// leave nonexistent paths, permission failures, and nonempty-directory errors
// to their original syscall results. Never recursively remove children.
inline int remove(const char* path) {
  if (::unlink(path) == 0)
    return 0;
  const int unlink_error = errno;
  if (unlink_error != EISDIR && unlink_error != EPERM)
    return -1;
  return ::rmdir(path);
}
#  else
using ::remove;
#  endif
'''

relative = 'libcxx/src/filesystem/posix_compat.h'
expected, replacements = CHANGES[relative]
CHANGES[relative] = (expected, [*replacements, (REMOVE_OLD, REMOVE_NEW)])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    patch(parser.parse_args().source.resolve(strict=True))
