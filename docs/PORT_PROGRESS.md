# Port progress: native Suyu title on Orbis

This is an evidence ledger, not a completion percentage. Real scheduled Suyu AOT execution passes on Linux. The modern Orbis C++ runtime and actual Common components now execute successfully in shadPS4, and the original CPU/kernel source slice cross-compiles for Orbis. The full Suyu core is **not yet linked and executing on Orbis**, and no title/GPU/hardware result is claimed.

## Current checkpoints

| Checkpoint | Code revision | Verified run |
|---|---|---|
| Linux scheduled process/SVC implementation | `4f3f3974eee5ce104ff24c20deac6b721c1cf2e3` | [35271227961](https://github.com/dougchansan/suyu-orbis/actions/runs/35271227961) |
| Native AOT framebuffer implementation | `25874425ad97238853b245667aa33ca7b51e2c2d` | [34916702772](https://github.com/dougchansan/suyu-orbis/actions/runs/34916702772) |
| Native C++20 and real Common execution | `cf5eaf1f9f516a31b5324a61e0e638b701da85a7` | [35686596568](https://github.com/dougchansan/suyu-orbis/actions/runs/35686596568) |
| Native tests repeated plus kernel compilation | `e3aaaa7d740a73452f064aefb49b079f358aa841` | [35687819373](https://github.com/dougchansan/suyu-orbis/actions/runs/35687819373) |

Development branch: `full-core-linux-smoke`. Pinned Suyu source remains `e6f53df9f160903fd15ed2b0cd91ac60f1f43428`. Read `deps.lock.json` before changing the exporter, generated runtime, ABI contract or upstream revision.

| Gate | Result | Boundary |
|---|---|---|
| Actual Suyu exporter and original AArch64 native execution | Pass | Existing original fixtures; not commercial title coverage |
| Checked memory, AOT yield/resume, host ASan/UBSan | Pass | Existing host/native regression scopes |
| OpenOrbis link/conversion and AOT-written VideoOut frames | Pass in shadPS4 | CPU framebuffer stores, not Maxwell/GPU rendering |
| Complete no-JIT Suyu Linux build and limited direct-HLE smoke | Pass | Run 35271227961 |
| Real Linux process/thread scheduler, normal SVC dispatch and same-CPU resume | Pass on Linux | Eight real SVCs, observed sleep/wake, clean ExitThread/shutdown |
| Dynamic CPU/JIT backend symbol guardrail | Pass for tested binaries/objects | Symbol inspection is not proof of every execution path |
| Modern Orbis C++ runtime | Pass in shadPS4 | 44 behavior checks; correct pinned libc++ identity |
| Real Suyu Common host components on Orbis | Pass in shadPS4 | 1,186,039 checks; 4,096 fiber round-trips and 32 migrations |
| Original Orbis CPU/kernel object compilation | Pass, compile-only | Clang 18.1.3, 98 units; no complete core executable |
| Full Suyu Core::System/services/process fixture on Orbis | Not validated | Common subset and object slice are insufficient |
| Native Maxwell/GPU shader rendering | Not validated | Independent driver/shader/backend work remains |
| Private title entry, rendering or playability | Not validated | No commercial inputs used by public CI |
| Physical PS4 execution | Not validated | Emulator evidence only |

## Linux scheduled-process evidence

The original AArch64 fixture executes through real Core::System, KProcess, KThread, process memory, TLS/stack, the normal SVC dispatcher and the same process-owned ArmRecomp. No manual HLE call replaces normal dispatch. The validated sequence is:

```text
0x1e GetSystemTick
0x25 GetThreadId
0x24 GetProcessId
0x10 GetCurrentProcessorNumber
0x25 GetThreadId (deliberately invalid handle)
0x0b SleepThread
0x1e GetSystemTick
0x0a ExitThread
```

Run 35271227961 observed the Waiting state and a 20,169,151 ns sleep/resume interval, clean guest exit/kernel shutdown, `jit_available:false`, `jit_transitions:0`, and ten static blocks. The interval is correctness evidence, not a performance benchmark.

The first attempt debug-suspended at main+0x100 because alignment alone did not create a generated block root. An explicit branch to process_entry in the original fixture made that entry a real control-flow target. The repair was at the fixture/exporter-root level, not a fallback or scheduler hack.

## 2026-09-22 UTC: native host gate completed

See [ORBIS_RUNTIME.md](ORBIS_RUNTIME.md) for exact hashes, runtime versions, fixes and limits. The clean native tests use Clang 18, isolated LLVM 20.1.8 libraries, public OpenOrbis v0.5.3 and unmodified shadPS4 v0.18.0. The installed SDK is unchanged.

The directory-removal adapter now calls actual rmdir when Orbis unlink returns EPERM/EISDIR, propagating other errors. The validator now checks the actual pinned `_LIBCPP_VERSION=200100`, rather than inferring 200108 from the LLVM release tag. All behavioral tests remained enabled.

Both native runtime/Common applications passed again in run 35687819373. The 98-unit CPU/kernel object gate also passed using supported Clang 18.1.3. Its remaining-undefined inventory retains normal runtime imports and unlinked real Suyu dependencies; no stubs satisfy them. The first broader CPU-memory compilation attempt reaches a Host1x/NVDEC include dependency on FFmpeg headers.

## Next accepted work

1. Link the complete real core on Orbis, reusing the validated runtime/Common components. Satisfy Core::System, CPU memory, service, native dependency and lifecycle requirements; do not replace them with successful stubs.
2. Run the same eight-SVC scheduled-process fixture inside an Orbis executable in shadPS4. Preserve the Linux reference and keep kernel-only original fixtures independent of game files.
3. Independently validate a native GPU backend with actual GPU commands/shaders, then representative Suyu shader output. CPU-written patterns do not satisfy this gate.
4. Use authorized private title inputs only after the native core is stable, then connect actual title graphics work. Distinguish first game frame, gameplay, frame pacing and physical hardware.

Read [LOCAL_AGENT_HANDOFF.md](LOCAL_AGENT_HANDOFF.md) for the broader implementation sequence, [NATIVE_ORBIS.md](NATIVE_ORBIS.md) for the AOT display regression, and the current runtime guide before repeating a historical failure. A compile-only pass, emulator result, native syscall test and full scheduled Horizon execution are separate claims.
