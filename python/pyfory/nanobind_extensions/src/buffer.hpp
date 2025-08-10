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

#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace pyfory {

/**
 * Simple buffer implementation that mimics the Cython Buffer class.
 * This provides basic binary data manipulation with reader/writer indices.
 */
class Buffer {
public:
    // Constructors (match Cython Buffer API)
    Buffer() : data_(), size_(0), reader_index_(0), writer_index_(0) {}
    
    explicit Buffer(const std::string& data)  // Match Buffer(b"bytes") pattern
        : data_(data.begin(), data.end()), size_(data.size()), reader_index_(0), writer_index_(0) {}
    
    explicit Buffer(const std::vector<uint8_t>& data)
        : data_(data), size_(data.size()), reader_index_(0), writer_index_(0) {}
    
    // Internal constructor for allocate
    explicit Buffer(size_t size) 
        : data_(size), size_(size), reader_index_(0), writer_index_(0) {}
    
    // Factory methods
    static Buffer allocate(int32_t size);
    
    // Size and capacity
    int32_t size() const { return size_; }
    int32_t capacity() const { return data_.size(); }
    void reserve(int32_t new_size);
    void resize(int32_t new_size);
    
    // Reader/writer indices
    int32_t reader_index() const { return reader_index_; }
    int32_t writer_index() const { return writer_index_; }
    void set_reader_index(int32_t index) { reader_index_ = index; }
    void set_writer_index(int32_t index) { writer_index_ = index; }
    
    // Bounds checking
    void check_bound(int32_t offset, int32_t length) const;
    
    // Put operations (write at specific offset)
    void put_bool(uint32_t offset, bool value);
    void put_int8(uint32_t offset, int8_t value);
    void put_uint8(uint32_t offset, uint8_t value);
    void put_int16(uint32_t offset, int16_t value);
    void put_int24(uint32_t offset, int32_t value);
    void put_int32(uint32_t offset, int32_t value);
    void put_int64(uint32_t offset, int64_t value);
    void put_float(uint32_t offset, float value);
    void put_double(uint32_t offset, double value);
    void put_bytes(uint32_t offset, const std::string& value);
    void put_bytes(uint32_t offset, const std::vector<uint8_t>& value);
    
    // Get operations (read from specific offset)
    bool get_bool(uint32_t offset) const;
    int8_t get_int8(uint32_t offset) const;
    uint8_t get_uint8(uint32_t offset) const;
    int16_t get_int16(uint32_t offset) const;
    int32_t get_int24(uint32_t offset) const;
    int32_t get_int32(uint32_t offset) const;
    int64_t get_int64(uint32_t offset) const;
    float get_float(uint32_t offset) const;
    double get_double(uint32_t offset) const;
    std::vector<uint8_t> get_bytes(uint32_t offset, uint32_t nbytes) const;
    
    // Write operations (write at writer_index and advance)
    void write_bool(bool value);
    void write_int8(int8_t value);
    void write_uint8(uint8_t value);
    void write_int16(int16_t value);
    void write_int24(int32_t value);
    void write_int32(int32_t value);
    void write_int64(int64_t value);
    void write_float(float value);
    void write_double(double value);
    void write_bytes(const std::string& value);
    void write_bytes(const std::vector<uint8_t>& value);
    void write_buffer(const std::string& value);  // Match Cython API
    void write_buffer(const std::vector<uint8_t>& value);
    void write_bytes_and_size(const std::string& value);
    void write_bytes_and_size(const std::vector<uint8_t>& value);
    
    // Read operations (read from reader_index and advance)
    bool read_bool();
    int8_t read_int8();
    uint8_t read_uint8();
    int16_t read_int16();
    int32_t read_int24();
    int32_t read_int32();
    int64_t read_int64();
    float read_float();
    double read_double();
    std::vector<uint8_t> read_bytes(int32_t length);
    std::vector<uint8_t> read_bytes_and_size();
    int64_t read_bytes_as_int64(int32_t length);
    
    // Variable length integer operations (match Cython API - return bytes written)
    int32_t write_varint32(int32_t value);
    int32_t write_varuint32(uint32_t value);
    int32_t write_varint64(int64_t value);
    int32_t write_varuint64(uint64_t value);
    int32_t read_varint32();
    uint32_t read_varuint32();
    int64_t read_varint64();
    uint64_t read_varuint64();
    
    // String operations
    void write_string(const std::string& value);
    std::string read_string();
    
    // Utility operations (match Cython API)
    void skip(int32_t length);
    void grow(int32_t needed_size);
    void ensure(int32_t length);
    std::string hex() const;  // Match Cython Buffer.hex()
    std::string to_hex() const;
    std::vector<uint8_t> to_bytes(int32_t offset = 0, int32_t length = 0) const;
    std::string to_pybytes(int32_t offset = 0, int32_t length = 0) const;  // Match Cython API
    
    // Buffer protocol support
    const uint8_t* data() const { return data_.data(); }
    uint8_t* mutable_data() { return data_.data(); }
    
    // Slicing and indexing
    Buffer slice(int32_t offset = 0, int32_t length = -1) const;
    uint8_t operator[](int32_t index) const;
    
    // String representation
    std::string repr() const;

private:
    std::vector<uint8_t> data_;
    int32_t size_;
    int32_t reader_index_;
    int32_t writer_index_;
    
    // Helper methods
    template<typename T>
    void put_value(uint32_t offset, T value);
    
    template<typename T>
    T get_value(uint32_t offset) const;
    
    template<typename T>
    void write_value(T value);
    
    template<typename T>
    T read_value();
};

} // namespace pyfory
