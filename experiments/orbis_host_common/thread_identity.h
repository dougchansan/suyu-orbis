// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
namespace SuyuOrbis::HostTest {
struct ThreadIdentity {
    unsigned cookie;
    const void* storage;
};
void SetThreadCookie(unsigned cookie);
ThreadIdentity ReadThreadIdentity();
}
