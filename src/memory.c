// SPDX-License-Identifier: GPL-2.0-or-later
#include "suyu_orbis/memory.h"
#include <string.h>

void so_memory_init(SoMemory* m) { if (m) memset(m, 0, sizeof(*m)); }
int so_memory_map(SoMemory* m, uint64_t address, void* backing, size_t size, unsigned perms) {
    if (!m || !backing || !size || !perms || (perms & ~3u) || m->faulted ||
        m->count >= SO_MEMORY_MAX_REGIONS || size > UINT64_MAX - address)
        return 0;
    for (size_t i = 0; i < m->count; ++i) {
        const SoMemoryRegion* r = &m->regions[i];
        if (address < r->address + r->size && r->address < address + size) return 0;
    }
    m->regions[m->count++] = (SoMemoryRegion){address, size, backing, perms};
    return 1;
}
static void fault(SoMemory* m, uint64_t address, size_t size, int write) {
    if (m && !m->faulted) {
        m->faulted = 1; m->fault_address = address;
        m->fault_size = size; m->fault_write = write != 0;
    }
}
int so_memory_access(SoMemory* m, uint64_t address, size_t size, int write, void** out) {
    if (out) *out = NULL;
    if (!m || !out || m->faulted) return 0;
    if (!size || size > UINT64_MAX - address) {
        fault(m, address, size, write); return 0;
    }
    for (size_t i = 0; i < m->count; ++i) {
        SoMemoryRegion* r = &m->regions[i];
        if (address < r->address) continue;
        const uint64_t offset = address - r->address;
        if (offset >= r->size) continue;
        const unsigned need = write ? SO_MEMORY_WRITE : SO_MEMORY_READ;
        if (size > r->size - (size_t)offset || !(r->permissions & need)) break;
        *out = r->data + (size_t)offset;
        return 1;
    }
    fault(m, address, size, write); return 0;
}
static int scalar_size(uint32_t size) { return size == 1 || size == 2 || size == 4 || size == 8; }
uint64_t so_memory_load(SoMemory* m, uint64_t address, uint32_t size) {
    if (!m || m->faulted) return 0;
    if (!scalar_size(size)) { fault(m, address, size, 0); return 0; }
    void* raw = NULL;
    if (!so_memory_access(m, address, size, 0, &raw)) return 0;
    const unsigned char* bytes = raw;
    uint64_t value = 0;
    for (uint32_t i = 0; i < size; ++i) value |= (uint64_t)bytes[i] << (8 * i);
    ++m->loads;
    return value;
}
void so_memory_store(SoMemory* m, uint64_t address, uint32_t size, uint64_t value) {
    if (!m || m->faulted) return;
    if (!scalar_size(size)) { fault(m, address, size, 1); return; }
    void* raw = NULL;
    if (!so_memory_access(m, address, size, 1, &raw)) return;
    unsigned char* bytes = raw;
    for (uint32_t i = 0; i < size; ++i) bytes[i] = (unsigned char)(value >> (8 * i));
    ++m->stores;
}
