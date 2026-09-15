// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef SO_MEMORY_H
#define SO_MEMORY_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

enum { SO_MEMORY_READ = 1, SO_MEMORY_WRITE = 2, SO_MEMORY_MAX_REGIONS = 16 };
typedef struct SoMemoryRegion {
    uint64_t address;
    size_t size;
    unsigned char* data;
    unsigned permissions;
} SoMemoryRegion;
typedef struct SoMemory {
    SoMemoryRegion regions[SO_MEMORY_MAX_REGIONS];
    size_t count;
    uint64_t loads, stores;
    uint64_t fault_address;
    size_t fault_size;
    int faulted, fault_write;
} SoMemory;

/* Single-owner address space. Backing storage remains owned by the caller and
 * must outlive the mappings. This does not implement a shared guest page table,
 * concurrent mappings, GPU cache tracking, or a Horizon memory manager.
 * A scalar access must fit in one region. Faults are sticky and fail closed. */
void so_memory_init(SoMemory* memory);
int so_memory_map(SoMemory*, uint64_t address, void* backing, size_t size, unsigned permissions);
int so_memory_access(SoMemory*, uint64_t address, size_t size, int write, void** out);
uint64_t so_memory_load(SoMemory*, uint64_t address, uint32_t size);
void so_memory_store(SoMemory*, uint64_t address, uint32_t size, uint64_t value);
#ifdef __cplusplus
}
#endif
#endif
