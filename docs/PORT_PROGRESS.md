# Port progress: native Suyu title on Orbis

This is an evidence ledger, not a completion percentage. The current native diagnostic is useful infrastructure, but it is not a running Switch title. Follow [the local-agent handoff](LOCAL_AGENT_HANDOFF.md) for the next engineering steps.

## Handoff snapshot

This snapshot is based on experimental branch `full-core-linux-smoke` at documentation revision `d985afaee87ad5ef65a4477d7ec90c44352a691e`. The verified native executable code is `25874425ad97238853b245667aa33ca7b51e2c2d`; the documentation revision is not a new runtime test.

Pinned Suyu source: `e6f53df9f160903fd15ed2b0cd91ac60f1f43428`. Read `deps.lock.json` before changing or importing generated code.

| Gate | Recorded result | Evidence / boundary |
|---|---|---|
| Actual Suyu exporter, original AArch64, native host execution | Pass | Native run 34916702772 |
| Checked memory, AOT yield/resume, Clang ASan/UBSan | Pass | Native run 34916702772; details in NATIVE_ORBIS.md |
| OpenOrbis static link and PS4 executable conversion | Pass | Native run 34916702772 |
| Guest CPU-written frames through native VideoOut in shadPS4 | Pass | Four completed flips; deterministic captures and independent standalone test |
| Complete no-JIT Suyu Linux configuration | Pass | Full-core run 34916507480 |
| Complete no-JIT Suyu Linux combined build/link | Fail | Full-core run 34916507480, job 104215234742; inspect its compiler/linker log |
| Existing limited full-core executable / direct real HLE call | Not established | Failed build did not establish a passing runtime test |
| Normal real process/thread/scheduler SVC dispatch and AOT resume | Not validated | Not equivalent to the existing direct-call smoke |
| Real Suyu core and Horizon host platform on Orbis | Not validated | Native diagnostic uses a smaller executor |
| Native GPU shader/Maxwell rendering | Not validated | Displayed diagnostic uses CPU framebuffer stores |
| Actual private title entry, rendering, or playability | Not validated | No commercial title tested by public CI |
| Physical PS4 execution | Not validated | shadPS4 evidence only |

### Native baseline evidence

[Successful native run 34916702772](https://github.com/dougchansan/suyu-orbis/actions/runs/34916702772), source `25874425ad97238853b245667aa33ca7b51e2c2d`:

- Checked-memory tests: 42 assertions. AOT state/failure tests: 74 assertions.
- Self-test: 327,680 checked pixel values, also executed inside the Orbis applications.
- Display sequence: 3,686,400 guest pixel stores and four completed VideoOut flips.
- Capture-controlled test: four images, 880 sampled pattern checks total.
- Standalone test: autonomous completion with no host ACK files; four guest flip reports and two checked final-frame captures. Intermediate standalone frames were not independently captured.

See [NATIVE_ORBIS.md](NATIVE_ORBIS.md) for build commands, runtime limits, exact binary hashes, and evidence provenance. No new performance or hardware claim is added by this handoff.

### Immediate blocker: full-core build

[Full-core run 34916507480](https://github.com/dougchansan/suyu-orbis/actions/runs/34916507480), source `74f6a1f4c186745c4e80bc5d51ef689b484b4aa5`, finished with a failed combined build. [Job 104215234742](https://github.com/dougchansan/suyu-orbis/actions/runs/34916507480/job/104215234742) is the diagnostic source to reproduce. This ledger does not assert an unverified specific unresolved symbol or root cause.

The earlier unrelated Oaknut example failure involving `<print>` was addressed by explicitly setting `BUILD_TESTING=OFF` and `DYNARMIC_TESTS=OFF`. That change did not by itself prove the complete runtime linked or executed. Keep the working timezone/dependency settings and inspect the actual current compile/link failure rather than repeatedly changing unrelated options.

The existing `experiments/full_core_smoke` test is limited: it directly invokes a real `GetSystemTick` implementation rather than proving normal process/thread SVC dispatch. Repair that test first, then add a separate genuine dispatcher test; do not relabel the limited test.

## Next accepted work sequence

1. Reproduce the known-good native baseline and the failed full-core build. Capture the first meaningful error and full link command; fix real target dependencies/implementations and execute the limited smoke.
2. Add real process/thread, memory, normal SVC dispatcher, and AOT resume coverage on Linux. Preserve no-JIT strict behavior and failure tests.
3. Port the required host abstractions and the real core fixture to Orbis. Validate memory, TLS/threads/fibers, clocks, exclusives, files, and lifecycle independently.
4. Boot the user's private static title headlessly through real HLE; separately validate the native GPU backend, then connect actual title graphics work.

The display regression remains mandatory, but another synthetic framebuffer demo is not the next production milestone. Details, constraints, and acceptance criteria are in [LOCAL_AGENT_HANDOFF.md](LOCAL_AGENT_HANDOFF.md).

## Update this ledger during implementation

Append a dated entry for each meaningful change. Use actual UTC timestamps, source revisions, and the exact environment tested. Do not update a pass/fail status from a queued or still-running job. Do not upload private title paths, hashes, registers containing sensitive data, or commercial inputs into public reports.

```text
Date/time (UTC):
Branch and commit:
Upstream revision / exporter identity:
Environment and toolchain:
Change:
Test command / expected result:
Actual result and scope:
Log, run, or artifact reference:
First remaining failure:
Next action:
```

Keep host execution, cross-compilation, emulator execution, physical-device execution, real HLE, native GPU output, and gameplay results distinct. Documentation-only commits do not add runtime evidence.
