# Bring-up milestones

Each milestone needs its own recorded evidence. Do not skip a failing stage by weakening its test.

| Stage | Acceptance criterion | Initial state |
|---|---|---|
| Host registry | Relocation, typed dispatch, failures, multi-module link, sanitizers | Implemented; local tests pass |
| Actual emitter | Original AArch64 -> Suyu C -> native host; memory store and SVC yield | Test implemented; requires pinned header checkout |
| OpenOrbis cross-build | SDK-backed ELF, symbol audit, nonempty eboot, hashes | Build path and CI configured; SDK required |
| Device diagnostic | Retrieve successful JSON report from real PS4, record device/firmware | Not tested |
| Actual Suyu core | Port dependencies/platform services, build SUYU_NO_JIT core on Orbis | Not implemented |
| Loader + AOT | Attach real hooks, bind real module bases, reach SVC on PS4 | Bridge source supplied; not integrated |
| HLE execution | Real memory, scheduler, exclusives, services; no dummy successes | Not implemented |
| Graphics | Feature audit, independent present/shader tests, then Suyu commands | Not implemented |
| Audio/input/saves | Device-tested platform backends and lifecycle | Not implemented |
| Title validation | Explicit game/version/input replay, no uncovered blocks, correctness | Not tested |
| Packaging/release | Reproducible package, reviewed source and inputs, approved release | Not implemented |

## Next engineering work

First run the actual-emitter test and fix genuine incompatibilities. Then cross-compile both diagnostics and run the smaller registry probe on a PS4 before attempting the emitted-runtime diagnostic. Record the hardware logs; a shadPS4 run, if used, is separate emulator evidence rather than hardware evidence.

For the real-core port, maintain a patch series against the locked source in a separate worktree. Start by inventorying platform/dependency blockers: C++20 library coverage, fibers/context switching, host virtual memory layout, mapping/protection semantics, signal handling, clocks, thread-local storage, atomics, and all linked libraries. Avoid propagating the host's `-march=native` flags onto the Jaguar target.

Extract a genuine headless core/frontend configuration with real no-JIT behavior. Do not call a flag `GUI=OFF` unless it actually exists upstream; inspect its CMake options. Disabling a window does not automatically remove the video-core dependency.

Only after the runtime and loader work should private title-specific exports be used. Record missing addresses by module and relative offset, re-export on the development host, and rebuild static modules. A known replay is evidence for that replay, not coverage of every mode, DLC, update, or multiplayer path.
