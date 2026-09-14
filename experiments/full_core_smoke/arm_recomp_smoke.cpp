// SPDX-License-Identifier: GPL-2.0-or-later
#include <cstdint>
#include <iostream>

#include "core/arm/recomp/arm_recomp.h"
#include "core/core.h"
#include "core/hle/kernel/svc.h"
#include "suyu_bridge.h"
#include "suyu_orbis/bundle.h"

namespace {
constexpr std::uint64_t kRtldBase = 0x0010'0000ULL;
constexpr std::uint64_t kMainBase = 0x0020'0000ULL;
constexpr std::uint64_t kReturnSentinel = 0x0030'0000ULL;

int Fail(const char* stage, Core::HaltReason reason = Core::HaltReason::BreakLoop) {
    std::cerr << "{\"test\":\"real_suyu_armrecomp_hle_smoke\",\"passed\":false,"
                 "\"stage\":\""
              << stage << "\",\"halt_reason\":" << static_cast<std::uint64_t>(reason)
              << "}\n";
    SuyuOrbis::DetachStaticBundle();
    return 1;
}
} // namespace

int main() {
#ifndef SUYU_NO_JIT
#error "full-core smoke must be compiled through a SUYU_NO_JIT core"
#endif

    Core::System system;
    system.Initialize();

    if (SuyuOrbis::AttachStaticBundle() != SO_OK) {
        return Fail("attach_bundle");
    }

    // The normal loader invokes the bridge's base callback after mapping every
    // NSO. This synthetic smoke has no KProcess/NSO loader, so bind the two
    // generated images explicitly at deterministic guest addresses. The
    // production callback remains the path tested later with a real process.
    if (so_bundle_count() != 2 || so_bundle_bind(0, kRtldBase) != SO_OK ||
        so_bundle_bind(1, kMainBase) != SO_OK || so_bundle_seal() != SO_OK) {
        return Fail("bind_bundle");
    }

    const auto lookup = Core::GetRecompLookup();
    if (!lookup) {
        return Fail("lookup_hook");
    }

    Kernel::Svc::ThreadContext ctx{};
    ctx.pc = kRtldBase;
    ctx.lr = kMainBase;

    std::uint64_t x0_before_hle = 0;
    std::uint32_t svc_number = 0;
    std::int64_t hle_tick = 0;
    Kernel::Svc::ThreadContext after_svc{};

    {
        // No KProcess or exclusive monitor is needed for this first smoke: the
        // fixture performs no guest memory/exclusive accesses, StepThread does
        // not touch KThread, and this core has no JIT fallback by construction.
        Core::ArmRecomp cpu(system, false, lookup, nullptr, nullptr, 0);
        cpu.SetContext(ctx);

        const Core::HaltReason rtld_reason = cpu.StepThread(nullptr);
        if (rtld_reason != Core::HaltReason::StepThread) {
            return Fail("rtld_step", rtld_reason);
        }
        cpu.GetContext(ctx);
        if (ctx.r[0] != 40 || ctx.pc != kMainBase) {
            return Fail("rtld_context");
        }

        const Core::HaltReason svc_reason = cpu.StepThread(nullptr);
        if (svc_reason != Core::HaltReason::SupervisorCall) {
            return Fail("svc_step", svc_reason);
        }
        svc_number = cpu.GetSvcNumber();
        cpu.GetContext(after_svc);
        x0_before_hle = after_svc.r[0];
        if (svc_number != 0x1e || x0_before_hle != 42 || after_svc.pc != kMainBase + 8) {
            return Fail("svc_context", svc_reason);
        }

        // This is Suyu's actual HLE implementation of svcGetSystemTick, not a
        // test stub. A production scheduler/dispatcher writes the return value
        // to x0; this smoke performs that one ABI write explicitly so we can
        // validate ArmRecomp -> real HLE -> context restore before constructing
        // a full KProcess/KThread.
        hle_tick = Kernel::Svc::GetSystemTick(system);
        after_svc.r[0] = static_cast<std::uint64_t>(hle_tick);
        after_svc.lr = kReturnSentinel;
    }

    // StepThread intentionally leaves its private pending-SVC latch set. A real
    // scheduler clears it via RunThread on resume. Restoring the architectural
    // ThreadContext into a fresh ArmRecomp instance is the smallest truthful
    // way to validate the same state transition without inventing a KThread.
    Kernel::Svc::ThreadContext final_ctx{};
    {
        Core::ArmRecomp resumed(system, false, lookup, nullptr, nullptr, 0);
        resumed.SetContext(after_svc);
        const Core::HaltReason ret_reason = resumed.StepThread(nullptr);
        if (ret_reason != Core::HaltReason::StepThread) {
            return Fail("resume_step", ret_reason);
        }
        resumed.GetContext(final_ctx);
    }

    const auto live = Core::GetRecompLiveStats();
    if (final_ctx.pc != kReturnSentinel ||
        final_ctx.r[0] != static_cast<std::uint64_t>(hle_tick) || live.jit_available) {
        return Fail("final_context");
    }

    std::cout << "{\"test\":\"real_suyu_armrecomp_hle_smoke\",\"passed\":true,"
                 "\"x0_before_hle\":"
              << x0_before_hle << ",\"svc\":" << svc_number << ",\"hle_tick\":" << hle_tick
              << ",\"final_pc\":" << final_ctx.pc
              << ",\"jit_available\":false,\"scheduler_dispatch\":false,"
                 "\"context_restore_resume\":true,\"game_tested\":false}\n";

    SuyuOrbis::DetachStaticBundle();
    return 0;
}
