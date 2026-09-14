// SPDX-License-Identifier: GPL-2.0-or-later
// Original synthetic AArch64 only; no game/firmware input.
#include <array>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include "arm64_to_c.h"

int main(int argc, char** argv) {
    if (argc != 2) return 2;

    // rtld: mov x0, #40; ret
    const std::array<std::uint32_t, 2> rtld = {
        0xd2800500,
        0xd65f03c0,
    };

    // main: add x0, x0, #2; svc #0x1e (GetSystemTick); ret
    // No guest memory access is used so this can exercise the real ArmRecomp
    // SVC handoff before a KProcess/address space exists.
    const std::array<std::uint32_t, 3> main_code = {
        0x91000800,
        0xd40003c1,
        0xd65f03c0,
    };

    const std::filesystem::path root(argv[1]);
    const auto a = suyu::recomp::EmitProject(
        "rtld", reinterpret_cast<const std::uint8_t*>(rtld.data()), sizeof(rtld),
        0, (root / "rtld").string(), true);
    const auto b = suyu::recomp::EmitProject(
        "main", reinterpret_cast<const std::uint8_t*>(main_code.data()), sizeof(main_code),
        0, (root / "main").string(), true);

    if (a.unhandled || b.unhandled || a.emitted != rtld.size() ||
        b.emitted != main_code.size()) {
        std::cerr << "fixture was not completely translated\n";
        return 1;
    }
    std::cout << "full-core fixture emitted by pinned Suyu exporter\n";
    return 0;
}
