// SPDX-License-Identifier: GPL-2.0-or-later
#include <inttypes.h>
#include <stdio.h>
#include "fixture.h"

int main(void) {
    SoRegistry registry = {0};
    struct GuestContext context = {0};
    SoBlockFn block = NULL;
    SoResult result = so_registry_init(&registry, so_fixture_modules, 2);
    if (result == SO_OK) result = so_registry_bind(&registry, 0, 0x100000, 16);
    if (result == SO_OK) result = so_registry_bind(&registry, 1, 0x200000, 16);
    if (result == SO_OK) result = so_registry_seal(&registry);
    for (size_t i = 0; result == SO_OK && i < 2; ++i) {
        result = so_registry_entry(&registry, i, &context.pc);
        if (result == SO_OK) result = so_registry_lookup(&registry, context.pc, &block);
        if (result == SO_OK) {
            context.x[30] = 0x300000;
            block(&context);
        }
    }
    int passed = result == SO_OK && context.x[0] == 42 && context.pc == 0x300000 &&
        so_registry_lookup(&registry, 0x200008, &block) == SO_UNCOVERED_PC && !block;
    char report[512];
    snprintf(report, sizeof report,
        "{\"test\":\"hand_authored_static_registry_fixture\",\"passed\":%s,"
        "\"result\":\"%s\",\"x0\":%" PRIu64 ",\"jit_fallback\":false,"
        "\"suyu_hle_linked\":false,\"game_tested\":false,\"renderer\":\"none\"}\n",
        passed ? "true" : "false", so_result_string(result), context.x[0]);
    fputs(report, stdout);
#ifdef SO_PLATFORM_ORBIS
    /* No display or GPU initialization. Retrieve this file after a device run. */
    FILE* log = fopen("/data/suyu-orbis-probe.json", "w");
    if (!log) return 2;
    int written = fputs(report, log) >= 0;
    int closed = fclose(log) == 0;
    if (!written || !closed) return 2;
#endif
    return passed ? 0 : 1;
}
