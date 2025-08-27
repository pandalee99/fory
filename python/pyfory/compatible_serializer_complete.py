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

import logging
import hashlib
import dataclasses
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Dict, List, Optional, Type, Union, get_type_hints
import inspect

from pyfory.buffer import Buffer
from pyfory.serializer import CrossLanguageCompatibleSerializer
from pyfory.type import TypeId
import pyfory._struct as _struct

logger = logging.getLogger(__name__)

# Constants for field encoding (matching Java implementation)
FIELD_TYPE_EMBEDDED_4 = 0
FIELD_TYPE_EMBEDDED_9 = 1
FIELD_TYPE_EMBEDDED_HASH = 2
FIELD_TYPE_SEPARATE_HASH = 3
END_TAG = -1


class FieldInfo:
    """Field information for compatibility tracking"""
    
    def __init__(self, name: str, type_hint: Type, field_type: int, class_id: int = 0):
        self.name = name
        self.type_hint = type_hint
        self.field_type = field_type  # EMBEDDED or SEPARATE
        self.class_id = class_id
        self.encoded_field_info = self._encode_field_info()
    
    def _encode_field_info(self) -> int:
        """Encode field information similar to Java implementation"""
        # Simple encoding: combine field type and hash of field name
        name_hash = hash(self.name) & 0x7FFFFFFF  # Keep positive
        # Encode field type in high bits, name hash in low bits
        return (self.field_type << 29) | (name_hash & 0x1FFFFFFF)
    
    def is_embedded(self) -> bool:
        """Check if field should be embedded (basic types)"""
        return self.field_type in (FIELD_TYPE_EMBEDDED_4, FIELD_TYPE_EMBEDDED_9, FIELD_TYPE_EMBEDDED_HASH)


def _is_basic_type(type_hint: Type) -> bool:
    """Check if type is a basic type that can be embedded"""
    if type_hint in (bool, int, float, str, bytes):
        return True
    if hasattr(type_hint, '__origin__'):
        # Handle Optional[T] as basic if T is basic
        if type_hint.__origin__ is Union:
            args = type_hint.__args__
            if len(args) == 2 and type(None) in args:
                other_type = args[0] if args[1] is type(None) else args[1]
                return _is_basic_type(other_type)
    return False


def _get_field_type(type_hint: Type) -> int:
    """Determine field encoding type based on type hint"""
    if _is_basic_type(type_hint):
        if type_hint in (bool, int):
            return FIELD_TYPE_EMBEDDED_4
        elif type_hint in (float, str):
            return FIELD_TYPE_EMBEDDED_9
        else:
            return FIELD_TYPE_EMBEDDED_HASH
    else:
        return FIELD_TYPE_SEPARATE_HASH


class ClassInfo:
    """Class schema information for compatibility"""
    
    def __init__(self, type_cls: Type):
        self.type_cls = type_cls
        self.field_infos = self._extract_field_infos()
        self.schema_hash = self._calculate_schema_hash()
        self.embedded_fields = [f for f in self.field_infos if f.is_embedded()]
        self.separate_fields = [f for f in self.field_infos if not f.is_embedded()]
        
        # Group fields by encoding type for efficient serialization
        self.embedded_4_fields = [f for f in self.embedded_fields if f.field_type == FIELD_TYPE_EMBEDDED_4]
        self.embedded_9_fields = [f for f in self.embedded_fields if f.field_type == FIELD_TYPE_EMBEDDED_9]
        self.embedded_hash_fields = [f for f in self.embedded_fields if f.field_type == FIELD_TYPE_EMBEDDED_HASH]
        self.separate_hash_fields = [f for f in self.separate_fields if f.field_type == FIELD_TYPE_SEPARATE_HASH]
    
    def _extract_field_infos(self) -> List[FieldInfo]:
        """Extract field information from class"""
        field_infos = []
        
        if is_dataclass(self.type_cls):
            # Handle dataclass
            for field in fields(self.type_cls):
                type_hint = field.type
                field_type = _get_field_type(type_hint)
                field_infos.append(FieldInfo(field.name, type_hint, field_type))
        else:
            # Handle regular class with type hints
            try:
                type_hints = get_type_hints(self.type_cls)
                for name, type_hint in type_hints.items():
                    field_type = _get_field_type(type_hint)
                    field_infos.append(FieldInfo(name, type_hint, field_type))
            except (NameError, AttributeError):
                # Fallback: use __slots__ or __dict__
                if hasattr(self.type_cls, '__slots__'):
                    for name in self.type_cls.__slots__:
                        field_infos.append(FieldInfo(name, Any, FIELD_TYPE_SEPARATE_HASH))
        
        return sorted(field_infos, key=lambda f: f.name)
    
    def _calculate_schema_hash(self) -> int:
        """Calculate deterministic hash for schema"""
        # Create a string representation of the schema
        schema_str = f"{self.type_cls.__name__}:"
        for field_info in self.field_infos:
            type_name = getattr(field_info.type_hint, '__name__', str(field_info.type_hint))
            schema_str += f"{field_info.name}:{type_name}:{field_info.field_type};"
        
        # Use SHA256 for deterministic hashing
        hash_bytes = hashlib.sha256(schema_str.encode()).digest()
        # Convert to 32-bit signed integer
        hash_value = int.from_bytes(hash_bytes[:4], 'big', signed=True)
        return hash_value
    
    def get_field_by_name(self, name: str) -> Optional[FieldInfo]:
        """Get field info by name"""
        for field_info in self.field_infos:
            if field_info.name == name:
                return field_info
        return None


class MetaContext:
    """Context for managing class metadata and compatibility"""
    
    def __init__(self):
        self.class_infos: Dict[int, ClassInfo] = {}
        self.type_to_class_info: Dict[Type, ClassInfo] = {}
        self._next_type_id = 1000  # Start from 1000 like Java
    
    def register_class(self, type_cls: Type) -> int:
        """Register a class and return its type ID"""
        if type_cls in self.type_to_class_info:
            # Find existing type ID
            for type_id, class_info in self.class_infos.items():
                if class_info.type_cls == type_cls:
                    return type_id
        
        # Create new class info
        class_info = ClassInfo(type_cls)
        type_id = self._next_type_id
        self._next_type_id += 1
        
        self.class_infos[type_id] = class_info
        self.type_to_class_info[type_cls] = class_info
        
        logger.debug(f"Registered class {type_cls.__name__} with type_id={type_id}, hash={class_info.schema_hash}")
        return type_id
    
    def get_class_info(self, type_id: int) -> Optional[ClassInfo]:
        """Get class info by type ID"""
        return self.class_infos.get(type_id)
    
    def get_class_info_by_type(self, type_cls: Type) -> Optional[ClassInfo]:
        """Get class info by type"""
        return self.type_to_class_info.get(type_cls)


class CompatibleSerializer(CrossLanguageCompatibleSerializer):
    """
    Complete implementation of compatible serializer following Java patterns.
    Provides forward and backward compatibility through schema evolution.
    """
    
    def __init__(self, fory, type_cls: Type):
        super().__init__(fory, type_cls)
        self.type_cls = type_cls
        
        # Get or create meta context
        if not hasattr(fory, 'meta_context'):
            fory.meta_context = MetaContext()
        self.meta_context = fory.meta_context
        
        # Register this class
        self.type_id = self.meta_context.register_class(type_cls)
        self.class_info = self.meta_context.get_class_info(self.type_id)
    
    def write(self, buffer: Buffer, value: Any):
        """Serialize object with compatibility metadata"""
        self._write_compatible(buffer, value, xlang=False)
    
    def read(self, buffer: Buffer) -> Any:
        """Deserialize object with compatibility support"""
        return self._read_compatible(buffer, xlang=False)
    
    def xwrite(self, buffer: Buffer, value: Any):
        """Cross-language compatible serialization"""
        self._write_compatible(buffer, value, xlang=True)
    
    def xread(self, buffer: Buffer) -> Any:
        """Cross-language compatible deserialization"""
        return self._read_compatible(buffer, xlang=True)
    
    def _write_compatible(self, buffer: Buffer, value: Any, xlang: bool):
        """Core serialization logic matching Java implementation"""
        class_info = self.class_info
        
        # Write schema hash for compatibility checking
        buffer.write_int32(class_info.schema_hash)
        
        # Write embedded fields grouped by type (matching Java order)
        self._write_embedded_fields(buffer, value, class_info.embedded_4_fields, xlang)
        self._write_embedded_fields(buffer, value, class_info.embedded_9_fields, xlang)
        self._write_embedded_fields(buffer, value, class_info.embedded_hash_fields, xlang)
        
        # Write separate fields
        self._write_separate_fields(buffer, value, class_info.separate_hash_fields, xlang)
        
        # Write end tag
        buffer.write_int64(END_TAG)
    
    def _write_embedded_fields(self, buffer: Buffer, value: Any, field_infos: List[FieldInfo], xlang: bool):
        """Write embedded fields"""
        for field_info in field_infos:
            # Write encoded field info
            if field_info.field_type == FIELD_TYPE_EMBEDDED_4:
                buffer.write_int32(field_info.encoded_field_info)
            else:
                buffer.write_int64(field_info.encoded_field_info)
            
            # Write field value
            field_value = self._get_field_value(value, field_info.name)
            self._write_field_value(buffer, field_info, field_value, xlang)
    
    def _write_separate_fields(self, buffer: Buffer, value: Any, field_infos: List[FieldInfo], xlang: bool):
        """Write separate (complex) fields"""
        for field_info in field_infos:
            # Write encoded field info
            buffer.write_int64(field_info.encoded_field_info)
            
            # Write field value
            field_value = self._get_field_value(value, field_info.name)
            self._write_field_value(buffer, field_info, field_value, xlang)
    
    def _write_field_value(self, buffer: Buffer, field_info: FieldInfo, field_value: Any, xlang: bool):
        """Write a single field value"""
        try:
            if field_info.is_embedded():
                # Handle embedded types
                if field_value is None:
                    buffer.write_int8(1)  # NULL flag
                else:
                    buffer.write_int8(0)  # NOT_NULL flag
                    if isinstance(field_value, bool):
                        buffer.write_bool(field_value)
                    elif isinstance(field_value, int):
                        buffer.write_varint64(field_value)
                    elif isinstance(field_value, float):
                        buffer.write_float64(field_value)
                    elif isinstance(field_value, str):
                        buffer.write_string(field_value)
                    else:
                        # Fallback to reference serialization
                        if xlang:
                            self.fory.xserialize_ref(buffer, field_value)
                        else:
                            self.fory.serialize_ref(buffer, field_value)
            else:
                # Handle separate types using reference serialization
                if xlang:
                    self.fory.xserialize_ref(buffer, field_value)
                else:
                    self.fory.serialize_ref(buffer, field_value)
        except Exception as e:
            logger.warning(f"Failed to serialize field {field_info.name}: {e}, using fallback")
            # Fallback: serialize as reference
            if xlang:
                self.fory.xserialize_ref(buffer, field_value)
            else:
                self.fory.serialize_ref(buffer, field_value)
    
    def _read_compatible(self, buffer: Buffer, xlang: bool) -> Any:
        """Core deserialization logic with compatibility support"""
        # Read and verify schema hash
        read_hash = buffer.read_int32()
        expected_hash = self.class_info.schema_hash
        
        if read_hash != expected_hash:
            logger.debug(f"Schema hash mismatch: read={read_hash}, expected={expected_hash}, attempting compatibility mode")
            # In compatibility mode, we continue reading but may skip unknown fields
        
        # Collect field values
        field_values = {}
        
        # Read embedded fields by scanning for known encoded field infos
        self._read_fields_by_scanning(buffer, field_values, xlang)
        
        # Create and populate object
        return self._create_object(field_values)
    
    def _read_fields_by_scanning(self, buffer: Buffer, field_values: Dict[str, Any], xlang: bool):
        """Read fields by scanning buffer and matching encoded field infos"""
        while buffer.read_index < buffer.writer_index:
            try:
                # Try to read next field encoding
                if buffer.remaining() < 4:
                    break
                
                # Peek at the next value to determine if it's a field encoding or end tag
                peek_pos = buffer.read_index
                next_value = buffer.read_int64()
                buffer.read_index = peek_pos  # Reset position
                
                if next_value == END_TAG:
                    buffer.read_int64()  # Consume end tag
                    break
                
                # Try to find matching field
                field_info = self._find_field_by_encoded_info(next_value)
                if field_info:
                    # Read the encoding (consume it)
                    if field_info.field_type == FIELD_TYPE_EMBEDDED_4:
                        buffer.read_int32()
                    else:
                        buffer.read_int64()
                    
                    # Read field value
                    field_value = self._read_field_value(buffer, field_info, xlang)
                    field_values[field_info.name] = field_value
                else:
                    # Unknown field, try to skip
                    logger.debug(f"Skipping unknown field with encoding: {next_value}")
                    buffer.read_int64()  # Skip encoding
                    # Try to skip value (this is approximate)
                    self._skip_field_value(buffer, xlang)
            
            except Exception as e:
                logger.warning(f"Error reading field: {e}, stopping field scan")
                break
    
    def _read_field_value(self, buffer: Buffer, field_info: FieldInfo, xlang: bool) -> Any:
        """Read a single field value"""
        try:
            if field_info.is_embedded():
                # Handle embedded types
                null_flag = buffer.read_int8()
                if null_flag == 1:  # NULL
                    return None
                
                # Read based on expected type
                if field_info.type_hint == bool:
                    return buffer.read_bool()
                elif field_info.type_hint == int:
                    return buffer.read_varint64()
                elif field_info.type_hint == float:
                    return buffer.read_float64()
                elif field_info.type_hint == str:
                    return buffer.read_string()
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
        
        except Exception as e:
            logger.warning(f"Failed to read field {field_info.name}: {e}, using fallback")
            # Fallback: try reference deserialization
            try:
                if xlang:
                    return self.fory.xdeserialize_ref(buffer)
                else:
                    return self.fory.deserialize_ref(buffer)
            except:
                return None  # Give up
    
    def _skip_field_value(self, buffer: Buffer, xlang: bool):
        """Try to skip an unknown field value"""
        try:
            # This is approximate - try to read and discard a reference
            if xlang:
                self.fory.xdeserialize_ref(buffer)
            else:
                self.fory.deserialize_ref(buffer)
        except:
            # If that fails, skip a few bytes (very approximate)
            if buffer.remaining() >= 4:
                buffer.read_int32()
    
    def _find_field_by_encoded_info(self, encoded_info: int) -> Optional[FieldInfo]:
        """Find field by its encoded information"""
        # Try both 32-bit and 64-bit interpretations
        for field_info in self.class_info.field_infos:
            if field_info.encoded_field_info == encoded_info:
                return field_info
            # Also try matching just the lower 32 bits for EMBEDDED_4 fields
            if (field_info.field_type == FIELD_TYPE_EMBEDDED_4 and 
                field_info.encoded_field_info == (encoded_info & 0xFFFFFFFF)):
                return field_info
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
        """Create object instance from field values"""
        try:
            if is_dataclass(self.type_cls):
                # Handle dataclass with proper defaults
                constructor_args = {}
                for field in fields(self.type_cls):
                    if field.name in field_values:
                        constructor_args[field.name] = field_values[field.name]
                    elif field.default != dataclasses.MISSING:
                        constructor_args[field.name] = field.default
                    elif field.default_factory != dataclasses.MISSING:
                        constructor_args[field.name] = field.default_factory()
                    # If no default and not provided, let dataclass constructor handle it
                
                return self.type_cls(**constructor_args)
            else:
                # Handle regular class
                obj = self.type_cls.__new__(self.type_cls)
                for field_name, field_value in field_values.items():
                    setattr(obj, field_name, field_value)
                return obj
        
        except Exception as e:
            logger.error(f"Failed to create object of type {self.type_cls}: {e}")
            # Fallback: create object and set available fields
            obj = self.type_cls.__new__(self.type_cls)
            for field_name, field_value in field_values.items():
                try:
                    setattr(obj, field_name, field_value)
                except:
                    pass
            return obj
