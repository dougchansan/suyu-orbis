# Local agent handoff: native Suyu title on Orbis

## Mission

Continue the native OpenOrbis port from the now-proven full-core Linux scheduler checkpoint. The next production milestone is **the same real Suyu process/thread/SVC execution path running inside an Orbis executable**, not another synthetic framebuffer demo and not another Linux scheduler proof.

Desired eventual path:

```text
private title modules -> pinned Suyu static exporter -> native x86-64 blocks
  -> Core::ArmRecomp + Core::System
  -> real processes, threads, guest memory, scheduler, SVC dispatcher and services
  -> Suyu Maxwell command/shader processing
  -> validated native PS4 graphics backend
  -> sceVideoOut
```

There must be no guest CPU JIT or interpreter fallback. Runtime/offline shader compilation is a separate subsystem and must not be confused with guest CPU code generation.

## Current proven checkpoint

| Item | Reference |
|---|---|
| Orbis repository | `dougchansan/suyu-orbis` |
| Development branch | `full-core-linux-smoke` |
| Scheduled-process implementation | `4f3f3974eee5ce104ff24c20deac6b721c1cf2e3` |
| Clean full-core CI | run `35271227961` |
| Host/OpenOrbis regression CI | run `35271227969` |
| Upstream Suyu | `dougchansan/suyu-v0.0.4` |
| Audited Suyu revision | `e6f53df9f160903fd15ed2b0cd91ac60f1f43428` |
| Audited emitter blob | `60b552c1e93bb4cafda11955d37238a62c4acde3` |

Read `deps.lock.json`, `docs/PORT_PROGRESS.md`, `docs/NATIVE_ORBIS.md`, `AGENTS.md`, and the relevant workflows before changing contracts.

### Gates already passed

Do not spend time reproving these unless a change touches them:

1. Real Suyu exporter on original synthetic AArch64.
2. Checked native AOT memory/yield/resume and host sanitizers.
3. OpenOrbis cross-build and converted PS4 executable generation.
4. AOT-written framebuffer presentation through native `sceVideoOut` under shadPS4.
5. Full no-JIT Suyu Linux configure/build/link.
6. Historical limited real-HLE `ArmRecomp` smoke.
7. **Real Linux `Core::System` + `KProcess` + `KThread` scheduler execution with normal SVC dispatch and same-CPU AOT resume.**
8. Full-core symbol gate with no `Dynarmic::`, `ArmDynarmic`, or `__jit_debug_register_code` in the tested binaries.

Run 35271227961 executes this exact SVC sequence through normal scheduler/dispatcher behavior:

```text
0x1e GetSystemTick
0x25 GetThreadId
0x24 GetProcessId
0x10 GetCurrentProcessorNumber
0x25 GetThreadId with deliberately invalid handle
0x0b SleepThread
0x1e GetSystemTick
0x0a ExitThread
```

It verifies TLS, process/thread identity, invalid-handle behavior, a real wait/resume transition, same process-owned `ArmRecomp` context, guest memory writes, normal exit and clean kernel shutdown. The fixture is in `experiments/process_smoke/`; `scripts/run_process_smoke.py` rejects incomplete or exaggerated reports.

The block-boundary fix in that fixture is intentional: `process_entry` is an explicit AArch64 branch target before alignment, ensuring the static exporter emits a lookup root at `main+0x100`. Do not remove that branch and then compensate with a fake lookup fallback.

## Immediate task: port the proven full-core fixture to Orbis

This is Gate 3 and the next engineering focus.

Do **not** start with MK8 and do **not** add more private diagnostic SVCs. Use the original scheduled-process fixture as the production-core acceptance test.

### 1. Create an explicit Orbis host profile

Add a clear build/platform definition, for example `SO_PLATFORM_ORBIS` / `PLATFORM_ORBIS`, while preserving upstream Suyu abstractions. Avoid scattering arbitrary platform conditionals when a host adapter can isolate them.

Inventory the exact source/dependency graph needed for:

```text
Core::System
Kernel
KProcess/KThread/scheduler
ArmRecomp
memory/page table
SVC dispatcher
basic required services
```

Exclude desktop-only features when justified: Qt, updater, Discord, Linux GameMode, desktop capture integrations, X11/Wayland UI plumbing, and any unused runtime library that cannot exist on Orbis. Do not remove a dependency merely because its name looks desktop-specific; trace actual target ownership and call sites first.

Use public OpenOrbis only. Never add proprietary Sony SDK material.

### 2. Port host contracts one by one

Validate each subsystem independently before combining it with the kernel fixture.

#### Logging

Provide console and/or `/data` diagnostics sufficient to identify the last stage, guest PC, SVC and thread without a debugger. Do not put private title paths or secrets into public CI logs.

#### Clock/timing

Implement the monotonic host counter/frequency contract required by Suyu using verified public OpenOrbis APIs. Add tests for monotonicity and conversion; do not rely on Linux clock semantics accidentally leaking into the target.

#### Virtual memory

This is critical. Determine the exact Suyu address-space operations used by the process fixture and eventual title path and map them to public OpenOrbis APIs. Test:

- reserve/map/unmap;
- read/write protections;
- alignment and large-range bounds;
- page-table backing;
- aliases if the pinned Suyu path requires them;
- failure behavior and cleanup.

Do not substitute the small native framebuffer diagnostic's checked-memory object for Suyu's real process memory manager.

#### Threads / TLS / synchronization

Port the host primitives needed for CPU worker threads and kernel scheduling. Prove thread create/join, TLS, mutex, condition variable, semaphore/event behavior, and clean shutdown before relying on them inside `Core::System`.

#### Fibers/context switching

Trace the exact pinned Suyu dependency and implementation. If Boost.Context or host assembly cannot build for OpenOrbis, implement the host-specific contract without altering guest scheduling semantics. Add an isolated context-switch test first.

#### Exclusive monitor

Preserve the shared guest exclusive-monitor behavior used by the real core. Do not use the native framebuffer diagnostic's unsupported/fail-closed exclusive callbacks as the production implementation.

#### Filesystem

Centralize Orbis paths and required create/read/write/rename behavior. Development storage may live under a controlled `/data/suyu-orbis/` tree, but do not spread literal paths through core code.

### 3. Build the real core for OpenOrbis

Start with the smallest full-core target that can support `experiments/process_smoke/`. Use the actual upstream `SUYU_NO_JIT=ON` path and the same static module bridge.

Requirements:

```text
SUYU_NO_JIT=ON
SUYU_RECOMP_STRICT=1
no Dynarmic CPU backend
no interpreter fallback
static generated module lookup
real Core::System
real KProcess/KThread
real normal SVC dispatcher
```

Keep the existing native diagnostic and Linux process regression intact.

### 4. Execute the scheduled-process fixture under shadPS4

Acceptance is **not** merely cross-linking an `.oelf`.

The Orbis program must:

1. initialize the ported real Suyu core;
2. create the real application process/thread;
3. map the original generated fixture;
4. execute the same eight SVCs through normal dispatch;
5. observe the requested `SleepThread` waiting/resume transition;
6. execute `ExitThread` normally;
7. write a machine-readable result under `/data`;
8. shut the core down cleanly.

The report must keep these scopes explicit:

```text
orbis_execution: true
scheduler_dispatch: true
normal_svc_dispatch: true
jit_available: false
jit_transitions: 0
game_tested: false
renderer: none
```

Do not mark physical PS4 execution from shadPS4 evidence.

## Parallel workstream: native GPU backend

This can advance while the core host layer is ported, but keep it independently testable.

The production goal is Suyu Maxwell work reaching the PS4 GPU; CPU-written framebuffer patterns do not satisfy this.

Audit the candidate OpenGNM/vulkan-ps4 stack against **the pinned Suyu renderer's actual requirements**. Previously identified areas requiring real validation include `shaderDrawParameters`, `variablePointers`, and `variablePointersStorageBuffer`; recheck current source rather than assuming those are the only gaps.

Progress in this order:

```text
GPU clear/present
native triangle
texture sampling
buffer/descriptor updates
synchronization/resource lifetime
representative SPIR-V
shader emitted by Suyu's actual translator
```

A feature bit must not be advertised without implementing and testing the behavior. If Vulkan adaptation is impractical, document the feature-gap evidence before considering a direct OpenGNM renderer that still reuses Suyu's Maxwell frontend, IR and resource semantics.

## After the real core works on Orbis: private title headless boot

Only then use the user's authorized local title/export inputs. Never download or commit NSP/XCI, keys, firmware, Nintendo assets, commercial generated code, commercial data segments, or private manifests/paths/hashes.

Use the real loader/process path. Validate module order, mappings, data/BSS, relocations, TLS/stack and static lookup coverage. Missing AOT coverage is a hard diagnostic failure and must be fixed in exporter/root discovery; never fall back to Dynarmic.

Advance title boot honestly:

```text
process creation
-> rtld
-> main
-> real SVCs
-> services/IPC
-> NV/GPU initialization
-> GPU command submission
```

Do not fake a service or GPU success solely to reach a later stage.

## Final rendering path

After the headless runtime and GPU backend are separately valid:

```text
private static title
-> real Suyu HLE
-> real Maxwell processing
-> PS4 GPU backend
-> real render target
-> sceVideoOut
```

Keep first render target, first presented title frame, menu, input, audio, race, measured performance and physical-console validation as separate milestones.

## Regression requirements

Retain independent CI/tests for:

- host unit tests;
- actual Suyu emitter execution;
- ASan/UBSan;
- historical limited full-core smoke;
- Linux scheduled-process/SVC regression;
- OpenOrbis cross-build;
- lightweight native Orbis AOT/display diagnostic;
- real-core Orbis scheduled-process test once available;
- GPU backend behavior.

Public CI must remain independent of commercial title data.

## Working rules

- Inspect current branch, status and build directories before modifying a local checkout.
- Do not reset/force-push/discard user work.
- Make cohesive commits on the development branch; do not merge `main` without explicit instruction.
- Use actual source/API signatures from pinned Suyu and public OpenOrbis; do not invent options or APIs.
- Preserve strict missing-block behavior and real service errors.
- Record the first meaningful failure and fix its actual cause rather than weakening the test.
- Keep Linux, shadPS4 and physical-console evidence distinct.
- Update `docs/PORT_PROGRESS.md` after each real milestone.

**Start at the Orbis host adaptation and full-core scheduled-process fixture. Gates 1 and 2 are now solved and have clean CI evidence.**
