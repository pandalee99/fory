# Custom BUILD file for Cython
load("@rules_python//python:defs.bzl", "py_binary", "py_library")

py_library(
    name = "cython_lib",
    srcs = glob(["Cython/**/*.py"]),
    visibility = ["//visibility:public"],
)

py_binary(
    name = "cython_binary",
    srcs = ["cython.py"],
    main = "cython.py",
    deps = [":cython_lib"],
    visibility = ["//visibility:public"],
)
