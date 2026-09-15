// SPDX-License-Identifier: GPL-2.0-or-later
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
#include "arm64_to_c.h"
int main(int argc, char** argv) {
    try {
        if (argc != 4) throw std::runtime_error("usage: emit rtld.bin main.bin exefs");
        for (int i=1;i<=2;++i) {
            std::ifstream stream(argv[i],std::ios::binary|std::ios::ate);
            if (!stream || stream.tellg() <= 0) throw std::runtime_error("missing instruction bytes");
            const auto size=static_cast<size_t>(stream.tellg());
            if (size%4) throw std::runtime_error("unaligned AArch64 text");
            std::vector<uint32_t> words(size/4);
            stream.seekg(0); stream.read(reinterpret_cast<char*>(words.data()),size);
            if (!stream) throw std::runtime_error("short instruction read");
            const char* name=i==1?"rtld":"main";
            const auto out=(std::filesystem::path(argv[3])/name).string();
            auto s=suyu::recomp::EmitProject(name,reinterpret_cast<const uint8_t*>(words.data()),size,0,out,true);
            std::cout<<name<<": blocks="<<s.blocks<<" emitted="<<s.emitted<<" unhandled="<<s.unhandled<<'\n';
            if (!s.blocks || !s.emitted || s.unhandled) throw std::runtime_error("incomplete fixture translation");
        }
        return 0;
    } catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; return 1; }
}
