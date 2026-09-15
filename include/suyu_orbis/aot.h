// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef SO_AOT_H
#define SO_AOT_H
#include "suyu_orbis/memory.h"
#include "suyu_orbis/registry.h"
#ifdef __cplusplus
extern "C" {
#endif

typedef struct SoAotMachine SoAotMachine;
typedef uint64_t (*SoAotCounter)(void* user);
typedef enum SoAotResult {
    SO_AOT_BUDGET = 0, SO_AOT_SVC, SO_AOT_HALTED, SO_AOT_UNCOVERED_PC,
    SO_AOT_UNALIGNED_PC, SO_AOT_MEMORY_FAULT, SO_AOT_UNSUPPORTED_HOST_OPERATION,
    SO_AOT_INVALID_ARGUMENT
} SoAotResult;
typedef struct SoAotStats { uint64_t dispatches, svc_yields; } SoAotStats;

/* A portable, single-guest-thread executor for the actual generated Suyu ABI.
 * It neither decodes instructions nor supplies Horizon HLE. SVCs are returned
 * to the caller untouched. Unsupported exclusive-memory operations fail closed;
 * a production shared-memory monitor must be integrated before using them.
 * All use (including mapped backing writes) must be serialized by the owner. */
SoAotMachine* so_aot_create(SoLookupFn lookup, SoAotCounter counter, void* counter_user);
void so_aot_destroy(SoAotMachine*);
SoMemory* so_aot_memory(SoAotMachine*);
struct GuestContext* so_aot_context(SoAotMachine*);
int so_aot_set_reg(SoAotMachine*, unsigned reg, uint64_t value);
uint64_t so_aot_get_reg(const SoAotMachine*, unsigned reg);
int so_aot_set_pc(SoAotMachine*, uint64_t pc);
uint64_t so_aot_pc(const SoAotMachine*);
uint64_t so_aot_pending_svc(const SoAotMachine*);
SoAotStats so_aot_stats(const SoAotMachine*);
SoAotResult so_aot_run(SoAotMachine*, size_t max_dispatches);
/* Resume only after the caller really handled this exact SVC. */
int so_aot_resume(SoAotMachine*, uint64_t expected_svc);
const char* so_aot_result_string(SoAotResult);
#ifdef __cplusplus
}
#endif
#endif
