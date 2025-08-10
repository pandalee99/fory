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

#include "buffer.hpp"
#include <stdexcept>
#include <sstream>
#include <iomanip>
#include <cstring>
#include <algorithm>

namespace pyfory {

Buffer Buffer::allocate(int32_t size) {
    if (size <= 0) {
        throw std::invalid_argument("Size must be positive");
    }
    return Buffer(size);
}

void Buffer::reserve(int32_t new_size) {
    if (new_size <= 0 || new_size >= (1 << 30)) {
        throw std::invalid_argument("Invalid size for reserve");
    }
    if (new_size > static_cast<int32_t>(data_.size())) {
        data_.resize(new_size);
    }
    size_ = new_size;
}

void Buffer::resize(int32_t new_size) {
    if (new_size < 0) {
        throw std::invalid_argument("Size cannot be negative");
    }
    data_.resize(new_size);
    size_ = new_size;
    reader_index_ = std::min(reader_index_, size_);
    writer_index_ = std::min(writer_index_, size_);
}

void Buffer::check_bound(int32_t offset, int32_t length) const {
    if (offset < 0 || length < 0 || offset + length > size_) {
        throw std::out_of_range("Address range [" + std::to_string(offset) + 
                               ", " + std::to_string(offset + length) + 
                               ") out of bound [0, " + std::to_string(size_) + ")");
    }
}

// Put operations
void Buffer::put_bool(uint32_t offset, bool value) {
    check_bound(offset, 1);
    data_[offset] = value ? 1 : 0;
}

void Buffer::put_int8(uint32_t offset, int8_t value) {
    check_bound(offset, 1);
    data_[offset] = static_cast<uint8_t>(value);
}

void Buffer::put_uint8(uint32_t offset, uint8_t value) {
    check_bound(offset, 1);
    data_[offset] = value;
}

void Buffer::put_int16(uint32_t offset, int16_t value) {
    check_bound(offset, 2);
    // Little-endian storage
    data_[offset] = static_cast<uint8_t>(value & 0xFF);
    data_[offset + 1] = static_cast<uint8_t>((value >> 8) & 0xFF);
}

void Buffer::put_int24(uint32_t offset, int32_t value) {
    check_bound(offset, 3);
    data_[offset] = static_cast<uint8_t>(value & 0xFF);
    data_[offset + 1] = static_cast<uint8_t>((value >> 8) & 0xFF);
    data_[offset + 2] = static_cast<uint8_t>((value >> 16) & 0xFF);
}

void Buffer::put_int32(uint32_t offset, int32_t value) {
    check_bound(offset, 4);
    std::memcpy(data_.data() + offset, &value, 4);
}

void Buffer::put_int64(uint32_t offset, int64_t value) {
    check_bound(offset, 8);
    std::memcpy(data_.data() + offset, &value, 8);
}

void Buffer::put_float(uint32_t offset, float value) {
    check_bound(offset, 4);
    std::memcpy(data_.data() + offset, &value, 4);
}

void Buffer::put_double(uint32_t offset, double value) {
    check_bound(offset, 8);
    std::memcpy(data_.data() + offset, &value, 8);
}

void Buffer::put_bytes(uint32_t offset, const std::string& value) {
    if (value.empty()) return;
    check_bound(offset, value.size());
    std::memcpy(data_.data() + offset, value.data(), value.size());
}

void Buffer::put_bytes(uint32_t offset, const std::vector<uint8_t>& value) {
    if (value.empty()) return;
    check_bound(offset, value.size());
    std::memcpy(data_.data() + offset, value.data(), value.size());
}

// Get operations
bool Buffer::get_bool(uint32_t offset) const {
    check_bound(offset, 1);
    return data_[offset] != 0;
}

int8_t Buffer::get_int8(uint32_t offset) const {
    check_bound(offset, 1);
    return static_cast<int8_t>(data_[offset]);
}

uint8_t Buffer::get_uint8(uint32_t offset) const {
    check_bound(offset, 1);
    return data_[offset];
}

int16_t Buffer::get_int16(uint32_t offset) const {
    check_bound(offset, 2);
    // Little-endian loading
    return static_cast<int16_t>(data_[offset] | (data_[offset + 1] << 8));
}

int32_t Buffer::get_int24(uint32_t offset) const {
    check_bound(offset, 3);
    int32_t result = data_[offset];
    result |= (static_cast<int32_t>(data_[offset + 1]) << 8);
    result |= (static_cast<int32_t>(data_[offset + 2]) << 16);
    return result;
}

int32_t Buffer::get_int32(uint32_t offset) const {
    check_bound(offset, 4);
    int32_t value;
    std::memcpy(&value, data_.data() + offset, 4);
    return value;
}

int64_t Buffer::get_int64(uint32_t offset) const {
    check_bound(offset, 8);
    int64_t value;
    std::memcpy(&value, data_.data() + offset, 8);
    return value;
}

float Buffer::get_float(uint32_t offset) const {
    check_bound(offset, 4);
    float value;
    std::memcpy(&value, data_.data() + offset, 4);
    return value;
}

double Buffer::get_double(uint32_t offset) const {
    check_bound(offset, 8);
    double value;
    std::memcpy(&value, data_.data() + offset, 8);
    return value;
}

std::vector<uint8_t> Buffer::get_bytes(uint32_t offset, uint32_t nbytes) const {
    if (nbytes == 0) return std::vector<uint8_t>();
    check_bound(offset, nbytes);
    return std::vector<uint8_t>(data_.begin() + offset, data_.begin() + offset + nbytes);
}

// Write operations (advance writer_index)
void Buffer::write_bool(bool value) {
    grow(1);
    put_bool(writer_index_, value);
    writer_index_ += 1;
}

void Buffer::write_int8(int8_t value) {
    grow(1);
    put_int8(writer_index_, value);
    writer_index_ += 1;
}

void Buffer::write_uint8(uint8_t value) {
    grow(1);
    put_uint8(writer_index_, value);
    writer_index_ += 1;
}

void Buffer::write_int16(int16_t value) {
    grow(2);
    put_int16(writer_index_, value);
    writer_index_ += 2;
}

void Buffer::write_int24(int32_t value) {
    grow(3);
    put_int24(writer_index_, value);
    writer_index_ += 3;
}

void Buffer::write_int32(int32_t value) {
    grow(4);
    put_int32(writer_index_, value);
    writer_index_ += 4;
}

void Buffer::write_int64(int64_t value) {
    grow(8);
    put_int64(writer_index_, value);
    writer_index_ += 8;
}

void Buffer::write_float(float value) {
    grow(4);
    put_float(writer_index_, value);
    writer_index_ += 4;
}

void Buffer::write_double(double value) {
    grow(8);
    put_double(writer_index_, value);
    writer_index_ += 8;
}

void Buffer::write_bytes(const std::string& value) {
    if (value.empty()) return;
    grow(value.size());
    put_bytes(writer_index_, value);
    writer_index_ += value.size();
}

void Buffer::write_bytes(const std::vector<uint8_t>& value) {
    if (value.empty()) return;
    grow(value.size());
    put_bytes(writer_index_, value);
    writer_index_ += value.size();
}

void Buffer::write_buffer(const std::string& value) {
    write_bytes(value);  // write_buffer is same as write_bytes in Cython
}

void Buffer::write_buffer(const std::vector<uint8_t>& value) {
    write_bytes(value);  // write_buffer is same as write_bytes in Cython
}

void Buffer::write_bytes_and_size(const std::string& value) {
    write_varuint32(value.size());
    write_bytes(value);
}

void Buffer::write_bytes_and_size(const std::vector<uint8_t>& value) {
    write_varuint32(value.size());
    write_bytes(value);
}

// Read operations (advance reader_index)
bool Buffer::read_bool() {
    bool value = get_bool(reader_index_);
    reader_index_ += 1;
    return value;
}

int8_t Buffer::read_int8() {
    int8_t value = get_int8(reader_index_);
    reader_index_ += 1;
    return value;
}

uint8_t Buffer::read_uint8() {
    uint8_t value = get_uint8(reader_index_);
    reader_index_ += 1;
    return value;
}

int16_t Buffer::read_int16() {
    int16_t value = get_int16(reader_index_);
    reader_index_ += 2;
    return value;
}

int32_t Buffer::read_int24() {
    int32_t value = get_int24(reader_index_);
    reader_index_ += 3;
    return value;
}

int32_t Buffer::read_int32() {
    int32_t value = get_int32(reader_index_);
    reader_index_ += 4;
    return value;
}

int64_t Buffer::read_int64() {
    int64_t value = get_int64(reader_index_);
    reader_index_ += 8;
    return value;
}

float Buffer::read_float() {
    float value = get_float(reader_index_);
    reader_index_ += 4;
    return value;
}

double Buffer::read_double() {
    double value = get_double(reader_index_);
    reader_index_ += 8;
    return value;
}

std::vector<uint8_t> Buffer::read_bytes(int32_t length) {
    std::vector<uint8_t> value = get_bytes(reader_index_, length);
    reader_index_ += length;
    return value;
}

std::vector<uint8_t> Buffer::read_bytes_and_size() {
    uint32_t length = read_varuint32();
    return read_bytes(length);
}

int64_t Buffer::read_bytes_as_int64(int32_t length) {
    if (length <= 0 || length > 8) {
        throw std::invalid_argument("Length must be between 1 and 8");
    }
    check_bound(reader_index_, length);
    int64_t result = 0;
    for (int i = 0; i < length; ++i) {
        result |= (static_cast<int64_t>(data_[reader_index_ + i]) << (i * 8));
    }
    reader_index_ += length;
    return result;
}

// Variable length integer operations
int32_t Buffer::write_varint32(int32_t value) {
    return write_varuint32(static_cast<uint32_t>((value << 1) ^ (value >> 31)));
}

int32_t Buffer::write_varuint32(uint32_t value) {
    grow(5);  // Maximum 5 bytes for varint32
    int32_t start = writer_index_;
    while (value >= 0x80) {
        data_[writer_index_++] = static_cast<uint8_t>((value & 0x7F) | 0x80);
        value >>= 7;
    }
    data_[writer_index_++] = static_cast<uint8_t>(value & 0x7F);
    return writer_index_ - start;  // Return bytes written
}

int32_t Buffer::write_varint64(int64_t value) {
    return write_varuint64(static_cast<uint64_t>((value << 1) ^ (value >> 63)));
}

int32_t Buffer::write_varuint64(uint64_t value) {
    grow(9);  // Maximum 9 bytes for varint64
    int32_t start = writer_index_;
    while (value >= 0x80) {
        data_[writer_index_++] = static_cast<uint8_t>((value & 0x7F) | 0x80);
        value >>= 7;
    }
    data_[writer_index_++] = static_cast<uint8_t>(value & 0x7F);
    return writer_index_ - start;  // Return bytes written
}

int32_t Buffer::read_varint32() {
    uint32_t value = read_varuint32();
    return static_cast<int32_t>((value >> 1) ^ -(value & 1));
}

uint32_t Buffer::read_varuint32() {
    uint32_t result = 0;
    int shift = 0;
    
    while (reader_index_ < size_) {
        uint8_t byte = data_[reader_index_++];
        result |= static_cast<uint32_t>(byte & 0x7F) << shift;
        if ((byte & 0x80) == 0) {
            break;
        }
        shift += 7;
        if (shift >= 32) {
            throw std::runtime_error("Varint32 too long");
        }
    }
    return result;
}

int64_t Buffer::read_varint64() {
    uint64_t value = read_varuint64();
    return static_cast<int64_t>((value >> 1) ^ -(value & 1));
}

uint64_t Buffer::read_varuint64() {
    uint64_t result = 0;
    int shift = 0;
    
    while (reader_index_ < size_) {
        uint8_t byte = data_[reader_index_++];
        result |= static_cast<uint64_t>(byte & 0x7F) << shift;
        if ((byte & 0x80) == 0) {
            break;
        }
        shift += 7;
        if (shift >= 64) {
            throw std::runtime_error("Varint64 too long");
        }
    }
    return result;
}

// String operations  
void Buffer::write_string(const std::string& value) {
    // Simple UTF-8 encoding with length prefix
    uint64_t header = (static_cast<uint64_t>(value.size()) << 2) | 2; // UTF-8 encoding
    write_varuint64(header);
    write_bytes(value);
}

std::string Buffer::read_string() {
    uint64_t header = read_varuint64();
    uint32_t size = static_cast<uint32_t>(header >> 2);
    std::vector<uint8_t> bytes = read_bytes(size);
    return std::string(bytes.begin(), bytes.end());
}

// Utility operations
void Buffer::skip(int32_t length) {
    check_bound(reader_index_, length);
    reader_index_ += length;
}

void Buffer::grow(int32_t needed_size) {
    int32_t required = writer_index_ + needed_size;
    if (required > size_) {
        reserve(std::max(required * 2, 64));
    }
}

void Buffer::ensure(int32_t length) {
    if (length > size_) {
        reserve(length * 2);
    }
}

std::string Buffer::to_hex() const {
    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    for (int32_t i = 0; i < size_; ++i) {
        oss << std::setw(2) << static_cast<unsigned>(data_[i]);
    }
    return oss.str();
}

std::string Buffer::hex() const {
    return to_hex();  // hex() is an alias for to_hex() to match Cython API
}

std::vector<uint8_t> Buffer::to_bytes(int32_t offset, int32_t length) const {
    if (length == 0) {
        length = size_ - offset;
    }
    check_bound(offset, length);
    return std::vector<uint8_t>(data_.begin() + offset, data_.begin() + offset + length);
}

std::string Buffer::to_pybytes(int32_t offset, int32_t length) const {
    if (length == 0) {
        length = size_ - offset;
    }
    check_bound(offset, length);
    return std::string(reinterpret_cast<const char*>(data_.data() + offset), length);
}

Buffer Buffer::slice(int32_t offset, int32_t length) const {
    if (length == -1) {
        length = size_ - offset;
    }
    check_bound(offset, length);
    
    std::vector<uint8_t> slice_data(data_.begin() + offset, data_.begin() + offset + length);
    return Buffer(slice_data);
}

uint8_t Buffer::operator[](int32_t index) const {
    if (index < 0 || index >= size_) {
        throw std::out_of_range("Index out of bounds");
    }
    return data_[index];
}

std::string Buffer::repr() const {
    return "Buffer(reader_index=" + std::to_string(reader_index_) + 
           ", writer_index=" + std::to_string(writer_index_) + 
           ", size=" + std::to_string(size_) + ")";
}

} // namespace pyfory
