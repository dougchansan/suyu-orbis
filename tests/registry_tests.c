// SPDX-License-Identifier: GPL-2.0-or-later
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include "fixture.h"

static unsigned assertions;
#define CHECK(x) do { ++assertions; if (!(x)) { \
    fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #x); return 1; } } while (0)
static uint64_t bad_entry(void) { return 4096; }
int main(void) {
    SoRegistry r = {0}; SoBlockFn fn = NULL; uint64_t pc = 0;
    CHECK(so_registry_init(NULL, so_fixture_modules, 2) == SO_INVALID_ARGUMENT);
    CHECK(so_registry_init(&r, NULL, 2) == SO_INVALID_ARGUMENT);
    CHECK(so_registry_init(&r, so_fixture_modules, 0) == SO_INVALID_ARGUMENT);
    CHECK(so_registry_init(&r, so_fixture_modules, 14) == SO_INVALID_ARGUMENT);
    SoModule invalid[2] = {so_fixture_modules[1], so_fixture_modules[0]};
    CHECK(so_registry_init(&r, invalid, 2) == SO_INVALID_MODULE_ORDER);
    invalid[0] = so_fixture_modules[0]; invalid[1] = invalid[0];
    CHECK(so_registry_init(&r, invalid, 2) == SO_INVALID_MODULE_ORDER);
    invalid[0].name = "cross2_Release.nss";
    CHECK(so_registry_init(&r, invalid, 1) == SO_INVALID_MODULE_ORDER);
    invalid[0] = so_fixture_modules[0]; invalid[0].lookup = NULL;
    CHECK(so_registry_init(&r, invalid, 1) == SO_INVALID_ARGUMENT);
    CHECK(so_registry_init(&r, so_fixture_modules, 2) == SO_OK);
    CHECK(so_registry_lookup(&r, 0, &fn) == SO_NOT_READY && fn == NULL);
    CHECK(so_registry_seal(&r) == SO_NOT_READY);
    CHECK(so_registry_bind(&r, 0, 1, 16) == SO_INVALID_ARGUMENT);
    CHECK(so_registry_bind(&r, 0, 0, 0) == SO_INVALID_ARGUMENT);
    CHECK(so_registry_bind(&r, 0, 0, 3) == SO_INVALID_ARGUMENT);
    CHECK(so_registry_bind(&r, 0, UINT64_MAX-3, 8) == SO_ADDRESS_OVERFLOW);
    CHECK(so_registry_bind(&r, 2, 0, 16) == SO_INVALID_ARGUMENT);
    CHECK(so_registry_bind(&r, 0, 0x100000, 16) == SO_OK);
    CHECK(so_registry_bind(&r, 0, 0x100000, 16) == SO_ALREADY_BOUND);
    CHECK(so_registry_bind(&r, 1, 0x100004, 16) == SO_OVERLAPPING_MODULES);
    CHECK(so_registry_bind(&r, 1, 0x200000, 16) == SO_OK);
    CHECK(so_registry_seal(&r) == SO_OK);
    CHECK(so_registry_seal(&r) == SO_ALREADY_SEALED);
    CHECK(so_registry_bind(&r, 0, 0x100000, 16) == SO_ALREADY_SEALED);
    CHECK(so_registry_entry(&r, 1, &pc) == SO_OK && pc == 0x200004);
    CHECK(so_registry_lookup(&r, pc, &fn) == SO_OK && fn != NULL);
    struct GuestContext context = {0}; context.x[0] = 40; context.x[30] = 0x400000;
    fn(&context);
    CHECK(context.x[0] == 42 && context.pc == 0x400000);
    CHECK(so_registry_lookup(&r, 0x200005, &fn) == SO_UNALIGNED_PC && fn == NULL);
    CHECK(so_registry_lookup(&r, 0x200008, &fn) == SO_UNCOVERED_PC && fn == NULL);
    CHECK(so_registry_lookup(&r, 0x200010, &fn) == SO_UNCOVERED_PC && fn == NULL);
    CHECK(so_registry_lookup(&r, UINT64_MAX-3, &fn) == SO_UNCOVERED_PC && fn == NULL);
    CHECK(so_registry_lookup(&r, 0x100000, NULL) == SO_INVALID_ARGUMENT);
    CHECK(so_registry_entry(&r, 2, &pc) == SO_INVALID_ARGUMENT);
    CHECK(strcmp(so_result_string(SO_UNCOVERED_PC), "uncovered_pc") == 0);
    CHECK(strcmp(so_result_string((SoResult)999), "unknown") == 0);
    invalid[0] = so_fixture_modules[0]; invalid[0].entry = bad_entry;
    CHECK(so_registry_init(&r, invalid, 1) == SO_OK);
    CHECK(so_registry_bind(&r, 0, 0x100000, 16) == SO_OK);
    CHECK(so_registry_seal(&r) == SO_INVALID_ENTRY);
    CHECK(!r.sealed);
    CHECK(so_registry_init(&r, so_fixture_modules, 2) == SO_OK);
    CHECK(so_registry_bind(&r, 0, 0x200000, 16) == SO_OK);
    CHECK(so_registry_bind(&r, 1, 0x100000, 16) == SO_OK);
    CHECK(so_registry_seal(&r) == SO_INVALID_MODULE_ORDER);
    /* Non-contiguous subsdk suffixes are valid; indices are still consecutive. */
    invalid[0] = so_fixture_modules[0]; invalid[0].name = "subsdk2";
    invalid[1] = so_fixture_modules[1]; invalid[1].name = "sdk";
    CHECK(so_registry_init(&r, invalid, 2) == SO_OK);
    printf("registry: %u assertions passed\n", assertions);
    return 0;
}
