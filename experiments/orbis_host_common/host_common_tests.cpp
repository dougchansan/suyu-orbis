// SPDX-License-Identifier: GPL-2.0-or-later
// Real pinned Suyu Common components, not a replacement guest scheduler.
#include "common/fiber.h"
#include "common/host_memory.h"
#include "common/steady_clock.h"
#include "common/virtual_buffer.h"
#include "host_support.h"
#include <array>
#include <atomic>
#include <cfenv>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <limits>
#include <memory>
#include <mutex>
#include <thread>
#include <utility>
#ifdef SO_PLATFORM_ORBIS
#include <orbis/libkernel.h>
#endif
namespace {
std::atomic<unsigned> checks{};
const char* stage="startup";
void Require(bool condition,const char* text) {
    checks.fetch_add(1);
    if (!condition) SuyuOrbis::Host::Fatal(text);
}
void Stage(const char* name) {
    stage=name;
    std::fprintf(stderr,"[host-common] %s\n",name);std::fflush(stderr);
#ifdef SO_PLATFORM_ORBIS
    if (FILE* f=std::fopen("/data/orbis-host-stage.txt","w")) {
        std::fprintf(f,"%s\n",name);std::fclose(f);
    }
#endif
}
thread_local unsigned tls_cookie=0;
void Pages() {
    Stage("real_virtual_buffer");
    using SuyuOrbis::Host::GetPageStats;
    const auto baseline=GetPageStats();
    std::size_t total=123;
    Require(!SuyuOrbis::Host::PageAllocationSize(0,total)&&!total,"zero-size policy");
    Require(!SuyuOrbis::Host::PageAllocationSize(std::numeric_limits<std::size_t>::max(),total),"overflow rejected");
    Require(Common::AllocateMemoryPages(0)==nullptr,"empty buffer has no mapping");
    for (std::size_t size : {1U,4095U,4096U,16383U,16384U,16385U,1048576U}) {
        Common::VirtualBuffer<unsigned char> a(size);
        Require(a.size()==size && a.data(),"VirtualBuffer allocation");
#ifdef SO_PLATFORM_ORBIS
        Require((reinterpret_cast<std::uintptr_t>(a.data())&0x3fff)==0,"16 KiB target alignment");
#endif
        for (std::size_t i=0;i<size;++i) Require(a[i]==0,"zero initialized backing");
        a[0]=0x25; a[size-1]=0x51;
        Common::VirtualBuffer<unsigned char> b(17);
        auto* original=a.data();
        const auto before=GetPageStats().live_allocations;
        b=std::move(a);
        Require(b.data()==original && !a.data() && !a.size(),"move ownership");
        Require(GetPageStats().live_allocations+1==before,"move assignment releases old pages");
        auto* self=&b;
        b=std::move(*self);
        Require(b.data()==original && b.size()==size,"self move retains ownership");
        Require(b[size-1]==0x51,"last byte survived move");
        b.resize(0);
        Require(!b.data() && b.size()==0,"resize empty releases pages");
    }
    Require(GetPageStats().live_allocations==baseline.live_allocations &&
            GetPageStats().live_bytes==baseline.live_bytes,"all direct pages released");
    Stage("real_host_memory_no_fastmem");
    {
        Common::HostMemory backing(1<<20,UINT64_C(1)<<39);
        Require(backing.BackingBasePointer()!=nullptr,"real HostMemory backing");
        Require(backing.VirtualBasePointer()==nullptr,"explicit no-fastmem mode");
        backing.BackingBasePointer()[0]=0x5a;
        backing.BackingBasePointer()[(1<<20)-1]=0xa5;
        backing.ClearBackingRegion(128,1024,0x6b);
        Require(backing.BackingBasePointer()[128]==0x6b &&
                backing.BackingBasePointer()[1151]==0x6b,"real HostMemory clear");
        Require(backing.BackingBasePointer()[0]==0x5a &&
                backing.BackingBasePointer()[(1<<20)-1]==0xa5,"backing boundary values");
    }
    Require(GetPageStats().live_allocations==baseline.live_allocations,"HostMemory destructor released backing");
}
std::uint64_t Clocks() {
    Stage("common_clock_interfaces");
    auto previous=Common::SteadyClock::Now();
    for (unsigned i=0;i<4096;++i) {
        const auto current=Common::SteadyClock::Now();
        Require(current>=previous,"monotonic counter");previous=current;
    }
    const auto start=Common::SteadyClock::Now();
    SuyuOrbis::Host::SleepMicroseconds(20000);
    const auto elapsed=(Common::SteadyClock::Now()-start).count();
    Require(elapsed>=10000000 && elapsed<5000000000LL,"counter units around native sleep");
    Require(Common::RealTimeClock::Now().time_since_epoch().count()>0,"real-time clock initialized");
    return static_cast<std::uint64_t>(elapsed);
}
void Threads() {
    Stage("cpp_threads_mutex_condvar_tls");
    std::mutex mutex;std::condition_variable cv;std::once_flag once;
    unsigned ready=0, count=0, once_count=0;bool go=false;
    std::array<std::thread,2> workers;
    for (unsigned n=0;n<workers.size();++n) workers[n]=std::thread([&,n]{
        tls_cookie=100+n;
        std::call_once(once,[&]{++once_count;});
        {
            std::unique_lock lock(mutex);
            ++ready;cv.notify_all();
            cv.wait(lock,[&]{return go;});
        }
        for (unsigned i=0;i<1024;++i) {
            std::lock_guard lock(mutex);
            ++count;Require(tls_cookie==100+n,"host thread TLS isolation");
        }
    });
    {
        std::unique_lock lock(mutex);
        Require(cv.wait_for(lock,std::chrono::seconds(5),[&]{return ready==2;}),"condition-variable wakeup");
        go=true;cv.notify_all();
    }
    for (auto& t:workers) t.join();
    Require(count==2048 && once_count==1 && tls_cookie==0,"thread joins, mutex and call_once");
    std::recursive_mutex recursive;
    recursive.lock();Require(recursive.try_lock(),"recursive mutex");recursive.unlock();recursive.unlock();
}
unsigned Fibers() {
    Stage("real_common_fiber_roundtrip");
    using Common::Fiber;
    auto root=Fiber::ThreadToFiber();
    std::shared_ptr<Fiber> fiber;
    unsigned trips=0;
    const int rounding=std::fegetround();
    Require(std::fesetround(FE_UPWARD)==0,"root floating-point mode");
    fiber=std::make_shared<Fiber>([&]{
        volatile std::uint64_t canary[16];
        for (unsigned i=0;i<16;++i) canary[i]=UINT64_C(0x8123456789abcdef)^i;
        Require(std::fesetround(FE_DOWNWARD)==0,"fiber floating-point mode");
        for (unsigned step=0;step<4096;++step) {
            for (unsigned i=0;i<16;++i) Require(canary[i]==(UINT64_C(0x8123456789abcdef)^i),"fiber stack preserved");
            Require(std::fegetround()==FE_DOWNWARD,"fiber FP state preserved");
            ++trips;Fiber::YieldTo(fiber,*root);
        }
        SuyuOrbis::Host::Fatal("unexpected return/resume past final fiber yield");
    });
    for (unsigned i=0;i<4096;++i) {
        Fiber::YieldTo(root,*fiber);
        Require(trips==i+1 && std::fegetround()==FE_UPWARD,"root state restored");
    }
    fiber.reset();root->Exit();root.reset();std::fesetround(rounding);
    return trips;
}
unsigned Migration() {
    Stage("real_common_fiber_cross_thread_migration");
    using Common::Fiber;
    std::mutex mutex;std::condition_variable cv;
    unsigned turn=0, hops=0;
    std::shared_ptr<Fiber> destination;
    std::shared_ptr<Fiber> fiber;
    fiber=std::make_shared<Fiber>([&]{
        volatile std::uint64_t sentinel=UINT64_C(0xabcdef9876543210);
        while (true) {
            Require(sentinel==UINT64_C(0xabcdef9876543210),"migrated fiber stack");
            Require(tls_cookie==200+turn,"migrated fiber uses current host TLS");
            Fiber::YieldTo(fiber,*destination);
        }
    });
    std::array<std::thread,2> workers;
    for (unsigned n=0;n<2;++n) workers[n]=std::thread([&,n]{
        tls_cookie=200+n;
        auto root=Fiber::ThreadToFiber();
        while (true) {
            std::unique_lock lock(mutex);
            cv.wait(lock,[&]{return hops==32 || turn==n;});
            if (hops==32) break;
            destination=root;
            Fiber::YieldTo(root,*fiber);
            ++hops;turn=1-n;cv.notify_all();
        }
        root->Exit();
    });
    for (auto& worker:workers) worker.join();
    destination.reset();fiber.reset();
    Require(hops==32,"fiber migrated 32 times without simultaneous execution");
    return hops;
}
}
int main() {
    Stage("entry");
    Pages();
    const auto slept=Clocks();
    Threads();
    const auto trips=Fibers();
    const auto hops=Migration();
    const auto pages=SuyuOrbis::Host::GetPageStats();
    Require(pages.live_allocations==0 && pages.live_bytes==0,"no native page allocation leaks");
    Stage("complete");
    char report[1024];
#ifdef SO_PLATFORM_ORBIS
    constexpr const char* OrbisApis="true";
#else
    constexpr const char* OrbisApis="false";
#endif
    std::snprintf(report,sizeof report,
        "{\"test\":\"real_suyu_common_host_adaptation\",\"passed\":true,\"checks\":%u,\"orbis_apis\":%s,"
        "\"fiber_roundtrips\":%u,\"cross_thread_hops\":%u,\"sleep_ns\":%llu,"
        "\"live_page_allocations\":%llu,\"full_core_linked\":false,"
        "\"scheduler_dispatch\":false,\"guest_fastmem\":false,\"game_tested\":false}\n",
        checks.load(),OrbisApis,trips,hops,static_cast<unsigned long long>(slept),
        static_cast<unsigned long long>(pages.live_allocations));
    std::fputs(report,stdout);std::fflush(stdout);
#ifdef SO_PLATFORM_ORBIS
    FILE* out=std::fopen("/data/orbis-host-common.json.tmp","w");
    if (!out) SuyuOrbis::Host::Fatal("report open");
    const int written=std::fputs(report,out);
    const int closed=std::fclose(out);
    if (written<0 || closed || std::rename("/data/orbis-host-common.json.tmp","/data/orbis-host-common.json"))
        SuyuOrbis::Host::Fatal("report commit");
#endif
    return 0;
}
