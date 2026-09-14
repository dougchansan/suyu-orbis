// SPDX-License-Identifier: GPL-2.0-or-later
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "core/arm/recomp/arm_recomp.h"
#include "suyu_orbis/bundle.h"
#include "suyu_bridge.h"
#ifndef SUYU_NO_JIT
#error "The Orbis bridge must link against a SUYU_NO_JIT=ON Suyu core"
#endif
namespace SuyuOrbis {
namespace {
size_t bound_count = 0;
bool attached = false;
[[noreturn]] void Fail(const char* operation, SoResult result) {
    std::fprintf(stderr, "suyu-orbis: %s: %s\n", operation, so_result_string(result));
    std::abort();
}
// Do not call a void(GuestContext*) function through a void(void*) function
// pointer. A typed trampoline bridges the two real upstream ABI signatures.
// This diagnostic bridge performs a second lookup; optimize only after tests.
void Execute(void* raw) {
    uint64_t pc;
    static_assert(offsetof(Core::RecompGuestRegs, pc) == 256);
    std::memcpy(&pc, static_cast<const unsigned char*>(raw) + 256, sizeof pc);
    SoBlockFn block = nullptr;
    SoResult result = so_bundle_lookup(pc, &block);
    if (result != SO_OK) Fail("execute", result);
    block(static_cast<GuestContext*>(raw));
}
Core::RecompBlockFn Lookup(u64 pc) {
    SoBlockFn block = nullptr;
    return so_bundle_lookup(pc, &block) == SO_OK ? Execute : nullptr;
}
void SetBase(size_t index, const char* /* internal_nso_name */, u64 base) {
    SoResult result = so_bundle_bind(index, base);
    if (result != SO_OK) Fail("module base", result);
    if (++bound_count == so_bundle_count()) {
        result = so_bundle_seal();
        if (result != SO_OK) Fail("seal", result);
    }
}
}
SoResult AttachStaticBundle() {
    if (attached) return SO_ALREADY_BOUND;
    SoResult result = so_bundle_init();
    if (result != SO_OK) return result;
    bound_count = 0;
    Core::SetRecompBaseSetter(SetBase);
    Core::SetRecompLookup(Lookup);
    attached = true;
    return SO_OK;
}
void DetachStaticBundle() {
    Core::SetRecompLookup(nullptr);
    Core::SetRecompBaseSetter(nullptr);
    bound_count = 0;
    attached = false;
}
}
