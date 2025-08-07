#!/usr/bin/env python3
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
Build script for PyFory nanobind extensions using setuptools.

This script provides an alternative to CMake for building the nanobind extensions.
It uses setuptools with nanobind integration.
"""

import os
import subprocess
import sys
from pathlib import Path

from setuptools import setup, Extension


def check_nanobind():
    """Check if nanobind is available and return cmake dir."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "nanobind", "--cmake_dir"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: nanobind not found. Please install it with:")
        print("  pip install nanobind")
        sys.exit(1)


def get_nanobind_cmake_info():
    """Get nanobind include directories and libraries."""
    cmake_dir = check_nanobind()
    
    # For setuptools integration, we need to get include paths
    try:
        import nanobind
        
        # Get include directories
        include_dirs = [nanobind.include_dir()]
        
        # Get nanobind cmake data
        cmake_args = [
            f"-Dnanobind_ROOT={cmake_dir}",
        ]
        
        return include_dirs, cmake_args
        
    except ImportError:
        print("ERROR: Cannot import nanobind. Please ensure it's properly installed.")
        sys.exit(1)


def create_nanobind_extension():
    """Create the nanobind extension using setuptools."""
    
    # Get current directory
    script_dir = Path(__file__).parent.absolute()
    extensions_dir = script_dir / "pyfory" / "nanobind_extensions"
    
    # Check if source file exists
    source_file = extensions_dir / "src" / "math_ops.cpp"
    if not source_file.exists():
        print(f"ERROR: Source file {source_file} not found!")
        sys.exit(1)
    
    include_dirs, cmake_args = get_nanobind_cmake_info()
    
    # Create extension
    ext = Extension(
        name="pyfory.nanobind_extensions.math_ops",
        sources=[str(source_file)],
        include_dirs=include_dirs,
        language="c++",
        cxx_std=17,
    )
    
    return [ext]


def main():
    """Main build function."""
    print("Building PyFory nanobind extensions...")
    
    # Change to the script directory
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    try:
        extensions = create_nanobind_extension()
        
        setup(
            name="pyfory-nanobind-extensions",
            ext_modules=extensions,
            zip_safe=False,
            python_requires=">=3.8",
        )
        
    except Exception as e:
        print(f"ERROR: Failed to build extensions: {e}")
        print("\nTry using CMake instead:")
        print("  cd python/pyfory/nanobind_extensions")
        print("  mkdir build && cd build")
        print("  cmake ..")
        print("  make -j4")
        sys.exit(1)


if __name__ == "__main__":
    main()
