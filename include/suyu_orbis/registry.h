// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef SUYU_ORBIS_REGISTRY_H
#define SUYU_ORBIS_REGISTRY_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

struct GuestContext;
typedef void (*SoBlockFn)(struct GuestContext*);
typedef SoBlockFn (*SoLookupFn)(uint64_t pc);
typedef void (*SoBaseFn)(uint64_t base);
typedef uint64_t (*SoEntryFn)(void);

enum { SO_MAX_MODULES = 13 };
typedef enum SoResult {
    SO_OK = 0, SO_INVALID_ARGUMENT, SO_INVALID_MODULE_ORDER, SO_ADDRESS_OVERFLOW,
    SO_OVERLAPPING_MODULES, SO_NOT_READY, SO_ALREADY_BOUND, SO_ALREADY_SEALED,
    SO_UNALIGNED_PC, SO_UNCOVERED_PC, SO_INVALID_ENTRY
} SoResult;

typedef struct SoModule {
    const char* name;
    SoLookupFn lookup;
    SoBaseFn set_base;
    SoEntryFn entry;
} SoModule;
typedef struct SoLoadedModule {
    SoModule module;
    uint64_t base;
    uint64_t text_size;
    int bound;
} SoLoadedModule;
typedef struct SoRegistry {
    SoLoadedModule modules[SO_MAX_MODULES];
    size_t count;
    int sealed;
} SoRegistry;

/* Initialize and bind only before guest threads start. Reinitializing a live
 * registry is forbidden. Sealed lookup is read-only and does not allocate.
 * Names and module code must outlive the registry. Index is NSO LOAD ORDER,
 * not the numeric suffix in subsdkN and not the module's internal NSO name.
 */
SoResult so_registry_init(SoRegistry*, const SoModule*, size_t count);
SoResult so_registry_bind(SoRegistry*, size_t index, uint64_t base, uint64_t text_size);
SoResult so_registry_seal(SoRegistry*);
SoResult so_registry_lookup(const SoRegistry*, uint64_t pc, SoBlockFn* out);
SoResult so_registry_entry(const SoRegistry*, size_t index, uint64_t* out);
const char* so_result_string(SoResult);
#ifdef __cplusplus
}
#endif
#endif
