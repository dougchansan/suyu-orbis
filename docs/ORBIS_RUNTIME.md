# Native Orbis runtime and Common validation

## Verified native execution

Code revision `cf5eaf1f9f516a31b5324a61e0e638b701da85a7` passed
[run 35686596568](https://github.com/dougchansan/suyu-orbis/actions/runs/35686596568)
on 2026-09-22 UTC. The applications were built with Clang 18 and public
OpenOrbis v0.5.3, then executed in unmodified shadPS4 v0.18.0 on Linux.
This is **Orbis guest execution in an emulator, not physical PS4 testing**.

| Native test | Verified result |
|---|---|
| Modern C++ library | 44 checks; LLVM 20.1.8 sources, `_LIBCPP_VERSION=200100` |
| Exception/unwind/RTTI | Throw/catch, destructor unwinding and dynamic cast passed |
| Threads and atomics | 4,096 atomic_ref increments, 8 barrier phases, atomic wait/notify |
| TLS and cooperative stop | Two TLS destructors; independent TLS; jthread stop-aware wait/destructor |
| Filesystem subset | Create, write, rename, read, exact size, remove file and empty directory |
| Random device | Four reads succeeded; not a statistical or security-quality test |
| Actual Suyu Common | 1,186,039 checks using upstream components and isolated platform adaptations |
| Fibers | 4,096 round-trips plus 32 migrations between two native worker threads |
| Floating point and TLS | x87/SSE rounding and current-thread TLS preserved through migration |
| Native memory | Zeroed, 16 KiB-aligned direct-memory backing; move ownership and cleanup |
| Clock/sleep | 20,075,162 ns measured around a requested 20 ms sleep |
| Allocation cleanup | Zero live tracked page allocations at completion |

The Common test compiles the real pinned `common/fiber.cpp`, a narrowly
overlaid `common/host_memory.cpp`, and checked Boost.Context assembly. It is
not an invented replacement scheduler. Its reports explicitly say
`full_core_linked:false`, `scheduler_dispatch:false`, `guest_fastmem:false`
and `game_tested:false`.

Executable SHA-256 from the recorded run:

```text
orbis-cxx20-probe.oelf
  ec894a30c24b8a9f36d896d1ebe6d9dd7e6230d4947dc167fe4d5750b29233a1
suyu-orbis-host-common.oelf
  0fc6ba484f0f5d53f8691358a4d353b908f5e79d0011626f204ffacc4c48338e
```

The authoritative commands and pinned SDK/emulator checksums are in
`.github/workflows/orbis-cxx20.yml`. That workflow builds an isolated installation
prefix from LLVM revision `87f0227cb60147a26a1eeb4fb06e3b505e9c7261`.
Modern headers are always paired with the matching libc++, libc++abi and
libunwind static archives. The installed OpenOrbis SDK stays unchanged.

## Repairs established by this stage

Earlier commits selected the correct musl locale, pthread TLS-destructor and
atomic-wait fallback paths, supplied static unwind metadata, and isolated the
SDK's legacy math-overload conflict. Native clocks use the Orbis process
counter with its reported frequency. The filesystem bridge uses the explicit
120-byte PS4 stat ABI rather than the SDK header's mismatched structure.

Commit `f313bffe57563782e4b700404990a09b68d0616f` repairs directory removal:
`unlink(directory)` may return EPERM on Orbis rather than Linux EISDIR.
The adapter invokes actual `rmdir` for either error, does not recursively
remove children itself, and propagates other syscall errors. The exact
adapter is also compiled by a host unit test with controlled syscall outcomes.

The first run after that repair completed all guest operations but was
rejected by an incorrect validator version. The pinned LLVM header defines
`_LIBCPP_VERSION` as 200100, not the 200108 inferred from its release tag.
Commit `cf5eaf1f` corrects that identity check without removing behavioral gates.

## Next core build gate

`experiments/orbis_core_compile/` compiles the original CPU/AOT objects and all
91 kernel/SVC translation units, 98 units total, with explicit no-JIT Orbis
flags. Its source-set digest and object reports retain exact coverage and
remaining undefined references. This is compilation only: normal library
imports and missing real core implementations remain unresolved until a
complete executable is linked.

The next production gate remains the same eight-SVC scheduled-process fixture
already working on Linux, now linked to the real Suyu core on Orbis. Do not
replace it with this Common test. The complete Core::System/service graph,
CPU memory implementation, native dependencies and lifecycle still need
integration. The exploratory memory.cpp compile encountered its transitive
Host1x/NVDEC dependency on FFmpeg headers; no fake video service was introduced.

### Supported-toolchain kernel result

[Run 35687819373](https://github.com/dougchansan/suyu-orbis/actions/runs/35687819373),
code `e3aaaa7d740a73452f064aefb49b079f358aa841`, completed successfully.
Clang 18.1.3 compiled all 98 units and passed the object/target/no-JIT symbol
checks. Both native runtime executables were rerun successfully with the
same hashes above. The second Common run measured 20,075,232 ns for its sleep.

The object report retains 201 undefined symbol names after subtracting
symbols defined by the selected objects. These include normal C/C++ runtime
and real Suyu components still to link; they are not 201 distinct bugs and
are not resolved by this compilation-only test. The report explicitly records
`full_core_linked:false` and `orbis_scheduler_executed:false`.

## Explicit limits

The memory test uses upstream's no-fastmem backing mode; it does not establish
large guest-address reservations, aliases or protection-fault behavior. The
fiber/clock tests are correctness checks, not game-performance measurements.
The filesystem test covers its listed regular-file/empty-directory operations,
not symlink, nonempty-directory or full POSIX semantics. The current lstat/stat
adaptation still needs a correct symlink policy before production use.

shadPS4's behavior is not evidence of physical-console behavior. No complete
Orbis Horizon scheduler, Maxwell shader backend, actual title frame, gameplay,
or hardware validation is claimed by either native executable.
