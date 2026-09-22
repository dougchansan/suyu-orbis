#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check the exact original kernel translation units, not a replacement HLE."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

UPSTREAM = 'e6f53df9f160903fd15ed2b0cd91ac60f1f43428'
EXPECTED_COUNT = 98
EXPECTED_DIGEST = '2f6d1925e95319d8882fa1c4a37d3cd8e9710e1fe8692e09695db97386ebc5b0'
CORE = ('core/arm/arm_interface.cpp', 'core/arm/recomp/arm_recomp.cpp',
        'core/arm/exclusive_monitor.cpp', 'core/arm/standalone_exclusive_monitor.cpp',
        'core/core_timing.cpp', 'core/cpu_manager.cpp', 'core/device_memory.cpp')

def fingerprint(root: Path, names: list[str]) -> tuple[str, dict[str, str]]:
    digest = hashlib.sha256()
    files = {}
    for name in sorted(names):
        path = root / name
        data = path.read_bytes()
        digest.update(name.encode() + b'\0' + len(data).to_bytes(8, 'little') + data)
        files[name] = hashlib.sha256(data).hexdigest()
    return digest.hexdigest(), files

def verify(source: Path, output: Path) -> None:
    root = source / 'src'
    names = list(CORE) + [str(p.relative_to(root)) for p in (root / 'core/hle/kernel').rglob('*.cpp')]
    digest, files = fingerprint(root, names)
    if len(names) != EXPECTED_COUNT or digest != EXPECTED_DIGEST:
        raise ValueError(f'Unreviewed kernel source set: {len(names)} units, digest {digest}')
    sources = []
    for name in sorted(files):
        text = (root / name).resolve().as_posix()
        if any(c in text for c in (';', '\n', '\r', ']=]')):
            raise ValueError('Unsupported source path')
        sources.append('[=[' + text + ']=]')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('set(SO_AUDITED_KERNEL_SOURCES\n  ' + '\n  '.join(sources) + '\n)\n')
    output.with_suffix('.json').write_text(json.dumps({
        'upstream_commit': UPSTREAM, 'translation_unit_count': len(files),
        'translation_unit_digest': digest, 'sources': files,
        'scope': 'translation-unit identity; dependency headers are supplied by pinned CI checkouts'
    }, indent=2) + '\n')
    print(f'Checked {len(files)} real upstream sources; compile-only, no runtime claim.')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    try:
        verify(a.source.resolve(strict=True), a.output.resolve())
    except (OSError, ValueError) as error:
        p.exit(1, f'{error}\n')
