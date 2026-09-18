// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstddef>
#include <cstdint>
namespace SuyuOrbis::Host {
struct PageStats { std::uint64_t live_allocations, live_bytes; };
PageStats GetPageStats() noexcept;
bool PageAllocationSize(std::size_t requested, std::size_t& total) noexcept;
[[noreturn]] void Fatal(const char* operation, int error = 0) noexcept;
void SleepMicroseconds(std::uint32_t duration);
}
