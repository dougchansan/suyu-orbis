# Architecture and pinned-source audit

## What is actually built

The default graph is `suyu-orbis-probe -> authored fixture modules -> suyu_orbis_registry`. It has no Suyu kernel, no GPU implementation, and no game loader. The separate upstream test replaces the authored fixture with two modules emitted by Suyu itself and its generated shared runtime. It is still not the full emulator.

The target graph for the future port is:

```
private AArch64 modules -> pinned Suyu exporter -> generated C/static libraries
                                                    |
PS4 executable <- Orbis platform port <- real Suyu HLE + ArmRecomp
                                                    |
                                       validated graphics backend (not present)
```

Static recompilation replaces guest CPU execution; it does not turn Switch OS calls or Maxwell graphics commands into native PS4 services automatically. Do not treat the CPU work as evidence that graphics or whole-game performance is solved.

## Audited source

Suyu repository: `https://github.com/dougchansan/suyu-v0.0.4`

Pinned revision: `e6f53df9f160903fd15ed2b0cd91ac60f1f43428`.

Relevant paths:

- `src/core/recompiler/arm64_to_c.h`: `EmitProject`, `RuntimeH`, and `RuntimeC`; generated static targets and image APIs.
- `src/core/arm/recomp/arm_recomp.h`: register prefix and real `SetRecompLookup` / `SetRecompBaseSetter` callback signatures.
- `src/core/arm/recomp/arm_recomp.cpp`: guest-context and host-memory offsets, chain budget, pending SVC behavior.
- `src/core/CMakeLists.txt`: real core dependencies remain linked to audio, HID, network, video, time-zone, SSL, compression, and other components. It is not a tiny freestanding library just because Dynarmic can be excluded.

## Concrete static-linking repair

The exporter already emits `recomp_static_rtld`, `recomp_static_main`, etc. and one `recomp_runtime_shared`. Creating a second custom translation pipeline is unnecessary.

However, its static-target compile definitions rename five older module symbols but not these three newer globals:

```
recomp_build_index
_recomp_index_view
recomp_image_index
```

Their definitions would collide in a multi-module static executable. The importer appends per-module compile-definition renames to all three, preserving original exports on disk. It does not hide or discard duplicate definitions, and it does not duplicate the generic shared runtime.

The local mock integration exercises this link shape. The separate real-emitter test is the evidence required to demonstrate it against upstream-generated code.

## Runtime rules

The importer accepts module-relative exports (`base = 0`) and requires matching generated runtime/header contents across modules. Imported files must remain immutable during a build. Fingerprints are checked before compilation; a changed source set or guest text requires a fresh import. This is a reproducibility guardrail, not a security sandbox for malicious build scripts.

`SoRegistry` is initialized and bound before guest execution. Base and size validation is completed before calling any generated base setter; sealing builds the generated indices single-threadedly. Lookup is read-only after that. Reinitialization is allowed only when every guest thread has stopped. The emitter's own module globals mean multiple simultaneously running processes/bundles are not supported.

Indices correspond to the actual exported modules in NSO load order: rtld, main, present subsdk0..9, sdk. There are no padded slots for absent subsdk modules. Internal names such as `nnSdk` are diagnostic only.

Unaligned PCs are rejected before reaching the generated dense index. Uncovered PCs return no block. A caller must report/stop on that failure; it must not silently call a dynamic recompiler.

## Full-core bridge

`integrations/` is an opt-in parent-superbuild component, not built by the default harness. It requires actual `core` and `so_module_bundle` targets and `SUYU_NO_JIT=ON`. Call `SuyuOrbis::AttachStaticBundle()` before the real loader begins, and detach only after stopping all guest threads.

The bridge uses a typed trampoline rather than invoking a `void(GuestContext*)` function through Suyu's `void(void*)` pointer type. This adds a lookup and is deliberately a correctness-first diagnostic implementation. It is not yet compiled against the complete Suyu core, nor verified with its loader on PS4.

Before promoting this integration, test attachment, actual module-base callback timing, entry execution, SVC handoff, process shutdown/reload, and a deliberately missing export. The full core's actual guest-memory and exclusive-monitor callbacks must be preserved; the synthetic fixture's memory callbacks are not a replacement.

## OpenOrbis and graphics

The toolchain configuration follows the public OpenOrbis sample's x86_64 FreeBSD-targeted Clang compilation and direct LLD/CRT/link.x link. `Generic` is used as CMake's system label to avoid accidentally discovering desktop FreeBSD/Linux libraries. That does not make Orbis ABI-compatible with arbitrary FreeBSD packages.

Source reference: `https://github.com/OpenOrbis/OpenOrbis-PS4-Toolchain/blob/master/samples/hello_world/Makefile`.

OpenGNM is an unintegrated candidate: `https://github.com/PS4-OpenGNM/opengnm-stack`. Its project advertises a Vulkan 1.0 ICD and shader tooling. That is not sufficient evidence of Suyu compatibility. Inventory Suyu's minimum API version, extensions/features, synchronization, memory model, formats, shader capabilities, and presentation requirements before choosing this route. No Vulkan loader/backend is present here.
