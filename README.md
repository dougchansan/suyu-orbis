# suyu-orbis

**Native PS4/OpenOrbis bring-up for Suyu's statically recompiled AArch64 code.**

Original AArch64 code now runs through the real Suyu static exporter, compiles to a native Orbis executable, writes every framebuffer pixel, and presents four alternating frames through native `SceVideoOut`. Both a deterministic capture build and an independent standalone build have passed in shadPS4 on Linux.

**This is not yet a working Switch emulator or Mario Kart 8 Deluxe port.** The tested native executor is a small generated-code runtime, not the complete Horizon HLE or Maxwell GPU renderer. No physical PS4 execution has been validated.

## Continue the native title port

**Local agents: start with [the persistent handoff](docs/LOCAL_AGENT_HANDOFF.md) and [the current port-progress ledger](docs/PORT_PROGRESS.md).** [AGENTS.md](AGENTS.md) points to both.

The next task is the real Suyu no-JIT core, not another synthetic display demo. The complete Linux core configuration passed, but [run 34916507480](https://github.com/dougchansan/suyu-orbis/actions/runs/34916507480) failed the combined build. Reproduce and repair that failure, execute the limited full-core smoke, then add normal process/thread SVC dispatch before moving the real core to Orbis. The native success below is independent evidence and does not mark that full-core gate as passed.

## Verified native milestone

[CI run 34916702772](https://github.com/dougchansan/suyu-orbis/actions/runs/34916702772), tested code revision `25874425ad97238853b245667aa33ca7b51e2c2d`:

| Check | Result |
|---|---|
| Actual pinned Suyu exporter -> original AArch64 diagnostic | Pass |
| GCC host tests and Clang ASan/UBSan | Pass |
| Checked guest memory and SVC yield/resume tests | Pass |
| Native Orbis cross-build and converted PS4 executable | Pass |
| Guest-written pixels / completed flips | 3,686,400 stores / four flips |
| Four-frame capture verification | 880 sampled pattern checks |
| Standalone execution without host capture acknowledgments | Pass |
| Full Suyu HLE, Switch GPU, game, physical PS4 | Not validated |

See **[native Orbis build, runtime contracts, and evidence](docs/NATIVE_ORBIS.md)**. The native CI artifacts include original diagnostic source, converted executables, reports, and actual captures. They are not game releases or installable PKGs.

## Implemented

- Static-module registry with ordered relocation, entry/range checks, and strict failure on missing or unaligned PCs.
- Local-export importer using Suyu's static targets and one generated shared runtime, with three missing module-symbol renames repaired and stale/mixed exports rejected.
- Actual generated `GuestContext` / `RecompHostMem` ABI checks.
- Native AOT executor with explicit SVC yield/resume and checked scalar guest-memory callbacks; unsupported exclusive operations fail closed.
- Native Orbis direct-memory and double-buffered `SceVideoOut` backend with completed-flip verification.
- OpenOrbis build/conversion tools, host tests, actual-emitter tests, and reproducible emulator capture workflows.
- A separate, still-experimental bridge to the complete Suyu core. A native diagnostic pass is not a full-core integration pass.

## Build the native diagnostic

Use Linux/WSL with Clang, a C++20 compiler, CMake 3.24+, Ninja, Python 3.10+, and the public OpenOrbis SDK. The SDK release ZIP contains a tarball; extract both layers. Detailed prerequisites are in the native guide and workflow.

```sh
git clone --branch full-core-linux-smoke https://github.com/dougchansan/suyu-orbis.git
cd suyu-orbis
python3 scripts/fetch_upstream.py
python3 scripts/emit_native_fixture.py

cmake -S native -B build/native-host -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DSO_MODULE_BUNDLE="$PWD/build/native-fixture/bundle"
cmake --build build/native-host --parallel 2
ctest --test-dir build/native-host --output-on-failure

export OO_PS4_TOOLCHAIN=/absolute/path/to/OpenOrbis/PS4Toolchain
cmake -S native -B build/native-standalone -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE="$PWD/cmake/toolchains/openorbis.cmake" \
  -DSO_MODULE_BUNDLE="$PWD/build/native-fixture/bundle" \
  -DSO_AOT_CAPTURE_HANDSHAKE=OFF
cmake --build build/native-standalone --target suyu-orbis-aot-render --parallel 2
```

Use `build/native-standalone/suyu-orbis-aot-render.oelf` for direct shadPS4 execution, not the intermediate `.elf`. The companion eboot is a converted SELF, not a PKG. The standalone app needs no host ACK files; the separate capture-controlled CI build intentionally does.

## Original host and exporter diagnostics

The original registry-only and two-module arithmetic tests remain available:

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

The original probe uses authored C functions, not recompiled game code. The separate actual-emitter tests use original AArch64 inputs. All use Suyu revision `e6f53df9f160903fd15ed2b0cd91ac60f1f43428`; the emitter's Git blob is checked. The symbol audit is a guardrail, not proof of every possible execution path, and should not be applied to ASan runtime imports as though they were JIT use.

Original headless Orbis cross-builds are still provided by `scripts/build_orbis.py`; see [earlier validation](docs/VALIDATION.md).

## Local generated module imports

Keep trusted exports generated together outside Git. Input is the directory containing `rtld/`, `main/`, optional `subsdkN/`, and optional `sdk/`.

```sh
python3 scripts/import_modules.py \
  --exefs /private/path/aot_cache/exefs \
  --output build/local-bundle
cmake -S . -B build/local-static -G Ninja \
  -DSO_MODULE_BUNDLE="$PWD/build/local-bundle"
cmake --build build/local-static --target so_module_bundle
```

This builds libraries, **not a standalone game application**. The native display diagnostic expects its specific original test program and private test SVC protocol, not an arbitrary title. Do not substitute those test services for actual Horizon HLE. Generated commercial-game C and manifests containing private paths/hashes must remain private.

## Remaining port work

The complete Suyu runtime still needs Orbis platform integration for virtual memory, process/thread scheduling, exclusives, timing, filesystem, services, audio, input, and saves. The present native backend displays CPU-written images; it does not implement Switch GPU commands or shaders. [OpenGNM](https://github.com/PS4-OpenGNM/opengnm-stack) remains a graphics candidate requiring a feature/behavior audit and independent GPU tests.

Read [native status](docs/NATIVE_ORBIS.md), [source audit](docs/ARCHITECTURE.md), [roadmap](docs/ROADMAP.md), and [agent instructions](AGENTS.md). Earlier documents retain historical baseline evidence; the native guide records the newer verified milestone. [PORT_PROGRESS.md](docs/PORT_PROGRESS.md) and [LOCAL_AGENT_HANDOFF.md](docs/LOCAL_AGENT_HANDOFF.md) identify the next implementation gates and their acceptance tests.

## License and inputs

Project source is GPL-2.0-or-later; see [LICENSE](LICENSE). External components retain their licenses. No Nintendo games, firmware, keys, generated commercial-game source, or proprietary Sony SDK files are included. See [repository policy](LEGAL.md). No game releases are published; native test artifacts contain only original diagnostics and their build/source evidence.
