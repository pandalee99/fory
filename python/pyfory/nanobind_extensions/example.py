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
Example usage of PyFory nanobind extensions.

This script demonstrates how to use the nanobind-based C++ extensions
for high-performance operations in PyFory.
"""

import sys
import os

# Add the parent directory to sys.path to make imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

def main():
    print("=== PyFory Nanobind Extensions Demo ===\n")
    
    try:
        from pyfory.nanobind_extensions import math_ops
        print("✓ Successfully imported nanobind extensions!")
        
        # Test basic addition
        print("\n--- Basic Addition ---")
        result = math_ops.add(5, 3)
        print(f"math_ops.add(5, 3) = {result}")
        
        # Test with default argument
        result = math_ops.add(10)
        print(f"math_ops.add(10) = {result}  # uses default b=1")
        
        # Test with keyword arguments
        result = math_ops.add(a=7, b=2)
        print(f"math_ops.add(a=7, b=2) = {result}")
        
        # Test multiplication
        print("\n--- Multiplication ---")
        result = math_ops.multiply(4, 6)
        print(f"math_ops.multiply(4, 6) = {result}")
        
        result = math_ops.multiply(3.14, 2.0)
        print(f"math_ops.multiply(3.14, 2.0) = {result}")
        
        # Test Calculator class
        print("\n--- Calculator Class ---")
        calc = math_ops.Calculator(100)
        print(f"Created calculator: {repr(calc)}")
        
        result = calc.add(50)
        print(f"calc.add(50) = {result}")
        print(f"Calculator state: {repr(calc)}")
        
        result = calc.subtract(25)
        print(f"calc.subtract(25) = {result}")
        print(f"Calculator state: {repr(calc)}")
        
        # Test module attributes
        print("\n--- Module Information ---")
        print(f"Version: {math_ops.VERSION}")
        print(f"Author: {math_ops.AUTHOR}")
        
        # Show function documentation
        print("\n--- Documentation ---")
        print("add() function documentation:")
        print(math_ops.add.__doc__)
        
    except ImportError as e:
        print(f"❌ Failed to import nanobind extensions: {e}")
        print("\nTo fix this issue:")
        print("1. Make sure nanobind is installed: pip install nanobind")
        print("2. Build the extensions:")
        print("   cd python/pyfory/nanobind_extensions")
        print("   mkdir build && cd build")
        print("   cmake ..")
        print("   make -j4")
        print("\nAlternatively, try building with setuptools:")
        print("   cd python")
        print("   python setup.py build_ext --inplace")
        return 1
    
    print("\n=== Demo completed successfully! ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
