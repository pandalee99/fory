# Contributing to Apache Fory Python

This document provides instructions for building and testing the `pyfory` package.

## Building

```bash
cd python
# Uninstall numpy first so that when we install pyarrow, it will install the correct numpy version automatically.
# For Python versions less than 3.13, numpy 2 is not currently supported.
pip uninstall -y numpy
# Install necessary environment for Python < 3.13.
pip install pyarrow==15.0.0 Cython wheel pytest
# For Python 3.13, pyarrow 18.0.0 is available and requires numpy version greater than 2.
# pip install pyarrow==18.0.0 Cython wheel pytest
pip install -v -e .
```

If the last steps fails with an error like `libarrow_python.dylib: No such file or directory`,
you are probably suffering from bazel's aggressive caching; the sought library is longer at the
temporary directory it was the last time bazel ran. To remedy this run

> bazel clean --expunge

In this situation, you might also find it fruitful to run bazel yourself before pip:

> bazel build -s //:cp_fory_so

### Environment Requirements

- python 3.8+

## Testing

```bash
cd python
pytest -v -s .
```

## Formatting

```bash
cd python
pip install ruff
ruff format python
```

## Debugging

```bash
cd python
python setup.py develop
```

- Use `cython --cplus -a  pyfory/_serialization.pyx` to produce an annotated HTML file of the source code. Then you can
  analyze interaction between Python objects and Python's C API.
- Read more: <https://cython.readthedocs.io/en/latest/src/userguide/debugging.html>

```bash
FORY_DEBUG=true python setup.py build_ext --inplace
# For linux
cygdb build
```

### Debugging with lldb

```bash
lldb
(lldb) target create -- python
(lldb) settings set -- target.run-args "-c" "from pyfory.tests.test_serializer import test_enum; test_enum()"
(lldb) run
(lldb) bt
```
