# Full-core Linux smoke

This experiment exercises the real pinned Suyu `core` library with `SUYU_NO_JIT=ON`, then attaches the suyu-orbis synthetic static bundle through the real `Core::SetRecompLookup` / `Core::SetRecompBaseSetter` bridge.

It is intentionally Linux-only and synthetic. It does not use game files, firmware, keys, graphics, or proprietary SDKs.

Acceptance target: compile the real Suyu core, create a minimal `Core::System`, bind the generated synthetic `rtld` + `main` images, execute at least one real `ArmRecomp` thread slice through an SVC boundary, and resume after HLE dispatch. If the current Suyu API requires more process/bootstrap state than can be safely synthesized, the experiment should fail at the first truthful integration boundary and record that boundary rather than mocking success.
