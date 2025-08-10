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

from pyfory.buffer import Buffer
from pyfory.tests.core import require_pyarrow
from pyfory.util import lazy_import

# Import nanobind Buffer for testing
try:
    from pyfory.nanobind_extensions import buffer_ops
    NANOBIND_AVAILABLE = True
    NanobindBuffer = buffer_ops.Buffer
except ImportError:
    NANOBIND_AVAILABLE = False
    NanobindBuffer = None

pa = lazy_import("pyarrow")


def test_buffer():
    _test_buffer_impl(Buffer, "Cython")

def test_nanobind_buffer():
    """Test that nanobind Buffer has the same API and behavior as Cython Buffer."""
    if not NANOBIND_AVAILABLE:
        print("⚠️  Nanobind Buffer not available, skipping test")
        return
    _test_buffer_impl(NanobindBuffer, "Nanobind")

def _test_buffer_impl(BufferClass, impl_name: str):
    """Implementation-agnostic buffer test."""
    print(f"\n🧪 Testing {impl_name} Buffer implementation")
    
    buffer = BufferClass.allocate(8)
    buffer.write_bool(True)
    buffer.write_int8(-1)
    buffer.write_int8(2**7 - 1)
    buffer.write_int8(-(2**7))
    buffer.write_int16(2**15 - 1)
    buffer.write_int16(-(2**15))
    buffer.write_int32(2**31 - 1)
    buffer.write_int32(-(2**31))
    buffer.write_int64(2**63 - 1)
    buffer.write_int64(-(2**63))
    buffer.write_float(1.0)
    buffer.write_float(-1.0)
    buffer.write_double(1.0)
    buffer.write_double(-1.0)
    buffer.write_bytes(b"")  # write empty buffer
    buffer.write_buffer(b"")  # write empty buffer
    binary = b"b" * 100
    buffer.write_bytes(binary)
    buffer.write_bytes_and_size(binary)
    print(f"buffer size {buffer.size()}, writer_index {buffer.writer_index}")
    
    # Test different constructor approaches based on implementation
    if impl_name == "Cython":
        new_buffer = BufferClass(buffer.get_bytes(0, buffer.writer_index))
    else:  # Nanobind
        # For nanobind, we need to use to_pybytes() to get bytes format compatible with constructor
        new_buffer = BufferClass(buffer.to_pybytes(0, buffer.writer_index))
    
    assert new_buffer.read_bool() is True
    assert new_buffer.read_int8() == -1
    assert new_buffer.read_int8() == 2**7 - 1
    assert new_buffer.read_int8() == -(2**7)
    assert new_buffer.read_int16() == 2**15 - 1
    assert new_buffer.read_int16() == -(2**15)
    assert new_buffer.read_int32() == 2**31 - 1
    assert new_buffer.read_int32() == -(2**31)
    assert new_buffer.read_int64() == 2**63 - 1
    assert new_buffer.read_int64() == -(2**63)
    assert new_buffer.read_float() == 1.0
    assert new_buffer.read_float() == -1.0
    assert new_buffer.read_double() == 1.0
    assert new_buffer.read_double() == -1.0
    assert new_buffer.read_bytes(0) == b""
    assert new_buffer.read_bytes(0) == b""
    assert new_buffer.read_bytes(len(binary)) == binary
    assert new_buffer.read_bytes_and_size() == binary
    
    # Test hex functionality (works for both implementations)
    if hasattr(new_buffer, 'hex'):
        assert new_buffer.hex() == new_buffer.to_pybytes().hex() if hasattr(new_buffer, 'to_pybytes') else new_buffer.to_hex()
    
        # Test slicing (adjust for different implementations)
        if impl_name == "Cython":
            assert new_buffer[:10].to_pybytes() == new_buffer.to_pybytes()[:10]
            assert new_buffer[5:30].to_pybytes() == new_buffer.to_pybytes()[5:30]
            assert new_buffer[-30:].to_pybytes() == new_buffer.to_pybytes()[-30:]
            for i in range(len(new_buffer)):
                assert new_buffer[i] == new_buffer.to_pybytes()[i]
                assert new_buffer[-i + 1] == new_buffer.to_pybytes()[-i + 1]
        else:  # Nanobind - test what we can
            assert new_buffer.slice(0, 10).to_pybytes() == new_buffer.to_pybytes()[:10]
            for i in range(len(new_buffer)):
                # nanobind [i] returns int, to_pybytes()[i] also returns int for bytes
                assert new_buffer[i] == new_buffer.to_pybytes()[i]
def test_empty_buffer():
    _test_empty_buffer_impl(Buffer, "Cython")

def test_nanobind_empty_buffer():
    """Test nanobind Buffer empty buffer behavior."""
    if not NANOBIND_AVAILABLE:
        print("⚠️  Nanobind Buffer not available, skipping test")
        return  
    _test_empty_buffer_impl(NanobindBuffer, "Nanobind")

def _test_empty_buffer_impl(BufferClass, impl_name: str):
    """Implementation-agnostic empty buffer test."""
    print(f"\n🧪 Testing {impl_name} Buffer empty buffer behavior")
    
    writable_buffer = BufferClass.allocate(8)
    
    # Test different empty buffer creation methods
    empty_buffers = []
    
    # Only test allocate(0) for Cython, nanobind doesn't support it
    if impl_name == "Cython":
        empty_buffers.append(BufferClass.allocate(0))
    
    # Test empty bytes constructor - both should support this
    empty_buffers.append(BufferClass(b""))
    
    # Add slice-based empty buffers if supported
    if hasattr(BufferClass.allocate(8), 'slice'):
        empty_buffers.extend([
            BufferClass.allocate(8).slice(8),
            BufferClass(b"1").slice(1),
        ])
    
    for buffer in empty_buffers:
        # Test various methods work with empty buffers
        if impl_name == "Cython":
            assert buffer.to_bytes() == b""
            assert buffer.to_pybytes() == b""
            if hasattr(buffer, 'slice'):
                assert buffer.slice().to_bytes() == b""
            assert buffer.hex() == ""
        else:  # Nanobind
            assert buffer.to_pybytes() == b""
            assert buffer.slice().to_pybytes() == b""
            assert buffer.hex() == ""
            
        writable_buffer.put_int32(0, 10)
        writable_buffer.write_buffer(buffer)
        assert writable_buffer.get_int32(0) == 10


def test_write_varint32():
    _test_write_varint32_impl(Buffer, "Cython")

def test_nanobind_write_varint32():
    """Test nanobind Buffer varint32 functionality."""
    if not NANOBIND_AVAILABLE:
        print("⚠️  Nanobind Buffer not available, skipping test")
        return
    _test_write_varint32_impl(NanobindBuffer, "Nanobind")

def _test_write_varint32_impl(BufferClass, impl_name: str):
    """Implementation-agnostic varint32 test."""
    print(f"\n🧪 Testing {impl_name} Buffer varint32 functionality")
    
    buf = BufferClass.allocate(32)
    for i in range(1):
        for j in range(i):
            buf.write_int8(1)
            buf.read_int8()
        check_varuint32(buf, 1, 1)
        check_varuint32(buf, 1 << 6, 1)
        check_varuint32(buf, 1 << 7, 2)
        check_varuint32(buf, 1 << 13, 2)
        check_varuint32(buf, 1 << 14, 3)
        check_varuint32(buf, 1 << 20, 3)
        check_varuint32(buf, 1 << 21, 4)
        check_varuint32(buf, 1 << 27, 4)
        check_varuint32(buf, 1 << 28, 5)
        check_varuint32(buf, 1 << 30, 5)

        check_varint32(buf, -1)
        check_varint32(buf, -1 << 6)
        check_varint32(buf, -1 << 7)
        check_varint32(buf, -1 << 13)
        check_varint32(buf, -1 << 14)
        check_varint32(buf, -1 << 20)
        check_varint32(buf, -1 << 21)
        check_varint32(buf, -1 << 27)
        check_varint32(buf, -1 << 28)
        check_varint32(buf, -1 << 30)


def check_varuint32(buf: Buffer, value: int, bytes_written: int):
    assert buf.writer_index == buf.reader_index
    actual_bytes_written = buf.write_varuint32(value)
    assert actual_bytes_written == bytes_written
    varint = buf.read_varuint32()
    assert buf.writer_index == buf.reader_index
    assert value == varint


def check_varint32(buf: Buffer, value: int):
    assert buf.writer_index == buf.reader_index
    buf.write_varint32(value)
    varint = buf.read_varint32()
    assert buf.writer_index == buf.reader_index
    assert value == varint


@require_pyarrow
def test_buffer_protocol():
    buffer = Buffer.allocate(32)
    binary = b"b" * 100
    buffer.write_bytes_and_size(binary)
    assert bytes(buffer) == bytes(pa.py_buffer(buffer))
    assert buffer.to_bytes() == bytes(pa.py_buffer(buffer))


def test_grow():
    binary = b"a" * 10
    buffer = Buffer(binary)
    assert not buffer.own_data()
    buffer.write_bytes(binary)
    assert not buffer.own_data()
    buffer.write_bytes(binary)
    assert buffer.own_data()


def test_write_varuint64():
    buf = Buffer.allocate(32)
    check_varuint64(buf, -1, 9)
    for i in range(32):
        for j in range(i):
            buf.write_int8(1)
            buf.read_int8()
        check_varuint64(buf, -1, 9)
        check_varuint64(buf, 1, 1)
        check_varuint64(buf, 1 << 6, 1)
        check_varuint64(buf, 1 << 7, 2)
        check_varuint64(buf, -(2**6), 9)
        check_varuint64(buf, -(2**7), 9)
        check_varuint64(buf, 1 << 13, 2)
        check_varuint64(buf, 1 << 14, 3)
        check_varuint64(buf, -(2**13), 9)
        check_varuint64(buf, -(2**14), 9)
        check_varuint64(buf, 1 << 20, 3)
        check_varuint64(buf, 1 << 21, 4)
        check_varuint64(buf, -(2**20), 9)
        check_varuint64(buf, -(2**21), 9)
        check_varuint64(buf, 1 << 27, 4)
        check_varuint64(buf, 1 << 28, 5)
        check_varuint64(buf, -(2**27), 9)
        check_varuint64(buf, -(2**28), 9)
        check_varuint64(buf, 1 << 30, 5)
        check_varuint64(buf, -(2**30), 9)
        check_varuint64(buf, 1 << 31, 5)
        check_varuint64(buf, -(2**31), 9)
        check_varuint64(buf, 1 << 32, 5)
        check_varuint64(buf, -(2**32), 9)
        check_varuint64(buf, 1 << 34, 5)
        check_varuint64(buf, -(2**34), 9)
        check_varuint64(buf, 1 << 35, 6)
        check_varuint64(buf, -(2**35), 9)
        check_varuint64(buf, 1 << 41, 6)
        check_varuint64(buf, -(2**41), 9)
        check_varuint64(buf, 1 << 42, 7)
        check_varuint64(buf, -(2**42), 9)
        check_varuint64(buf, 1 << 48, 7)
        check_varuint64(buf, -(2**48), 9)
        check_varuint64(buf, 1 << 49, 8)
        check_varuint64(buf, -(2**49), 9)
        check_varuint64(buf, 1 << 55, 8)
        check_varuint64(buf, -(2**55), 9)
        check_varuint64(buf, 1 << 56, 9)
        check_varuint64(buf, -(2**56), 9)
        check_varuint64(buf, 1 << 62, 9)
        check_varuint64(buf, -(2**62), 9)
        check_varuint64(buf, 1 << 63 - 1, 9)
        check_varuint64(buf, -(2**63), 9)


def check_varuint64(buf: Buffer, value: int, bytes_written: int):
    reader_index = buf.reader_index
    assert buf.writer_index == buf.reader_index
    actual_bytes_written = buf.write_varuint64(value)
    assert actual_bytes_written == bytes_written
    varint = buf.read_varuint64()
    assert buf.writer_index == buf.reader_index
    assert value == varint
    # test slow read branch in `read_varint64`
    assert (
        buf.slice(reader_index, buf.reader_index - reader_index).read_varuint64()
        == value
    )


def test_write_buffer():
    buf = Buffer.allocate(32)
    buf.write(b"")
    buf.write(b"123")
    buf.write(Buffer.allocate(32))
    assert buf.writer_index == 35
    assert buf.read(0) == b""
    assert buf.read(3) == b"123"


def test_read_bytes_as_int64():
    # test small buffer whose length < 8
    buf = Buffer(b"1234")
    assert buf.read_bytes_as_int64(0) == 0
    assert buf.read_bytes_as_int64(1) == 49

    # test big buffer whose length > 8
    buf = Buffer(b"12345678901234")
    assert buf.read_bytes_as_int64(0) == 0
    assert buf.read_bytes_as_int64(1) == 49
    assert buf.read_bytes_as_int64(8) == 4123106164818064178

    # test fix for `OverflowError: Python int too large to convert to C long`
    buf = Buffer(b"\xa6IOr\x9ch)\x80\x12\x02")
    buf.read_bytes_as_int64(8)


if __name__ == "__main__":
    test_grow()
