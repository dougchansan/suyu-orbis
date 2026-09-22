cmake_minimum_required(VERSION 3.24)
project(suyu_orbis_core_compile LANGUAGES C CXX)
# This gate only compiles real translation units. It never defines a fake core
# library, links an executable, or substitutes missing runtime implementations.
if(NOT SO_PLATFORM_ORBIS)
    message(FATAL_ERROR "Use the modern Orbis consumer toolchain")
endif()
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
foreach(var SO_SUYU_SOURCE SO_BOOST_HEADERS SO_FMT_SOURCE SO_UNORDERED_SOURCE)
    if(NOT DEFINED ${var} OR NOT IS_DIRECTORY "${${var}}")
        message(FATAL_ERROR "${var} must identify the audited source/header directory")
    endif()
endforeach()
find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
execute_process(COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/verify_sources.py"
    --source "${SO_SUYU_SOURCE}" --output "${CMAKE_CURRENT_BINARY_DIR}/selected-sources.cmake"
    COMMAND_ERROR_IS_FATAL ANY)
include("${CMAKE_CURRENT_BINARY_DIR}/selected-sources.cmake")
add_library(suyu_orbis_kernel_objects OBJECT ${SO_AUDITED_KERNEL_SOURCES})
target_include_directories(suyu_orbis_kernel_objects PRIVATE
    "${SO_SUYU_SOURCE}/src" "${SO_SUYU_SOURCE}/src/core")
target_include_directories(suyu_orbis_kernel_objects SYSTEM PRIVATE
    "${SO_BOOST_HEADERS}" "${SO_FMT_SOURCE}/include" "${SO_UNORDERED_SOURCE}/include")
target_compile_definitions(suyu_orbis_kernel_objects PRIVATE
    SUYU_NO_JIT=1 ARCHITECTURE_x86_64=1 __OPENORBIS__=1 PS4=1 _GNU_SOURCE=1)
# GCC-only permissive flags, host ISA tuning, and dynamic CPU libraries are not used.
target_compile_options(suyu_orbis_kernel_objects PRIVATE -Wall -Wextra)
