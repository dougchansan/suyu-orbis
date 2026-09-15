// SPDX-License-Identifier: GPL-2.0-or-later
#include "suyu_orbis/memory.h"
#include <stdio.h>
#include <string.h>
#define CHECK(e) do { ++checks; if (!(e)) { fprintf(stderr,"line %d: %s\n",__LINE__,#e); return 1; } } while (0)
int main(void) {
    unsigned checks = 0;
    unsigned char b[32] = {0}; SoMemory m; void* pointer = NULL;
    so_memory_init(&m);
    CHECK(!so_memory_map(&m, UINT64_MAX-7, b, 8, 3));
    CHECK(!so_memory_map(&m, 0x1000, b, 0, 3));
    CHECK(!so_memory_map(&m, 0x1000, b, sizeof b, 4));
    CHECK(so_memory_map(&m, 0x1000, b, sizeof b, 3));
    CHECK(!so_memory_map(&m, 0x1004, b, 4, 3));
    for (unsigned size = 1; size <= 8; size *= 2) {
        uint64_t value = UINT64_C(0xfedcba9876543210);
        const uint64_t mask = size == 8 ? UINT64_MAX : ((UINT64_C(1) << (8*size))-1);
        so_memory_store(&m, 0x1001, size, value);
        CHECK(so_memory_load(&m, 0x1001, size) == (value & mask));
    }
    CHECK(b[1] == 0x10 && b[8] == 0xfe);
    CHECK(m.loads == 4 && m.stores == 4);
    CHECK(so_memory_access(&m, 0x101f, 1, 1, &pointer) && pointer == &b[31]);
    CHECK(!so_memory_access(&m, 0x101f, 2, 1, &pointer) && !pointer);
    CHECK(m.faulted && m.fault_address == 0x101f && m.fault_size == 2 && m.fault_write);
    unsigned char copy[32]; memcpy(copy,b,sizeof b);
    so_memory_store(&m,0x1000,4,0);
    CHECK(!memcmp(copy,b,sizeof b) && m.stores == 4);
    CHECK(so_memory_load(&m,0x1000,4) == 0 && m.loads == 4);
    so_memory_init(&m); CHECK(so_memory_map(&m,0x1000,b,sizeof b,SO_MEMORY_READ));
    CHECK(so_memory_load(&m,0x1001,1) == 0x10);
    so_memory_store(&m,0x1001,1,0xff);
    CHECK(m.faulted && b[1] == 0x10);
    so_memory_init(&m); CHECK(so_memory_map(&m,0,b,sizeof b,SO_MEMORY_WRITE));
    CHECK(!so_memory_access(&m,0,1,0,&pointer) && m.faulted);
    so_memory_init(&m);
    CHECK(!so_memory_access(&m,UINT64_MAX-3,8,0,&pointer));
    CHECK(m.faulted && m.fault_address == UINT64_MAX-3);
    so_memory_init(&m); CHECK(so_memory_map(&m,0,b,sizeof b,3));
    so_memory_store(&m,0,3,0);
    CHECK(m.faulted && m.fault_size == 3);
    so_memory_init(&m);
    for (unsigned i=0; i<SO_MEMORY_MAX_REGIONS; ++i)
        CHECK(so_memory_map(&m,0x1000+i*0x100,b,1,3));
    CHECK(!so_memory_map(&m,0x3000,b,1,3));
    printf("memory: %u assertions passed\n",checks);
    return 0;
}
