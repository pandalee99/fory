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

import struct
import logging
from typing import Dict, List, Any, Union, get_type_hints, get_origin, get_args
from dataclasses import is_dataclass, fields

from pyfory.buffer import Buffer
from pyfory.serializer import Serializer, CrossLanguageCompatibleSerializer
from pyfory.type import TypeId
from pyfory.error import TypeNotCompatibleError
from pyfory.resolver import NULL_FLAG, NOT_NULL_VALUE_FLAG

# Handle imports that may not be available in all configurations
try:
    from pyfory.type import infer_field
except ImportError:
    def infer_field(field_name, type_hint, visitor, types_path):
        """Fallback field inference"""
        return None

try:
    from pyfory._struct import ComplexTypeVisitor, _get_hash
except ImportError:
    def _get_hash(fory, field_names, type_hints):
        """Fallback hash computation"""
        return hash(tuple(field_names)) & 0x7FFFFFFF
    
    class ComplexTypeVisitor:
        def __init__(self, fory):
            self.fory = fory


logger = logging.getLogger(__name__)


class ClassDef:
    """Class definition information for schema evolution."""
    
    def __init__(self, type_cls: type, field_names: List[str], type_hints: Dict[str, type]):
        self.type_cls = type_cls
        self.field_names = field_names
        self.type_hints = type_hints
        self.fields_info = {}  # field_name -> FieldInfo
        
    def __str__(self):
        return f"ClassDef({self.type_cls.__name__}, fields={self.field_names})"


class FieldInfo:
    """Field information for schema evolution."""
    
    def __init__(self, name: str, type_hint: type, serializer: Serializer = None, 
                 tag: int = None, is_embedded_type: bool = False):
        self.name = name
        self.type_hint = type_hint
        self.serializer = serializer
        self.tag = tag  # Field tag for ordering
        self.is_embedded_type = is_embedded_type
        
    def __str__(self):
        return f"FieldInfo({self.name}, {self.type_hint}, tag={self.tag})"


class MetaContext:
    """Context for handling type meta information during serialization."""
    
    def __init__(self):
        self.type_defs: Dict[int, ClassDef] = {}  # type_id -> ClassDef
        self.type_hash_to_id: Dict[int, int] = {}  # type_hash -> type_id
        self.next_type_id = 1000  # Start from 1000 to avoid conflicts
        
    def register_class_def(self, type_cls: type, field_names: List[str], type_hints: Dict[str, type]) -> int:
        """Register a class definition and return its type ID."""
        # Compute hash using simplified method
        type_hash = hash(tuple(sorted(field_names))) & 0x7FFFFFFF
        
        if type_hash in self.type_hash_to_id:
            return self.type_hash_to_id[type_hash]
            
        type_id = self.next_type_id
        self.next_type_id += 1
        
        class_def = ClassDef(type_cls, field_names, type_hints)
        self.type_defs[type_id] = class_def
        self.type_hash_to_id[type_hash] = type_id
        
        logger.debug(f"Registered class {type_cls.__name__} with type_id={type_id}, hash={type_hash}")
        return type_id
        
    def get_class_def(self, type_id: int) -> ClassDef:
        """Get class definition by type ID."""
        return self.type_defs.get(type_id)


class CompatibleSerializer(CrossLanguageCompatibleSerializer):
    """
    Python implementation of Java's CompatibleSerializer for schema evolution.
    
    This serializer provides forward/backward compatibility by encoding field metadata
    and handling schema differences between serialization and deserialization.
    """
    
    # Field flags - matches Java implementation
    EMBED_TYPES_FLAG = 0b1
    SEPARATE_TYPES_FLAG = 0b10
    SIZE_TWO_BYTES_FLAG = 0b100
    
    def __init__(self, fory, clz: type, field_resolver=None):
        super().__init__(fory, clz)
        self.type_cls = clz
        
        # Get field information
        self._type_hints = get_type_hints(clz)
        self._field_names = self._get_field_names(clz)
        self._has_slots = hasattr(clz, "__slots__")
        
        # Initialize field serializers
        self._field_serializers: Dict[str, Serializer] = {}
        self._embed_types_fields: List[FieldInfo] = []
        self._separate_types_fields: List[FieldInfo] = []
        
        # Set up field information
        self._setup_fields()
        
        # Meta context for type definitions
        self.meta_context = fory.meta_context if hasattr(fory, 'meta_context') else MetaContext()
        
    def _get_field_names(self, clz):
        """Get field names from class."""
        if is_dataclass(clz):
            return [f.name for f in fields(clz)]
        elif hasattr(clz, "__slots__"):
            return list(clz.__slots__)
        elif hasattr(clz, "__dict__"):
            return sorted(self._type_hints.keys())
        return []
        
    def _setup_fields(self):
        """Set up field serializers and categorization."""
        visitor = ComplexTypeVisitor(self.fory)
        
        for field_name in self._field_names:
            if field_name not in self._type_hints:
                continue
                
            type_hint = self._type_hints[field_name]
            serializer = infer_field(field_name, type_hint, visitor, types_path=[])
            
            field_info = FieldInfo(field_name, type_hint, serializer)
            
            # Determine if this is an embedded type or separate type
            if self._is_embedded_type(type_hint):
                field_info.is_embedded_type = True
                self._embed_types_fields.append(field_info)
            else:
                field_info.is_embedded_type = False
                self._separate_types_fields.append(field_info)
                
            self._field_serializers[field_name] = serializer
            
        # Sort fields for consistent serialization order
        self._embed_types_fields.sort(key=lambda f: f.name)
        self._separate_types_fields.sort(key=lambda f: f.name)
        
    def _is_embedded_type(self, type_hint: type) -> bool:
        """Determine if a type should be embedded or separate."""
        # Basic types are embedded
        if type_hint in (int, float, bool, str, bytes):
            return True
            
        # Check for generic types
        origin = get_origin(type_hint)
        if origin is not None:
            # Collections are usually separate types
            if origin in (list, dict, set, tuple):
                return False
            # Union types are separate
            if origin is Union:
                return False
                
        # Custom classes are separate types
        if hasattr(type_hint, '__module__') and type_hint.__module__ != 'builtins':
            return False
            
        return True
        
    def write(self, buffer: Buffer, value):
        """Write object with schema evolution support (Python mode)."""
        self._write_compatible(buffer, value, xlang=False)
        
    def read(self, buffer: Buffer):
        """Read object with schema evolution support (Python mode)."""
        return self._read_compatible(buffer, xlang=False)
        
    def xwrite(self, buffer: Buffer, value):
        """Write object with schema evolution support (cross-language mode)."""
        self._write_compatible(buffer, value, xlang=True)
        
    def xread(self, buffer: Buffer):
        """Read object with schema evolution support (cross-language mode)."""
        return self._read_compatible(buffer, xlang=True)
        
    def _write_compatible(self, buffer: Buffer, value, xlang: bool):
        """Main write method with schema evolution support."""
        # Write type hash for consistency check
        type_hash = hash(tuple(sorted(self._field_names))) & 0x7FFFFFFF
        buffer.write_int32(type_hash)
        
        # Write number of embedded type fields
        embed_types_count = len(self._embed_types_fields)
        buffer.write_varuint32(embed_types_count)
        
        # Write embedded type fields
        for field_info in self._embed_types_fields:
            field_value = getattr(value, field_info.name, None)
            self._write_field_info(buffer, field_info)
            self._write_field_value(buffer, field_value, field_info, xlang)
            
        # Write number of separate type fields  
        separate_types_count = len(self._separate_types_fields)
        buffer.write_varuint32(separate_types_count)
        
        # Write separate type fields
        for field_info in self._separate_types_fields:
            field_value = getattr(value, field_info.name, None)
            self._write_field_info(buffer, field_info)
            self._write_field_value(buffer, field_value, field_info, xlang)
            
    def _write_field_info(self, buffer: Buffer, field_info: FieldInfo):
        """Write field metadata information."""
        # Write field name
        buffer.write_string(field_info.name)
        
        # Write type information (simplified)
        type_hint = field_info.type_hint
        if type_hint == int:
            buffer.write_varuint32(TypeId.INT64)
        elif type_hint == float:
            buffer.write_varuint32(TypeId.FLOAT64)
        elif type_hint == bool:
            buffer.write_varuint32(TypeId.BOOL)
        elif type_hint == str:
            buffer.write_varuint32(TypeId.STRING)
        elif type_hint == bytes:
            buffer.write_varuint32(TypeId.BINARY)
        else:
            # For complex types, use generic object type
            buffer.write_varuint32(TypeId.FORY_TYPE_TAG)
            
    def _write_field_value(self, buffer: Buffer, field_value: Any, field_info: FieldInfo, xlang: bool):
        """Write field value using appropriate serializer."""
        if field_value is None:
            buffer.write_int8(NULL_FLAG)
            return
            
        buffer.write_int8(NOT_NULL_VALUE_FLAG)
        
        serializer = field_info.serializer
        if serializer is not None:
            if xlang:
                if hasattr(serializer, 'xwrite'):
                    serializer.xwrite(buffer, field_value)
                else:
                    serializer.write(buffer, field_value)
            else:
                serializer.write(buffer, field_value)
        else:
            # Fallback to fory's built-in serialization
            if xlang:
                self.fory.xserialize_ref(buffer, field_value)
            else:
                self.fory.serialize_ref(buffer, field_value)
                
    def _read_compatible(self, buffer: Buffer, xlang: bool):
        """Main read method with schema evolution support."""
        # Read and verify type hash
        read_hash = buffer.read_int32()
        current_hash = hash(tuple(sorted(self._field_names))) & 0x7FFFFFFF
        
        if read_hash != current_hash:
            logger.warning(f"Type hash mismatch: read={read_hash}, current={current_hash}. "
                          f"Attempting schema evolution for {self.type_cls.__name__}")
        
        # Create object instance
        obj = self.type_cls.__new__(self.type_cls)
        if xlang and hasattr(self.fory, 'ref_resolver'):
            self.fory.ref_resolver.reference(obj)
        
        # Initialize default values
        for field_name in self._field_names:
            setattr(obj, field_name, None)
        
        # Read embedded type fields
        embed_types_count = buffer.read_varuint32()
        embed_fields_read = {}
        
        for _ in range(embed_types_count):
            field_name, field_value = self._read_field(buffer, xlang)
            embed_fields_read[field_name] = field_value
            
        # Read separate type fields
        separate_types_count = buffer.read_varuint32()
        separate_fields_read = {}
        
        for _ in range(separate_types_count):
            field_name, field_value = self._read_field(buffer, xlang)
            separate_fields_read[field_name] = field_value
            
        # Apply read field values to object
        all_read_fields = {**embed_fields_read, **separate_fields_read}
        
        for field_name in self._field_names:
            if field_name in all_read_fields:
                setattr(obj, field_name, all_read_fields[field_name])
            else:
                # Field not present in serialized data - use default
                logger.debug(f"Field {field_name} not found in serialized data, using None")
                
        return obj
        
    def _read_field(self, buffer: Buffer, xlang: bool) -> tuple:
        """Read a single field with its name and value."""
        # Read field name
        field_name = buffer.read_string()
        
        # Read type information
        type_id = buffer.read_varuint32()
        
        # Read null flag
        null_flag = buffer.read_int8()
        if null_flag == NULL_FLAG:
            return field_name, None
            
        # Read field value
        field_value = None
        
        # Try to find serializer for this field
        if field_name in self._field_serializers:
            serializer = self._field_serializers[field_name]
            if xlang:
                if hasattr(serializer, 'xread'):
                    field_value = serializer.xread(buffer)
                else:
                    field_value = serializer.read(buffer)
            else:
                field_value = serializer.read(buffer)
        else:
            # Field not known in current schema - try to deserialize based on type
            field_value = self._read_unknown_field(buffer, type_id, xlang)
            
        return field_name, field_value
        
    def _read_unknown_field(self, buffer: Buffer, type_id: int, xlang: bool) -> Any:
        """Read a field that's not in current schema."""
        logger.debug(f"Reading unknown field with type_id={type_id}")
        
        # Handle basic types
        if type_id == TypeId.INT64:
            return buffer.read_varint64()
        elif type_id == TypeId.FLOAT64:
            return buffer.read_double()
        elif type_id == TypeId.BOOL:
            return buffer.read_bool()
        elif type_id == TypeId.STRING:
            return buffer.read_string()
        elif type_id == TypeId.BINARY:
            return buffer.read_bytes_and_size()
        else:
            # For complex types, use generic deserialization
            if xlang:
                return self.fory.xdeserialize_ref(buffer)
            else:
                return self.fory.deserialize_ref(buffer)


# Factory function to create compatible serializer instances
def create_compatible_serializer(fory, clz: type) -> CompatibleSerializer:
    """Create a CompatibleSerializer instance for the given class."""
    return CompatibleSerializer(fory, clz)
