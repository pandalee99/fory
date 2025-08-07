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

"""
PyFory Nanobind Extensions

This package provides nanobind-based C++ extensions for PyFory,
demonstrating high-performance Python-C++ bindings.
"""

__version__ = "1.0.0"
__author__ = "PyFory Team"

# Try to import the compiled extension
try:
    from . import math_ops
    __all__ = ['math_ops']
except ImportError as e:
    import warnings
    warnings.warn(
        f"Failed to import nanobind extensions: {e}. "
        "Please build the extensions first. See README.md for instructions.",
        ImportWarning
    )
    __all__ = []
