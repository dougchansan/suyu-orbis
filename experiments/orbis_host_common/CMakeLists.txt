cmake_minimum_required(VERSION 3.24)
project(suyu_orbis_host_common LANGUAGES C CXX ASM)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(SO_PLATFORM_ORBIS)
    # libc++ consumes the POSIX/musl declarations even under strict -std=c++20.
    add_compile_definitions(_GNU_SOURCE=1 PS4=1)
endif()
get_filename_component(SO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
foreach(var SO_SUYU_SOURCE SO_BOOST_HEADERS SO_BOOST_CONTEXT SO_FMT_SOURCE)
    if(NOT ${var})
        message(FATAL_ERROR "${var} is required; use pinned sources and isolated headers")
    endif()
endforeach()
find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
set(SO_OVERLAY "${CMAKE_CURRENT_BINARY_DIR}/overlay")
execute_process(COMMAND "${Python3_EXECUTABLE}" "${SO_ROOT}/scripts/prepare_orbis_common.py"
    --suyu "${SO_SUYU_SOURCE}" --context "${SO_BOOST_CONTEXT}" --output "${SO_OVERLAY}"
    COMMAND_ERROR_IS_FATAL ANY)
set(FMT_TEST OFF CACHE BOOL "" FORCE)
set(FMT_DOC OFF CACHE BOOL "" FORCE)
set(FMT_INSTALL OFF CACHE BOOL "" FORCE)
add_subdirectory("${SO_FMT_SOURCE}" fmt)
add_library(orbis_host_common STATIC
    "${SO_SUYU_SOURCE}/src/common/fiber.cpp"
    "${SO_OVERLAY}/common/host_memory.cpp"
    "${SO_ROOT}/platform/orbis/common/pages.cpp"
    "${SO_ROOT}/platform/orbis/common/clocks.cpp"
    "${SO_ROOT}/platform/orbis/common/logging.cpp"
    "${SO_BOOST_CONTEXT}/src/asm/make_x86_64_sysv_elf_gas.S"
    "${SO_BOOST_CONTEXT}/src/asm/jump_x86_64_sysv_elf_gas.S")
target_include_directories(orbis_host_common PUBLIC
    "${SO_OVERLAY}" "${SO_SUYU_SOURCE}/src" "${SO_ROOT}/platform/orbis/common")
target_include_directories(orbis_host_common SYSTEM PUBLIC "${SO_BOOST_HEADERS}")
target_link_libraries(orbis_host_common PUBLIC fmt::fmt)
# Test the SAME upstream no-fastmem fallback on both platforms. It is an
# explicit backing-memory test, not proof of guest permission/alias behavior.
target_compile_definitions(orbis_host_common PUBLIC __OPENORBIS__=1 BOOST_CONTEXT_NO_LIB=1)
add_executable(suyu-orbis-host-common host_common_tests.cpp)
target_link_libraries(suyu-orbis-host-common PRIVATE orbis_host_common)
target_compile_options(suyu-orbis-host-common PRIVATE -Wall -Wextra -Wpedantic -Werror)
if(SO_PLATFORM_ORBIS)
    target_sources(orbis_host_common PRIVATE "${SO_ROOT}/platform/orbis/common/fenv_rounding.cpp")
    # Direct LLD link: these are linker arguments, not -Wl driver arguments.
    target_link_options(orbis_host_common INTERFACE --wrap=fegetround --wrap=fesetround)
    target_compile_definitions(orbis_host_common PUBLIC SO_PLATFORM_ORBIS=1 PS4=1)
    set_target_properties(suyu-orbis-host-common PROPERTIES SUFFIX ".elf")
    find_program(FSELF NAMES create-fself create-fself-macos
        HINTS "${OO_PS4_TOOLCHAIN}/bin/linux" "${OO_PS4_TOOLCHAIN}/bin/macos"
        NO_CMAKE_FIND_ROOT_PATH REQUIRED)
    add_custom_command(TARGET suyu-orbis-host-common POST_BUILD
        COMMAND "${CMAKE_COMMAND}" -E env "OO_PS4_TOOLCHAIN=${OO_PS4_TOOLCHAIN}" "${FSELF}" "-in=$<TARGET_FILE:suyu-orbis-host-common>"
            "-out=${CMAKE_CURRENT_BINARY_DIR}/suyu-orbis-host-common.oelf"
            --eboot "${CMAKE_CURRENT_BINARY_DIR}/eboot.bin" --paid 0x3800000000000011
        BYPRODUCTS "${CMAKE_CURRENT_BINARY_DIR}/suyu-orbis-host-common.oelf"
                   "${CMAKE_CURRENT_BINARY_DIR}/eboot.bin" VERBATIM)
else()
    find_package(Threads REQUIRED)
    target_link_libraries(orbis_host_common PUBLIC Threads::Threads)
    enable_testing()
    add_test(NAME real-common-components COMMAND suyu-orbis-host-common)
    set_tests_properties(real-common-components PROPERTIES TIMEOUT 30)
endif()
