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
TypeDef decoder for xlang serialization.

This module implements the decoding of TypeDef objects according to the xlang serialization specification.
"""

from typing import List
from pyfory._util import Buffer
from pyfory.meta.typedef import TypeDef, FieldInfo, FieldType
from pyfory.meta.typedef import (
    FieldInfo,
    TypeDef,
    SMALL_NUM_FIELDS_THRESHOLD,
    REGISTER_BY_NAME_FLAG,
    FIELD_NAME_SIZE_THRESHOLD,
    COMPRESS_META_FLAG,
    HAS_FIELDS_META_FLAG,
    META_SIZE_MASKS,
    NUM_HASH_BITS,
    FIELD_NAME_ENCODINGS,
)
from pyfory.type import TypeId
from pyfory.meta.metastring import MetaStringDecoder, Encoding


# Meta string decoders
NAMESPACE_DECODER = MetaStringDecoder(".", "_")
TYPENAME_DECODER = MetaStringDecoder("$", "_")
FIELD_NAME_DECODER = MetaStringDecoder("$", "_")


def decode_typedef(buffer: Buffer, resolver) -> TypeDef:
    """
    Decode a TypeDef from the buffer.

    Args:
        buffer: The buffer containing the encoded TypeDef.
        resolver: The type resolver.

    Returns:
        The decoded TypeDef.
    """
    # Read global binary header
    header = buffer.read_int64()

    # Extract components from header
    meta_size = header & META_SIZE_MASKS
    has_fields_meta = (header & HAS_FIELDS_META_FLAG) != 0
    is_compressed = (header & COMPRESS_META_FLAG) != 0

    # If meta size is at maximum, read additional size
    if meta_size == META_SIZE_MASKS:
        meta_size += buffer.read_varuint32()

    # Read meta data
    meta_data = buffer.read_bytes(meta_size)

    # Decompress if needed
    if is_compressed:
        meta_data = resolver.get_meta_compressor().decompress(meta_data)

    # Create a new buffer for meta data
    meta_buffer = Buffer(meta_data)

    # Read meta header
    meta_header = meta_buffer.read_uint8()

    # Extract number of fields
    num_fields = meta_header & 0b11111
    if num_fields == SMALL_NUM_FIELDS_THRESHOLD:
        num_fields += meta_buffer.read_varuint32()

    # Check if registered by name
    is_registered_by_name = (meta_header & REGISTER_BY_NAME_FLAG) != 0

    # Read type info
    if is_registered_by_name:
        namespace = read_namespace(meta_buffer)
        typename = read_typename(meta_buffer)
        name = namespace + "." + typename if namespace else typename
        # Look up the type_id from namespace and typename
        type_info = resolver.get_typeinfo_by_name(namespace, typename)
        if type_info:
            type_id = type_info.type_id
        else:
            # Fallback to COMPATIBLE_STRUCT if not found
            type_id = TypeId.COMPATIBLE_STRUCT
    else:
        type_id = meta_buffer.read_varuint32()
        type_info = resolver.get_typeinfo_by_id(type_id)
        name = type_info.cls.__name__

    # Read fields info if present
    field_infos = []
    if has_fields_meta:
        field_infos = read_fields_info(meta_buffer, resolver, name, num_fields)

    # Create TypeDef object
    return TypeDef(name, type_id, field_infos, meta_data, is_compressed)


def read_namespace(buffer: Buffer) -> str:
    """Read namespace from the buffer."""
    return read_meta_string(buffer, NAMESPACE_DECODER)


def read_typename(buffer: Buffer) -> str:
    """Read typename from the buffer."""
    return read_meta_string(buffer, TYPENAME_DECODER)


def read_meta_string(buffer: Buffer, decoder: MetaStringDecoder) -> str:
    """Read a meta string from the buffer."""
    # Read encoding and length combined in first byte
    header = buffer.read_uint8()

    # Extract encoding (2 bits) and size (6 bits)
    encoding_value = header & 0b11
    size_value = (header >> 2) & 0b111111

    encoding = Encoding(encoding_value)

    # Read length - same logic as encoder
    length = 0
    if size_value >= FIELD_NAME_SIZE_THRESHOLD:
        length = size_value - FIELD_NAME_SIZE_THRESHOLD + buffer.read_varuint32()
    else:
        length = size_value

    # Read encoded data
    if length > 0:
        encoded_data = buffer.read_bytes(length)
        return decoder.decode(encoded_data, encoding)
    else:
        return ""


def read_fields_info(buffer: Buffer, resolver, defined_class: str, num_fields: int) -> List[FieldInfo]:
    """Read field information from the buffer."""
    field_infos = []
    for _ in range(num_fields):
        field_info = read_field_info(buffer, resolver, defined_class)
        field_infos.append(field_info)
    return field_infos


def read_field_info(buffer: Buffer, resolver, defined_class: str) -> FieldInfo:
    """Read a single field info from the buffer."""
    # Read field header
    header = buffer.read_uint8()

    # Extract field header components
    field_name_encoding = (header >> 6) & 0b11
    field_name_size = (header >> 2) & 0b1111
    if field_name_size == FIELD_NAME_SIZE_THRESHOLD:
        field_name_size += buffer.read_varuint32()
    field_name_size += 1
    encoding = FIELD_NAME_ENCODINGS[field_name_encoding]
    is_nullable = (header & 0b10) != 0
    is_tracking_ref = header & 0b1

    # Read field type info (without flags since they're in the header)
    xtype_id = buffer.read_varuint32()
    field_type = FieldType.xread_with_type(buffer, resolver, xtype_id, is_nullable, is_tracking_ref)

    # Read field name
    field_name = FIELD_NAME_DECODER.decode(buffer.read_bytes(field_name_size), encoding)
    return FieldInfo(field_name, field_type, defined_class)
