// SPDX-License-Identifier: GPL-2.0-or-later
// A real synchronous logging/assertion backend for isolated Common tests.
// It formats every diagnostic; failed assertions abort instead of becoming stubs.
#include "host_support.h"
#include "common/assert.h"
#include "common/logging.h"
#include <cstdio>
#include <cstdlib>
namespace SuyuOrbis::Host {
[[noreturn]] void Fatal(const char* what,int rc) noexcept {
    std::fprintf(stderr,"[orbis-host] fatal: %s (%d / %#x)\n",what,rc,static_cast<unsigned>(rc));
    std::fflush(stderr);
    std::abort();
}
}
void AssertFailSoftImpl() { SuyuOrbis::Host::Fatal("Suyu assertion failed"); }
[[noreturn]] void AssertFatalImpl() { SuyuOrbis::Host::Fatal("Suyu fatal assertion"); }
namespace Common::Log {
void FmtLogMessageImpl(Class,Level,const char* file,unsigned line,const char* function,
                      fmt::string_view format,const fmt::format_args& args) {
    const auto message=fmt::vformat(format,args);
    std::fprintf(stderr,"[suyu-common] %s:%u %s: %s\n",file,line,function,message.c_str());
    std::fflush(stderr);
}
}
