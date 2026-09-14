// SPDX-License-Identifier: GPL-2.0-or-later
#include "fixture.h"
static uint64_t rtld_base, main_base;
static void rtld_block(struct GuestContext* c) { c->x[0] = 40; c->pc = c->x[30]; }
static void main_block(struct GuestContext* c) { c->x[0] += 2; c->pc = c->x[30]; }
static SoBlockFn rtld_lookup(uint64_t pc) { return pc == rtld_base ? rtld_block : NULL; }
static SoBlockFn main_lookup(uint64_t pc) { return pc == main_base + 4 ? main_block : NULL; }
static void rtld_set_base(uint64_t base) { rtld_base = base; }
static void main_set_base(uint64_t base) { main_base = base; }
static uint64_t rtld_entry(void) { return 0; }
static uint64_t main_entry(void) { return 4; }
const SoModule so_fixture_modules[2] = {
    {"rtld", rtld_lookup, rtld_set_base, rtld_entry},
    {"main", main_lookup, main_set_base, main_entry}
};
