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

# Nanobind extensions
genrule(
    name = "nanobind_math_ops",
    srcs = [
        "src/math_ops.cpp",
    ],
    outs = [
        "math_ops.so",
    ],
    cmd = """
        set -e
        NANOBIND_DIR=$$(python -c "import nanobind; print(nanobind.get_cmake_dir() + '/../..')")
        PYTHON_INCLUDE=$$(python -c "import sysconfig; print(sysconfig.get_path('include'))")
        PYTHON_LIB=$$(python -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")
        
        g++ -O3 -Wall -shared -std=c++17 -fPIC \
            -I"$$NANOBIND_DIR/include" \
            -I"$$PYTHON_INCLUDE" \
            $(location src/math_ops.cpp) \
            -o $@ \
            -L"$$PYTHON_LIB" -lpython3.12
    """,
    local = 1,
    tags = ["no-cache"],
    visibility = ["//visibility:public"],
)

genrule(
    name = "nanobind_buffer_ops",
    srcs = [
        "src/buffer_ops.cpp",
        "src/buffer.cpp",
        "src/buffer.hpp",
    ],
    outs = [
        "buffer_ops.so",
    ],
    cmd = """
        set -e
        NANOBIND_DIR=$$(python -c "import nanobind; print(nanobind.get_cmake_dir() + '/../..')")
        PYTHON_INCLUDE=$$(python -c "import sysconfig; print(sysconfig.get_path('include'))")
        PYTHON_LIB=$$(python -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")
        
        g++ -O3 -Wall -shared -std=c++17 -fPIC \
            -I"$$NANOBIND_DIR/include" \
            -I"$$PYTHON_INCLUDE" \
            -Isrc \
            $(location src/buffer_ops.cpp) \
            $(location src/buffer.cpp) \
            -o $@ \
            -L"$$PYTHON_LIB" -lpython3.12
    """,
    local = 1,
    tags = ["no-cache"],
    visibility = ["//visibility:public"],
)
