// SPDX-License-Identifier: GPL-2.0-or-later
// Original AArch64 on Suyu's real process/thread scheduler and SVC dispatcher.
// The observer only reads execution state and forwards to the existing bridge.
#include <array>
#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <iterator>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>
#include <nlohmann/json.hpp>
#include "common/logging.h"
#include "common/settings.h"
#include "core/arm/recomp/arm_recomp.h"
#include "core/core.h"
#include "core/core_timing.h"
#include "core/cpu_manager.h"
#include "core/file_sys/program_metadata.h"
#include "core/hle/kernel/code_set.h"
#include "core/hle/kernel/svc_common.h"
#include "core/hle/kernel/svc_results.h"
#include "core/hle/kernel/k_process.h"
#include "core/hle/kernel/k_synchronization_object.h"
#include "core/hle/kernel/k_thread.h"
#include "core/hle/kernel/kernel.h"
#include "core/memory.h"
#include "suyu_bridge.h"
#include "suyu_orbis/bundle.h"
#include "recomp_runtime.h"
#include "program.h"
#ifndef SUYU_NO_JIT
#error "Scheduled process smoke requires a real SUYU_NO_JIT core"
#endif
namespace {
using json = nlohmann::json;
const char* stage = "startup";
void Stage(const char* s) {
    stage = s;
    std::fprintf(stderr, "[process-smoke] %s\n", s);
    std::fflush(stderr);
}
void Require(bool value, const char* why) {
    if (!value) throw std::runtime_error(why);
}
void Check(Result value, const char* why) {
    if (value.IsError()) {
        std::fprintf(stderr, "[process-smoke] %s: result=%#x\n", why, value.raw);
        throw std::runtime_error(why);
    }
}
struct Observation {
    std::uint64_t pc, resume_pc, svc, thread_id, process_id, host_ns;
    std::uint32_t core;
};
struct Observer {
    Core::System* system{};
    Kernel::KProcess* process{};
    Kernel::KThread* thread{};
    Core::ArmInterface* cpu{};
    Core::RecompLookupFn underlying{};
    void* first_context{};
    bool identities_ok = true;
    bool latch_ok = true;
    std::mutex mutex;
    std::vector<Observation> blocks;
} observer;
std::uint64_t Read64(const void* raw, std::size_t off) {
    std::uint64_t value;
    std::memcpy(&value, static_cast<const unsigned char*>(raw)+off, sizeof value);
    return value;
}
void ObserveExecute(void* raw) {
    const auto pc = Read64(raw, offsetof(GuestContext, pc));
    const auto pending_before = Read64(raw, offsetof(GuestContext, pending_svc));
    auto& kernel = observer.system->Kernel();
    auto* thread = Kernel::GetCurrentThreadPointer(kernel);
    const auto core = kernel.CurrentPhysicalCoreIndex();
    auto* process = thread->GetOwnerProcess();
    auto* cpu = process ? process->GetArmInterface(core) : nullptr;
    const auto block = observer.underlying(pc);
    if (!block) std::abort();
    block(raw); // The real generated code alone writes CPU state/guest memory.
    const auto next_pc = Read64(raw, offsetof(GuestContext, pc));
    const auto svc = Read64(raw, offsetof(GuestContext, pending_svc));
    std::scoped_lock lock(observer.mutex);
    if (observer.blocks.size() >= 1024) std::abort();
    if (!observer.first_context) observer.first_context = raw;
    observer.identities_ok &= thread == observer.thread && process == observer.process &&
                              cpu == observer.cpu && raw == observer.first_context && core == 0;
    observer.latch_ok &= pending_before == UINT64_MAX;
    observer.blocks.push_back({pc,next_pc,svc,thread->GetThreadId(),
                               process ? process->GetProcessId() : 0,
                               static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                                   std::chrono::steady_clock::now().time_since_epoch()).count()),
                               static_cast<std::uint32_t>(core)});
}
Core::RecompBlockFn ObservedLookup(std::uint64_t pc) {
    return observer.underlying(pc) ? ObserveExecute : nullptr;
}
template <std::size_t N>
Kernel::CodeSet MakeModule(const char* name, const std::array<std::uint32_t,N>& words) {
    Kernel::CodeSet code;
    code.memory.resize(ProcessFixture::kModuleStride,0);
    code.CodeSegment() = {0,0,0x1000};
    code.RODataSegment() = {0x1000,0x1000,0x1000};
    code.DataSegment() = {0x2000,0x2000,0x2000};
    static_assert(sizeof(words) <= 0x1000);
    std::memcpy(code.memory.data(),words.data(),sizeof words);
    // FindModules discovers executable maps and the following RO path record.
    const std::uint32_t length = static_cast<std::uint32_t>(std::strlen(name));
    std::memcpy(code.memory.data()+0x1004,&length,sizeof length);
    std::memcpy(code.memory.data()+0x1008,name,length);
    return code;
}
}
int main() {
    // Keep ownership outside try: failure emits its stage before fail-fast
    // process exit instead of hanging in teardown of a partially started kernel.
    std::unique_ptr<Core::System> owner;
    try {
        Common::Log::Initialize();
        Common::Log::SetGlobalFilter(Common::Log::Filter(Common::Log::Level::Info));
        Common::Log::Start();
        Settings::values.use_multi_core = true;
        Settings::values.use_asynchronous_gpu_emulation = true;
        Settings::values.memory_layout_mode = Settings::MemoryLayout::Memory_4Gb;
        owner = std::make_unique<Core::System>();
        auto& system = *owner;
        Stage("initialize_system_and_kernel");
        system.Initialize();
        auto& kernel = system.Kernel();
        kernel.Initialize();
        Stage("attach_static_images");
        Require(SuyuOrbis::AttachStaticBundle()==SO_OK,"attach_static_bundle");
        observer.system=&system;
        observer.underlying=Core::GetRecompLookup();
        Require(observer.underlying!=nullptr,"missing_static_lookup");
        Core::SetRecompLookup(ObservedLookup);
        Stage("create_real_application_process");
        auto* process=Kernel::KProcess::Create(kernel);
        Require(process!=nullptr,"allocate_KProcess");
        auto metadata=FileSys::ProgramMetadata::GetDefault();
        Check(process->LoadFromMetadata(kernel,metadata,2*ProcessFixture::kModuleStride,0,0),"LoadFromMetadata");
        Kernel::KProcess::Register(kernel,process);
        kernel.AppendNewProcess(process);
        kernel.MakeApplicationProcess(process);
        Require(process->IsApplication()&&process->Is64Bit(),"real_AArch64_application");
        observer.process=process;
        observer.cpu=process->GetArmInterface(0);
        Require(observer.cpu!=nullptr,"process_owned_ArmRecomp");
        const auto rtld=GetInteger(process->GetEntryPoint());
        const auto main_base=rtld+ProcessFixture::kModuleStride;
        const auto output=main_base+ProcessFixture::kOutputOffset;
        Stage("map_original_modules_with_real_page_table");
        process->LoadModule(kernel,MakeModule("rtld",ProcessFixture::kRtld),rtld);
        process->LoadModule(kernel,MakeModule("main",ProcessFixture::kMain),main_base);
        Require(process->GetMemory().IsValidVirtualAddressRange(output,112),"mapped_output_page");
        Stage("create_real_main_thread");
        Check(process->Run(kernel,metadata.GetMainThreadPriority(),0x10000),"KProcess_Run");
        auto& threads=process->GetThreadList();
        Require(std::distance(threads.begin(),threads.end())==1,"one_main_thread");
        auto* thread=&threads.front();
        thread->Open(kernel);
        observer.thread=thread;
        const auto thread_id=thread->GetThreadId();
        const auto process_id=process->GetProcessId();
        const auto tls=GetInteger(thread->GetTlsAddress());
        const auto handle=thread->GetContext().r[1];
        const auto stack=thread->GetContext().sp;
        // Initial test-loader entry only, BEFORE any CPU thread is started.
        // The limited-smoke prefix remains intact at main+0. There are NO
        // test-side architectural writes once the scheduler starts.
        thread->GetContext().pc=main_base+ProcessFixture::kEntryOffset;
        Require(process->GetMemory().Read32(tls+0x110)==handle,"kernel_TLS_handle");
        // Observe only the atomic state; do not manipulate scheduler decisions.
        std::atomic<bool> saw_waiting{false};
        std::jthread waiter_observer([&](std::stop_token stop) {
            while (!stop.stop_requested()) {
                if (thread->GetState()==Kernel::ThreadState::Waiting) saw_waiting.store(true);
                std::this_thread::sleep_for(std::chrono::microseconds(250));
            }
        });
        Stage("start_real_scheduler_and_cpu_threads");
        system.GetCpuManager().Initialize();
        system.Run();
        // Kernel-only fixture: release the normal CPU startup barrier. No GPU
        // or service emulation replacement is constructed/claimed here.
        system.GetCpuManager().OnGpuReady();
        Stage("wait_for_normal_guest_thread_exit");
        Kernel::KSynchronizationObject* objects[]={thread};
        std::int32_t index=-1;
        Check(Kernel::KSynchronizationObject::Wait(kernel,&index,objects,1,Kernel::Svc::WaitInfinite),"wait_thread_exit");
        Require(index==0&&thread->GetState()==Kernel::ThreadState::Terminated,"normal_ExitThread");
        waiter_observer.request_stop();
        waiter_observer.join();
        Stage("verify_guest_written_results");
        std::array<std::uint64_t,14> values{};
        for(std::size_t i=0;i<values.size();++i)values[i]=process->GetMemory().Read64(output+i*8);
        const auto live=Core::GetRecompLiveStats();
        std::vector<std::uint32_t> svcs;
        json trace=json::array();
        bool ids_ok,latch_ok;
        std::uint64_t sleep_start_ns=0, sleep_resume_ns=0;
        {
            std::scoped_lock lock(observer.mutex);
            ids_ok=observer.identities_ok; latch_ok=observer.latch_ok;
            for(const auto& b:observer.blocks) {
                if (sleep_start_ns && !sleep_resume_ns) sleep_resume_ns=b.host_ns;
                if (b.svc==0x0b) sleep_start_ns=b.host_ns;
                if(b.svc!=UINT64_MAX)svcs.push_back(static_cast<std::uint32_t>(b.svc));
                trace.push_back({{"pc",b.pc},{"resume_pc",b.resume_pc},{"pending_svc",b.svc},
                                 {"thread_id",b.thread_id},{"process_id",b.process_id},{"core",b.core}});
            }
        }
        const bool passed=values[0]==42&&values[1]==tls&&values[2]==handle&&values[3]>0&&
            values[4]==0&&values[5]==thread_id&&values[6]==0&&values[7]==process_id&&
            values[8]==0&&values[9]==Kernel::ResultInvalidHandle.raw&&values[10]>=values[3]&&
            values[11]==tls&&values[12]==ProcessFixture::kDone&&values[13]==stack&&
            ids_ok&&latch_ok&&saw_waiting.load()&&sleep_resume_ns>sleep_start_ns&&
            !live.jit_available&&live.jit_transitions==0&&live.static_blocks>0&&
            svcs==std::vector<std::uint32_t>(ProcessFixture::kExpectedSvcs.begin(),ProcessFixture::kExpectedSvcs.end());
        json result={{"test","real_suyu_scheduled_process_svc"},{"passed",passed},
            {"scheduler_dispatch",true},{"normal_svc_dispatch",true},{"same_cpu_instance",ids_ok},
            {"pending_svc_cleared_on_resume",latch_ok},{"guest_memory_verified",passed},
            {"thread_exited",true},{"observed_waiting",saw_waiting.load()},
            {"sleep_resume_interval_ns",sleep_resume_ns-sleep_start_ns},{"thread_id",thread_id},{"process_id",process_id},
            {"thread_handle",handle},{"tls",tls},{"guest_values",values},{"svcs",svcs},{"trace",trace},
            {"jit_available",live.jit_available},{"jit_transitions",live.jit_transitions},
            {"static_blocks",live.static_blocks},{"real_title_loader",false},
            {"renderer","none"},{"orbis_execution",false},{"game_tested",false}};
        Stage("shutdown_real_kernel");
        thread->Close(kernel); process->Close(kernel);
        system.ShutdownMainProcess();
        SuyuOrbis::DetachStaticBundle();
        owner.reset();
        Common::Log::Stop();
        result["clean_shutdown"]=true;
        std::cout<<result.dump()<<std::endl;
        return passed?0:1;
    } catch(const std::exception& e) {
        std::cerr<<json({{"test","real_suyu_scheduled_process_svc"},{"passed",false},
                         {"stage",stage},{"error",e.what()}}).dump()<<std::endl;
        std::_Exit(1);
    }
}
