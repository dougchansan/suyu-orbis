// SPDX-License-Identifier: GPL-2.0-or-later
#include "thread_identity.h"
namespace SuyuOrbis::HostTest {
namespace {
thread_local unsigned cookie_value{};
}
// These functions never yield. Callers cannot inline them or infer that the
// calling host thread stays the same across a fiber suspension/resumption.
void SetThreadCookie(unsigned cookie) {
    cookie_value = cookie;
}
ThreadIdentity ReadThreadIdentity() {
    return {cookie_value, &cookie_value};
}
}
