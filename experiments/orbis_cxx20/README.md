# Isolated modern C++ runtime experiment

The public OpenOrbis v0.5.3 SDK ships libc++ headers identifying themselves as
version 11000. The existing audit fails the real Suyu C++20 requirements for
stop tokens, jthread, stop-aware condition variables, atomic_ref, bit_cast and
ranges. A newer compiler alone does not replace these headers or libraries.

This experiment builds LLVM 20.1.8 libc++, libc++abi, and libunwind against the
public SDK in an isolated prefix. Pin:
`87f0227cb60147a26a1eeb4fb06e3b505e9c7261` (llvmorg-20.1.8).

It does NOT overwrite the SDK, change the passing native target, or claim a
full Suyu build. Never mix new headers with the old libc++ archive. Keep
exceptions, RTTI, threads, locale and filesystem enabled; a failing primitive
is a real portability gap, not permission to stub successful behavior.

C++ chrono's time-zone database is disabled in this experimental library
because no IANA database is provided in the target image; Suyu's separate
TZDB remains a distinct dependency. Upstream runtime tests are not executed by
a cross-compile. Static archives and compile-only checks are not runtime proof.

See `.github/workflows/orbis-cxx20.yml` for the reproducible build. LLVM sources
retain Apache-2.0 WITH LLVM-exception notices. Future use requires linking and
running explicit native Orbis threading, stop/wake, exception/unwind, TLS and
filesystem tests, then repeating the real Common and full-core fixtures.
