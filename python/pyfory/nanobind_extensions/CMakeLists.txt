# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

cmake_minimum_required(VERSION 3.15...3.27)
project(pyfory_nanobind_extensions)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Configure build type
if (NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Choose the type of build." FORCE)
    set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release" "MinSizeRel" "RelWithDebInfo")
endif()

# Find Python
if (CMAKE_VERSION VERSION_LESS 3.18)
    set(DEV_MODULE Development)
else()
    set(DEV_MODULE Development.Module)
endif()

find_package(Python 3.8 COMPONENTS Interpreter ${DEV_MODULE} REQUIRED)

# Find nanobind
# Method 1: If nanobind is installed via pip
execute_process(
    COMMAND "${Python_EXECUTABLE}" -m nanobind --cmake_dir
    OUTPUT_STRIP_TRAILING_WHITESPACE OUTPUT_VARIABLE nanobind_ROOT
    RESULT_VARIABLE nanobind_FOUND
)

if(nanobind_FOUND EQUAL 0)
    find_package(nanobind CONFIG REQUIRED)
else()
    message(WARNING "Could not find nanobind via pip. Please install it with: pip install nanobind")
    # Fallback: try to find via system package manager or manual installation
    find_package(nanobind CONFIG)
    if(NOT nanobind_FOUND)
        message(FATAL_ERROR "nanobind not found. Please install it with: pip install nanobind")
    endif()
endif()

# Create the extension module
nanobind_add_module(math_ops src/math_ops.cpp)

# Optional: Set specific compile features or options
target_compile_features(math_ops PRIVATE cxx_std_17)

# Optional: Add compiler-specific optimizations
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(math_ops PRIVATE -Wall -Wextra -O3)
endif()

# Set the output directory to make the module easily importable
set_target_properties(math_ops PROPERTIES 
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)

# For development: copy the built module to the parent directory for easier importing
add_custom_command(TARGET math_ops POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy 
    $<TARGET_FILE:math_ops> 
    ${CMAKE_CURRENT_SOURCE_DIR}/../math_ops$<TARGET_FILE_SUFFIX:math_ops>
    COMMENT "Copying built module to parent directory"
)

# Print some useful information
message(STATUS "Python executable: ${Python_EXECUTABLE}")
message(STATUS "Python version: ${Python_VERSION}")
message(STATUS "nanobind found at: ${nanobind_ROOT}")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
