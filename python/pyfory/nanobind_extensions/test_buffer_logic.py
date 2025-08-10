#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyFory Buffer Logic Tests
Tests all functionality of the nanobind Buffer implementation.

Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
"""

import sys
import os
import traceback
from typing import List, Any

# Add the build directory to Python path to import our nanobind module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'build'))

try:
    import buffer_ops
except ImportError as e:
    print(f"Error importing buffer_ops: {e}")
    print("Please make sure the nanobind module is built first.")
    print("Run: ./build_nanobind_extensions.sh")
    sys.exit(1)


class BufferLogicTester:
    """Comprehensive test suite for Buffer functionality."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def assert_equal(self, actual, expected, test_name: str):
        """Assert that actual equals expected."""
        try:
            if actual == expected:
                self.passed += 1
                print(f"✅ {test_name}")
                return True
            else:
                self.failed += 1
                print(f"❌ {test_name}")
                print(f"   Expected: {expected}")
                print(f"   Actual: {actual}")
                return False
        except Exception as e:
            self.failed += 1
            print(f"❌ {test_name} - Exception: {e}")
            return False
    
    def assert_true(self, condition: bool, test_name: str):
        """Assert that condition is True."""
        return self.assert_equal(condition, True, test_name)
    
    def assert_false(self, condition: bool, test_name: str):
        """Assert that condition is False."""
        return self.assert_equal(condition, False, test_name)
    
    def run_test(self, test_func, test_name: str):
        """Run a single test with error handling."""
        try:
            print(f"\n🧪 Running {test_name}")
            test_func()
        except Exception as e:
            self.failed += 1
            print(f"❌ {test_name} - Exception: {e}")
            traceback.print_exc()
    
    def test_buffer_creation(self):
        """Test buffer creation and basic properties."""
        # Test empty buffer
        buf1 = buffer_ops.Buffer()
        self.assert_equal(buf1.size(), 0, "Empty buffer size")
        self.assert_equal(buf1.reader_index, 0, "Empty buffer reader index")
        self.assert_equal(buf1.writer_index, 0, "Empty buffer writer index")
        
        # Test buffer with size
        buf2 = buffer_ops.Buffer(100)
        self.assert_equal(buf2.size(), 100, "Sized buffer size")
        self.assert_true(buf2.capacity() >= 100, "Sized buffer capacity")
        
        # Test buffer from data
        data = [1, 2, 3, 4, 5]
        buf3 = buffer_ops.Buffer(data)
        self.assert_equal(buf3.size(), 5, "Data buffer size")
        
        # Test allocate
        buf4 = buffer_ops.Buffer.allocate(50)
        self.assert_equal(buf4.size(), 50, "Allocated buffer size")
    
    def test_put_get_operations(self):
        """Test put/get operations at specific offsets."""
        buf = buffer_ops.Buffer(100)
        
        # Test boolean
        buf.put_bool(0, True)
        self.assert_equal(buf.get_bool(0), True, "Put/get bool True")
        buf.put_bool(1, False)
        self.assert_equal(buf.get_bool(1), False, "Put/get bool False")
        
        # Test integers
        buf.put_int8(2, -42)
        self.assert_equal(buf.get_int8(2), -42, "Put/get int8")
        
        buf.put_uint8(3, 200)
        self.assert_equal(buf.get_uint8(3), 200, "Put/get uint8")
        
        buf.put_int16(4, -12345)
        self.assert_equal(buf.get_int16(4), -12345, "Put/get int16")
        
        buf.put_int24(6, 1000000)
        self.assert_equal(buf.get_int24(6), 1000000, "Put/get int24")
        
        buf.put_int32(9, -123456789)
        self.assert_equal(buf.get_int32(9), -123456789, "Put/get int32")
        
        buf.put_int64(13, -9223372036854775808)  # MIN_INT64
        self.assert_equal(buf.get_int64(13), -9223372036854775808, "Put/get int64")
        
        # Test floating point
        buf.put_float(21, 3.14159)
        self.assert_true(abs(buf.get_float(21) - 3.14159) < 0.001, "Put/get float")
        
        buf.put_double(25, 2.718281828459045)
        self.assert_true(abs(buf.get_double(25) - 2.718281828459045) < 0.00001, "Put/get double")
        
        # Test bytes
        test_bytes = [1, 2, 3, 4, 5]
        buf.put_bytes(33, test_bytes)
        result_bytes = buf.get_bytes(33, 5)
        self.assert_equal(result_bytes, test_bytes, "Put/get bytes")
    
    def test_write_read_operations(self):
        """Test write/read operations that advance indices."""
        buf = buffer_ops.Buffer(1000)
        
        # Test write/read boolean
        buf.write_bool(True)
        buf.write_bool(False)
        self.assert_equal(buf.writer_index, 2, "Write bool advances writer index")
        
        buf.reader_index = 0
        self.assert_equal(buf.read_bool(), True, "Read bool True")
        self.assert_equal(buf.read_bool(), False, "Read bool False")
        self.assert_equal(buf.reader_index, 2, "Read bool advances reader index")
        
        # Test write/read integers
        buf.write_int8(-42)
        buf.write_uint8(200)
        buf.write_int16(-12345)
        buf.write_int32(-123456789)
        buf.write_int64(-9223372036854775808)
        
        buf.reader_index = 2
        self.assert_equal(buf.read_int8(), -42, "Write/read int8")
        self.assert_equal(buf.read_uint8(), 200, "Write/read uint8")
        self.assert_equal(buf.read_int16(), -12345, "Write/read int16")
        self.assert_equal(buf.read_int32(), -123456789, "Write/read int32")
        self.assert_equal(buf.read_int64(), -9223372036854775808, "Write/read int64")
        
        # Test write/read floating point
        buf.write_float(3.14159)
        buf.write_double(2.718281828459045)
        
        # Read floats from correct position
        float_start = buf.writer_index - 12  # float(4) + double(8)
        buf.reader_index = float_start
        float_val = buf.read_float()
        double_val = buf.read_double()
        self.assert_true(abs(float_val - 3.14159) < 0.001, "Write/read float")
        self.assert_true(abs(double_val - 2.718281828459045) < 0.00001, "Write/read double")
        
        # Test write/read bytes
        test_bytes = [10, 20, 30, 40, 50]
        buf.write_bytes(test_bytes)
        buf.reader_index = buf.writer_index - 5  # Go back to read bytes
        result_bytes = buf.read_bytes(5)
        self.assert_equal(result_bytes, test_bytes, "Write/read bytes")
        
        # Test write/read bytes with size
        test_bytes2 = [100, 101, 102]
        start_writer = buf.writer_index
        buf.write_bytes_and_size(test_bytes2)
        buf.reader_index = start_writer  # Go back to exact start position
        result_bytes2 = buf.read_bytes_and_size()
        self.assert_equal(result_bytes2, test_bytes2, "Write/read bytes and size")
    
    def test_varint_operations(self):
        """Test variable-length integer encoding/decoding."""
        buf = buffer_ops.Buffer(1000)
        
        # Test various varint32 values
        test_values_32 = [0, 1, -1, 127, -127, 128, -128, 16383, -16383, 16384, -16384]
        for value in test_values_32:
            buf.writer_index = 0
            buf.reader_index = 0
            buf.write_varint32(value)
            buf.reader_index = 0
            result = buf.read_varint32()
            self.assert_equal(result, value, f"Varint32: {value}")
        
        # Test various varuint32 values  
        test_values_u32 = [0, 1, 127, 128, 16383, 16384, 4294967295]
        for value in test_values_u32:
            buf.writer_index = 0
            buf.reader_index = 0
            buf.write_varuint32(value)
            buf.reader_index = 0
            result = buf.read_varuint32()
            self.assert_equal(result, value, f"Varuint32: {value}")
        
        # Test various varint64 values
        test_values_64 = [0, 1, -1, 127, -127, 128, -128, 
                          9223372036854775807, -9223372036854775808]
        for value in test_values_64:
            buf.writer_index = 0
            buf.reader_index = 0
            buf.write_varint64(value)
            buf.reader_index = 0
            result = buf.read_varint64()
            self.assert_equal(result, value, f"Varint64: {value}")
        
        # Test various varuint64 values
        test_values_u64 = [0, 1, 127, 128, 18446744073709551615]
        for value in test_values_u64:
            buf.writer_index = 0
            buf.reader_index = 0
            buf.write_varuint64(value)
            buf.reader_index = 0
            result = buf.read_varuint64()
            self.assert_equal(result, value, f"Varuint64: {value}")
    
    def test_string_operations(self):
        """Test string encoding/decoding."""
        buf = buffer_ops.Buffer(1000)
        
        # Test ASCII string
        test_string1 = "Hello, World!"
        buf.write_string(test_string1)
        buf.reader_index = 0
        result1 = buf.read_string()
        self.assert_equal(result1, test_string1, "ASCII string")
        
        # Test UTF-8 string
        test_string2 = "Hello, 世界! 🌍"
        buf.writer_index = 0
        buf.reader_index = 0
        buf.write_string(test_string2)
        buf.reader_index = 0
        result2 = buf.read_string()
        self.assert_equal(result2, test_string2, "UTF-8 string")
        
        # Test empty string
        test_string3 = ""
        buf.writer_index = 0
        buf.reader_index = 0
        buf.write_string(test_string3)
        buf.reader_index = 0
        result3 = buf.read_string()
        self.assert_equal(result3, test_string3, "Empty string")
    
    def test_buffer_management(self):
        """Test buffer management operations."""
        buf = buffer_ops.Buffer(10)
        
        # Test resize
        original_size = buf.size()
        buf.resize(20)
        self.assert_equal(buf.size(), 20, "Buffer resize")
        
        # Test reserve
        buf.reserve(100)
        self.assert_true(buf.capacity() >= 100, "Buffer reserve")
        
        # Test grow
        buf.writer_index = buf.size()
        buf.grow(50)
        self.assert_true(buf.size() >= buf.writer_index + 50, "Buffer grow")
        
        # Test ensure
        buf.ensure(200)
        self.assert_true(buf.capacity() >= 200, "Buffer ensure")
        
        # Test skip
        buf.reader_index = 0
        original_reader = buf.reader_index
        buf.skip(5)
        self.assert_equal(buf.reader_index, original_reader + 5, "Buffer skip")
    
    def test_indexing_and_slicing(self):
        """Test indexing and slicing operations."""
        data = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        buf = buffer_ops.Buffer(data)
        
        # Test indexing
        self.assert_equal(buf[0], 0, "Buffer index 0")
        self.assert_equal(buf[5], 5, "Buffer index 5")
        self.assert_equal(buf[9], 9, "Buffer index 9")
        
        # Test length
        self.assert_equal(len(buf), 10, "Buffer length")
        
        # Test slicing
        slice_buf = buf.slice(2, 5)
        self.assert_equal(slice_buf.size(), 5, "Buffer slice size")
        expected_slice = [2, 3, 4, 5, 6]
        for i in range(5):
            self.assert_equal(slice_buf[i], expected_slice[i], f"Buffer slice index {i}")
        
        # Test slice with default parameters
        full_slice = buf.slice()
        self.assert_equal(full_slice.size(), buf.size(), "Buffer full slice")
    
    def test_utility_operations(self):
        """Test utility operations."""
        data = [0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF]
        buf = buffer_ops.Buffer(data)
        
        # Test to_hex
        hex_str = buf.to_hex()
        expected_hex = "0123456789abcdef"
        self.assert_equal(hex_str, expected_hex, "Buffer to_hex")
        
        # Test to_bytes
        bytes_result = buf.to_bytes()
        self.assert_equal(bytes_result, data, "Buffer to_bytes full")
        
        # Test to_bytes with offset and length
        partial_bytes = buf.to_bytes(2, 4)
        expected_partial = [0x45, 0x67, 0x89, 0xAB]
        self.assert_equal(partial_bytes, expected_partial, "Buffer to_bytes partial")
        
        # Test repr
        repr_str = buf.__repr__()
        self.assert_true(len(repr_str) > 0, "Buffer repr not empty")
        self.assert_true("Buffer" in repr_str, "Buffer repr contains 'Buffer'")
    
    def test_complex_scenarios(self):
        """Test complex scenarios combining multiple operations."""
        buf = buffer_ops.Buffer(1000)
        
        # Scenario: Mixed data types
        buf.write_string("Header")
        buf.write_int32(42)
        buf.write_float(3.14159)
        buf.write_varint64(9223372036854775807)
        buf.write_bytes([1, 2, 3, 4, 5])
        buf.write_bool(True)
        
        # Read back in order
        buf.reader_index = 0
        header = buf.read_string()
        int_val = buf.read_int32()
        float_val = buf.read_float()
        varint_val = buf.read_varint64()
        bytes_val = buf.read_bytes(5)
        bool_val = buf.read_bool()
        
        self.assert_equal(header, "Header", "Complex scenario: string")
        self.assert_equal(int_val, 42, "Complex scenario: int32")
        self.assert_true(abs(float_val - 3.14159) < 0.001, "Complex scenario: float")
        self.assert_equal(varint_val, 9223372036854775807, "Complex scenario: varint64")
        self.assert_equal(bytes_val, [1, 2, 3, 4, 5], "Complex scenario: bytes")
        self.assert_equal(bool_val, True, "Complex scenario: bool")
    
    def run_all_tests(self):
        """Run all tests and report results."""
        print("🚀 Starting PyFory Buffer Logic Tests")
        print("=" * 50)
        
        self.run_test(self.test_buffer_creation, "Buffer Creation")
        self.run_test(self.test_put_get_operations, "Put/Get Operations")
        self.run_test(self.test_write_read_operations, "Write/Read Operations")
        self.run_test(self.test_varint_operations, "Variable Integer Operations")
        self.run_test(self.test_string_operations, "String Operations")
        self.run_test(self.test_buffer_management, "Buffer Management")
        self.run_test(self.test_indexing_and_slicing, "Indexing and Slicing")
        self.run_test(self.test_utility_operations, "Utility Operations")
        self.run_test(self.test_complex_scenarios, "Complex Scenarios")
        
        print("\n" + "=" * 50)
        print(f"📊 Test Results: {self.passed} passed, {self.failed} failed")
        
        if self.failed == 0:
            print("🎉 All tests passed! Buffer implementation is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Please check the implementation.")
            return False


def main():
    """Main test runner."""
    tester = BufferLogicTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
