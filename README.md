# suyu-orbis

**Native PS4/OpenOrbis bring-up for Suyu's statically recompiled AArch64 code.**

Original AArch64 code runs through the real Suyu static exporter, compiles to a native Orbis executable, writes every framebuffer pixel, and presents four alternating frames through native SceVideoOut. Both a deterministic capture build and an independent standalone build have passed in shadPS4 on Linux.

**This is not yet a working Switch emulator or Mario Kart 8 Deluxe port.** The complete Horizon/HLE application and Maxwell GPU renderer have not run on Orbis. No physical PS4 execution has been validated.

## Current native port checkpoint

The real no-JIT Linux process/thread scheduler test passes. The modern Orbis C++ runtime and actual Suyu Common memory, clock, thread and fiber tests also pass in shadPS4. An additional 98-unit original CPU/kernel source gate cross-compiles for Orbis with Clang 18.1.3. **That object compilation is not full-core execution.**

See [the native runtime results](docs/ORBIS_RUNTIME.md), [current port ledger](docs/PORT_PROGRESS.md), and [persistent handoff](docs/LOCAL_AGENT_HANDOFF.md). The next task is complete Orbis core linkage and the same normal SVC/scheduler fixture there, not another synthetic display pattern. [AGENTS.md](AGENTS.md) identifies the continuation rules.

## Verified milestones

| Milestone | Result / reference |
|---|---|
| Real scheduled AOT process, eight Horizon SVCs, sleep/resume and clean exit | Linux; [run 35271227961](https://github.com/dougchansan/suyu-orbis/actions/runs/35271227961) |
| Modern C++20 and actual Common native execution | Orbis in shadPS4; [run 35686596568](https://github.com/dougchansan/suyu-orbis/actions/runs/35686596568) |
| Repeat native execution plus original 98-unit kernel compilation | [run 35687819373](https://github.com/dougchansan/suyu-orbis/actions/runs/35687819373); compile-only kernel gate |
| Native AOT-written framebuffer and autonomous standalone display | [run 34916702772](https://github.com/dougchansan/suyu-orbis/actions/runs/34916702772) |
| Full Orbis Horizon core, actual Switch GPU/game, physical PS4 | Not validated |

The native display baseline checks 3,686,400 guest pixel stores, four completed flips, and 880 sampled pattern checks in the capture-controlled build. The independent standalone completes without host acknowledgment files. See [native display contracts and evidence](docs/NATIVE_ORBIS.md). These artifacts are original diagnostics, not game releases or installable PKGs.

## Implemented

- Static-module registry with ordered relocation, entry/range checks, and strict failure on missing or unaligned PCs.
- Local-export importer using Suyu's static targets and one matching generated runtime, repaired per-module symbols, and stale/mixed-input rejection.
- Actual generated GuestContext/RecompHostMem ABI checks, native AOT executor, and checked scalar memory callbacks.
- Native direct-memory and double-buffered VideoOut presentation with completed-flip verification.
- Real Suyu Linux process/thread/SVC regression, isolated modern Orbis C++ libraries, actual Common component adaptations and tests.
- Original CPU/kernel object coverage, source/target checks and an unresolved-dependency inventory for the remaining native link.

## Build the native display diagnostic

Use Linux/WSL, CMake 3.24+, Ninja, Python 3.10+ and the public OpenOrbis SDK. The SDK ZIP contains a tarball; extract both layers. The modern-runtime workflow separately requires Clang 18 or later and matching LLVM runtime libraries.

```sh
git clone --branch full-core-linux-smoke https://github.com/dougchansan/suyu-orbis.git
cd suyu-orbis
python3 scripts/fetch_upstream.py
python3 scripts/emit_native_fixture.py

cmake -S native -B build/native-host -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DSO_MODULE_BUNDLE="$PWD/build/native-fixture/bundle"
cmake --build build/native-host --parallel 2
ctest --test-dir build/native-host --output-on-failure
```

See [NATIVE_ORBIS.md](docs/NATIVE_ORBIS.md) for the cross-build and emulator commands. Launch the converted `.oelf`, not the intermediate `.elf`. The companion eboot is a SELF, not a PKG. Standalone and capture-controlled builds have different acknowledgment contracts.

## Original host and exporter diagnostics

```sh
python3 scripts/doctor.py
cmake --preset host
cmake --build --preset host
ctest --preset host
./build/host/suyu-orbis-probe

CC=clang cmake --preset host-sanitize
cmake --build --preset host-sanitize
ctest --preset host-sanitize
python3 scripts/audit_binary.py build/host/suyu-orbis-probe

# After fetching the pinned upstream once:
python3 scripts/test_upstream.py
```

The original registry probe uses authored C functions, not generated game code. Actual-emitter tests use original AArch64 inputs. The audited Suyu revision is `e6f53df9f160903fd15ed2b0cd91ac60f1f43428`. Symbol audits are guardrails; do not treat ASan/desktop loader imports as automatic CPU-JIT use.

## Local generated module imports

Keep trusted exports generated together outside Git. Input contains rtld/, main/, optional subsdkN/ and sdk/.

```sh
python3 scripts/import_modules.py \
  --exefs /private/path/aot_cache/exefs --output build/local-bundle
cmake -S . -B build/local-static -G Ninja \
  -DSO_MODULE_BUNDLE="$PWD/build/local-bundle"
cmake --build build/local-static --target so_module_bundle
```

This builds libraries, not a standalone game. The display diagnostic expects its specific original test program/private SVC protocol, not arbitrary title modules. Do not substitute diagnostic services for Horizon HLE. Commercial generated C and private manifests stay outside public Git and CI.

## Remaining work and inputs

The complete real core still needs native Orbis linkage and scheduled-process validation. Guest virtual-memory/protection semantics, remaining services/dependencies, GPU translation, audio/input, saves and physical-console behavior need their own tests. OpenGNM remains a graphics candidate, not a proven Suyu-compatible backend.

Project source is GPL-2.0-or-later; external components retain their licenses. See [LICENSE](LICENSE) and [repository policy](LEGAL.md). No games, firmware, keys, commercial generated code or proprietary Sony SDK files are included. No game releases are published.
