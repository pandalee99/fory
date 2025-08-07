#!/bin/bash

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

# Build script for PyFory nanobind extensions

set -e  # Exit on any error

echo "=== Building PyFory Nanobind Extensions ==="

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTENSIONS_DIR="${SCRIPT_DIR}/pyfory/nanobind_extensions"

cd "${EXTENSIONS_DIR}"

# Clean and create build directory
echo "Setting up build directory..."
rm -rf build
mkdir build
cd build

# Configure and build
echo "Configuring with CMake..."
cmake ..

echo "Building..."
cmake --build . --parallel 4

echo "Copying extension to parent directory..."
find . -name "math_ops*.so" -o -name "math_ops*.dylib" -o -name "math_ops*.pyd" | head -1 | xargs -I {} cp {} ../

echo "Testing the extension..."
cd "${SCRIPT_DIR}"
python3 -c "
import sys
sys.path.insert(0, '.')
from pyfory.nanobind_extensions import math_ops
print('✓ Extension imported successfully')
result = math_ops.add(2, 3)
print(f'✓ Test: math_ops.add(2, 3) = {result}')
print(f'✓ Version: {math_ops.VERSION}')
print(f'✓ Author: {math_ops.AUTHOR}')
"

echo ""
echo "🎉 Build and test completed successfully!"
echo ""
echo "Usage:"
echo "  python3 -c \"from pyfory.nanobind_extensions import math_ops; print(math_ops.add(1, 2))\""
echo "  python3 pyfory/nanobind_extensions/example.py"
echo "  python3 -m pytest pyfory/nanobind_extensions/tests/ -v"
