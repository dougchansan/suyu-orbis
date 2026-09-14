# suyu-orbis

**A PS4/OpenOrbis bring-up project for Suyu's statically recompiled AArch64 code.**

This is an early port foundation, **not a working Switch emulator or Mario Kart 8 Deluxe port**. The default executable is an explicitly labelled, hand-authored static-dispatch diagnostic. A separate integration test runs original synthetic AArch64 instructions through the actual pinned Suyu exporter. Neither test substitutes for the Suyu HLE kernel, GPU, or a console test.

## Implemented

- C11 static-module registry with NSO load-order binding, relocation, entry checks, overflow/overlap checks, immutable post-bind lookup, and no fallback on uncovered or misaligned PCs.
- Local-export importer using Suyu's existing `recomp_static_<module>` targets and one shared generated runtime. It repairs three missing per-module symbol renames, checks runtime/header identity, and fingerprints build inputs to reject stale exports.
- Compile-time checks for the actual generated `GuestContext` and `RecompHostMem` ABI; no guessed context allocations.
- OpenOrbis CMake toolchain, SDK doctor, ELF-to-`eboot.bin` build script, and machine-readable diagnostic reports.
- An opt-in bridge to the real `Core::SetRecompLookup` / `Core::SetRecompBaseSetter` hooks. Full-core integration is not yet built or validated.
- Host tests, sanitizer configuration, no-JIT symbol guardrail, real-emitter synthetic test, and CI cross-build configuration.

## Verified build status

[CI run 34817696559](https://github.com/dougchansan/suyu-orbis/actions/runs/34817696559), code revision `3530e5394fcef18bb4752397ade7be3e8baa16f5`, passed the GCC and Clang host jobs, Clang ASan/UBSan, the actual Suyu-emitter synthetic integration, and OpenOrbis cross-builds of **both diagnostics through nonempty `eboot.bin` output**. ELF/eboot hashes are recorded in [the validation ledger](docs/VALIDATION.md).

**No physical PS4 execution, full Suyu HLE, graphics, or game boot has been validated.** CI produces build evidence, not a playable release, and does not upload the binaries.

## Start on a host

Requirements: a C11 compiler, CMake 3.24+, Ninja, and Python 3.10+. The optional exporter integration needs a C++20 compiler. Linux/WSL is the initial reference build environment.

```sh
git clone https://github.com/dougchansan/suyu-orbis.git
cd suyu-orbis
python3 scripts/doctor.py
cmake --preset host
cmake --build --preset host
ctest --preset host
./build/host/suyu-orbis-probe
```

The probe reports `x0: 42`, `suyu_hle_linked: false`, and `game_tested: false`. Its two functions are authored test fixtures, not recompiled game code.

```sh
CC=clang cmake --preset host-sanitize
cmake --build --preset host-sanitize
ctest --preset host-sanitize
python3 scripts/audit_binary.py build/host/suyu-orbis-probe
```

The audit checks symbols, not arbitrary memory permissions or every possible executable-code path.

## Exercise the actual Suyu recompiler

```sh
python3 scripts/fetch_upstream.py
python3 scripts/test_upstream.py
```

The pinned emitter is `dougchansan/suyu-v0.0.4` at `e6f53df9f160903fd15ed2b0cd91ac60f1f43428`. Its Git blob is verified before use. The test emits two original AArch64 modules, compiles and statically links them, and checks arithmetic, a host-memory store, SVC yield, relocation, and uncovered-address failure. It uses no game assets, firmware, or keys. Existing work directories are not overwritten; choose a new `--work` path to rerun.

## Build the PS4 diagnostic

Install the public [OpenOrbis toolchain](https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain), including its libraries, CRT, linker script, and host conversion tools. A source checkout containing only headers is insufficient. The CI reference is the official v0.5.3 `toolchain-llvm-18.2.zip` release with host LLVM 18 tools. The release ZIP contains a tarball; extract both layers.

```sh
export OO_PS4_TOOLCHAIN=/absolute/path/to/OpenOrbis/PS4Toolchain
python3 scripts/doctor.py --orbis
python3 scripts/build_orbis.py

# After the actual-exporter host test above:
python3 scripts/build_orbis.py --fixture-bundle build/upstream-fixture/bundle
```

Outputs are under `build/orbis/` and `out/orbis/<diagnostic>/`. The script converts an ELF to `eboot.bin`; it does **not** create an installable PKG, install anything, or launch a PS4. A supported homebrew execution environment must already exist. The headless diagnostics do not initialize a display. Successful device runs write `/data/suyu-orbis-probe.json` or `/data/suyu-orbis-upstream-smoke.json`; writing that report is part of the device test.

An ELF or eboot build is **not** proof of a console boot. See [validation](docs/VALIDATION.md).

## Bring local generated modules into the build

Use trusted exports generated together by the audited exporter, kept outside Git. Input is the directory containing `rtld/`, `main/`, optional `subsdkN/`, and optional `sdk/`.

```sh
python3 scripts/import_modules.py \
  --exefs /private/path/aot_cache/exefs \
  --output build/local-bundle
cmake -S . -B build/local-static -G Ninja \
  -DSO_MODULE_BUNDLE="$PWD/build/local-bundle"
cmake --build build/local-static --target so_module_bundle
```

This builds static libraries, **not a standalone game application**. The importer never copies guest segments into this repository. Generated C still embodies the input program; keep commercial-game exports and their bundles private. Do not publish local manifests: they include private paths and content fingerprints.

## What remains

The full Suyu C++ runtime and dependencies still need an Orbis port: virtual memory, threading/fibers, timing, files, saves, audio, input, and HLE integration. Graphics needs an independently validated backend. [OpenGNM](https://github.com/PS4-OpenGNM/opengnm-stack) is a candidate, not a linked or proven Suyu dependency. Its advertised Vulkan support must be checked against Suyu's actual feature/extension requirements.

See [architecture and source audit](docs/ARCHITECTURE.md), [bring-up milestones](docs/ROADMAP.md), and [agent instructions](AGENTS.md).

## License and inputs

Project source is GPL-2.0-or-later; see [LICENSE](LICENSE). External components retain their licenses. No Nintendo games, firmware, keys, generated commercial game code, or proprietary Sony SDK files are included. See [repository policy](LEGAL.md). CI does not publish releases or upload binaries.
