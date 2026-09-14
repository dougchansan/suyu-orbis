// SPDX-License-Identifier: GPL-2.0-or-later
#include <stdio.h>
#include <string.h>
#include "recomp_runtime.h"
#include "suyu_orbis/abi_contract.h"
#include "suyu_orbis/bundle.h"
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "upstream smoke line %d: %s\n", __LINE__, #x); return 1; } } while (0)
static uint64_t stored;
static unsigned stores;
static uint64_t load(void* user, uint64_t va, uint32_t size) {
    (void)user; (void)va; (void)size; return stored;
}
static void store(void* user, uint64_t va, uint32_t size, uint64_t value) {
    (void)user;
    if (va == 0x400000 && size == 8) { stored = value; ++stores; }
}
int main(void) {
    CHECK(so_bundle_count() == 2);
    CHECK(so_bundle_init() == SO_OK);
    CHECK(so_bundle_bind(0, 0x100000) == SO_OK);
    CHECK(so_bundle_bind(1, 0x200000) == SO_OK);
    CHECK(so_bundle_seal() == SO_OK);
    /* Allocate the ACTUAL generated context, including its private tail. */
    GuestContext c; memset(&c, 0, sizeof c);
    RecompHostMem memory; memset(&memory, 0, sizeof memory);
    memory.load = load; memory.store = store;
    c.host_mem = &memory;
    c.pending_svc = UINT64_MAX;
    c.x[1] = 0x400000; c.x[30] = 0x300000;
    c.chain_budget = 1;
    SoBlockFn block = NULL;
    CHECK(so_bundle_entry(0, &c.pc) == SO_OK && c.pc == 0x100000);
    CHECK(so_bundle_lookup(c.pc, &block) == SO_OK); block(&c);
    CHECK(c.x[0] == 40 && c.pc == 0x300000 && c.pending_svc == UINT64_MAX);
    CHECK(so_bundle_entry(1, &c.pc) == SO_OK && c.pc == 0x200000);
    c.chain_budget = 1;
    CHECK(so_bundle_lookup(c.pc, &block) == SO_OK); block(&c);
    CHECK(c.x[0] == 42 && stored == 42 && stores == 1);
    CHECK(c.pending_svc == 0x11 && c.pc == 0x20000c);
    /* The host observes the SVC. No fake success handler services it. */
    c.pending_svc = UINT64_MAX;
    c.chain_budget = 1;
    CHECK(so_bundle_lookup(c.pc, &block) == SO_OK); block(&c);
    CHECK(c.pc == 0x300000);
    CHECK(so_bundle_lookup(0x200001, &block) == SO_UNALIGNED_PC && !block);
    CHECK(so_bundle_lookup(0x300000, &block) == SO_UNCOVERED_PC && !block);
    const char* report = "{\"test\":\"suyu_emitted_synthetic_aarch64\",\"passed\":true,"
        "\"modules\":2,\"x0\":42,\"host_store\":42,\"svc\":17,"
        "\"suyu_hle_linked\":false,\"game_tested\":false}\n";
    fputs(report, stdout);
#ifdef SO_PLATFORM_ORBIS
    FILE* log = fopen("/data/suyu-orbis-upstream-smoke.json", "w");
    if (!log) return 2;
    int written = fputs(report, log) >= 0;
    int closed = fclose(log) == 0;
    if (!written || !closed) return 2;
#endif
    return 0;
}
