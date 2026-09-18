# SPDX-License-Identifier: GPL-2.0-or-later
# Native application profile: modern headers MUST be paired with their archives.
list(APPEND CMAKE_TRY_COMPILE_PLATFORM_VARIABLES SO_CXX_PREFIX SO_ORBIS_C_OVERLAY)
include("${CMAKE_CURRENT_LIST_DIR}/../../cmake/toolchains/openorbis.cmake")
set(SO_CXX_PREFIX "" CACHE PATH "Isolated, built LLVM C++ runtime prefix")
set(SO_ORBIS_C_OVERLAY "" CACHE PATH "Checked SDK C-header overlay")
foreach(required include/c++/v1/__config_site lib/libc++.a lib/libc++abi.a lib/libunwind.a)
    if(NOT EXISTS "${SO_CXX_PREFIX}/${required}")
        message(FATAL_ERROR "Missing modern runtime ${required}; never fall back to SDK libc++")
    endif()
endforeach()
if(NOT EXISTS "${SO_ORBIS_C_OVERLAY}/math.h")
    message(FATAL_ERROR "Missing reviewed math-header overlay")
endif()
set(CMAKE_CXX_FLAGS_INIT "-fPIC -funwind-tables -march=btver2 -DPS4=1 -D_GNU_SOURCE=1 -nostdinc++ -isystem \"${SO_CXX_PREFIX}/include/c++/v1\" -isystem \"${SO_ORBIS_C_OVERLAY}\" -isystem \"${OO_PS4_TOOLCHAIN}/include\"")
# No -lc++ search flag: all three modern libraries are named explicitly. SDK
# libc, libkernel and compiler builtins stay in the same linker rescan group.
set(CMAKE_CXX_LINK_EXECUTABLE "${_SO_LINK} \"${SO_CXX_PREFIX}/lib/libc++.a\" \"${SO_CXX_PREFIX}/lib/libc++abi.a\" \"${SO_CXX_PREFIX}/lib/libunwind.a\" \"${OO_PS4_TOOLCHAIN}/lib/libclang_rt.builtins-x86_64.a\" --end-group")
