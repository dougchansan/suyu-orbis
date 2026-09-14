# Evidence contract

For this experiment, keep these states separate:

1. Full pinned Suyu source configures with `SUYU_NO_JIT=ON`.
2. The real `core` static library compiles and links.
3. The suyu-orbis bridge compiles against the real Suyu headers and core target.
4. Synthetic Suyu-generated modules statically link into the same executable.
5. A real `Core::System` / process / `ArmRecomp` execution path reaches an SVC boundary.
6. The real HLE kernel dispatches that SVC and execution resumes.

Do not mark a later state successful because an earlier state passes. Do not replace missing kernel/bootstrap state with dummy-success SVC handlers. The first failing state is a useful result and should be preserved in logs/tests.
