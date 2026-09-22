# Actual Orbis kernel compilation gate

This compiles 98 original upstream translation units: ArmInterface, ArmRecomp,
the standalone exclusive monitor, CoreTiming, CPU manager, device memory, and
all 91 C++ files under the pinned `core/hle/kernel` directory. There are no
replacement SVC implementations, no fake `core` library, and no linked app.
The target is explicitly `SUYU_NO_JIT=1` / Orbis x86-64.

The source-set fingerprint rejects missing, additional or changed translation
units. Public CI supplies dependency headers from fixed source checkouts.
The object report verifies one ELF64 x86-64 relocatable object per source,
actual ArmRecomp/KProcess/KThread definitions, and no dynamic CPU/loader
symbols. The static-assert-only `k_class_token.cpp` legitimately emits no
global symbols; it is still compiled and checked.

**Compilation is not full-core linking or runtime execution.** The unresolved
symbol inventory is retained rather than satisfied with stubs. It includes
normal library imports and real core dependencies, not a count of distinct
bugs. Core::System, the CPU memory implementation, services, and video/audio
backends are not all part of this object slice. In particular, the exploratory
memory.cpp build reaches a Host1x/NVDEC include dependency on FFmpeg headers;
a native multimedia dependency build is still needed for the complete core.

After building the modern runtime with `orbis-cxx20.yml`, use its paths:

```sh
cmake -S experiments/orbis_core_compile -B build/kernel-orbis -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE="$PWD/experiments/orbis_cxx20/consumer_toolchain.cmake" \
  -DSO_CXX_PREFIX="$PWD/build/cxx-prefix" \
  -DSO_ORBIS_C_OVERLAY="$PWD/build/c-header-overlay" \
  -DSO_SUYU_SOURCE="$PWD/vendor/suyu" \
  -DSO_BOOST_HEADERS="$PWD/vendor/boost-headers" \
  -DSO_FMT_SOURCE="$PWD/vendor/fmt" \
  -DSO_UNORDERED_SOURCE="$PWD/vendor/unordered_dense"
cmake --build build/kernel-orbis --parallel 2
python3 experiments/orbis_core_compile/report_objects.py \
  --build build/kernel-orbis --output build/kernel-report.json
```

Use Clang 18 or later with LLVM 20.1.8 libc++. The initial local Clang 17
compile emitted the library's unsupported-compiler warning; supported CI
compilation is recorded separately. Never mix the modern headers with the
SDK's old libc++ archives or include a host Linux standard-library sysroot.
