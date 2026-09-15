// SPDX-License-Identifier: GPL-2.0-or-later
#include <stdlib.h>
#include "recomp_runtime.h"
#include "suyu_orbis/abi_contract.h"
#include "suyu_orbis/aot.h"

struct SoAotMachine {
    GuestContext cpu; /* Full generated structure, including its private tail. */
    RecompHostMem bridge;
    SoMemory memory;
    SoLookupFn lookup;
    SoAotCounter counter;
    void* counter_user;
    SoAotStats stats;
    int unsupported;
};
static uint64_t load(void* user, uint64_t va, uint32_t size) {
    SoAotMachine* m = user;
    uint64_t value = so_memory_load(&m->memory, va, size);
    if (m->memory.faulted) m->cpu.halted = 1;
    return value;
}
static void store(void* user, uint64_t va, uint32_t size, uint64_t value) {
    SoAotMachine* m = user;
    so_memory_store(&m->memory, va, size, value);
    if (m->memory.faulted) m->cpu.halted = 1;
}
static void unsupported(void* user) {
    SoAotMachine* m = user;
    m->unsupported = 1;
    m->cpu.halted = 1;
}
static uint64_t excl_load(void* u, uint64_t va, uint32_t size) {
    (void)va; (void)size; unsupported(u); return 0;
}
static uint32_t excl_store(void* u, uint64_t va, uint32_t size, uint64_t value) {
    (void)va; (void)size; (void)value; unsupported(u); return 1;
}
static void excl_pair_load(void* u, uint64_t va, uint32_t size, uint64_t* lo, uint64_t* hi) {
    (void)va; (void)size;
    if (lo) *lo = 0;
    if (hi) *hi = 0;
    unsupported(u);
}
static uint32_t excl_pair_store(void* u, uint64_t va, uint32_t size, uint64_t lo, uint64_t hi) {
    (void)va; (void)size; (void)lo; (void)hi; unsupported(u); return 1;
}
static uint64_t counter(void* user) {
    SoAotMachine* m = user;
    if (!m->counter) { unsupported(user); return 0; }
    return m->counter(m->counter_user);
}
SoAotMachine* so_aot_create(SoLookupFn lookup, SoAotCounter clock, void* clock_user) {
    if (!lookup) return NULL;
    SoAotMachine* m = calloc(1, sizeof(*m));
    if (!m) return NULL;
    m->lookup = lookup; m->counter = clock; m->counter_user = clock_user;
    m->bridge.user = m;
    m->bridge.load = load; m->bridge.store = store;
    m->bridge.excl_load = excl_load; m->bridge.excl_store = excl_store;
    m->bridge.clear_excl = unsupported;
    m->bridge.excl_load_pair = excl_pair_load; m->bridge.excl_store_pair = excl_pair_store;
    m->bridge.read_cntpct = counter;
    /* No inline host page table: every access must pass region checks. */
    m->cpu.host_mem = &m->bridge;
    m->cpu.pending_svc = UINT64_MAX;
    return m;
}
void so_aot_destroy(SoAotMachine* m) { free(m); }
SoMemory* so_aot_memory(SoAotMachine* m) { return m ? &m->memory : NULL; }
struct GuestContext* so_aot_context(SoAotMachine* m) { return m ? &m->cpu : NULL; }
int so_aot_set_reg(SoAotMachine* m, unsigned reg, uint64_t value) {
    if (!m || reg >= 32) return 0;
    m->cpu.x[reg] = value; return 1;
}
uint64_t so_aot_get_reg(const SoAotMachine* m, unsigned reg) {
    return m && reg < 32 ? m->cpu.x[reg] : 0;
}
int so_aot_set_pc(SoAotMachine* m, uint64_t pc) {
    if (!m || m->cpu.pending_svc != UINT64_MAX) return 0;
    m->cpu.pc = pc; return 1;
}
uint64_t so_aot_pc(const SoAotMachine* m) { return m ? m->cpu.pc : 0; }
uint64_t so_aot_pending_svc(const SoAotMachine* m) { return m ? m->cpu.pending_svc : UINT64_MAX; }
SoAotStats so_aot_stats(const SoAotMachine* m) { return m ? m->stats : (SoAotStats){0,0}; }
static SoAotResult state(const SoAotMachine* m) {
    if (m->memory.faulted) return SO_AOT_MEMORY_FAULT;
    if (m->unsupported) return SO_AOT_UNSUPPORTED_HOST_OPERATION;
    if (m->cpu.halted) return SO_AOT_HALTED;
    if (m->cpu.pending_svc != UINT64_MAX) return SO_AOT_SVC;
    return SO_AOT_BUDGET;
}
SoAotResult so_aot_run(SoAotMachine* m, size_t max_dispatches) {
    if (!m || !max_dispatches) return SO_AOT_INVALID_ARGUMENT;
    SoAotResult result = state(m);
    if (result != SO_AOT_BUDGET) return result;
    for (size_t i = 0; i < max_dispatches; ++i) {
        if (m->cpu.pc & 3) return SO_AOT_UNALIGNED_PC;
        SoBlockFn block = m->lookup(m->cpu.pc);
        if (!block) return SO_AOT_UNCOVERED_PC;
        /* Bounded direct chaining; count dispatcher entries, not instructions. */
        m->cpu.chain_budget = 1;
        block(&m->cpu);
        ++m->stats.dispatches;
        result = state(m);
        if (result == SO_AOT_SVC) ++m->stats.svc_yields;
        if (result != SO_AOT_BUDGET) return result;
    }
    return SO_AOT_BUDGET;
}
int so_aot_resume(SoAotMachine* m, uint64_t expected_svc) {
    if (!m || state(m) != SO_AOT_SVC || expected_svc == UINT64_MAX ||
        m->cpu.pending_svc != expected_svc) return 0;
    m->cpu.pending_svc = UINT64_MAX;
    return 1;
}
const char* so_aot_result_string(SoAotResult value) {
    static const char* const names[] = {"budget", "svc", "halted", "uncovered_pc", "unaligned_pc",
        "memory_fault", "unsupported_host_operation", "invalid_argument"};
    return (unsigned)value < sizeof(names)/sizeof(names[0]) ? names[value] : "unknown";
}
