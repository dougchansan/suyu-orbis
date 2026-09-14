// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef SUYU_ORBIS_ABI_CONTRACT_H
#define SUYU_ORBIS_ABI_CONTRACT_H
#include <stddef.h>
#include <stdint.h>
/* Include AFTER the actual generated recomp_runtime.h. Never approximate a
 * whole GuestContext by allocating only the register prefix. These offsets
 * are audited against suyu e6f53df9 / arm_recomp.cpp and RuntimeH(). */
#ifdef __cplusplus
#define SO_ABI_ASSERT(expr) static_assert((expr), "Suyu AOT ABI mismatch: " #expr)
#else
#define SO_ABI_ASSERT(expr) _Static_assert((expr), "Suyu AOT ABI mismatch: " #expr)
#endif
SO_ABI_ASSERT(sizeof(void*) == 8);
SO_ABI_ASSERT(offsetof(GuestContext, pc) == 256);
SO_ABI_ASSERT(offsetof(GuestContext, pending_svc) == 304);
SO_ABI_ASSERT(offsetof(GuestContext, vreg) == 312);
SO_ABI_ASSERT(offsetof(GuestContext, tpidr_el0) == 824);
SO_ABI_ASSERT(offsetof(GuestContext, host_mem) == 832);
SO_ABI_ASSERT(offsetof(GuestContext, tpidrro_el0) == 840);
SO_ABI_ASSERT(offsetof(GuestContext, fpcr) == 848);
SO_ABI_ASSERT(offsetof(GuestContext, fpsr) == 856);
SO_ABI_ASSERT(offsetof(GuestContext, chain_budget) == 864);
SO_ABI_ASSERT(offsetof(RecompHostMem, excl_load_pair) == 56);
SO_ABI_ASSERT(offsetof(RecompHostMem, excl_store_pair) == 64);
SO_ABI_ASSERT(offsetof(RecompHostMem, page_entries) == 72);
SO_ABI_ASSERT(offsetof(RecompHostMem, page_entry_stride) == 80);
SO_ABI_ASSERT(offsetof(RecompHostMem, page_bits) == 88);
SO_ABI_ASSERT(offsetof(RecompHostMem, pointer_mask) == 96);
SO_ABI_ASSERT(offsetof(RecompHostMem, address_space_max) == 104);
SO_ABI_ASSERT(sizeof(RecompHostMem) == 112);
#undef SO_ABI_ASSERT
#endif
