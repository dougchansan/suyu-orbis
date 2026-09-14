# Validation ledger

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

These are local harness/mock results. They do **not** establish that the complete Suyu HLE was compiled, that the real exporter test passed, or that a PS4 executable ran.

The local build environment did not contain an OpenOrbis SDK and direct network checkout was unavailable. The GitHub-connected source audit succeeded. The actual-emitter test and public-SDK cross-build are configured in CI; inspect the run for the exact commit rather than assuming they passed. Any subsequent CI results should be added as separate evidence with run and commit IDs.

## Required evidence for promotion

Record source revision, exporter blob, compiler/linker versions, SDK release/path/hash, build command, ELF/eboot hashes, and test output. For a device run add PS4 model, firmware, execution environment, logs, crash details, and the diagnostic report retrieved from `/data`.

Keep these claims distinct:

- Authored host fixture passes.
- Actual Suyu-emitted synthetic C passes on the host.
- PS4 ELF links and eboot conversion succeeds.
- The executable starts and reports success on a real PS4.
- Real Suyu HLE loads a title and handles services.
- Rendering and gameplay are correct at a measured performance level.

There is currently no measured PS4 frame rate or Mario Kart compatibility claim. Do not infer either from desktop AOT benchmarks or raw hardware specifications.
