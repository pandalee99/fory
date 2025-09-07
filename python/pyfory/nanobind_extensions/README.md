# Nanobind Extensions with Official nanobind-bazel

This directory contains nanobind extensions built using the official [nanobind-bazel](https://github.com/nicholasjng/nanobind-bazel) package.

## Requirements

- Bazel 7.0+ (for full bzlmod support)
- Current project uses Bazel 6.3.2 (legacy WORKSPACE mode)

## Configuration

### WORKSPACE Configuration
```python
# Add nanobind-bazel for cross-platform nanobind support
http_archive(
    name = "nanobind_bazel",
    urls = ["https://github.com/nicholasjng/nanobind-bazel/archive/refs/tags/v2.8.0.tar.gz"],
    sha256 = "63c517c5d921214604c787e61b20b89c2213bbac9ba80b35ba570ac1b1432457",
    strip_prefix = "nanobind-bazel-2.8.0",
)
```

### Dependencies
- rules_cc (added to bazel/fory_deps_setup.bzl)
- rules_python (existing)

### BUILD File Usage
```python
load("@nanobind_bazel//:build_defs.bzl", "nanobind_extension")

nanobind_extension(
    name = "math_ops",
    srcs = ["math_ops.cpp"],
    hdrs = ["math_ops.h"],
)
```

## Notes

- This replaces the previous custom nanobind build scripts
- Official package provides better cross-platform support
- Configuration is ready for future Bazel upgrade
