// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef SUYU_ORBIS_BUNDLE_H
#define SUYU_ORBIS_BUNDLE_H
#include "suyu_orbis/registry.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Implemented by scripts/import_modules.py, not by the fixture probe.
 * One bundle/process at a time, just like the upstream global AOT hooks.
 * bind() takes the actual NSO loader base, never an invented fixed address.
 */
SoResult so_bundle_init(void);
size_t so_bundle_count(void);
SoResult so_bundle_bind(size_t index, uint64_t actual_load_base);
SoResult so_bundle_seal(void);
SoResult so_bundle_lookup(uint64_t pc, SoBlockFn* block);
SoResult so_bundle_entry(size_t index, uint64_t* pc);
#ifdef __cplusplus
}
#endif
#endif
