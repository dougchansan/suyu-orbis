// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
namespace SuyuOrbis::HostTest {
struct ThreadIdentity {
    unsigned cookie;
    const void* storage;
};
// Call on each side of a migrating fiber yield. Never retain a TLS pointer for
// dereference after migration. This accessor is deliberately out-of-line in a
// separate non-LTO translation unit: a compiler may cache a thread_local
// address across an ordinary function call that actually migrates a fiber.
void SetThreadCookie(unsigned cookie);
ThreadIdentity ReadThreadIdentity();
}
