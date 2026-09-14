// SPDX-License-Identifier: GPL-2.0-or-later
// Entirely original instruction sequences; no game/firmware inputs.
#include <array>
#include <filesystem>
#include <iostream>
#include "arm64_to_c.h"
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const std::array<uint32_t, 2> rtld = {0xd2800500, 0xd65f03c0}; // mov x0,#40; ret
    const std::array<uint32_t, 4> main_code = {
        0x91000800, // add x0,x0,#2
        0xf9000020, // str x0,[x1]
        0xd4000221, // svc #0x11
        0xd65f03c0  // ret
    };
    const std::filesystem::path root(argv[1]);
    auto a = suyu::recomp::EmitProject("rtld", reinterpret_cast<const uint8_t*>(rtld.data()),
        sizeof rtld, 0, (root/"rtld").string(), true);
    auto b = suyu::recomp::EmitProject("main", reinterpret_cast<const uint8_t*>(main_code.data()),
        sizeof main_code, 0, (root/"main").string(), true);
    if (a.unhandled || b.unhandled || a.emitted != rtld.size() || b.emitted != main_code.size()) {
        std::cerr << "Synthetic AArch64 instructions were not completely translated\n";
        return 1;
    }
    std::cout << "Emitted two synthetic modules through the pinned Suyu exporter\n";
    return 0;
}
