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

load("//bazel:cython_library.bzl", "pyx_library")
load("@compile_commands_extractor//:refresh_compile_commands.bzl", "refresh_compile_commands")


pyx_library(
    name = "_util",
    srcs = glob([
        "python/pyfory/includes/*.pxd",
        "python/pyfory/_util.pxd",
        "python/pyfory/_util.pyx",
        "python/pyfory/__init__.py",
    ]),
    cc_kwargs = dict(
        linkstatic = 1,
    ),
    deps = [
        "//cpp/fory/util:fory_util",
    ],
)

pyx_library(
    name = "mmh3",
    srcs = glob([
        "python/pyfory/lib/mmh3/*.pxd",
        "python/pyfory/lib/mmh3/*.pyx",
        "python/pyfory/lib/mmh3/__init__.py",
    ]),
    cc_kwargs = dict(
        linkstatic = 1,
    ),
    deps = [
        "//cpp/fory/thirdparty:libmmh3",
    ],
)

pyx_library(
    name = "_serialization",
    srcs = glob([
        "python/pyfory/includes/*.pxd",
        "python/pyfory/_util.pxd",
        "python/pyfory/_serialization.pyx",
        "python/pyfory/__init__.py",
    ]),
    cc_kwargs = dict(
        linkstatic = 1,
    ),
    deps = [
        "//cpp/fory/util:fory_util",
        "//cpp/fory/type:fory_type",
        "//cpp/fory/python:_pyfory",
        "@com_google_absl//absl/container:flat_hash_map",
    ],
)

pyx_library(
    name = "_format",
    srcs = glob([
        "python/pyfory/__init__.py",
        "python/pyfory/includes/*.pxd",
        "python/pyfory/_util.pxd",
        "python/pyfory/*.pxi",
        "python/pyfory/format/_format.pyx",
        "python/pyfory/format/__init__.py",
        "python/pyfory/format/*.pxi",
    ]),
    cc_kwargs = dict(
        linkstatic = 1,
    ),
    deps = [
        "//cpp/fory:fory",
        "@local_config_pyarrow//:python_numpy_headers",
        "@local_config_pyarrow//:arrow_python_shared_library"
    ],
)

genrule(
    name = "cp_fory_so",
    srcs = [
        ":python/pyfory/_util.so",
        ":python/pyfory/lib/mmh3/mmh3.so",
        ":python/pyfory/format/_format.so",
        ":python/pyfory/_serialization.so",
    ],
    outs = [
        "cp_fory_py_generated.out",
    ],
    cmd = """
        set -e
        set -x
        WORK_DIR=$$(pwd)
        u_name=`uname -s`
        if [ "$${u_name: 0: 4}" == "MING" ] || [ "$${u_name: 0: 4}" == "MSYS" ]
        then
            cp -f $(location python/pyfory/_util.so) "$$WORK_DIR/python/pyfory/_util.pyd"
            cp -f $(location python/pyfory/lib/mmh3/mmh3.so) "$$WORK_DIR/python/pyfory/lib/mmh3/mmh3.pyd"
            cp -f $(location python/pyfory/format/_format.so) "$$WORK_DIR/python/pyfory/format/_format.pyd"
            cp -f $(location python/pyfory/_serialization.so) "$$WORK_DIR/python/pyfory/_serialization.pyd"
        else
            cp -f $(location python/pyfory/_util.so) "$$WORK_DIR/python/pyfory"
            cp -f $(location python/pyfory/lib/mmh3/mmh3.so) "$$WORK_DIR/python/pyfory/lib/mmh3"
            cp -f $(location python/pyfory/format/_format.so) "$$WORK_DIR/python/pyfory/format"
            cp -f $(location python/pyfory/_serialization.so) "$$WORK_DIR/python/pyfory"
        fi
        echo $$(date) > $@
    """,
    local = 1,
    tags = ["no-cache"],
    visibility = ["//visibility:public"],
)

refresh_compile_commands(
    name = "refresh_compile_commands",
    exclude_headers = "all",
    exclude_external_sources = True,
)