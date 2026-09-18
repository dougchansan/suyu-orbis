#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Prepare an isolated C-header overlay for the pinned modern libc++ build.

The SDK's legacy C++ math overloads conflict with libc++ 20. Select the SDK's
existing C math macros, as modern musl does; libc++ supplies its own C++
overloads. Keep the installed SDK byte-for-byte unchanged.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path

MATH_SHA256 = '58287f18ea3a475e376a1b43326a3fefb38677c9082c616c541e3c836dfa1879'
OLD = '#ifdef __cplusplus\n\n#define _fpclassify(x)'
NEW = ('// Orbis libc++20 overlay: use existing C macros below; libc++ owns C++ overloads.\n'
       '#if 0\n\n#define _fpclassify(x)')

def prepare(sdk: Path, output: Path) -> Path:
    data = (sdk/'include/math.h').read_bytes()
    if hashlib.sha256(data).hexdigest() != MATH_SHA256:
        raise ValueError('Unreviewed OpenOrbis math.h; expected the pinned v0.5.3 SDK')
    text = data.decode('utf-8')
    if text.count(OLD) != 1:
        raise ValueError('Ambiguous SDK math compatibility boundary')
    output.mkdir(parents=True, exist_ok=True)
    result = output/'math.h'
    replacement = text.replace(OLD, NEW).encode('utf-8')
    if result.exists() and result.read_bytes() != replacement:
        raise ValueError('Refusing to replace an unrelated header overlay')
    result.write_bytes(replacement)
    print(f'Isolated C-header overlay: {result}')
    return result

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sdk', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    prepare(a.sdk.resolve(strict=True), a.output.resolve())
