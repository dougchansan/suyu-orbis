cmake_minimum_required(VERSION 3.24)
project(orbis_cxx20_runtime_probe LANGUAGES CXX)
add_executable(orbis-cxx20-probe runtime_probe.cpp)
target_compile_features(orbis-cxx20-probe PRIVATE cxx_std_20)
target_compile_options(orbis-cxx20-probe PRIVATE -Wall -Wextra -Wpedantic)
if(SO_PLATFORM_ORBIS)
    target_compile_definitions(orbis-cxx20-probe PRIVATE SO_PLATFORM_ORBIS=1)
    set_target_properties(orbis-cxx20-probe PROPERTIES SUFFIX ".elf")
    find_program(FSELF NAMES create-fself create-fself-macos
        HINTS "${OO_PS4_TOOLCHAIN}/bin/linux" "${OO_PS4_TOOLCHAIN}/bin/macos"
        NO_CMAKE_FIND_ROOT_PATH REQUIRED)
    add_custom_command(TARGET orbis-cxx20-probe POST_BUILD
        COMMAND "${CMAKE_COMMAND}" -E env "OO_PS4_TOOLCHAIN=${OO_PS4_TOOLCHAIN}"
            "${FSELF}" "-in=$<TARGET_FILE:orbis-cxx20-probe>"
            "-out=${CMAKE_CURRENT_BINARY_DIR}/orbis-cxx20-probe.oelf"
            --eboot "${CMAKE_CURRENT_BINARY_DIR}/eboot.bin" --paid 0x3800000000000011
        BYPRODUCTS "${CMAKE_CURRENT_BINARY_DIR}/orbis-cxx20-probe.oelf"
                   "${CMAKE_CURRENT_BINARY_DIR}/eboot.bin" VERBATIM)
else()
    find_package(Threads REQUIRED)
    target_link_libraries(orbis-cxx20-probe PRIVATE Threads::Threads)
    enable_testing()
    add_test(NAME cpp20-primitives COMMAND orbis-cxx20-probe)
    set_tests_properties(cpp20-primitives PROPERTIES TIMEOUT 30)
endif()
