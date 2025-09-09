# Python configuration for Bazel
load("@rules_python//python:repositories.bzl", "python_register_toolchains")

def python_configure(name):
    # Use rules_python toolchain registration
    python_register_toolchains(
        name = "python3_toolchain",
        python_version = "3.11",
    )
    
    # Create a custom repository for Python headers
    native.new_local_repository(
        name = name,
        path = "/usr/include/python3.11",  # Adjust path as needed
        build_file_content = """
cc_library(
    name = "python_headers",
    hdrs = glob(["**/*.h"]),
    includes = ["."],
    visibility = ["//visibility:public"],
)
""",
    )
