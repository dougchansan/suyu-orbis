// SPDX-License-Identifier: GPL-2.0-or-later
#include "host_support.h"
#include "common/steady_clock.h"
#include <limits>
#ifdef SO_PLATFORM_ORBIS
#include <orbis/libkernel.h>
#else
#include <thread>
#endif
namespace SuyuOrbis::Host {
void SleepMicroseconds(std::uint32_t usec) {
#ifdef SO_PLATFORM_ORBIS
    int rc=sceKernelUsleep(usec);
    if (rc) Fatal("sceKernelUsleep",rc);
#else
    std::this_thread::sleep_for(std::chrono::microseconds(usec));
#endif
}
}
namespace Common {
SteadyClock::time_point SteadyClock::Now() noexcept {
#ifdef SO_PLATFORM_ORBIS
    const auto frequency=sceKernelGetProcessTimeCounterFrequency();
    const auto counter=sceKernelGetProcessTimeCounter();
    // A checked quotient/remainder avoids libgcc/__udivti3 and overflow.
    constexpr std::uint64_t Billion=1000000000;
    if (!frequency || frequency>std::numeric_limits<std::uint64_t>::max()/Billion)
        SuyuOrbis::Host::Fatal("invalid process counter frequency");
    const auto whole=counter/frequency;
    if (whole>(std::numeric_limits<std::int64_t>::max()-Billion)/Billion)
        SuyuOrbis::Host::Fatal("process counter overflow");
    return time_point{duration{static_cast<std::int64_t>(whole*Billion+(counter%frequency)*Billion/frequency)}};
#else
    return time_point{std::chrono::duration_cast<duration>(std::chrono::steady_clock::now().time_since_epoch())};
#endif
}
RealTimeClock::time_point RealTimeClock::Now() noexcept {
#ifdef SO_PLATFORM_ORBIS
    OrbisKernelTimeval tv{};
    const int rc=sceKernelGettimeofday(&tv);
    if (rc || tv.tv_sec<0 || tv.tv_usec<0 || tv.tv_usec>=1000000 ||
        static_cast<std::uint64_t>(tv.tv_sec) >
            static_cast<std::uint64_t>((std::numeric_limits<std::int64_t>::max()-1000000000)/1000000000))
        SuyuOrbis::Host::Fatal("sceKernelGettimeofday",rc);
    return time_point{std::chrono::seconds(tv.tv_sec)+std::chrono::microseconds(tv.tv_usec)};
#else
    return time_point{std::chrono::duration_cast<duration>(std::chrono::system_clock::now().time_since_epoch())};
#endif
}
}
