/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/operators.h>
#include "buffer.hpp"

namespace nb = nanobind;
using namespace nb::literals;

/**
 * Nanobind module for Buffer operations.
 * This module provides a complete Buffer implementation compatible with PyFory's Cython version.
 */
NB_MODULE(buffer_ops, m) {
    m.doc() = "PyFory nanobind Buffer implementation - high-performance binary data manipulation";
    
    // Bind the Buffer class
    nb::class_<pyfory::Buffer>(m, "Buffer", 
        "High-performance buffer for binary data manipulation with reader/writer indices")
        
        // Constructors (match Cython API)
        .def(nb::init<>(), "Create an empty buffer")
        .def(nb::init<const std::string&>(), "data"_a, "Create a buffer from bytes")
        .def(nb::init<const std::vector<uint8_t>&>(), "data"_a, "Create a buffer from byte vector")
        .def("__init__", [](pyfory::Buffer* t, nb::bytes data) {
            new (t) pyfory::Buffer(std::string(data.c_str(), data.size()));
        }, "data"_a, "Create a buffer from Python bytes")
        
        // Factory methods (match Cython API)
        .def_static("allocate", &pyfory::Buffer::allocate, "size"_a,
            "Allocate a new buffer with the specified size")
        
        // Size and capacity methods
        .def("size", &pyfory::Buffer::size, "Get the current buffer size")
        .def("capacity", &pyfory::Buffer::capacity, "Get the buffer capacity")
        .def("reserve", &pyfory::Buffer::reserve, "new_size"_a, "Reserve space for new_size bytes")
        .def("resize", &pyfory::Buffer::resize, "new_size"_a, "Resize the buffer to new_size")
        
        // Reader/writer index properties
        .def_prop_rw("reader_index", 
            &pyfory::Buffer::reader_index, &pyfory::Buffer::set_reader_index,
            "Current reader index position")
        .def_prop_rw("writer_index",
            &pyfory::Buffer::writer_index, &pyfory::Buffer::set_writer_index, 
            "Current writer index position")
        
        // Put operations (write at specific offset)
        .def("put_bool", &pyfory::Buffer::put_bool, "offset"_a, "value"_a,
            "Write a boolean value at the specified offset")
        .def("put_int8", &pyfory::Buffer::put_int8, "offset"_a, "value"_a,
            "Write an int8 value at the specified offset")
        .def("put_uint8", &pyfory::Buffer::put_uint8, "offset"_a, "value"_a, 
            "Write a uint8 value at the specified offset")
        .def("put_int16", &pyfory::Buffer::put_int16, "offset"_a, "value"_a,
            "Write an int16 value at the specified offset")
        .def("put_int24", &pyfory::Buffer::put_int24, "offset"_a, "value"_a,
            "Write a 24-bit integer value at the specified offset")
        .def("put_int32", &pyfory::Buffer::put_int32, "offset"_a, "value"_a,
            "Write an int32 value at the specified offset")
        .def("put_int64", &pyfory::Buffer::put_int64, "offset"_a, "value"_a,
            "Write an int64 value at the specified offset")
        .def("put_float", &pyfory::Buffer::put_float, "offset"_a, "value"_a,
            "Write a float value at the specified offset")
        .def("put_double", &pyfory::Buffer::put_double, "offset"_a, "value"_a,
            "Write a double value at the specified offset")
        .def("put_bytes", static_cast<void (pyfory::Buffer::*)(uint32_t, const std::string&)>(&pyfory::Buffer::put_bytes), "offset"_a, "value"_a,
            "Write bytes at the specified offset")
        .def("put_bytes", static_cast<void (pyfory::Buffer::*)(uint32_t, const std::vector<uint8_t>&)>(&pyfory::Buffer::put_bytes), "offset"_a, "value"_a,
            "Write bytes at the specified offset")
        
        // Get operations (read from specific offset)
        .def("get_bool", &pyfory::Buffer::get_bool, "offset"_a,
            "Read a boolean value from the specified offset")
        .def("get_int8", &pyfory::Buffer::get_int8, "offset"_a,
            "Read an int8 value from the specified offset")
        .def("get_uint8", &pyfory::Buffer::get_uint8, "offset"_a,
            "Read a uint8 value from the specified offset")
        .def("get_int16", &pyfory::Buffer::get_int16, "offset"_a,
            "Read an int16 value from the specified offset")
        .def("get_int24", &pyfory::Buffer::get_int24, "offset"_a,
            "Read a 24-bit integer from the specified offset")
        .def("get_int32", &pyfory::Buffer::get_int32, "offset"_a,
            "Read an int32 value from the specified offset")
        .def("get_int64", &pyfory::Buffer::get_int64, "offset"_a,
            "Read an int64 value from the specified offset")
        .def("get_float", &pyfory::Buffer::get_float, "offset"_a,
            "Read a float value from the specified offset")
        .def("get_double", &pyfory::Buffer::get_double, "offset"_a,
            "Read a double value from the specified offset")
        .def("get_bytes", &pyfory::Buffer::get_bytes, "offset"_a, "nbytes"_a,
            "Read bytes from the specified offset")
        
        // Write operations (write at writer_index and advance)
        .def("write_bool", &pyfory::Buffer::write_bool, "value"_a,
            "Write a boolean value at writer_index and advance")
        .def("write_int8", &pyfory::Buffer::write_int8, "value"_a,
            "Write an int8 value at writer_index and advance")
        .def("write_uint8", &pyfory::Buffer::write_uint8, "value"_a,
            "Write a uint8 value at writer_index and advance")
        .def("write_int16", &pyfory::Buffer::write_int16, "value"_a,
            "Write an int16 value at writer_index and advance")
        .def("write_int24", &pyfory::Buffer::write_int24, "value"_a,
            "Write a 24-bit integer at writer_index and advance")
        .def("write_int32", &pyfory::Buffer::write_int32, "value"_a,
            "Write an int32 value at writer_index and advance")
        .def("write_int64", &pyfory::Buffer::write_int64, "value"_a,
            "Write an int64 value at writer_index and advance")
        .def("write_float", &pyfory::Buffer::write_float, "value"_a,
            "Write a float value at writer_index and advance")
        .def("write_double", &pyfory::Buffer::write_double, "value"_a,
            "Write a double value at writer_index and advance")
        .def("write_bytes", static_cast<void (pyfory::Buffer::*)(const std::string&)>(&pyfory::Buffer::write_bytes), "value"_a,
            "Write bytes at writer_index and advance")
        .def("write_bytes", static_cast<void (pyfory::Buffer::*)(const std::vector<uint8_t>&)>(&pyfory::Buffer::write_bytes), "value"_a,
            "Write bytes at writer_index and advance")
        .def("write_bytes", [](pyfory::Buffer& self, nb::bytes data) {
            std::string str(data.c_str(), data.size());
            self.write_bytes(str);
        }, "value"_a, "Write bytes from Python bytes object")
        .def("write_buffer", static_cast<void (pyfory::Buffer::*)(const std::string&)>(&pyfory::Buffer::write_buffer), "value"_a,
            "Write buffer at writer_index and advance")
        .def("write_buffer", static_cast<void (pyfory::Buffer::*)(const std::vector<uint8_t>&)>(&pyfory::Buffer::write_buffer), "value"_a,
            "Write buffer at writer_index and advance")
        .def("write_buffer", [](pyfory::Buffer& self, nb::bytes data) {
            std::string str(data.c_str(), data.size());
            self.write_buffer(str);
        }, "value"_a, "Write buffer from Python bytes object")
        .def("write_bytes_and_size", static_cast<void (pyfory::Buffer::*)(const std::string&)>(&pyfory::Buffer::write_bytes_and_size), "value"_a,
            "Write bytes with size prefix at writer_index and advance")
        .def("write_bytes_and_size", static_cast<void (pyfory::Buffer::*)(const std::vector<uint8_t>&)>(&pyfory::Buffer::write_bytes_and_size), "value"_a,
            "Write bytes with size prefix at writer_index and advance")
        .def("write_bytes_and_size", [](pyfory::Buffer& self, nb::bytes data) {
            std::string str(data.c_str(), data.size());
            self.write_bytes_and_size(str);
        }, "value"_a, "Write bytes with size prefix from Python bytes object")
        
        // Read operations (read from reader_index and advance)
        .def("read_bool", &pyfory::Buffer::read_bool,
            "Read a boolean value from reader_index and advance")
        .def("read_int8", &pyfory::Buffer::read_int8,
            "Read an int8 value from reader_index and advance")
        .def("read_uint8", &pyfory::Buffer::read_uint8,
            "Read a uint8 value from reader_index and advance")
        .def("read_int16", &pyfory::Buffer::read_int16,
            "Read an int16 value from reader_index and advance")
        .def("read_int24", &pyfory::Buffer::read_int24,
            "Read a 24-bit integer from reader_index and advance")
        .def("read_int32", &pyfory::Buffer::read_int32,
            "Read an int32 value from reader_index and advance")
        .def("read_int64", &pyfory::Buffer::read_int64,
            "Read an int64 value from reader_index and advance")
        .def("read_float", &pyfory::Buffer::read_float,
            "Read a float value from reader_index and advance")
        .def("read_double", &pyfory::Buffer::read_double,
            "Read a double value from reader_index and advance")
        .def("read_bytes", [](pyfory::Buffer& self, int32_t length) -> nb::bytes {
            auto vec = self.read_bytes(length);
            return nb::bytes(reinterpret_cast<const char*>(vec.data()), vec.size());
        }, "length"_a, "Read bytes from reader_index and advance")
        .def("read_bytes_and_size", [](pyfory::Buffer& self) -> nb::bytes {
            auto vec = self.read_bytes_and_size();
            return nb::bytes(reinterpret_cast<const char*>(vec.data()), vec.size());
        }, "Read bytes with size prefix from reader_index and advance")
        .def("read_bytes_as_int64", &pyfory::Buffer::read_bytes_as_int64, "length"_a,
            "Read bytes as int64 from reader_index and advance")
        
        // Variable length integer operations (match Cython API - return bytes written)
        .def("write_varint32", &pyfory::Buffer::write_varint32, "value"_a,
            "Write a signed 32-bit variable-length integer, return bytes written")
        .def("write_varuint32", &pyfory::Buffer::write_varuint32, "value"_a,
            "Write an unsigned 32-bit variable-length integer, return bytes written")
        .def("write_varint64", &pyfory::Buffer::write_varint64, "value"_a,
            "Write a signed 64-bit variable-length integer, return bytes written")
        .def("write_varuint64", &pyfory::Buffer::write_varuint64, "value"_a,
            "Write an unsigned 64-bit variable-length integer, return bytes written")
        .def("read_varint32", &pyfory::Buffer::read_varint32,
            "Read a signed 32-bit variable-length integer")
        .def("read_varuint32", &pyfory::Buffer::read_varuint32,
            "Read an unsigned 32-bit variable-length integer")
        .def("read_varint64", &pyfory::Buffer::read_varint64,
            "Read a signed 64-bit variable-length integer")
        .def("read_varuint64", &pyfory::Buffer::read_varuint64,
            "Read an unsigned 64-bit variable-length integer")
        
        // String operations
        .def("write_string", &pyfory::Buffer::write_string, "value"_a,
            "Write a string with encoding header")
        .def("read_string", &pyfory::Buffer::read_string,
            "Read a string with encoding header")
        
        // Utility operations (match Cython API)
        .def("skip", &pyfory::Buffer::skip, "length"_a,
            "Skip the specified number of bytes in reader_index")
        .def("grow", &pyfory::Buffer::grow, "needed_size"_a,
            "Grow the buffer to accommodate needed_size more bytes")
        .def("ensure", &pyfory::Buffer::ensure, "length"_a,
            "Ensure the buffer has at least length bytes")
        .def("hex", &pyfory::Buffer::hex,
            "Get hexadecimal representation of buffer content (Cython API)")
        .def("to_hex", &pyfory::Buffer::to_hex,
            "Get hexadecimal representation of buffer content")
        .def("to_bytes", &pyfory::Buffer::to_bytes, "offset"_a = 0, "length"_a = 0,
            "Convert buffer content to bytes vector")
        .def("to_pybytes", [](const pyfory::Buffer& self, int32_t offset = 0, int32_t length = 0) -> nb::bytes {
            std::string data = self.to_pybytes(offset, length);
            return nb::bytes(data.data(), data.size());
        }, "offset"_a = 0, "length"_a = 0,
            "Convert buffer content to bytes string (Cython API)")
        .def("get_bytes", &pyfory::Buffer::get_bytes, "offset"_a, "nbytes"_a,
            "Get bytes from the specified offset")
        
        // Slicing and indexing
        .def("slice", &pyfory::Buffer::slice, "offset"_a = 0, "length"_a = -1,
            "Create a new buffer from a slice of this buffer")
        .def("__getitem__", [](const pyfory::Buffer& buf, int32_t index) {
            return buf[index];
        }, "Get byte at index")
        
        // Special methods
        .def("__len__", &pyfory::Buffer::size, "Get buffer size")
        .def("__repr__", &pyfory::Buffer::repr, "String representation of buffer");
    
    // Module constants
    m.attr("VERSION") = "1.0.0";
    m.attr("AUTHOR") = "PyFory Team";
}
