# Validation ledger

## Verified remote CI

[Run 34817696559](https://github.com/dougchansan/suyu-orbis/actions/runs/34817696559), code revision `3530e5394fcef18bb4752397ade7be3e8baa16f5`, completed successfully. Subsequent documentation-only changes do not change the tested code.

| Check | Result |
|---|---|
| GCC host build and tests | Pass |
| Clang host build and tests | Pass |
| Clang AddressSanitizer and UndefinedBehaviorSanitizer | Pass |
| Actual pinned Suyu emitter -> synthetic modules -> native host | Pass; all four CTest entries |
| Host emitted-code symbol guardrail | Pass; no forbidden symbols |
| Checksum-verified OpenOrbis SDK extraction | Pass |
| Registry diagnostic: PS4 ELF link, symbol audit, eboot conversion | Pass |
| Actual-emitter diagnostic: PS4 ELF link, symbol audit, eboot conversion | Pass |
| Physical PS4 execution | Not tested |
| Complete Suyu HLE, renderer, or game execution | Not implemented/validated |

The actual-emitter test verifies two original AArch64 modules, relocation, arithmetic yielding 42, a host-memory store of 42, SVC 17 yield, and uncovered/misaligned address rejection. It does not replace the real HLE services with success stubs or claim a game boot.

The cross-build used Clang 18.1.3 on Ubuntu 24.04, targeting `x86_64-pc-freebsd12-elf`, with the public OpenOrbis v0.5.3 `toolchain-llvm-18.2.zip` SDK. The generated-code host build used GCC 13.3.0. The release ZIP wraps `toolchain-llvm-18.tar.gz`; both layers are extracted.

SDK archive SHA-256:

```
5006bb8629a40093b712fac971456fa4d5ad3fafaadb16d11c10b8a93b8b496f
```

### Cross-build output hashes

These identify the outputs of the recorded run, not a claim that every compiler/build environment produces byte-identical binaries. The runner outputs were not uploaded as artifacts or releases.

| Diagnostic | Artifact | SHA-256 |
|---|---|---|
| suyu-orbis-probe | ELF | `89089203e1d53603c7e2a6c2208e65e10d2747ec4ba2dff2decd6b6e6f42368f` |
| suyu-orbis-probe | eboot.bin | `5da98eb8ea272952ca74d5d5156e1c20458f8ddd7beab477af845f351887ba57` |
| suyu-orbis-upstream-smoke | ELF | `2f58e86cb3ce6e5d34cc7669e34a10991c25036ae4ec77a35da10088fbb9d728` |
| suyu-orbis-upstream-smoke | eboot.bin | `204eeafaa4b8efd0b66e573734719a6f02c7894e5a3fe2deeaf104148f6acc8e` |

Each diagnostic's build report explicitly records `cross_compiled: true`, `ps4_run: false`, `game_run: false`, and `renderer: none`. The script verifies that eboot conversion produces a nonempty output. It does not create a PKG or launch the console.

## Local bootstrap validation

Environment: Linux x86-64; GCC 14.2.0; Clang 17.0.0; CMake 3.31.6; Python 3.13.5.

Executed during repository creation:

```
cmake --preset host
cmake --build --preset host
ctest --preset host
CC=clang cmake --preset host-sanitize
cmake --build --preset host-sanitize
ctest --preset host-sanitize
python3 scripts/audit_binary.py build/host/suyu-orbis-probe
```

Both host configurations pass all three CTest entries. These include 43 registry assertions, the JSON-emitting probe, and 13 Python tests. The Python suite configures, compiles, links, and executes an additional two-module mock bundle. The no-JIT symbol guardrail finds no forbidden symbols in the host fixture probe.

The local environment lacked an OpenOrbis SDK and direct network checkout. The actual Suyu-emitter and public-SDK tests were therefore executed in GitHub Actions as recorded above. Local mock tests and remote real-emitter results are separate evidence.

## Initial CI failure and repair

[Run 34817319186](https://github.com/dougchansan/suyu-orbis/actions/runs/34817319186), commit `112e156b63481cf9bd5dcea300411c752fb8321e`, passed both host jobs, sanitizers, and the actual-emitter test. SDK setup then failed because it extracted the outer ZIP but not the inner toolchain tarball. Cross-compilation was not reached. The corrected extraction and pinned checksum were verified by the successful run above; no test was disabled to obtain the passing result.

## Required evidence for promotion

For a device run, record PS4 model, firmware, execution environment, exact source and build hashes, logs, crash details, and the diagnostic report retrieved from `/data`. Running under a PS4 emulator would be separate emulator evidence, not physical-hardware evidence.

Keep host execution, cross-compilation, eboot conversion, physical-device execution, full HLE integration, and rendered gameplay as distinct milestones. There is currently no measured PS4 frame rate or Mario Kart compatibility claim. Do not infer either from desktop AOT benchmarks or raw hardware specifications.
