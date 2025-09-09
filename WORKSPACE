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

workspace(name = "fory")

load("//bazel:fory_deps_setup.bzl", "setup_deps")
setup_deps()

load("@bazel_skylib//:workspace.bzl", "bazel_skylib_workspace")

load("//bazel/arrow:pyarrow_configure.bzl", "pyarrow_configure")
load("@bazel_tools//tools/build_defs/repo:git.bzl", "git_repository")  
load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

# Add Benchmark
git_repository(
    name = "com_google_benchmark",
    remote = "https://github.com/google/benchmark.git",
    tag = "v1.9.1",
)

# Add SIMDUTF
http_archive(
    name = "simdutf",
    urls = ["https://github.com/simdutf/simdutf/releases/download/v6.1.2/singleheader.zip"],
    sha256 = "41bb25074fe1e917e96e539c7a87c502e530d88746d7c25d06fb55a28b884340",
    build_file = "//cpp/fory/thirdparty:BUILD",
)

bazel_skylib_workspace()

load("@rules_python//python:repositories.bzl", "py_repositories")
py_repositories()

load("@rules_python//python:repositories.bzl", "python_register_toolchains")
python_register_toolchains(
    name = "python",
    python_version = "3.12",
)

load("@rules_python//python:pip.bzl", "pip_parse")
pip_parse(
   name = "pip_deps",
   requirements_lock = "//:requirements_lock.txt",
)

load("@pip_deps//:requirements.bzl", "install_deps")
install_deps()

pyarrow_configure(name="local_config_pyarrow")
