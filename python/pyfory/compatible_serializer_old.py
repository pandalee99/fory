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
import struct
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

# Constants from Java implementation
EMBEDDED_TYPES_HASH = 0
SEPARATE_TYPES_HASH = 1
END_TAG = 0x7F7F7F7F  # Same as Java Long.MAX_VALUE >> 32

# Field types (from Java FieldResolver.FieldTypes)
class FieldTypes:
    OBJECT = 0
    COLLECTION_ELEMENT_FINAL = 1
    MAP_KV_FINAL = 2
    MAP_KEY_FINAL = 3
    MAP_VALUE_FINAL = 4


@dataclass
class FieldInfo:
    """Information about a field in the class"""
    name: str
    field_type: int  # FieldTypes
    type_hint: Type
    nullable: bool = True
    embedded_class_id: int = -1  # For embedded types like int, str, etc
    
    def __post_init__(self):
        # Determine if this is an embedded type (primitive)
        if self.type_hint in (int, float, bool, str, bytes):
            self.embedded_class_id = self._get_embedded_class_id(self.type_hint)
            self.field_type = FieldTypes.OBJECT  # Even primitives are handled as objects in compatible mode
        else:
            self.embedded_class_id = -1
            self.field_type = FieldTypes.OBJECT
            
    def _get_embedded_class_id(self, type_hint: Type) -> int:
        """Get class ID for embedded types"""
        if type_hint == int:
            return TypeId.INT64
        elif type_hint == str:
            return TypeId.STRING
        elif type_hint == float:
            return TypeId.FLOAT64
        elif type_hint == bool:
            return TypeId.BOOL
        elif type_hint == bytes:
            return TypeId.BINARY
        else:
            return -1


@dataclass
class ClassDef:
    """Class definition for schema evolution"""
    type_cls: Type
    field_infos: List[FieldInfo]
    type_hash: int
    
    @classmethod
    def create_from_class(cls, type_cls: Type) -> "ClassDef":
        """Create ClassDef from a Python class"""
        field_infos = []
        
        if is_dataclass(type_cls):
            # Handle dataclass
            for field in fields(type_cls):
                field_info = FieldInfo(
                    name=field.name,
                    field_type=FieldTypes.OBJECT,
                    type_hint=field.type,
                    nullable=True
                )
                field_infos.append(field_info)
        else:
            # Handle regular class with __slots__ or __dict__
            if hasattr(type_cls, '__slots__'):
                field_names = type_cls.__slots__
            elif hasattr(type_cls, '__annotations__'):
                field_names = list(type_cls.__annotations__.keys())
            else:
                # Fallback to __dict__ inspection
                instance = type_cls()
                field_names = list(instance.__dict__.keys())
            
            type_hints = get_type_hints(type_cls) if hasattr(type_cls, '__annotations__') else {}
            
            for field_name in field_names:
                field_type_hint = type_hints.get(field_name, Any)
                field_info = FieldInfo(
                    name=field_name,
                    field_type=FieldTypes.OBJECT,
                    type_hint=field_type_hint,
                    nullable=True
                )
                field_infos.append(field_info)
        
        # Calculate type hash based on field names and types
        type_hash = cls._calculate_type_hash(type_cls, field_infos)
        
        return cls(
            type_cls=type_cls,
            field_infos=field_infos,
            type_hash=type_hash
        )
    
    @classmethod
    def _calculate_type_hash(cls, type_cls: Type, field_infos: List[FieldInfo]) -> int:
        """Calculate hash for the class schema (similar to Java implementation)"""
        # Create a deterministic string representation of the class schema
        schema_str = f"{type_cls.__name__}:"
        for field_info in sorted(field_infos, key=lambda f: f.name):  # Sort for consistency
            type_name = getattr(field_info.type_hint, '__name__', str(field_info.type_hint))
            schema_str += f"{field_info.name}:{type_name};"
        
        # Use MD5 hash and convert to signed int32 (like Java hashCode)
        hash_bytes = hashlib.md5(schema_str.encode('utf-8')).digest()
        hash_uint = struct.unpack('<I', hash_bytes[:4])[0]
        # Convert to signed int32 range
        if hash_uint >= 2**31:
            return hash_uint - 2**32
        else:
            return hash_uint


class MetaContext:
    """Context for managing type metadata during serialization"""
    
    def __init__(self):
        self.class_defs: Dict[int, ClassDef] = {}
        self.next_type_id = 1000  # Start from 1000 like Java
    
    def register_class_def(self, type_cls: Type, field_names: List[str] = None, type_hints: Dict[str, Type] = None) -> int:
        """Register a class definition and return its type ID"""
        class_def = ClassDef.create_from_class(type_cls)
        
        # Check if already registered by hash
        for type_id, existing_def in self.class_defs.items():
            if existing_def.type_hash == class_def.type_hash:
                return type_id
        
        # Register new class definition
        type_id = self.next_type_id
        self.next_type_id += 1
        self.class_defs[type_id] = class_def
        
        logger.debug(f"Registered class {type_cls.__name__} with type_id={type_id}, hash={class_def.type_hash}")
        return type_id
    
    def get_class_def(self, type_id: int) -> Optional[ClassDef]:
        """Get class definition by type ID"""
        return self.class_defs.get(type_id)
    
    def get_class_def_by_hash(self, type_hash: int) -> Optional[ClassDef]:
        """Get class definition by type hash"""
        for class_def in self.class_defs.values():
            if class_def.type_hash == type_hash:
                return class_def
        return None


class CompatibleSerializer(CrossLanguageCompatibleSerializer):
    """Compatible serializer that supports schema evolution"""
    
    def __init__(self, fory: "Fory", type_cls: Type):
        super().__init__(fory, type_cls)
        self.type_cls = type_cls
        self.class_def = ClassDef.create_from_class(type_cls)
        self.need_to_write_ref = True
        
        # Register this class in the meta context
        if hasattr(fory, 'meta_context') and fory.meta_context:
            self.type_id = fory.meta_context.register_class_def(type_cls)
        else:
            self.type_id = 1000
    
    def write(self, buffer: Buffer, value: Any):
        """Serialize object in compatible mode"""
        self._write_compatible(buffer, value, xlang=False)
    
    def read(self, buffer: Buffer) -> Any:
        """Deserialize object in compatible mode"""
        return self._read_compatible(buffer, xlang=False)
    
    def xwrite(self, buffer: Buffer, value: Any):
        """Serialize object in xlang compatible mode"""
        self._write_compatible(buffer, value, xlang=True)
    
    def xread(self, buffer: Buffer) -> Any:
        """Deserialize object in xlang compatible mode"""
        return self._read_compatible(buffer, xlang=True)
    
    def _write_compatible(self, buffer: Buffer, value: Any, xlang: bool):
        """Write object with schema evolution support"""
        # Write type hash for schema validation
        buffer.write_int32(self.class_def.type_hash)
        
        # Separate fields into embedded and separate types
        embedded_fields = []
        separate_fields = []
        
        for field_info in self.class_def.field_infos:
            field_value = self._get_field_value(value, field_info.name)
            if field_value is None:
                continue
                
            if field_info.embedded_class_id >= 0:
                embedded_fields.append((field_info, field_value))
            else:
                separate_fields.append((field_info, field_value))
        
        # Write embedded fields
        buffer.write_int32(EMBEDDED_TYPES_HASH)
        buffer.write_varint32(len(embedded_fields))
        
        for field_info, field_value in embedded_fields:
            self._write_embedded_field(buffer, field_info, field_value)
        
        # Write separate fields
        buffer.write_int32(SEPARATE_TYPES_HASH)  
        buffer.write_varint32(len(separate_fields))
        
        for field_info, field_value in separate_fields:
            self._write_separate_field(buffer, field_info, field_value, xlang)
        
        # Write end tag
        buffer.write_int64(END_TAG)
    
    def _write_embedded_field(self, buffer: Buffer, field_info: FieldInfo, field_value: Any):
        """Write an embedded (primitive) field"""
        # Write field name
        buffer.write_string(field_info.name)
        
        # Write null flag and value
        if field_value is None:
            buffer.write_int8(1)  # null
        else:
            buffer.write_int8(0)  # not null
            
            # Write value based on type
            if field_info.embedded_class_id == TypeId.INT64:
                buffer.write_varint64(field_value)
            elif field_info.embedded_class_id == TypeId.STRING:
                buffer.write_string(field_value)
            elif field_info.embedded_class_id == TypeId.FLOAT64:
                buffer.write_double(field_value)
            elif field_info.embedded_class_id == TypeId.BOOL:
                buffer.write_bool(field_value)
            elif field_info.embedded_class_id == TypeId.BINARY:
                buffer.write_bytes_and_size(field_value)
            else:
                # For unknown types, just serialize as string representation
                buffer.write_string(str(field_value))
    
    def _write_separate_field(self, buffer: Buffer, field_info: FieldInfo, field_value: Any, xlang: bool):
        """Write a separate (complex) field"""
        # Write field name
        buffer.write_string(field_info.name)
        
        # Write field type
        buffer.write_int8(field_info.field_type)
        
        # For now, serialize complex objects as strings to avoid type registration issues
        if field_value is None:
            buffer.write_string("null")
        else:
            buffer.write_string(str(field_value))
    
    def _read_compatible(self, buffer: Buffer, xlang: bool) -> Any:
        """Read object with schema evolution support"""
        # Read and validate type hash
        serialized_hash = buffer.read_int32()
        current_hash = self.class_def.type_hash
        
        if serialized_hash != current_hash:
            logger.info(f"Type hash mismatch: read={serialized_hash}, current={current_hash}. "
                       f"Attempting schema evolution for {self.type_cls.__name__}")
        
        # Read embedded fields
        embedded_hash = buffer.read_int32()
        assert embedded_hash == EMBEDDED_TYPES_HASH
        embedded_count = buffer.read_varint32()
        
        embedded_values = {}
        for _ in range(embedded_count):
            field_name = buffer.read_string()
            is_null = buffer.read_int8()
            
            if is_null:
                embedded_values[field_name] = None
            else:
                # Find field info by name
                field_info = self._find_field_by_name(field_name)
                if field_info and field_info.embedded_class_id >= 0:
                    # Read known embedded field
                    if field_info.embedded_class_id == TypeId.INT64:
                        embedded_values[field_name] = buffer.read_varint64()
                    elif field_info.embedded_class_id == TypeId.STRING:
                        embedded_values[field_name] = buffer.read_string()
                    elif field_info.embedded_class_id == TypeId.FLOAT64:
                        embedded_values[field_name] = buffer.read_double()
                    elif field_info.embedded_class_id == TypeId.BOOL:
                        embedded_values[field_name] = buffer.read_bool()
                    elif field_info.embedded_class_id == TypeId.BINARY:
                        embedded_values[field_name] = buffer.read_bytes_and_size()
                    else:
                        # Unknown embedded type, skip it
                        logger.warning(f"Unknown embedded field type for field {field_name}")
                        embedded_values[field_name] = self.fory.deserialize_nonref(buffer)
                else:
                    # Unknown field, try to skip it (this is simplified)
                    logger.debug(f"Skipping unknown embedded field: {field_name}")
                    # For now, we'll try to read it as a simple value to avoid complex type registration
                    try:
                        embedded_values[field_name] = buffer.read_string()  # Try as string first
                    except:
                        try:
                            embedded_values[field_name] = buffer.read_varint64()  # Try as int
                        except:
                            # Skip this field completely
                            pass
        
        # Read separate fields
        separate_hash = buffer.read_int32()
        assert separate_hash == SEPARATE_TYPES_HASH
        separate_count = buffer.read_varint32()
        
        separate_values = {}
        for _ in range(separate_count):
            field_name = buffer.read_string()
            field_type = buffer.read_int8()
            
            # Read the string representation (temporary fix to avoid type registration issues)
            field_value_str = buffer.read_string()
            if field_value_str == "null":
                separate_values[field_name] = None
            else:
                separate_values[field_name] = field_value_str
        
        # Read end tag
        end_tag = buffer.read_int64()
        assert end_tag == END_TAG, f"Expected end tag {END_TAG}, got {end_tag}"
        
        # Reconstruct object
        return self._create_object(embedded_values, separate_values)
    
    def _find_field_by_name(self, field_name: str) -> Optional[FieldInfo]:
        """Find field info by field name"""
        for field_info in self.class_def.field_infos:
            if field_info.name == field_name:
                return field_info
        return None
    
    def _get_field_value(self, obj: Any, field_name: str) -> Any:
        """Get field value from object"""
        if hasattr(obj, field_name):
            return getattr(obj, field_name)
        return None
    
    def _create_object(self, embedded_values: Dict[str, Any], separate_values: Dict[str, Any]) -> Any:
        """Create object from field values"""
        all_values = {**embedded_values, **separate_values}
        
        if is_dataclass(self.type_cls):
            # For dataclass, filter only known fields and provide defaults for missing ones
            constructor_args = {}
            for field in fields(self.type_cls):
                if field.name in all_values:
                    constructor_args[field.name] = all_values[field.name]
                elif field.default != dataclasses.MISSING:
                    constructor_args[field.name] = field.default
                elif field.default_factory != dataclasses.MISSING:
                    constructor_args[field.name] = field.default_factory()
                else:
                    # No default, might cause issues but let's try
                    pass
            
            return self.type_cls(**constructor_args)
        else:
            # For regular classes, create instance and set attributes
            obj = self.type_cls()
            for field_name, field_value in all_values.items():
                if hasattr(obj, field_name):
                    setattr(obj, field_name, field_value)
            return obj
