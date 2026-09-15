# Local agent handoff: native Suyu title on Orbis

## Mission

Continue this repository toward a native OpenOrbis application that executes the user's privately supplied static-recompiled Switch title through the real Suyu Horizon/HLE environment and eventually renders its actual GPU workload on PS4.

The native AOT framebuffer diagnostic is already a working regression baseline. Do not spend this phase creating a larger private syscall protocol or another unrelated framebuffer demo. The next missing layer is the real Suyu core and its platform dependencies, followed by the native GPU integration.

Desired production path:

```text
private title modules -> pinned Suyu static exporter -> native x86-64 blocks
  -> Core::ArmRecomp + Core::System
  -> real processes, threads, guest memory, scheduler, SVC dispatcher and services
  -> Suyu Maxwell command/shader processing
  -> validated native PS4 graphics backend
  -> sceVideoOut
```

There must be no guest CPU JIT or interpreter fallback. A renderer compiling shaders is a different subsystem; do not confuse offline/runtime shader compilation with guest CPU code generation.

## Sources, branch, and evidence

| Item | Reference |
|---|---|
| Orbis repository | `dougchansan/suyu-orbis` |
| Starting development branch | `full-core-linux-smoke` |
| Last verified native implementation | `25874425ad97238853b245667aa33ca7b51e2c2d` |
| Native documentation follow-up | `d985afaee87ad5ef65a4477d7ec90c44352a691e` |
| Upstream Suyu | `dougchansan/suyu-v0.0.4` |
| Audited upstream revision | `e6f53df9f160903fd15ed2b0cd91ac60f1f43428` |
| Emitter | `src/core/recompiler/arm64_to_c.h` |
| Audited emitter Git blob | `60b552c1e93bb4cafda11955d37238a62c4acde3` |

Use `deps.lock.json` as the machine-readable dependency authority. Do not silently update the exporter, generated runtime, ABI contract, or upstream core revision independently. A deliberate upgrade requires a reviewed compatibility change and rerunning the complete generated-code tests.

Read, in order:

1. `AGENTS.md`, `docs/PORT_PROGRESS.md`, and this handoff.
2. `docs/NATIVE_ORBIS.md` for the actual native implementation and proof boundaries.
3. `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, and `docs/VALIDATION.md` for the source audit and historical evidence.
4. `.github/workflows/full-core-linux-smoke.yml`, `experiments/full_core_smoke/`, `integrations/`, and `native/` before changing their contracts.

Native evidence: [run 34916702772](https://github.com/dougchansan/suyu-orbis/actions/runs/34916702772). Full-core failure to reproduce: [run 34916507480](https://github.com/dougchansan/suyu-orbis/actions/runs/34916507480), [job 104215234742](https://github.com/dougchansan/suyu-orbis/actions/runs/34916507480/job/104215234742). These are separate tests; never use one to mark the other successful.

## Working rules

Inspect the local repository, `git status`, branches, remotes, current HEAD, installed tools, and existing build directories before making changes. Reuse an existing user worktree only when safe. Do not reset it, discard uncommitted work, force-push, or switch a dirty tree unexpectedly. Start a branch such as `native-title-orbis` from the current reviewed experimental branch; preserve newer work rather than resetting to the known-good hash.

Record the exact source and toolchain versions. Use a separate upstream checkout/worktree for the port patches. Keep any patch injection reproducible and idempotent; do not repeatedly append an integration include to a user's normal Suyu checkout.

Work through the acceptance gates below. When a command fails, retain its output, identify the first meaningful error, fix the smallest correct cause, add a regression test where possible, and rerun affected tests. Do not stop solely because the initial command failed, and do not report a stage as passing before its acceptance test executes.

## Gate 0: reproduce the existing regression baseline

Use the exact commands and prerequisites in `docs/NATIVE_ORBIS.md` and the native workflow. Start with the original host tests, actual-emitter native tests, Clang ASan/UBSan tests, OpenOrbis cross-build, and standalone `.oelf` execution in shadPS4.

For a new clone and empty build directories, the native host path is:

```sh
python3 scripts/doctor.py
python3 scripts/fetch_upstream.py
python3 scripts/emit_native_fixture.py
cmake -S native -B build/native-host -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DSO_MODULE_BUNDLE="$PWD/build/native-fixture/bundle"
cmake --build build/native-host --parallel 2
ctest --test-dir build/native-host --output-on-failure
python3 scripts/audit_binary.py build/native-host/aot-runtime-tests

CC=clang CXX=clang++ cmake -S native -B build/native-sanitize -G Ninja \
  -DCMAKE_BUILD_TYPE=Debug -DSO_SANITIZE=ON \
  -DSO_MODULE_BUNDLE="$PWD/build/native-fixture/bundle"
cmake --build build/native-sanitize --parallel 2
ctest --test-dir build/native-sanitize --output-on-failure
```

The fetch/import/emission helpers deliberately reject existing or populated destinations. Inspect their `--help` and verify/reuse existing inputs or choose fresh supported output paths. Do not remove user data just to make the commands above work.

Audit the Release binary, not ASan's dynamic-loader imports. Symbol absence is a guardrail, not complete proof of all memory permissions or execution paths.

Acceptance: reproduce the existing native guide's checked-memory/generated-code tests and standalone Orbis capture, recording fresh evidence. Keep this diagnostic unchanged as a regression test unless a real bug requires a fix.

## Gate 1: repair the real Suyu no-JIT Linux build

This is the immediate blocker, not another display pattern.

Reproduce `.github/workflows/full-core-linux-smoke.yml` using its pinned upstream source, dependencies, and integration target. Run 34916507480 configured successfully but failed its combined build; runtime checks were not established. Inspect the full job log and the local verbose compiler/linker invocation. Do not assume that an unresolved symbol mentioned in a chat is the current root cause.

The earlier unrelated Oaknut example failure involving `<print>` was addressed by explicitly disabling `BUILD_TESTING` and `DYNARMIC_TESTS`. Do not remove valid runtime tests to obtain a passing build.

Required settings include the actual upstream `SUYU_NO_JIT=ON` option, `BUILD_TESTING=OFF`, and `DYNARMIC_TESTS=OFF`. Preserve the working timezone/dependency configuration in the workflow. Inspect actual upstream CMake options instead of inventing generic flags such as `GUI=OFF`.

Build targets and execution path already present:

```sh
cmake --build build/full-suyu \
  --target core suyu_orbis_bridge so_module_bundle suyu_orbis_full_core_smoke \
  --parallel 2

python3 scripts/audit_binary.py build/full-suyu/bin/suyu_orbis_full_core_smoke
SUYU_RECOMP_STRICT=1 build/full-suyu/bin/suyu_orbis_full_core_smoke
```

The workflow supplies the prerequisite fixture generation and CMake configuration; the commands above are not a substitute for those steps.

Resolve missing definitions by linking their real implementation, fixing target ownership/dependency propagation, or making a justified exclusion of a genuinely unused component. Do not provide dummy constructors, empty services, ignored link errors, or `--allow-multiple-definition`.

Acceptance: the real core, bridge, static modules, and smoke executable link; the existing limited smoke executes; its actual results and Release symbol audit pass. Update CI and record which behavior was tested.

## Gate 2: prove normal process/thread SVC dispatch on Linux

The existing full-core fixture's direct call to the real `GetSystemTick` implementation is not normal Horizon scheduler/SVC-dispatch coverage. Retain that limited test, then add a separate test with a real process, current thread, mapped guest memory, TLS/stack, real AOT execution, and the normal SVC dispatcher.

Target path:

```text
generated AOT block -> ArmRecomp -> normal SVC dispatch
  -> real Horizon implementation -> guest result/context -> resumed AOT block
```

Use a small original program and a supported real SVC, such as `0x1e GetSystemTick`, after checking the pinned implementation's preconditions. Test valid return-state behavior, an appropriate monotonic/timebase invariant, and resume PC; do not demand a constant tick value or a positive delta without allowing for timer resolution. Do not bypass the current-thread or process requirements to make the test pass.

Include negative tests for uncovered PCs, incorrect module binding, and invalid memory. Do not report `scheduler_dispatch:true` until the scheduler/dispatcher path is actually exercised.

Acceptance: `Core::System`, process/thread state, the real dispatcher, and AOT resume work together without a CPU fallback, with logs and a CI regression test distinct from the direct-call fixture.

## Gate 3: explicit Orbis host adaptation

Introduce a clear Orbis platform/build profile while preserving the real Suyu abstractions. Inventory which dependencies and source units are actually required. Exclude desktop UI/updater/Discord/X11/Wayland/GameMode/desktop capture integrations where appropriate; do not assume disabling a window eliminates the video core or other transitive dependencies.

Confirm all native API signatures against the installed public OpenOrbis headers. Avoid guessed function names or assuming Linux/FreeBSD ABI compatibility. Keep target sysroots and dependency discovery isolated so desktop libc, libstdc++, or shared libraries cannot leak into the Orbis executable.

| Subsystem | Required isolated proof |
|---|---|
| Logging | Startup/fault reports usable without a window or debugger; no private data in public logs |
| Clocks | Consistent counter frequency, monotonic behavior, and correct guest time conversion |
| Virtual memory | Alignment, reservations, mappings, protections, unmap, required aliases, large-range bounds, and guest-address translation |
| Threads/TLS | Create/join, mutex/condition/semaphore semantics, per-thread state, and shutdown |
| Fibers | Preserve Suyu's context-switch contract; validate required register/stack state before using it in scheduling |
| Exclusives | Shared guest exclusive-monitor semantics across cores/threads, not the diagnostic's unsupported callbacks |
| Filesystem | Centralized development paths, meaningful errors, and required create/read/write/rename behavior |

The native diagnostic's checked memory is a single-owner test address space, not a production Horizon memory manager. Reuse the real Suyu memory and exclusive-monitor design rather than quietly treating those implementations as equivalent.

Use the repository's reviewed target ISA configuration, currently `-march=btver2`, and inspect compiler output for unsupported instructions. Do not inherit `-march=native` or make blanket ISA claims without checking the target. Evaluate C++ library coverage and fiber/assembly dependencies explicitly.

Acceptance: platform tests run as Orbis executables and then the real process/SVC fixture from Gate 2 runs through the ported core under shadPS4. A lightweight native diagnostic pass does not satisfy this gate.

## Gate 4: real private title boot, initially headless

Locate the user's authorized local game/export inputs from the local workspace or explicit configuration. Do not download title data or assume a repository contains it. Preserve existing known-working desktop exports and their source revision. Keep commercial generated code, segments, firmware, keys, title-private manifests, and private paths/hashes outside public Git and CI.

Use the actual NSO/process loader and static-image bridge. Check module order, segment mappings, data/BSS, relocation, entry/TLS/stack state, and module-version identity. Link generated modules statically with one matching generated runtime; do not substitute dynamic CPU-code loading or a missing-code interpreter.

Headless acceptance is staged: process creation, module binding, entry into rtld, main execution, real kernel/services/IPC, then NV/GPU initialization. Do not fake GPU/service success solely to advance boot. A null backend is acceptable only when its intentional limitations are reported and the test does not require the behavior it omits.

For the first failure, record module-relative PC, thread, registers, SVC/service/IPC command, and the exact failing assertion. A missing AOT block must fail and be fixed at exporter/root-discovery/coverage level before regenerating and rebuilding. Never silently fall back to Dynarmic.

## Gate 5: prove the native GPU backend independently

This workstream can proceed alongside runtime porting. OpenGNM/vulkan-ps4 is a candidate, not a proven Suyu-compatible driver. Pin the examined source revisions and compare Suyu's actual mandatory features and fallback paths with implemented behavior, not a advertised Vulkan version.

Pay particular attention to the previously identified `shaderDrawParameters`, `variablePointers`, and `variablePointersStorageBuffer` requirements, then audit formats, memory binding, descriptors, synchronization, shader capabilities, resource updates, presentation, and all additional requirements in the pinned Suyu device code. Recheck their current implementation before classifying a gap.

Classify each requirement as implemented and tested, correct fallback available, implementation needed, or unresolved. Never set a feature bit to true without the necessary behavior and tests.

Progress through GPU clear/present, triangle, texture sampling, buffer/descriptor updates, synchronization/resource lifetime, and a representative shader emitted by Suyu's actual shader translator. These must execute GPU work, not substitute CPU-written images. Compare outputs against a host reference where useful.

If a Vulkan adaptation becomes less tractable than a direct OpenGNM backend, document the evidence and tradeoffs before changing direction. Preserve Suyu's Maxwell frontend, shader IR, and resource semantics where possible. A successful standalone triangle does not establish whole-game compatibility.

## Gate 6: connect the title and renderer

Connect real title execution to the validated graphics backend. Track the highest demonstrated stage separately:

```text
process entry -> rtld/main -> real HLE/services -> NV/GPU submission
 -> shader translation -> actual render target -> sceVideoOut
 -> title/menu frame -> input -> audio -> race -> measured playability
```

A game screenshot supplied by a host, a pre-recorded replay, a native pattern, and an actual live game frame are different evidence. Label each honestly. Add native pad and audio host backends without changing game logic or replacing Suyu's emulated HID/audio stack. Test saves and process shutdown separately.

Keep first frame, gameplay correctness, frame pacing/performance, and physical-console validation as separate milestones. Profile only after correctness; do not promise frame rates from the synthetic diagnostic.

## Orbis deployment and emulator contracts

Use public OpenOrbis tools. The linked `.elf` is an intermediate; launch the converted `.oelf` in shadPS4. A converted `eboot.bin` SELF is not an installable PKG and does not prove physical-console execution.

Preserve `.github/workflows/native-orbis-aot.yml` and the original native checks. Fresh shadPS4 profiles need their empty home directories prepared to avoid the first-run migration dialog. Capture-enabled and standalone builds have intentionally different acknowledgment behavior; use the corresponding script from `scripts/ci/`.

Any low-address Linux mapping exception belongs only in an isolated disposable test VM, with the original setting restored and the emulator unprivileged. Do not weaken an everyday host's policy blindly. Hardware testing assumes an already authorized homebrew development environment; adding exploitation or asset-acquisition tooling is outside this task.

## Completion and reporting rules

Keep public CI independent of commercial title data. Retain separate tests for host units, actual-emitter execution, sanitizers, limited full-core smoke, normal process/SVC dispatch, Orbis platform/core tests, native presentation, and GPU behavior. Review logs/artifacts for private inputs before pushing.

Make cohesive commits on the development branch, run the relevant regression suite, and update `docs/PORT_PROGRESS.md` with evidence. Do not merge into `main`, change visibility, force-push, or publish game binaries without explicit authorization.

For each meaningful milestone report: what changed; what actually executed; exact source/toolchain revisions; test commands; log/artifact/screenshot; and the first remaining blocker. If a test could not run, say why instead of borrowing a success from another platform or fixture.

Start with the failed full-core build after reproducing the known-good baseline. Continue through the next reasonable gate when one passes. Preserve this handoff in the repository so progress does not depend on chat history.
