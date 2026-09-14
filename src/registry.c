// SPDX-License-Identifier: GPL-2.0-or-later
#include "suyu_orbis/registry.h"
#include <string.h>

static int module_rank(const char* name) {
    if (!name) return -1;
    if (strcmp(name, "rtld") == 0) return 0;
    if (strcmp(name, "main") == 0) return 1;
    if (strcmp(name, "sdk") == 0) return 12;
    if (strlen(name) == 7 && strncmp(name, "subsdk", 6) == 0 &&
        name[6] >= '0' && name[6] <= '9') return 2 + name[6] - '0';
    return -1;
}
SoResult so_registry_init(SoRegistry* registry, const SoModule* modules, size_t count) {
    if (!registry || !modules || count == 0 || count > SO_MAX_MODULES)
        return SO_INVALID_ARGUMENT;
    SoRegistry next = {0};
    int previous = -1;
    for (size_t i = 0; i < count; ++i) {
        int rank = module_rank(modules[i].name);
        if (rank < 0 || rank <= previous) return SO_INVALID_MODULE_ORDER;
        if (!modules[i].lookup || !modules[i].set_base || !modules[i].entry)
            return SO_INVALID_ARGUMENT;
        next.modules[i].module = modules[i];
        previous = rank;
    }
    next.count = count;
    *registry = next;
    return SO_OK;
}
SoResult so_registry_bind(SoRegistry* registry, size_t index,
                          uint64_t base, uint64_t text_size) {
    if (!registry || index >= registry->count) return SO_INVALID_ARGUMENT;
    if (registry->sealed) return SO_ALREADY_SEALED;
    if (registry->modules[index].bound) return SO_ALREADY_BOUND;
    if ((base & 3) || (text_size & 3) || text_size == 0) return SO_INVALID_ARGUMENT;
    if (base > UINT64_MAX - text_size) return SO_ADDRESS_OVERFLOW;
    for (size_t i = 0; i < registry->count; ++i) {
        const SoLoadedModule* other = &registry->modules[i];
        if (other->bound && base < other->base + other->text_size &&
            other->base < base + text_size) return SO_OVERLAPPING_MODULES;
    }
    SoLoadedModule* loaded = &registry->modules[index];
    loaded->base = base;
    loaded->text_size = text_size;
    loaded->bound = 1;
    return SO_OK;
}
SoResult so_registry_seal(SoRegistry* registry) {
    if (!registry || registry->count == 0) return SO_INVALID_ARGUMENT;
    if (registry->sealed) return SO_ALREADY_SEALED;
    /* Validate EVERYTHING before touching the emitter's global load bases. */
    for (size_t i = 0; i < registry->count; ++i) {
        const SoLoadedModule* m = &registry->modules[i];
        if (!m->bound) return SO_NOT_READY;
        uint64_t offset = m->module.entry();
        if ((offset & 3) || offset >= m->text_size) return SO_INVALID_ENTRY;
        if (i && registry->modules[i-1].base >= m->base)
            return SO_INVALID_MODULE_ORDER;
    }
    for (size_t i = 0; i < registry->count; ++i) {
        SoLoadedModule* m = &registry->modules[i];
        m->module.set_base(m->base); /* Also builds the upstream index. */
    }
    registry->sealed = 1;
    return SO_OK;
}
SoResult so_registry_lookup(const SoRegistry* registry, uint64_t pc, SoBlockFn* out) {
    if (!out) return SO_INVALID_ARGUMENT;
    *out = NULL;
    if (!registry) return SO_INVALID_ARGUMENT;
    if (!registry->sealed) return SO_NOT_READY;
    /* Upstream's dense index shifts by 2: without this guard PC+1 could alias
     * a valid block. Do not let an invalid PC execute that block. */
    if (pc & 3) return SO_UNALIGNED_PC;
    for (size_t i = 0; i < registry->count; ++i) {
        const SoLoadedModule* m = &registry->modules[i];
        if (pc >= m->base && pc - m->base < m->text_size) {
            *out = m->module.lookup(pc);
            return *out ? SO_OK : SO_UNCOVERED_PC;
        }
    }
    return SO_UNCOVERED_PC; /* No interpreter or JIT fallback. */
}
SoResult so_registry_entry(const SoRegistry* registry, size_t index, uint64_t* out) {
    if (!out || !registry || index >= registry->count) return SO_INVALID_ARGUMENT;
    if (!registry->sealed) return SO_NOT_READY;
    const SoLoadedModule* m = &registry->modules[index];
    *out = m->base + m->module.entry();
    return SO_OK;
}
const char* so_result_string(SoResult result) {
    static const char* const names[] = {
        "ok", "invalid_argument", "invalid_module_order", "address_overflow",
        "overlapping_modules", "not_ready", "already_bound", "already_sealed",
        "unaligned_pc", "uncovered_pc", "invalid_entry"
    };
    return (unsigned)result < sizeof(names)/sizeof(names[0]) ? names[result] : "unknown";
}
