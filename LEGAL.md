# Repository content and distribution policy

This repository contains project source and original synthetic test inputs. It does not include commercial games, firmware, encryption keys, generated commercial-game machine/source code, proprietary Sony SDK material, or console-modification payloads.

Use only inputs and development tools you are authorized to use. Ownership alone is not represented here as a universal authorization to extract, transform, or distribute software. This policy is not a legal opinion about a particular jurisdiction or distribution plan.

Keep local game inputs and generated title-specific C outside Git. The importer accepts trusted local source and never downloads games. Its output manifests contain source paths and hashes and should also stay private. The synthetic emitter tests may be shared as project source; they contain only the original short instruction sequences in tests/upstream_fixture.cpp.

Project source is GPL-2.0-or-later. Preserve existing notices in Suyu and all external components. OpenOrbis is obtained separately from its public project. Any future binary distribution requires a separate review of applicable licenses, corresponding source/build materials, and embedded inputs. A binary is not cleared for publication merely because it contains no JIT.

There are no automated release or binary-publication jobs in this repository. Build configuration and diagnostic hashes are not claims of compatibility, certification, or legal clearance. This project is not affiliated with Nintendo or Sony.
