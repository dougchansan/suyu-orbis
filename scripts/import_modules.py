#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build a static bundle around trusted, LOCAL Suyu exports; never copy game data.

The pinned exporter already offers static targets but omits three newer symbols
from its per-module renames. Add those to each target without editing the exports.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

NAMES = ['rtld', 'main', *[f'subsdk{i}' for i in range(10)], 'sdk']
PIN = 'e6f53df9f160903fd15ed2b0cd91ac60f1f43428'
RENAMES = ['recomp_build_index', '_recomp_index_view', 'recomp_image_index']


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def cmake_path(path: Path) -> str:
    text = path.resolve().as_posix()
    if any(x in text for x in [';', '\n', '\r', ']=]']):
        raise ValueError(f'Unsupported CMake path characters: {path}')
    return '[=[' + text + ']=]'


def inspect_exports(exefs: Path) -> list[dict]:
    exefs = exefs.resolve(strict=True)
    modules = []
    runtime_hashes = None
    for name in NAMES:
        directory = exefs / name
        if not directory.exists():
            continue
        if not directory.is_dir():
            raise ValueError(f'{directory} is not an exported module directory')
        required = ['CMakeLists.txt', 'recomp_runtime.h', 'recomp_runtime.c',
                    'recomp_export.c', 'data/text.bin']
        for filename in required:
            if not (directory / filename).is_file():
                raise ValueError(f'Missing {directory / filename}; re-export the module')
        sources = sorted((directory / 'src').glob('*.c'))
        if not sources:
            raise ValueError(f'No generated C units in {directory / "src"}')
        cm = (directory / 'CMakeLists.txt').read_text(encoding='utf-8')
        for token in [f'recomp_static_{name}', 'RECOMP_STATIC_ONLY',
                      'recomp_runtime_shared', 'RECOMP_STATIC_HOST']:
            if token not in cm:
                raise ValueError(f'{name}: exporter lacks {token}; use audited revision {PIN}')
        hashes = [digest(directory / 'recomp_runtime.h'), digest(directory / 'recomp_runtime.c')]
        if runtime_hashes is not None and hashes != runtime_hashes:
            raise ValueError(f'{name}: mixed runtime/header versions; re-export ALL modules together')
        runtime_hashes = hashes
        size = (directory / 'data/text.bin').stat().st_size
        if size == 0 or size % 4 or size >= (1 << 64):
            raise ValueError(f'{name}: invalid AArch64 text size {size}')
        coverage = None
        if (directory / 'recomp_coverage.json').exists():
            coverage = json.loads((directory / 'recomp_coverage.json').read_text())
        inputs = [directory / filename for filename in required if filename != 'data/text.bin']
        inputs += sources
        modules.append({'name': name, 'directory': str(directory), 'text_size': size,
                        'text_sha256': digest(directory / 'data/text.bin'),
                        'runtime_sha256': hashes, 'decode_coverage': coverage,
                        'inputs': {str(p.relative_to(directory)): digest(p) for p in inputs}})
    if not modules:
        raise ValueError('No exported modules found; pass the aot_cache/exefs directory')
    if not {'rtld', 'main'}.issubset({m['name'] for m in modules}):
        raise ValueError('Bring-up requires rtld and main exports in NSO load order')
    return modules


def import_modules(exefs: Path, output: Path) -> dict:
    modules = inspect_exports(exefs)
    output = output.resolve()
    # Never overwrite user exports or arbitrary populated directories.
    if output == exefs.resolve() or exefs.resolve() in output.parents:
        raise ValueError('Place the bundle OUTSIDE the original exports')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Bundle output must be empty; choose a new build directory')
    first = Path(modules[0]['directory'])
    cm = ['# Generated locally; paths and manifests may identify private exports.',
          'set(RECOMP_STATIC_ONLY ON)',
          'find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)']
    script = Path(__file__).resolve()
    cm += [f'set(SO_BUNDLE_VERIFIER {cmake_path(script)})',
           'add_custom_target(so_verify_bundle',
           '  COMMAND "${Python3_EXECUTABLE}" "${SO_BUNDLE_VERIFIER}" --verify',
           '          "${CMAKE_CURRENT_SOURCE_DIR}/manifest.json"',
           '  VERBATIM)']
    # These are locally generated CMake files and must be treated as executable
    # build inputs. The user deliberately chooses this trusted export directory.
    for m in modules:
        name = m['name']
        cm += [f'add_subdirectory({cmake_path(Path(m["directory"]))} upstream_{name})',
               f'target_compile_definitions(recomp_static_{name} PRIVATE']
        cm += [f'  {symbol}={symbol}_{name}' for symbol in RENAMES]
        cm += [')', f'add_dependencies(recomp_static_{name} so_verify_bundle)']
    cm += ['add_dependencies(recomp_runtime_shared so_verify_bundle)',
           'add_library(so_module_bundle STATIC module_table.c)',
           f'target_include_directories(so_module_bundle PUBLIC {cmake_path(first)})',
           'target_link_libraries(so_module_bundle PUBLIC suyu_orbis_registry']
    cm += [f'  recomp_static_{m["name"]}' for m in modules]
    cm += ['  recomp_runtime_shared)', 'if(UNIX AND NOT SO_PLATFORM_ORBIS)',
           '  target_link_libraries(so_module_bundle PUBLIC m)', 'endif()']
    table = ['// Generated locally by suyu-orbis. No guest code/data embedded here.',
             '#include "recomp_runtime.h"', '#include "suyu_orbis/abi_contract.h"',
             '#include "suyu_orbis/bundle.h"']
    for m in modules:
        name = m['name']
        table += [f'extern BlockFn recomp_image_lookup_{name}(uint64_t);',
                  f'extern void recomp_image_set_base_{name}(uint64_t);',
                  f'extern uint64_t recomp_image_entry_{name}(void);']
    table += ['static const SoModule modules[] = {']
    for m in modules:
        n = m['name']
        table += [f'  {{"{n}", recomp_image_lookup_{n}, recomp_image_set_base_{n}, recomp_image_entry_{n}}},']
    table += ['};', 'static const uint64_t text_sizes[] = {']
    table += [f'  UINT64_C({m["text_size"]}),' for m in modules]
    table += ['};', 'static SoRegistry registry;',
              'size_t so_bundle_count(void) { return sizeof(modules)/sizeof(modules[0]); }',
              'SoResult so_bundle_init(void) { return so_registry_init(&registry, modules, so_bundle_count()); }',
              'SoResult so_bundle_bind(size_t i, uint64_t base) {',
              '  if (i >= so_bundle_count()) return SO_INVALID_ARGUMENT;',
              '  return so_registry_bind(&registry, i, base, text_sizes[i]);', '}',
              'SoResult so_bundle_seal(void) { return so_registry_seal(&registry); }',
              'SoResult so_bundle_lookup(uint64_t pc, SoBlockFn* out) { return so_registry_lookup(&registry, pc, out); }',
              'SoResult so_bundle_entry(size_t i, uint64_t* out) { return so_registry_entry(&registry, i, out); }',
              '/* Shared generated runtime expects ONE process-wide dispatcher. */',
              'BlockFn recomp_lookup(uint64_t pc) {',
              '  SoBlockFn block = NULL;',
              '  return so_bundle_lookup(pc, &block) == SO_OK ? block : NULL;', '}']
    manifest = {'schema': 1, 'audited_suyu_revision': PIN, 'modules': modules,
                'status': 'build inputs inspected; game coverage and execution NOT validated'}
    # Validate paths before creating any output.
    output.mkdir(parents=True, exist_ok=True)
    (output / 'CMakeLists.txt').write_text('\n'.join(cm) + '\n')
    (output / 'module_table.c').write_text('\n'.join(table) + '\n')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def verify_manifest(path: Path) -> None:
    manifest = json.loads(path.read_text())
    if manifest.get('schema') != 1:
        raise ValueError('Unsupported bundle manifest schema')
    for m in manifest['modules']:
        directory = Path(m['directory'])
        for relative, expected in m['inputs'].items():
            if digest(directory / relative) != expected:
                raise ValueError(f'{m["name"]}/{relative} changed; import into a fresh bundle')
        if digest(directory / 'data/text.bin') != m['text_sha256']:
            raise ValueError(f'{m["name"]}: guest text changed; re-export and re-import')
        recorded = {p for p in m['inputs'] if p.startswith('src/')}
        current = {str(p.relative_to(directory)) for p in (directory/'src').glob('*.c')}
        if recorded != current:
            raise ValueError(f'{m["name"]}: generated source set changed; re-import')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exefs', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            if args.exefs or args.output:
                parser.error('--verify cannot be combined with import arguments')
            verify_manifest(args.verify)
            print('bundle source fingerprints match')
        else:
            if not args.exefs or not args.output:
                parser.error('--exefs and --output are required')
            result = import_modules(args.exefs, args.output)
            print(f'Imported {len(result["modules"])} static modules; no game data copied')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'import error: {exc}\n')

if __name__ == '__main__':
    raise SystemExit(main())
