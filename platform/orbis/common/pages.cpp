// SPDX-License-Identifier: GPL-2.0-or-later
// Common::VirtualBuffer's real allocation interface, backed by Orbis direct
// memory. This is backing storage, NOT a fastmem/guest virtual-address mapper.
#include "host_support.h"
#include "common/virtual_buffer.h"
#include <atomic>
#include <cstdint>
#include <cstring>
#include <limits>
#ifdef SO_PLATFORM_ORBIS
#include <orbis/libkernel.h>
#else
#include <cerrno>
#include <sys/mman.h>
#endif
namespace {
constexpr std::size_t Page = 0x4000;
constexpr std::uint64_t Magic = UINT64_C(0x534F504147453031);
struct Header { std::uint64_t magic; std::size_t requested, total; std::int64_t physical; };
static_assert(sizeof(Header) <= Page);
std::atomic<std::uint64_t> live_count{}, live_bytes{};
}
namespace SuyuOrbis::Host {
bool PageAllocationSize(std::size_t size, std::size_t& total) noexcept {
    total=0;
    if (!size || size > std::numeric_limits<std::size_t>::max()-(2*Page-1)) return false;
    total=((size+Page-1)&~(Page-1))+Page;
    return true;
}
PageStats GetPageStats() noexcept { return {live_count.load(),live_bytes.load()}; }
}
namespace Common {
void* AllocateMemoryPages(std::size_t size) noexcept {
    if (!size) return nullptr;
    std::size_t total;
    if (!SuyuOrbis::Host::PageAllocationSize(size,total))
        SuyuOrbis::Host::Fatal("page allocation size overflow");
    void* base=nullptr;
    std::int64_t physical=-1;
#ifdef SO_PLATFORM_ORBIS
    off_t offset;
    int rc=sceKernelAllocateDirectMemory(0,sceKernelGetDirectMemorySize(),total,Page,3,&offset);
    if (rc) SuyuOrbis::Host::Fatal("sceKernelAllocateDirectMemory",rc);
    physical=offset;
    rc=sceKernelMapDirectMemory(&base,total,ORBIS_KERNEL_PROT_CPU_RW,0,offset,Page);
    if (rc || !base) {
        sceKernelReleaseDirectMemory(offset,total);
        SuyuOrbis::Host::Fatal("sceKernelMapDirectMemory",rc);
    }
#else
    // Host regression uses the same ownership/size accounting; it is not an
    // Orbis ABI simulation. The guest execution test uses the branch above.
    base=mmap(nullptr,total,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if (base==MAP_FAILED) SuyuOrbis::Host::Fatal("host mmap",errno);
#endif
    // Preserve VirtualBuffer's mmap-originated zero-initialization contract.
    std::memset(base,0,total);
    auto* h=static_cast<Header*>(base);
    *h={Magic,size,total,physical};
    live_bytes.fetch_add(total); live_count.fetch_add(1);
    return static_cast<unsigned char*>(base)+Page;
}
void FreeMemoryPages(void* data,std::size_t size) noexcept {
    if (!data) return;
    auto* h=reinterpret_cast<Header*>(static_cast<unsigned char*>(data)-Page);
    if (h->magic!=Magic || h->requested!=size)
        SuyuOrbis::Host::Fatal("page allocation ownership/size mismatch");
    const auto total=h->total;
#ifdef SO_PLATFORM_ORBIS
    const off_t physical=h->physical;
#endif
    h->magic=0;
#ifdef SO_PLATFORM_ORBIS
    int rc=sceKernelMunmap(h,total);
    if (rc) SuyuOrbis::Host::Fatal("sceKernelMunmap",rc);
    rc=sceKernelReleaseDirectMemory(physical,total);
    if (rc) SuyuOrbis::Host::Fatal("sceKernelReleaseDirectMemory",rc);
#else
    if (munmap(h,total)) SuyuOrbis::Host::Fatal("host munmap",errno);
#endif
    live_bytes.fetch_sub(total); live_count.fetch_sub(1);
}
}
