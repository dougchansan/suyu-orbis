# Port progress: native Suyu title on Orbis

This is an evidence ledger, not a completion percentage. The project has now proved Suyu-generated AArch64 executing through a real Suyu process/thread scheduler and normal Horizon SVC dispatch on Linux with the CPU JIT disabled. It has **not** yet proved the full Suyu core on Orbis, a native Maxwell/GPU backend, a commercial title boot, or physical-PS4 execution.

## Current checkpoint

Development branch: `full-core-linux-smoke`  
Scheduled-process implementation: `4f3f3974eee5ce104ff24c20deac6b721c1cf2e3`  
Pinned Suyu: `e6f53df9f160903fd15ed2b0cd91ac60f1f43428`  
Clean full-core CI: [run 35271227961](https://github.com/dougchansan/suyu-orbis/actions/runs/35271227961)  
Host/OpenOrbis regression CI: [run 35271227969](https://github.com/dougchansan/suyu-orbis/actions/runs/35271227969)

Read `deps.lock.json` before changing the exporter, generated runtime, ABI contract, or pinned Suyu revision.

| Gate | Result | Evidence / boundary |
|---|---|---|
| Actual Suyu exporter, original AArch64, native host execution | **Pass** | Existing native regression plus run 35271227969 |
| Checked memory, AOT yield/resume, Clang ASan/UBSan | **Pass** | Existing native regression; host Clang job remains green in run 35271227969 |
| OpenOrbis static link and PS4 executable conversion | **Pass** | OpenOrbis job remains green in run 35271227969 |
| Guest AOT-written frames through native VideoOut in shadPS4 | **Pass** | Existing native four-frame + standalone evidence; this is not Suyu GPU rendering |
| Complete no-JIT Suyu Linux configuration | **Pass** | Run 35271227961 |
| Complete no-JIT Suyu Linux combined build/link | **Pass** | `core`, bridge, static bundle, direct-call smoke, and scheduled-process smoke all linked in run 35271227961 |
| Limited real-HLE `ArmRecomp` smoke | **Pass** | Historical direct `GetSystemTick` fixture retained and passed in run 35271227961 |
| Normal real process/thread/scheduler SVC dispatch and AOT resume | **Pass on Linux** | New scheduled-process regression passed in run 35271227961 |
| Dynamic guest CPU/JIT backend absent from full-core binaries | **Pass at symbol gate** | No `Dynarmic::`, `ArmDynarmic`, or `__jit_debug_register_code` in either full-core test binary in run 35271227961 |
| Real Suyu core and Horizon host platform on Orbis | **Not validated** | Native Orbis diagnostic still uses the smaller native executor |
| Native GPU shader/Maxwell rendering | **Not validated** | Existing displayed diagnostic uses guest CPU framebuffer stores |
| Actual private title entry / headless boot | **Not validated** | No commercial title used by public CI |
| Actual title rendering/playability | **Not validated** | No game frame claim |
| Physical PS4 execution | **Not validated** | shadPS4 evidence only |

## Scheduled-process milestone

Commit `4f3f3974eee5ce104ff24c20deac6b721c1cf2e3` adds a separate original AArch64 fixture and a strict report validator. The fixture is translated by the pinned real Suyu exporter, statically linked, loaded into a real `KProcess`, and executed by a real `KThread` through the normal CPU-manager/scheduler path.

The clean CI report from run 35271227961 proved:

- real `Core::System`, `KProcess`, `KThread`, process page table, TLS and stack;
- the same process-owned `ArmRecomp` context across SVC yields/resumes;
- normal SVC dispatch, rather than the old direct HLE function call;
- actual `GetSystemTick`, `GetThreadId`, `GetProcessId`, `GetCurrentProcessorNumber`, invalid-handle handling, `SleepThread`, resumed `GetSystemTick`, and `ExitThread`;
- observed transition into `ThreadState::Waiting` during a requested 20 ms sleep and successful resume;
- clean guest thread exit and kernel shutdown;
- `jit_available:false`, `jit_transitions:0`, and ten observed static blocks.

Validated SVC sequence:

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

The clean CI report recorded a `20,169,151 ns` host-observed sleep/resume interval. Timing is evidence of waiting/resume behavior, **not** a performance benchmark.

### Static block-boundary bug found and fixed

The first scheduled run did enter the real scheduler but debug-suspended immediately because the fixture started at `main+0x100` and that address was not a generated static lookup root. The exporter had legally merged the aligned padding into an earlier straight-line block.

The original fixture now branches explicitly to `process_entry` before the alignment padding. That makes `0x100` a real control-flow target, so the Suyu exporter emits a static block lookup entry there. This is a fixture/root-boundary correction, not a scheduler workaround or JIT fallback.

## Native Orbis baseline

The earlier native diagnostic remains a mandatory regression baseline:

- real Suyu exporter generates native C from original AArch64;
- generated code writes the framebuffer pixels;
- the OpenOrbis host provides checked memory and `sceVideoOut` presentation;
- shadPS4 captures and validates deterministic frames;
- no claim is made that this path contains the full Suyu kernel/services or Maxwell renderer.

See `docs/NATIVE_ORBIS.md` for its exact proof boundaries.

## Next accepted work sequence

1. **Port the proven process/SVC fixture to the real Suyu core on Orbis.** Build an explicit Orbis host profile and satisfy the required memory, threads/TLS, timing, synchronization/fibers, filesystem, logging and lifecycle contracts using public OpenOrbis APIs.
2. Run the same scheduled-process regression as an Orbis executable in shadPS4. Preserve the exact Linux test as a reference and do not replace real SVC behavior with the native diagnostic's private protocol.
3. In parallel, validate the native GPU path independently: real GPU clear/present, triangle, texture/resource updates, synchronization, then representative Suyu-generated shader output. CPU-written display patterns do not satisfy this gate.
4. Only after the real core is stable on Orbis, use the user's authorized private static title inputs to reach process entry/rtld/main and real HLE headlessly. Keep all commercial inputs outside public Git and CI.
5. Connect actual title Maxwell work to the validated PS4 GPU backend and distinguish first render target, first presented game frame, menu, gameplay, performance, and physical-console validation as separate milestones.

## Evidence discipline

Keep these claims distinct:

- Linux host execution;
- OpenOrbis cross-compilation;
- shadPS4 execution;
- physical PS4 execution;
- direct HLE call versus normal scheduler/SVC dispatch;
- CPU framebuffer output versus native GPU rendering;
- original synthetic fixture versus private commercial title;
- first game frame versus playable performance.

Do not introduce Dynarmic/JIT fallback, fake successful services, ignore missing static blocks, or mark an emulator result as physical-device validation. Public CI must remain free of games, keys, firmware, proprietary SDK material, and commercial generated code.
