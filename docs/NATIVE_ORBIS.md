# Native Orbis AOT execution and presentation

## Verified implementation

`native/` builds a PS4 application from actual Suyu-generated C, a small native AOT executor, checked guest memory, and a native `SceVideoOut` backend. No PC-side service draws its framebuffer. The Linux host in the integration test runs shadPS4 as the PS4 execution environment; the application itself is an Orbis executable.

```
original AArch64 assembly (rtld + main)
  -> pinned Suyu EmitProject
  -> generated per-module C and shared runtime
  -> OpenOrbis clang/LLD x86-64 code
  -> converted PS4 OELF/SELF
  -> native static dispatch and checked memory callbacks
  -> native SceVideoOut completed flips
```

The original diagnostic has a 3-instruction bootstrap and a 43-instruction main program. It writes every pixel of four alternating 1280x720 frames. The host supplies buffer addresses and presents completed images; it does not generate or copy in the pattern. Two patterns alternate across the four frames.

**This is not yet the full Switch game port.** The native executor is not the complete Suyu `Core::System`/`ArmRecomp`/Horizon environment. There is no native Maxwell renderer, normal NSO loader, guest scheduler, filesystem/service manager, shared-memory exclusive monitor, input/audio/save backend, or commercial game validation. The framebuffer test uses CPU stores, not Switch GPU commands. Physical PS4 execution has not been tested.

## Runtime contracts

`src/aot.c` allocates the entire generated `GuestContext`, checks the existing ABI assertions, and calls actual statically compiled block functions. It contains no instruction decoder, interpreter, or CPU JIT. It yields on pending SVCs and only resumes when the caller explicitly acknowledges that exact SVC. No fake Horizon success values are returned.

The diagnostic's `0xf000` (acquire), `0xf001` (present), and `0xf002` (finish) SVCs are a **private test protocol**, not implementations of Nintendo system calls. Unexpected SVCs fail the diagnostic. This protocol must not replace production HLE services when loading a title.

`src/memory.c` provides checked regions and little-endian scalar loads/stores. Permissions, overflow, overlaps, and complete-access bounds are checked. A fault is sticky. The owner must serialize execution and mappings; this is not a thread-safe Horizon address space. Unsupported exclusive-memory callbacks fail closed rather than pretending to implement a shared monitor. A missing counter provider also fails closed.

`platform/orbis/video_out.cpp` allocates aligned direct memory through native kernel APIs, registers two linear buffers, prevents reuse of the current front buffer, and waits for flip count, tag, and current-buffer status to confirm presentation. A timed-out/in-flight allocation is not freed unsafely. Successful runs intentionally hold the final frame until termination; normal shutdown/release is not an additional validated milestone.

## Reproduce on a Linux development host

Read `deps.lock.json` and `AGENTS.md`. Use empty build directories; the importer refuses to overwrite populated export bundles. Requirements include Clang with its AArch64 assembler, a C++20 host compiler, CMake 3.24+, Ninja, and Python 3.10+.

```sh
git clone --branch full-core-linux-smoke https://github.com/dougchansan/suyu-orbis.git
cd suyu-orbis
python3 scripts/fetch_upstream.py
python3 scripts/emit_native_fixture.py

cmake -S native -B build/native-host -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DSO_MODULE_BUNDLE="$PWD/build/native-fixture/bundle"
cmake --build build/native-host --parallel 2
ctest --test-dir build/native-host --output-on-failure
python3 scripts/audit_binary.py build/native-host/aot-runtime-tests

CC=clang CXX=clang++ cmake -S native -B build/native-sanitize -G Ninja \
  -DCMAKE_BUILD_TYPE=Debug -DSO_SANITIZE=ON \
  -DSO_MODULE_BUNDLE="$PWD/build/native-fixture/bundle"
cmake --build build/native-sanitize --parallel 2
ctest --test-dir build/native-sanitize --output-on-failure
```

The pinned emitter blob must match; do not silently update the exporter. Sanitizer libraries can import dynamic-loader symbols, so run the symbol guardrail on the Release executable, not the ASan executable.

## Build the independent native application

Install the public OpenOrbis v0.5.3 SDK and LLVM 18 as in CI. Extract both the release ZIP and its inner tarball. Do not use proprietary Sony SDKs.

```sh
export OO_PS4_TOOLCHAIN=/absolute/path/to/OpenOrbis/PS4Toolchain
python3 scripts/doctor.py --orbis
cmake -S native -B build/native-standalone -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE="$PWD/cmake/toolchains/openorbis.cmake" \
  -DSO_MODULE_BUNDLE="$PWD/build/native-fixture/bundle" \
  -DSO_AOT_CAPTURE_HANDSHAKE=OFF
cmake --build build/native-standalone --target suyu-orbis-aot-render --parallel 2
```

Outputs:

| File | Use |
|---|---|
| `suyu-orbis-aot-render.elf` | Intermediate LLD image; inspect symbols here |
| `suyu-orbis-aot-render.oelf` | Converted PS4 image for direct shadPS4 testing |
| `suyu-orbis-aot-render-eboot.bin` | Converted SELF; not an installable PKG |

**Launch the `.oelf`, not the intermediate `.elf`, in shadPS4.** OpenOrbis conversion adds PS4 executable metadata and NID imports, not just a filename change.

With `SO_AOT_CAPTURE_HANDSHAKE=OFF` (the default), the app presents four frames autonomously, paces them with native kernel sleep, and holds the last frame. It writes diagnostic evidence to guest `/data` but needs no external acknowledgment files. `SO_AOT_CAPTURE_HANDSHAKE=ON` is only for deterministic CI capture: that version waits for acknowledgments and times out without them.

## Emulator validation

The workflow `.github/workflows/native-orbis-aot.yml` uses unmodified official shadPS4 v.0.18.0, Xvfb, and Mesa lavapipe. The two tests are intentionally separate:

```sh
# Requires handshake-enabled native build in build/native-orbis.
python3 scripts/ci/capture_native_aot.py --emulator /path/Shadps4-sdl.AppImage \
  --executable build/native-orbis/suyu-orbis-aot-render.oelf \
  --output build/native-evidence

# Requires handshake-disabled build from the instructions above.
python3 scripts/ci/capture_native_standalone.py --emulator /path/Shadps4-sdl.AppImage \
  --executable build/native-standalone/suyu-orbis-aot-render.oelf \
  --output build/standalone-evidence
```

Both need working Linux emulator prerequisites. Each gets a fresh profile. Empty user home directories prevent shadPS4's first-run save-migration dialog from blocking unattended execution. The CI temporarily permits low-address guest mappings only on a disposable GitHub-hosted VM, runs the emulator unprivileged, and restores the original policy. Do not copy that system-wide setting blindly onto a daily-use machine.

The deterministic test requires four completed-flip reports and four external captures, each checked at 220 known pixel positions. It confirms that phases 0 and 1 differ. The standalone test writes no ACK files: it requires autonomous completion, all four guest reports, and two captures of held phase 3. It does not claim to have externally captured the intermediate standalone frames. Neither test measures game performance.

## Evidence ledger

Baseline [run 34915860127](https://github.com/dougchansan/suyu-orbis/actions/runs/34915860127) passed at `25d6a1e7256063077f1b23950e90c71c76e24cdc`.

The expanded [run 34916702772](https://github.com/dougchansan/suyu-orbis/actions/runs/34916702772) passed at **`25874425ad97238853b245667aa33ca7b51e2c2d`**, including both standalone and capture-controlled native executables.

| Check | Verified result |
|---|---|
| Original assembly through actual pinned Suyu exporter | Pass |
| GCC Release host execution | Pass |
| Clang ASan/UBSan generated-code execution | Pass |
| Checked-memory assertions | 42 pass |
| AOT state/failure assertions | 74 pass |
| Self-test pixel values | 327,680 checked |
| Same AOT self-test inside each Orbis application | Pass |
| PS4 link, OELF conversion, symbol guardrail | Pass |
| Guest-written display pixels per complete run | 3,686,400 stores |
| Completed native VideoOut flips per complete run | Four |
| Capture-controlled external checks | 220 per frame; 880 total |
| Standalone without any host ACKs | Pass; four flip reports and completion |
| Standalone external captures | Two correct final-phase images; 440 checks |
| Full Suyu HLE / Maxwell GPU / game / physical PS4 | Not validated |

Hashes from the expanded successful run:

| Artifact | SHA-256 |
|---|---|
| Capture-controlled OELF | `671a326802a3f2edbf42b55a904cfd042d3a479a33a292af2eb6e7346915342e` |
| Standalone OELF | `c4ad6b4bdd9c1f9c2bd5917717cf6c5728fb1f8aa458a56f257e35d32bfc74dc` |
| Standalone intermediate ELF | `1bda125b217f791dcd70eb82a52c71a5078fcf29b52ce0c9e294c0c6391637d0` |
| Standalone eboot SELF (conversion, not separately executed) | `ac3ebb8e6b7a410bbb82812c2d60ae5c7e3ce417763b815897fa7cf67a68520e` |
| Downloaded evidence/source ZIP | `245426253a2f2c6b10e5f06b9748193e2613d7ec64ea8c8b4c4781ae2a2e1405` |

The downloaded captures and binaries were independently re-hashed. The baseline archived generated sources were re-imported, built, and executed in the Linux sandbox: Release and Clang ASan/UBSan both passed. A wrong-phase image was correctly rejected as a capture-validator negative control. Results describe these exact tests, not arbitrary generated-code coverage.

## Continue toward the actual title

Do not expand the private test SVC protocol to imitate Horizon piecemeal. Reuse the real Suyu process, thread, memory, and HLE components and validate each platform dependency on Orbis. Preserve this diagnostic as a known-working ABI, static-link, memory, and scanout regression test. Separately prove a native GPU backend with shader execution before connecting Suyu's Maxwell command stream.

The full-core Linux smoke remains separate. Its earlier build stopped in an unrelated Oaknut example requiring `<print>` on GCC 13. The workflow now explicitly sets `BUILD_TESTING=OFF` and `DYNARMIC_TESTS=OFF`, matching the no-JIT target's scope; a passing native diagnostic must never be used to mark the full-core smoke successful.
