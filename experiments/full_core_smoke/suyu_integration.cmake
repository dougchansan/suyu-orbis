# SPDX-License-Identifier: GPL-2.0-or-later
# Included from the pinned Suyu top-level CMakeLists after its own src/core
# target and dependency graph have been created.

if(NOT SUYU_NO_JIT)
    message(FATAL_ERROR "Full-core smoke requires -DSUYU_NO_JIT=ON")
endif()

get_filename_component(SO_REPO_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
if(NOT SO_FULL_CORE_BUNDLE OR NOT EXISTS "${SO_FULL_CORE_BUNDLE}/CMakeLists.txt")
    message(FATAL_ERROR "Pass -DSO_FULL_CORE_BUNDLE=/absolute/path/to/imported/bundle")
endif()

# Keep the embedded suyu-orbis project to just the libraries needed by this
# experiment. The full Suyu build owns all external dependency discovery.
set(SO_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(SO_BUILD_UPSTREAM_FIXTURE OFF CACHE BOOL "" FORCE)
set(SO_MODULE_BUNDLE "${SO_FULL_CORE_BUNDLE}" CACHE PATH "" FORCE)

add_subdirectory("${SO_REPO_ROOT}" "${CMAKE_BINARY_DIR}/suyu-orbis")
add_subdirectory("${SO_REPO_ROOT}/integrations" "${CMAKE_BINARY_DIR}/suyu-orbis-integrations")

# core's NS query service uses PlayTimeManager, whose actual implementation is
# owned by frontend_common even with Qt disabled. The old standalone link
# omitted that archive and failed on its constructor/destructor/GetPlayTime.
# Link the real target, including its declared transitive dependencies; never
# replace the service with stubs or suppress unresolved symbols.
if(NOT TARGET frontend_common)
    message(FATAL_ERROR "Pinned Suyu frontend_common target is required for PlayTimeManager")
endif()

add_executable(suyu_orbis_full_core_smoke
    "${CMAKE_CURRENT_LIST_DIR}/arm_recomp_smoke.cpp")
target_compile_features(suyu_orbis_full_core_smoke PRIVATE cxx_std_20)
target_include_directories(suyu_orbis_full_core_smoke PRIVATE
    "${CMAKE_SOURCE_DIR}/src"
    "${SO_REPO_ROOT}/integrations")
target_link_libraries(suyu_orbis_full_core_smoke PRIVATE
    suyu_orbis_bridge
    so_module_bundle
    core
    frontend_common)

# The smoke binary must inherit SUYU_NO_JIT from core. Make that assumption
# visible during configuration rather than silently relying on target order.
get_target_property(_so_core_defs core INTERFACE_COMPILE_DEFINITIONS)
message(STATUS "suyu-orbis full-core smoke: core interface definitions=${_so_core_defs}")
