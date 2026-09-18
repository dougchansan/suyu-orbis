// SPDX-License-Identifier: GPL-2.0-or-later
// The public SDK libc's fegetround/__fesetround are no-op fallbacks. Redirect
// only these two C entry points; do NOT claim the rest of fenv is implemented.
#include <cfenv>
#include <cstdint>
#include <xmmintrin.h>
static_assert(FE_TONEAREST==0 && FE_DOWNWARD==0x400 && FE_UPWARD==0x800 && FE_TOWARDZERO==0xc00);
extern "C" int __wrap_fegetround() noexcept {
    std::uint16_t cw;
    asm volatile("fnstcw %0" : "=m"(cw));
    return cw & 0xc00;
}
extern "C" int __wrap_fesetround(int direction) noexcept {
    if (direction!=FE_TONEAREST && direction!=FE_DOWNWARD &&
        direction!=FE_UPWARD && direction!=FE_TOWARDZERO) return -1;
    std::uint16_t cw;
    asm volatile("fnstcw %0" : "=m"(cw));
    cw=static_cast<std::uint16_t>((cw & ~0xc00U) | static_cast<unsigned>(direction));
    const auto csr=(_mm_getcsr() & ~0x6000U) | (static_cast<unsigned>(direction)<<3);
    asm volatile("fldcw %0" :: "m"(cw));
    _mm_setcsr(csr);
    return 0;
}
