// SPDX-License-Identifier: GPL-2.0-or-later
#include <filesystem>
#include <iostream>
#include "arm64_to_c.h"
#include "program.h"
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const std::filesystem::path root(argv[1]);
    const auto a = suyu::recomp::EmitProject("rtld", reinterpret_cast<const std::uint8_t*>(ProcessFixture::kRtld.data()), sizeof(ProcessFixture::kRtld), 0, (root/"rtld").string(), true);
    const auto b = suyu::recomp::EmitProject("main", reinterpret_cast<const std::uint8_t*>(ProcessFixture::kMain.data()), sizeof(ProcessFixture::kMain), 0, (root/"main").string(), true);
    if (a.unhandled || b.unhandled || a.emitted != ProcessFixture::kRtld.size() || b.emitted != ProcessFixture::kMain.size()) {
        std::cerr << "Original process fixture did not fully translate\n"; return 1;
    }
    std::cout << "Original scheduled-process fixture emitted by real Suyu exporter\n";
}
