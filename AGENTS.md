# Working on suyu-orbis

The objective is a native OpenOrbis/PS4 host for the user's Suyu AOT work. Do not label the fixture probe as a working emulator, ported HLE, or a game boot.

## Current continuation task

Read [docs/PORT_PROGRESS.md](docs/PORT_PROGRESS.md) and [docs/LOCAL_AGENT_HANDOFF.md](docs/LOCAL_AGENT_HANDOFF.md) first. They make the local-agent handoff persistent and distinguish the passing native AOT display diagnostic from the still-failing complete Suyu Linux build.

Preserve the verified native diagnostic as a regression baseline. The immediate work is to reproduce and repair the real no-JIT core build, execute the existing limited smoke, then prove normal process/thread SVC dispatch and carry the real core to Orbis. Do not replace that task with a larger synthetic framebuffer demo or extend the private diagnostic SVC protocol into fake Horizon services.

Read README.md, docs/NATIVE_ORBIS.md, docs/ARCHITECTURE.md, docs/ROADMAP.md, and docs/VALIDATION.md for implementation contracts and historical evidence. Current stage status is recorded in PORT_PROGRESS.md; historical passing results do not establish a newer or different test. Start with `python3 scripts/doctor.py` and the host CMake preset. Run the complete host tests after changes. Use `CC=clang` with host-sanitize. The actual-emitter test is separate: `scripts/test_upstream.py` verifies its pinned header before building. The newer native test and standalone Orbis instructions are in NATIVE_ORBIS.md.

Preserve these constraints:

1. No JIT/interpreter fallback in the Orbis target. The real core must be built with its actual `SUYU_NO_JIT=ON` option. Do not claim a fixture's missing Dynarmic symbols proves a full-core no-JIT build.
2. Reuse the pinned Suyu exporter and HLE interfaces; do not replace failing SVCs with dummy success. Unknown operations must fail visibly. The diagnostic's `0xf000`/`0xf001`/`0xf002` protocol is not Horizon HLE.
3. Use each module's generated header and full GuestContext. Keep ABI checks. Preserve SIMD registers, FPCR/FPSR, both thread pointers, pending SVC, and host-memory hooks.
4. Bind by actual NSO load order, not internal NSO name or fixed desktop address. Complete all base/index setup before any guest thread executes.
5. Do not modify or reset existing user worktrees. No force push, history rewrite, visibility change, releases, game downloads, or toolchain installers without a task that needs them. Keep new port work on a development branch; do not merge into main without authorization.
6. Never commit commercial-game exports, data segments, keys, firmware, local manifests, proprietary SDKs, or device credentials. Keep them in ignored private/build directories or outside the repository.
7. OpenGNM/Vulkan-PS4 remains a research candidate. Audit actual requirements and compile/run a minimal renderer test before integrating it. A library README or a feature bit is not proof of Suyu compatibility.
8. Record commands, compiler versions, commit IDs, outputs, and hardware evidence separately. A successful host test, cross-build, eboot conversion, device boot, rendered frame, and playable game are six different milestones. Real HLE direct-call and normal scheduler/dispatcher tests are also distinct.

Continue with the first unmet acceptance gate in LOCAL_AGENT_HANDOFF.md and update PORT_PROGRESS.md with actual results. Commit cohesive changes and their tests; do not add untested platform shims merely to make a build green. Do not upload private logs without reviewing them. Keep stdout reports honest about their scope.
