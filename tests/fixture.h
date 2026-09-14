// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef SO_TEST_FIXTURE_H
#define SO_TEST_FIXTURE_H
#include "suyu_orbis/registry.h"
/* Hand-authored harness context; NOT the full Suyu GuestContext. */
struct GuestContext { uint64_t x[32]; uint64_t pc; };
extern const SoModule so_fixture_modules[2];
#endif
