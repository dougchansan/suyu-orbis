cmake_minimum_required(VERSION 3.24)
project(suyu_orbis_full_core_smoke LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT DEFINED SUYU_SOURCE_DIR)
  message(FATAL_ERROR "Pass -DSUYU_SOURCE_DIR=/path/to/pinned/suyu")
endif()

if(NOT EXISTS "${SUYU_SOURCE_DIR}/src/core/CMakeLists.txt")
  message(FATAL_ERROR "Invalid SUYU_SOURCE_DIR: ${SUYU_SOURCE_DIR}")
endif()

# The parent Suyu project owns dependency discovery and platform feature flags.
# This file is consumed from a patched/pinned Suyu checkout by the CI harness;
# it is not currently intended to add Suyu as an arbitrary CMake subproject.
message(STATUS "Full-core smoke harness configured for ${SUYU_SOURCE_DIR}")
