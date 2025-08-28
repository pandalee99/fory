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
Enhanced Compatible Serializer Implementation

This module provides a comprehensive implementation of schema evolution
for Fory serialization, supporting forward and backward compatibility
between different versions of data structures.

Key Features:
- Type Definition (TypeDef) based serialization with schema metadata
- Intelligent field matching for schema evolution
- Performance optimized implementation
- Both Python and Cython support
- Comprehensive error handling and recovery
"""

import logging
import hashlib
import dataclasses
import struct
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Dict, List, Set, Optional, Type, Union, get_type_hints, get_origin, get_args
import inspect
from abc import ABC, abstractmethod
from collections import defaultdict
import weakref

from pyfory.buffer import Buffer
from pyfory.serializer import CrossLanguageCompatibleSerializer
from pyfory.type import TypeId
import pyfory._struct as _struct

logger = logging.getLogger(__name__)

# Schema evolution constants - matching Java implementation
SCHEMA_CONSISTENT = 0
SCHEMA_COMPATIBLE = 1

# Field encoding types
NOT_NULL_VALUE_FLAG = -1
NULL_FLAG = -3
END_TAG = -1

# Field type encodings
FIELD_TYPE_EMBEDDED_4 = 0    # Small types like bool, int8
FIELD_TYPE_EMBEDDED_9 = 1    # Medium types like int32, float
FIELD_TYPE_EMBEDDED_HASH = 2 # Complex embedded types like strings
FIELD_TYPE_SEPARATE_HASH = 3 # Complex separate types like objects

# Type definition encodings
TYPE_DEF_ID_OFFSET = 0b11111111  # Special marker for first-time type definition


class FieldType:
    """Field type classification for optimization"""
    BASIC = "basic"          # int, float, bool, str
    NULLABLE_BASIC = "nullable_basic"  # Optional[int], etc
    COLLECTION = "collection"  # List, Dict, Set, etc  
    OBJECT = "object"        # User-defined classes
    UNION = "union"          # Union types


def get_field_classification(type_hint: Type) -> str:
    """Classify field type for serialization optimization"""
    if type_hint in (bool, int, float, str, bytes):
        return FieldType.BASIC
    
    origin = get_origin(type_hint)
    if origin is Union:
        args = get_args(type_hint)
        if len(args) == 2 and type(None) in args:
            # Optional[T] case
            other_type = args[0] if args[1] is type(None) else args[1]
            if other_type in (bool, int, float, str, bytes):
                return FieldType.NULLABLE_BASIC
            return FieldType.OBJECT
        return FieldType.UNION
    
    if origin in (list, tuple, set, dict):
        return FieldType.COLLECTION
    
    return FieldType.OBJECT


class FieldInfo:
    """Enhanced field information for compatibility tracking"""
    
    __slots__ = ('name', 'type_hint', 'field_type', 'classification', 
                 'encoded_field_info', 'type_id', 'nullable', 'default_value')
    
    def __init__(self, name: str, type_hint: Type, field_type: int, 
                 type_id: int = 0, default_value: Any = None):
        self.name = name
        self.type_hint = type_hint
        self.field_type = field_type
        self.type_id = type_id
        self.classification = get_field_classification(type_hint)
        self.nullable = self._is_nullable()
        self.default_value = default_value
        self.encoded_field_info = self._encode_field_info()
    
    def _is_nullable(self) -> bool:
        """Check if field can be null"""
        origin = get_origin(self.type_hint)
        if origin is Union:
            args = get_args(self.type_hint)
            return type(None) in args
        return False
    
    def _encode_field_info(self) -> int:
        """Encode field information for wire format"""
        # Use FNV-1a hash for better distribution and determinism
        name_bytes = self.name.encode('utf-8')
        hash_val = 2166136261  # FNV offset basis
        for byte in name_bytes:
            hash_val ^= byte
            hash_val = (hash_val * 16777619) & 0xFFFFFFFF
        
        # Combine field type and hash - ensuring uniqueness
        return ((self.field_type & 0x7) << 29) | (hash_val & 0x1FFFFFFF)
    
    def is_embedded(self) -> bool:
        """Check if field should be embedded (basic types)"""
        return self.field_type in (
            FIELD_TYPE_EMBEDDED_4, 
            FIELD_TYPE_EMBEDDED_9, 
            FIELD_TYPE_EMBEDDED_HASH
        )
    
    def can_fast_serialize(self) -> bool:
        """Check if field can use optimized serialization path"""
        return self.classification in (FieldType.BASIC, FieldType.NULLABLE_BASIC)


def _determine_field_type(type_hint: Type) -> int:
    """Determine appropriate field encoding type"""
    classification = get_field_classification(type_hint)
    
    if classification == FieldType.BASIC:
        if type_hint in (bool,):
            return FIELD_TYPE_EMBEDDED_4
        elif type_hint in (int, float):
            return FIELD_TYPE_EMBEDDED_9
        elif type_hint in (str, bytes):
            return FIELD_TYPE_EMBEDDED_HASH
    elif classification == FieldType.NULLABLE_BASIC:
        return FIELD_TYPE_EMBEDDED_HASH
    
    return FIELD_TYPE_SEPARATE_HASH


class TypeDefinition:
    """Type definition containing schema information"""
    
    __slots__ = ('type_cls', 'type_id', 'field_infos', 'schema_hash',
                 '_field_lookup', '_embedded_fields', '_separate_fields', 
                 '_fast_fields', 'is_dataclass', 'constructor_hints')
    
    def __init__(self, type_cls: Type, type_id: int):
        self.type_cls = type_cls
        self.type_id = type_id
        self.is_dataclass = is_dataclass(type_cls)
        self.field_infos = self._extract_field_infos()
        self.schema_hash = self._calculate_schema_hash()
        self.constructor_hints = self._get_constructor_info()
        
        # Create optimized lookups
        self._field_lookup = {f.name: f for f in self.field_infos}
        self._embedded_fields = [f for f in self.field_infos if f.is_embedded()]
        self._separate_fields = [f for f in self.field_infos if not f.is_embedded()]
        self._fast_fields = [f for f in self.field_infos if f.can_fast_serialize()]
    
    def _extract_field_infos(self) -> List[FieldInfo]:
        """Extract field information from class with enhanced analysis"""
        field_infos = []
        
        if self.is_dataclass:
            # Handle dataclass with full introspection
            for field in fields(self.type_cls):
                field_type = _determine_field_type(field.type)
                default_value = None
                if field.default != dataclasses.MISSING:
                    default_value = field.default
                elif field.default_factory != dataclasses.MISSING:
                    default_value = field.default_factory
                
                field_info = FieldInfo(field.name, field.type, field_type, 
                                     default_value=default_value)
                field_infos.append(field_info)
        else:
            # Handle regular class with comprehensive type hint analysis
            try:
                type_hints = get_type_hints(self.type_cls)
                for name, type_hint in type_hints.items():
                    if not name.startswith('_'):  # Skip private fields
                        field_type = _determine_field_type(type_hint)
                        field_info = FieldInfo(name, type_hint, field_type)
                        field_infos.append(field_info)
            except (NameError, AttributeError, TypeError) as e:
                logger.warning(f"Failed to get type hints for {self.type_cls}: {e}")
                # Fallback: use __annotations__ or __slots__
                if hasattr(self.type_cls, '__annotations__'):
                    for name, type_hint in self.type_cls.__annotations__.items():
                        field_type = _determine_field_type(type_hint)
                        field_info = FieldInfo(name, type_hint, field_type)
                        field_infos.append(field_info)
                elif hasattr(self.type_cls, '__slots__'):
                    for name in self.type_cls.__slots__:
                        field_info = FieldInfo(name, Any, FIELD_TYPE_SEPARATE_HASH)
                        field_infos.append(field_info)
        
        # Sort by name for deterministic ordering
        return sorted(field_infos, key=lambda f: f.name)
    
    def _calculate_schema_hash(self) -> int:
        """Calculate deterministic schema hash using more comprehensive method"""
        # Create canonical representation
        schema_components = [
            self.type_cls.__name__,
            self.type_cls.__module__ if hasattr(self.type_cls, '__module__') else '',
        ]
        
        for field_info in self.field_infos:
            type_repr = self._get_type_representation(field_info.type_hint)
            component = f"{field_info.name}:{type_repr}:{field_info.field_type}"
            schema_components.append(component)
        
        schema_str = '|'.join(schema_components)
        
        # Use SHA-256 for consistency across platforms and Python versions
        hash_bytes = hashlib.sha256(schema_str.encode('utf-8')).digest()
        # Convert to 32-bit signed integer for compatibility
        return struct.unpack('>i', hash_bytes[:4])[0]
    
    def _get_type_representation(self, type_hint: Type) -> str:
        """Get canonical string representation of type"""
        if hasattr(type_hint, '__name__'):
            return type_hint.__name__
        
        # Handle complex types like Optional, Union, List, etc.
        origin = get_origin(type_hint)
        if origin:
            args = get_args(type_hint)
            if origin is Union and len(args) == 2 and type(None) in args:
                # Optional[T] case
                inner_type = args[0] if args[1] is type(None) else args[1]
                return f"Optional[{self._get_type_representation(inner_type)}]"
            elif origin in (list, List):
                if args:
                    return f"List[{self._get_type_representation(args[0])}]"
                return "List"
            elif origin in (dict, Dict):
                if len(args) >= 2:
                    return f"Dict[{self._get_type_representation(args[0])},{self._get_type_representation(args[1])}]"
                return "Dict"
        
        return str(type_hint)
    
    def _get_constructor_info(self) -> Dict[str, Any]:
        """Analyze constructor for optimal object creation"""
        if self.is_dataclass:
            return {'type': 'dataclass'}
        
        try:
            sig = inspect.signature(self.type_cls.__init__)
            params = {}
            for name, param in sig.parameters.items():
                if name != 'self':
                    params[name] = {
                        'has_default': param.default != inspect.Parameter.empty,
                        'default': param.default if param.default != inspect.Parameter.empty else None
                    }
            return {'type': 'regular', 'params': params}
        except (TypeError, ValueError):
            return {'type': 'unknown'}
    
    def get_field_by_name(self, name: str) -> Optional[FieldInfo]:
        """Get field info by name - optimized lookup"""
        return self._field_lookup.get(name)
    
    def get_field_by_encoded_info(self, encoded_info: int) -> Optional[FieldInfo]:
        """Find field by encoded information"""
        for field_info in self.field_infos:
            if field_info.encoded_field_info == encoded_info:
                return field_info
        return None
    
    @property
    def embedded_fields(self) -> List[FieldInfo]:
        """Get embedded fields for fast serialization"""
        return self._embedded_fields
    
    @property
    def separate_fields(self) -> List[FieldInfo]:
        """Get separate fields requiring reference serialization"""
        return self._separate_fields


class MetaContext:
    """Enhanced meta context for schema management"""
    
    def __init__(self, enable_compression: bool = True):
        self.type_definitions: Dict[int, TypeDefinition] = {}
        self.type_to_definition: Dict[Type, TypeDefinition] = {}
        self.type_id_to_sent: Dict[int, bool] = {}  # Track which type defs were sent
        self._next_type_id = 1000  # Start from 1000 for compatibility
        self._enable_compression = enable_compression
        self._schema_cache = weakref.WeakValueDictionary()  # Cache for performance
    
    def register_type(self, type_cls: Type) -> int:
        """Register type and return its ID"""
        if type_cls in self.type_to_definition:
            # Find existing type ID
            for type_id, type_def in self.type_definitions.items():
                if type_def.type_cls == type_cls:
                    return type_id
        
        # Create new type definition
        type_id = self._next_type_id
        self._next_type_id += 1
        
        type_def = TypeDefinition(type_cls, type_id)
        self.type_definitions[type_id] = type_def
        self.type_to_definition[type_cls] = type_def
        self.type_id_to_sent[type_id] = False
        
        logger.debug(f"Registered type {type_cls.__name__} -> ID={type_id}, hash={type_def.schema_hash}")
        return type_id
    
    def register_class(self, type_cls: Type) -> int:
        """Alias for register_type for compatibility"""
        return self.register_type(type_cls)
    
    def get_type_definition(self, type_id: int) -> Optional[TypeDefinition]:
        """Get type definition by ID"""
        return self.type_definitions.get(type_id)
    
    def get_type_definition_by_type(self, type_cls: Type) -> Optional[TypeDefinition]:
        """Get type definition by type"""
        return self.type_to_definition.get(type_cls)
    
    def mark_type_def_sent(self, type_id: int):
        """Mark type definition as sent"""
        self.type_id_to_sent[type_id] = True
    
    def is_type_def_sent(self, type_id: int) -> bool:
        """Check if type definition was already sent"""
        return self.type_id_to_sent.get(type_id, False)
    
    def reset_session(self):
        """Reset session state (for new serialization contexts)"""
        self.type_id_to_sent.clear()


class EnhancedCompatibleSerializer(CrossLanguageCompatibleSerializer):
    """
    Enhanced compatible serializer with comprehensive schema evolution support.
    
    Features:
    - Optimized field serialization based on type classification
    - Intelligent schema evolution with field matching
    - Performance optimizations for common patterns
    - Comprehensive error handling and recovery
    - Support for both Python-only and cross-language serialization
    """
    
    def __init__(self, fory, type_cls: Type):
        super().__init__(fory, type_cls)
        self.type_cls = type_cls
        
        # Initialize or get meta context
        if not hasattr(fory, 'meta_context'):
            fory.meta_context = MetaContext()
        self.meta_context = fory.meta_context
        
        # Register type and get definition
        self.type_id = self.meta_context.register_class(type_cls)
        self.type_def = self.meta_context.get_type_definition(self.type_id)
        
        # Performance optimization flags
        self._has_fast_fields = len(self.type_def.field_infos) > 0
        self._all_embedded = len(self.type_def.separate_fields) == 0
    
    def write(self, buffer: Buffer, value: Any):
        """Serialize object with schema evolution support"""
        self._write_compatible(buffer, value, xlang=False)
    
    def read(self, buffer: Buffer) -> Any:
        """Deserialize object with schema evolution support"""
        return self._read_compatible(buffer, xlang=False)
    
    def xwrite(self, buffer: Buffer, value: Any):
        """Cross-language compatible serialization"""
        self._write_compatible(buffer, value, xlang=True)
    
    def xread(self, buffer: Buffer) -> Any:
        """Cross-language compatible deserialization"""
        return self._read_compatible(buffer, xlang=True)
    
    def _write_compatible(self, buffer: Buffer, value: Any, xlang: bool):
        """Core serialization with type definition management"""
        type_id = self.type_id
        type_def = self.type_def
        
        # Write type ID with potential type definition
        if not self.meta_context.is_type_def_sent(type_id):
            # First time: write type definition
            buffer.write_varint32((type_id << 1) | TYPE_DEF_ID_OFFSET)
            self._write_type_definition(buffer, type_def)
            self.meta_context.mark_type_def_sent(type_id)
        else:
            # Reference to existing definition
            buffer.write_varint32(type_id << 1)
        
        # Write schema hash for verification
        buffer.write_int32(type_def.schema_hash)
        
        # Serialize fields using optimized approach
        if self._all_embedded and self._has_fast_fields:
            self._write_fast_path(buffer, value, type_def, xlang)
        else:
            self._write_general_path(buffer, value, type_def, xlang)
        
        # Write end marker
        buffer.write_varint64(END_TAG)
    
    def _write_type_definition(self, buffer: Buffer, type_def: TypeDefinition):
        """Write complete type definition to buffer"""
        # Write class name and module
        buffer.write_string(type_def.type_cls.__name__)
        module_name = getattr(type_def.type_cls, '__module__', '')
        buffer.write_string(module_name)
        
        # Write field count and field information
        buffer.write_varint32(len(type_def.field_infos))
        
        for field_info in type_def.field_infos:
            buffer.write_string(field_info.name)
            buffer.write_int8(field_info.field_type)
            
            # Write type information for complex types
            if field_info.field_type == FIELD_TYPE_SEPARATE_HASH:
                type_repr = type_def._get_type_representation(field_info.type_hint)
                buffer.write_string(type_repr)
    
    def _write_fast_path(self, buffer: Buffer, value: Any, type_def: TypeDefinition, xlang: bool):
        """Optimized serialization for simple embedded types"""
        for field_info in type_def._fast_fields:
            field_value = self._get_field_value(value, field_info.name)
            
            if field_info.nullable and field_value is None:
                buffer.write_int8(NULL_FLAG)
                continue
            else:
                buffer.write_int8(NOT_NULL_VALUE_FLAG)
            
            # Fast serialization for basic types
            if field_info.classification == FieldType.BASIC:
                self._write_basic_type(buffer, field_value, field_info.type_hint)
            else:  # nullable basic
                inner_type = self._get_inner_nullable_type(field_info.type_hint)
                self._write_basic_type(buffer, field_value, inner_type)
    
    def _write_general_path(self, buffer: Buffer, value: Any, type_def: TypeDefinition, xlang: bool):
        """General serialization path with full compatibility features"""
        # Write embedded fields first (grouped by type for efficiency)
        self._write_embedded_fields_grouped(buffer, value, type_def.embedded_fields, xlang)
        
        # Write separate fields
        for field_info in type_def.separate_fields:
            buffer.write_int32(field_info.encoded_field_info)
            field_value = self._get_field_value(value, field_info.name)
            self._write_field_value(buffer, field_info, field_value, xlang)
    
    def _write_embedded_fields_grouped(self, buffer: Buffer, value: Any, 
                                     embedded_fields: List[FieldInfo], xlang: bool):
        """Write embedded fields grouped by type for better compression"""
        # Group by field type for better serialization efficiency
        type_groups = defaultdict(list)
        for field_info in embedded_fields:
            type_groups[field_info.field_type].append(field_info)
        
        # Write in deterministic order
        for field_type in sorted(type_groups.keys()):
            fields = type_groups[field_type]
            for field_info in fields:
                buffer.write_int32(field_info.encoded_field_info)
                field_value = self._get_field_value(value, field_info.name)
                self._write_field_value(buffer, field_info, field_value, xlang)
    
    def _write_basic_type(self, buffer: Buffer, value: Any, type_hint: Type):
        """Optimized writing for basic types"""
        if type_hint == bool:
            buffer.write_bool(value)
        elif type_hint == int:
            buffer.write_varint64(value)
        elif type_hint == float:
            buffer.write_double(value)
        elif type_hint == str:
            buffer.write_string(value)
        elif type_hint == bytes:
            buffer.write_bytes(value)
        else:
            # Fallback for unexpected types
            logger.warning(f"Unexpected basic type: {type_hint}")
            buffer.write_string(str(value))
    
    def _write_field_value(self, buffer: Buffer, field_info: FieldInfo, field_value: Any, xlang: bool):
        """Write field value with appropriate serialization method"""
        if field_info.is_embedded():
            # Handle null for embedded types
            if field_info.nullable and field_value is None:
                buffer.write_int8(NULL_FLAG)
                return
            else:
                buffer.write_int8(NOT_NULL_VALUE_FLAG)
            
            # Serialize based on classification
            if field_info.classification == FieldType.BASIC:
                self._write_basic_type(buffer, field_value, field_info.type_hint)
            elif field_info.classification == FieldType.NULLABLE_BASIC:
                inner_type = self._get_inner_nullable_type(field_info.type_hint)
                self._write_basic_type(buffer, field_value, inner_type)
            else:
                # Fallback to reference serialization
                if xlang:
                    self.fory.xserialize_ref(buffer, field_value)
                else:
                    self.fory.serialize_ref(buffer, field_value)
        else:
            # Handle separate types
            if xlang:
                self.fory.xserialize_ref(buffer, field_value)
            else:
                self.fory.serialize_ref(buffer, field_value)
    
    def _read_compatible(self, buffer: Buffer, xlang: bool) -> Any:
        """Enhanced deserialization with schema evolution support"""
        # Read type ID/reference
        type_id_info = buffer.read_varint32()
        
        remote_type_def = None
        if type_id_info & 1 == TYPE_DEF_ID_OFFSET:
            # This is a first-time type definition
            remote_type_id = type_id_info >> 1
            remote_type_def = self._read_type_definition(buffer)
            logger.debug(f"Received new type definition for ID {remote_type_id}")
        else:
            # Reference to existing type definition
            remote_type_id = type_id_info >> 1
            logger.debug(f"Using cached type definition for ID {remote_type_id}")
        
        # Read and verify schema hash
        remote_schema_hash = buffer.read_int32()
        local_schema_hash = self.type_def.schema_hash
        
        field_values = {}
        
        if remote_schema_hash == local_schema_hash and remote_type_def is None:
            # Schema matches perfectly - use optimized path
            logger.debug("Schema matches - using optimized deserialization")
            self._read_same_schema(buffer, field_values, xlang)
        else:
            # Schema evolution case - use compatibility mode
            logger.debug(f"Schema evolution detected: remote={remote_schema_hash}, local={local_schema_hash}")
            self._read_evolved_schema(buffer, field_values, remote_type_def, xlang)
        
        return self._create_object(field_values)
    
    def _read_type_definition(self, buffer: Buffer) -> TypeDefinition:
        """Read type definition from buffer"""
        class_name = buffer.read_string()
        module_name = buffer.read_string()
        field_count = buffer.read_varint32()
        
        # Create a temporary type definition for compatibility checking
        field_infos = []
        for _ in range(field_count):
            field_name = buffer.read_string()
            field_type = buffer.read_int8()
            
            if field_type == FIELD_TYPE_SEPARATE_HASH:
                type_repr = buffer.read_string()
                # Try to resolve type from string representation
                type_hint = self._resolve_type_from_repr(type_repr)
            else:
                # For embedded types, we can infer from field_type
                type_hint = self._infer_type_from_field_type(field_type)
            
            field_info = FieldInfo(field_name, type_hint, field_type)
            field_infos.append(field_info)
        
        # Create a temporary type definition
        class RemoteTypeDef:
            def __init__(self):
                self.type_cls = type(f"RemoteClass_{class_name}", (), {})
                self.field_infos = field_infos
                self._field_lookup = {f.name: f for f in field_infos}
            
            def get_field_by_encoded_info(self, encoded_info: int) -> Optional[FieldInfo]:
                for field_info in self.field_infos:
                    if field_info.encoded_field_info == encoded_info:
                        return field_info
                return None
        
        return RemoteTypeDef()
    
    def _read_same_schema(self, buffer: Buffer, field_values: Dict[str, Any], xlang: bool):
        """Optimized reading when schemas match"""
        if self._all_embedded and self._has_fast_fields:
            self._read_fast_path(buffer, field_values, xlang)
        else:
            self._read_fields_in_order(buffer, field_values, self.type_def.field_infos, xlang)
        
        # Read and verify end tag
        end_tag = buffer.read_varint64()
        if end_tag != END_TAG:
            logger.warning(f"Expected end tag {END_TAG}, got {end_tag}")
    
    def _read_fast_path(self, buffer: Buffer, field_values: Dict[str, Any], xlang: bool):
        """Optimized reading for simple types"""
        for field_info in self.type_def._fast_fields:
            if field_info.nullable:
                null_flag = buffer.read_int8()
                if null_flag == NULL_FLAG:
                    field_values[field_info.name] = None
                    continue
            
            # Read basic type value
            if field_info.classification == FieldType.BASIC:
                value = self._read_basic_type(buffer, field_info.type_hint)
            else:  # nullable basic
                inner_type = self._get_inner_nullable_type(field_info.type_hint)
                value = self._read_basic_type(buffer, inner_type)
            
            field_values[field_info.name] = value
    
    def _read_evolved_schema(self, buffer: Buffer, field_values: Dict[str, Any], 
                           remote_type_def: Optional[TypeDefinition], xlang: bool):
        """Read with schema evolution support"""
        logger.debug("Reading with schema evolution support")
        
        # Read fields by scanning and matching
        while True:
            try:
                # Check for end tag
                peek_pos = buffer.reader_index
                if buffer.reader_index >= buffer.writer_index:
                    break
                
                next_val = buffer.read_varint64()
                if next_val == END_TAG:
                    break
                
                buffer.reader_index = peek_pos  # Reset position
                
                # Read field encoding
                encoded_info = buffer.read_int32()
                logger.debug(f"Reading field with encoding: {encoded_info}")
                
                # Try to match with local schema
                local_field = self.type_def.get_field_by_encoded_info(encoded_info)
                
                if local_field:
                    logger.debug(f"Matched local field: {local_field.name}")
                    value = self._read_field_value(buffer, local_field, xlang)
                    field_values[local_field.name] = value
                else:
                    # Try to match with remote schema
                    if remote_type_def:
                        remote_field = remote_type_def.get_field_by_encoded_info(encoded_info)
                        if remote_field:
                            logger.debug(f"Found remote field: {remote_field.name}, skipping")
                            self._skip_field_value(buffer, remote_field, xlang)
                        else:
                            logger.debug(f"Unknown field encoding {encoded_info}, attempting generic skip")
                            self._skip_unknown_field(buffer, xlang)
                    else:
                        logger.debug(f"Unknown field encoding {encoded_info}, attempting generic skip")
                        self._skip_unknown_field(buffer, xlang)
                        
            except Exception as e:
                logger.warning(f"Error during schema evolution reading: {e}")
                break
        
        # Fill in default values for missing fields
        self._fill_default_values(field_values)
    
    def _read_fields_in_order(self, buffer: Buffer, field_values: Dict[str, Any], 
                            field_infos: List[FieldInfo], xlang: bool):
        """Read fields in predefined order"""
        for field_info in field_infos:
            encoded_info = buffer.read_int32()
            if encoded_info != field_info.encoded_field_info:
                logger.warning(f"Field encoding mismatch for {field_info.name}: "
                             f"expected {field_info.encoded_field_info}, got {encoded_info}")
            
            value = self._read_field_value(buffer, field_info, xlang)
            field_values[field_info.name] = value
    
    def _read_basic_type(self, buffer: Buffer, type_hint: Type) -> Any:
        """Optimized reading for basic types"""
        if type_hint == bool:
            return buffer.read_bool()
        elif type_hint == int:
            return buffer.read_varint64()
        elif type_hint == float:
            return buffer.read_double()
        elif type_hint == str:
            return buffer.read_string()
        elif type_hint == bytes:
            return buffer.read_bytes()
        else:
            logger.warning(f"Unexpected basic type: {type_hint}")
            return buffer.read_string()
    
    def _read_field_value(self, buffer: Buffer, field_info: FieldInfo, xlang: bool) -> Any:
        """Read field value based on field information"""
        if field_info.is_embedded():
            # Handle embedded types
            if field_info.nullable:
                null_flag = buffer.read_int8()
                if null_flag == NULL_FLAG:
                    return None
            
            if field_info.classification == FieldType.BASIC:
                return self._read_basic_type(buffer, field_info.type_hint)
            elif field_info.classification == FieldType.NULLABLE_BASIC:
                inner_type = self._get_inner_nullable_type(field_info.type_hint)
                return self._read_basic_type(buffer, inner_type)
            else:
                # Fallback to reference deserialization
                if xlang:
                    return self.fory.xdeserialize_ref(buffer)
                else:
                    return self.fory.deserialize_ref(buffer)
        else:
            # Handle separate types
            if xlang:
                return self.fory.xdeserialize_ref(buffer)
            else:
                return self.fory.deserialize_ref(buffer)
    
    def _skip_field_value(self, buffer: Buffer, field_info: FieldInfo, xlang: bool):
        """Skip field value based on field type"""
        logger.debug(f"Skipping field {field_info.name} of type {field_info.field_type}")
        
        if field_info.is_embedded():
            if field_info.nullable:
                null_flag = buffer.read_int8()
                if null_flag == NULL_FLAG:
                    return
            
            # Skip based on field classification
            if field_info.classification in (FieldType.BASIC, FieldType.NULLABLE_BASIC):
                self._skip_basic_type(buffer, field_info.type_hint)
            else:
                # Try to skip as reference
                if xlang:
                    try:
                        self.fory.xdeserialize_ref(buffer)
                    except:
                        self._skip_bytes_conservative(buffer, 8)
                else:
                    try:
                        self.fory.deserialize_ref(buffer)
                    except:
                        self._skip_bytes_conservative(buffer, 8)
        else:
            # Skip separate field
            if xlang:
                try:
                    self.fory.xdeserialize_ref(buffer)
                except:
                    self._skip_bytes_conservative(buffer, 4)
            else:
                try:
                    self.fory.deserialize_ref(buffer)
                except:
                    self._skip_bytes_conservative(buffer, 4)
    
    def _skip_basic_type(self, buffer: Buffer, type_hint: Type):
        """Skip basic type value"""
        origin = get_origin(type_hint)
        if origin is Union:
            # Handle Optional[T]
            args = get_args(type_hint)
            if len(args) == 2 and type(None) in args:
                inner_type = args[0] if args[1] is type(None) else args[1]
                type_hint = inner_type
        
        if type_hint == bool:
            buffer.read_bool()
        elif type_hint == int:
            buffer.read_varint64()
        elif type_hint == float:
            buffer.read_double()
        elif type_hint == str:
            buffer.read_string()
        elif type_hint == bytes:
            buffer.read_bytes()
        else:
            # Conservative skip
            self._skip_bytes_conservative(buffer, 8)
    
    def _skip_unknown_field(self, buffer: Buffer, xlang: bool):
        """Skip unknown field conservatively"""
        logger.debug("Attempting to skip unknown field")
        try:
            # Try to read as reference first
            if xlang:
                self.fory.xdeserialize_ref(buffer)
            else:
                self.fory.deserialize_ref(buffer)
        except:
            # Fall back to conservative byte skipping
            self._skip_bytes_conservative(buffer, 4)
    
    def _skip_bytes_conservative(self, buffer: Buffer, default_bytes: int):
        """Conservative byte skipping"""
        remaining = buffer.writer_index - buffer.reader_index
        bytes_to_skip = min(default_bytes, remaining)
        if bytes_to_skip > 0:
            buffer.reader_index += bytes_to_skip
            logger.debug(f"Skipped {bytes_to_skip} bytes conservatively")
    
    def _fill_default_values(self, field_values: Dict[str, Any]):
        """Fill in default values for missing fields"""
        for field_info in self.type_def.field_infos:
            if field_info.name not in field_values:
                default_value = self._get_default_value(field_info)
                field_values[field_info.name] = default_value
                logger.debug(f"Using default value for {field_info.name}: {default_value}")
    
    def _get_default_value(self, field_info: FieldInfo) -> Any:
        """Get appropriate default value for field"""
        if field_info.default_value is not None:
            if callable(field_info.default_value):
                try:
                    return field_info.default_value()
                except:
                    pass
            else:
                return field_info.default_value
        
        # Use type-based defaults
        if field_info.nullable:
            return None
        
        type_hint = field_info.type_hint
        origin = get_origin(type_hint)
        
        if origin is Union:
            args = get_args(type_hint)
            if type(None) in args:
                return None
            # Use first non-None type
            for arg in args:
                if arg is not type(None):
                    type_hint = arg
                    break
        
        # Basic type defaults
        if type_hint == bool:
            return False
        elif type_hint == int:
            return 0
        elif type_hint == float:
            return 0.0
        elif type_hint == str:
            return ""
        elif type_hint == bytes:
            return b""
        elif origin in (list, List):
            return []
        elif origin in (dict, Dict):
            return {}
        elif origin in (set, Set):
            return set()
        else:
            return None
    
    def _get_field_value(self, obj: Any, field_name: str) -> Any:
        """Get field value from object"""
        try:
            return getattr(obj, field_name)
        except AttributeError:
            if hasattr(obj, '__dict__') and field_name in obj.__dict__:
                return obj.__dict__[field_name]
            return None
    
    def _create_object(self, field_values: Dict[str, Any]) -> Any:
        """Create object from field values with enhanced error handling"""
        logger.debug(f"Creating {self.type_cls.__name__} with values: {field_values}")
        
        try:
            if self.type_def.is_dataclass:
                return self._create_dataclass(field_values)
            else:
                return self._create_regular_class(field_values)
        except Exception as e:
            logger.error(f"Failed to create {self.type_cls.__name__}: {e}")
            # Fallback strategy
            return self._create_object_fallback(field_values)
    
    def _create_dataclass(self, field_values: Dict[str, Any]) -> Any:
        """Create dataclass instance"""
        constructor_args = {}
        
        for field in dataclasses.fields(self.type_cls):
            if field.name in field_values:
                constructor_args[field.name] = field_values[field.name]
            elif field.default != dataclasses.MISSING:
                constructor_args[field.name] = field.default
            elif field.default_factory != dataclasses.MISSING:
                constructor_args[field.name] = field.default_factory()
        
        return self.type_cls(**constructor_args)
    
    def _create_regular_class(self, field_values: Dict[str, Any]) -> Any:
        """Create regular class instance"""
        constructor_info = self.type_def.constructor_hints
        
        if constructor_info['type'] == 'regular' and 'params' in constructor_info:
            # Try to match constructor parameters
            constructor_args = {}
            params = constructor_info['params']
            
            for param_name, param_info in params.items():
                if param_name in field_values:
                    constructor_args[param_name] = field_values[param_name]
                elif param_info['has_default']:
                    constructor_args[param_name] = param_info['default']
            
            try:
                obj = self.type_cls(**constructor_args)
                
                # Set remaining fields as attributes
                for field_name, field_value in field_values.items():
                    if field_name not in constructor_args:
                        try:
                            setattr(obj, field_name, field_value)
                        except:
                            pass
                
                return obj
            except:
                pass
        
        # Fallback: create empty object and set attributes
        return self._create_object_fallback(field_values)
    
    def _create_object_fallback(self, field_values: Dict[str, Any]) -> Any:
        """Fallback object creation"""
        try:
            obj = self.type_cls.__new__(self.type_cls)
            for field_name, field_value in field_values.items():
                try:
                    setattr(obj, field_name, field_value)
                except:
                    pass
            return obj
        except:
            # Last resort: create a simple object with the fields
            class FallbackObject:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)
                
                def __repr__(self):
                    items = [f"{k}={v!r}" for k, v in self.__dict__.items()]
                    return f"FallbackObject({', '.join(items)})"
            
            return FallbackObject(**field_values)
    
    def _get_inner_nullable_type(self, type_hint: Type) -> Type:
        """Get inner type from Optional[T]"""
        origin = get_origin(type_hint)
        if origin is Union:
            args = get_args(type_hint)
            if len(args) == 2 and type(None) in args:
                return args[0] if args[1] is type(None) else args[1]
        return type_hint
    
    def _resolve_type_from_repr(self, type_repr: str) -> Type:
        """Resolve type from string representation"""
        # Simple type resolution - can be enhanced
        basic_types = {
            'bool': bool,
            'int': int,
            'float': float,
            'str': str,
            'bytes': bytes,
            'list': list,
            'dict': dict,
            'set': set,
        }
        
        return basic_types.get(type_repr, Any)
    
    def _infer_type_from_field_type(self, field_type: int) -> Type:
        """Infer type from field type encoding"""
        if field_type == FIELD_TYPE_EMBEDDED_4:
            return bool  # Most common for this category
        elif field_type == FIELD_TYPE_EMBEDDED_9:
            return int   # Most common for this category
        elif field_type == FIELD_TYPE_EMBEDDED_HASH:
            return str   # Most common for this category
        else:
            return Any


# Import handling for both Cython and pure Python versions
try:
    import os
    ENABLE_FORY_CYTHON_SERIALIZATION = os.environ.get(
        "ENABLE_FORY_CYTHON_SERIALIZATION", "True").lower() in ("true", "1")
    
    if ENABLE_FORY_CYTHON_SERIALIZATION:
        # Try to import Cython-accelerated version if available
        try:
            from pyfory._serialization import CythonCompatibleSerializer as CompatibleSerializer
            logger.info("Using Cython-accelerated compatible serializer")
        except ImportError:
            CompatibleSerializer = EnhancedCompatibleSerializer
            logger.info("Cython acceleration not available, using pure Python compatible serializer")
    else:
        CompatibleSerializer = EnhancedCompatibleSerializer
        logger.info("Using pure Python compatible serializer (Cython disabled)")
except ImportError:
    CompatibleSerializer = EnhancedCompatibleSerializer
    logger.info("Using pure Python compatible serializer")


__all__ = [
    'CompatibleSerializer',
    'EnhancedCompatibleSerializer', 
    'MetaContext',
    'TypeDefinition',
    'FieldInfo',
    'FieldType'
]
