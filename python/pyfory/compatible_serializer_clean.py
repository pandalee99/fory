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
Compatible Serializer Implementation

This module provides a simple implementation of schema evolution
for Fory serialization, supporting basic forward and backward compatibility
between different versions of data structures.
"""

import logging
import hashlib
import dataclasses
from dataclasses import dataclass, fields, is_dataclass, MISSING, field
from typing import Any, Dict, List, Set, Optional, Type, Union, get_type_hints, get_origin, get_args
import inspect

from pyfory.buffer import Buffer
from pyfory.serializer import CrossLanguageCompatibleSerializer
from pyfory.type import TypeId
import pyfory._struct as _struct

logger = logging.getLogger(__name__)


class FieldClassification:
    """Field type classification constants"""
    PRIMITIVE = 0
    PRIMITIVE_NULLABLE = 1
    STRING = 2  
    STRING_NULLABLE = 3
    OBJECT = 4
    OBJECT_NULLABLE = 5


@dataclass
class FieldInfo:
    """Field information for schema evolution"""
    name: str
    field_type: Type
    classification: int
    nullable: bool = False
    default_value: Any = field(default_factory=lambda: MISSING)
    
    def __post_init__(self):
        self.encoded_field_info = self._compute_hash()
        
    def _compute_hash(self) -> int:
        """Compute field hash for compatibility checking"""
        field_str = f"{self.name}:{self.field_type.__name__ if hasattr(self.field_type, '__name__') else str(self.field_type)}:{self.classification}:{self.nullable}"
        hash_result = mmh3.hash_buffer(field_str.encode('utf-8'))
        # mmh3 returns a tuple for 128-bit hash, we use the first 64 bits and convert to 32-bit
        return (hash_result[0] & 0xFFFFFFFFFFFFFFFF) & 0xFFFFFFFF
    
    def is_embedded(self) -> bool:
        """Check if field can be embedded (inlined)"""
        return self.classification in [
            FieldClassification.PRIMITIVE,
            FieldClassification.PRIMITIVE_NULLABLE,
            FieldClassification.STRING,
            FieldClassification.STRING_NULLABLE
        ]


@dataclass  
class TypeDefinition:
    """Type definition with schema metadata"""
    type_cls: Type
    type_id: int
    field_infos: List[FieldInfo]
    schema_hash: int
    
    def __post_init__(self):
        # Group fields by characteristics
        self.embedded_fields = [f for f in self.field_infos if f.is_embedded()]
        self.separate_fields = [f for f in self.field_infos if not f.is_embedded()]
        
        # Fast path optimization
        self._fast_primitive_fields = [f for f in self.embedded_fields 
                                      if f.classification == FieldClassification.PRIMITIVE]
    
    def get_field_by_name(self, name: str) -> Optional[FieldInfo]:
        """Get field info by name"""
        for field in self.field_infos:
            if field.name == name:
                return field
        return None
    
    def get_field_by_hash(self, hash_val: int) -> Optional[FieldInfo]:
        """Get field info by hash"""
        for field in self.field_infos:
            if field.encoded_field_info == hash_val:
                return field
        return None


class MetaContext:
    """Metadata context for type management"""
    
    def __init__(self):
        self._type_definitions: Dict[int, TypeDefinition] = {}
        self._class_to_type_id: Dict[Type, int] = {}
        self._type_id_counter = 1000
        self._sent_types: Set[int] = set()  # Session state
        
    def register_class(self, type_cls: Type) -> int:
        """Register a class and return its type ID"""
        # Check if already registered
        if type_cls in self._class_to_type_id:
            return self._class_to_type_id[type_cls]
            
        # Create new type definition
        type_id = self._type_id_counter
        self._type_id_counter += 1
        
        field_infos = self._analyze_class_fields(type_cls)
        schema_hash = self._compute_schema_hash(field_infos)
        
        type_def = TypeDefinition(
            type_cls=type_cls,
            type_id=type_id,
            field_infos=field_infos,
            schema_hash=schema_hash
        )
        
        self._type_definitions[type_id] = type_def
        self._class_to_type_id[type_cls] = type_id
        
        logger.debug(f"Registered type {type_cls.__name__} with ID {type_id}")
        return type_id
    
    def get_type_definition(self, type_id: int) -> Optional[TypeDefinition]:
        """Get type definition by ID"""
        return self._type_definitions.get(type_id)
        
    def is_type_def_sent(self, type_id: int) -> bool:
        """Check if type definition was sent in current session"""
        return type_id in self._sent_types
        
    def mark_type_def_sent(self, type_id: int):
        """Mark type definition as sent"""
        self._sent_types.add(type_id)
        
    def reset_session(self):
        """Reset session state"""
        self._sent_types.clear()
    
    def _analyze_class_fields(self, type_cls: Type) -> List[FieldInfo]:
        """Analyze class fields and create field info"""
        field_infos = []
        
        if is_dataclass(type_cls):
            # Handle dataclass
            type_hints = get_type_hints(type_cls)
            for field in fields(type_cls):
                field_type = type_hints.get(field.name, field.type)
                classification = self._determine_field_classification(field_type)
                nullable = self._is_nullable_field(field_type, field)
                
                field_info = FieldInfo(
                    name=field.name,
                    field_type=field_type,
                    classification=classification,
                    nullable=nullable,
                    default_value=field.default if field.default is not MISSING else field.default_factory if field.default_factory is not MISSING else MISSING
                )
                field_infos.append(field_info)
        else:
            # Handle regular class
            type_hints = get_type_hints(type_cls) if hasattr(type_cls, '__annotations__') else {}
            
            # Get fields from __init__ signature or attributes
            if hasattr(type_cls, '__init__'):
                sig = inspect.signature(type_cls.__init__)
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                        
                    field_type = type_hints.get(param_name, param.annotation if param.annotation != param.empty else Any)
                    classification = self._determine_field_classification(field_type)
                    nullable = param.default is not param.empty and param.default is None
                    
                    field_info = FieldInfo(
                        name=param_name,
                        field_type=field_type,
                        classification=classification,
                        nullable=nullable,
                        default_value=param.default if param.default is not param.empty else MISSING
                    )
                    field_infos.append(field_info)
                    
        return field_infos
    
    def _determine_field_classification(self, field_type: Type) -> int:
        """Determine field classification"""
        # Handle Optional types
        origin = get_origin(field_type)
        args = get_args(field_type)
        
        nullable = False
        actual_type = field_type
        
        if origin is Union:
            # Check if it's Optional (Union[T, None])
            if len(args) == 2 and type(None) in args:
                nullable = True
                actual_type = args[0] if args[1] is type(None) else args[1]
        
        # Classify the actual type
        if actual_type in (int, float, bool) or (hasattr(actual_type, '__name__') and actual_type.__name__ in ('int', 'float', 'bool')):
            return FieldClassification.PRIMITIVE_NULLABLE if nullable else FieldClassification.PRIMITIVE
        elif actual_type is str or (hasattr(actual_type, '__name__') and actual_type.__name__ == 'str'):
            return FieldClassification.STRING_NULLABLE if nullable else FieldClassification.STRING
        else:
            return FieldClassification.OBJECT_NULLABLE if nullable else FieldClassification.OBJECT
    
    def _is_nullable_field(self, field_type: Type, field=None) -> bool:
        """Check if field is nullable"""
        origin = get_origin(field_type)
        args = get_args(field_type)
        
        # Check Optional type
        if origin is Union and len(args) == 2 and type(None) in args:
            return True
            
        # Check default value
        if field and hasattr(field, 'default') and field.default is None:
            return True
            
        return False
    
    def _compute_schema_hash(self, field_infos: List[FieldInfo]) -> int:
        """Compute schema hash"""
        field_hashes = [str(f.encoded_field_info) for f in field_infos]
        schema_str = ":".join(sorted(field_hashes))
        return (mmh3.hash_buffer(schema_str.encode('utf-8'))[0] & 0xFFFFFFFFFFFFFFFF) & 0xFFFFFFFF


class CompatibleSerializer(CrossLanguageCompatibleSerializer):
    """Simple compatible serializer with basic schema evolution"""
    
    def __init__(self, fory, type_cls: Type):
        super().__init__(fory, type_cls)
        self._type_cls = type_cls
        
        # Get or create meta context
        if not hasattr(fory, 'meta_context'):
            fory.meta_context = MetaContext()
        self._meta_context = fory.meta_context
        
        # Register type and get definition
        self._type_id = self._meta_context.register_class(type_cls)
        self._type_def = self._meta_context.get_type_definition(self._type_id)
        
        logger.debug(f"Created CompatibleSerializer for {type_cls.__name__}")
        
    def write(self, buffer: Buffer, value: Any):
        """Write object to buffer"""
        try:
            # Write schema hash for verification
            buffer.write_int32(self._type_def.schema_hash)
            
            # Write all fields in order
            for field in self._type_def.field_infos:
                field_value = getattr(value, field.name, None)
                self._write_field_value(buffer, field, field_value)
                
        except Exception as e:
            logger.error(f"Failed to serialize {self._type_cls.__name__}: {e}")
            raise
    
    def read(self, buffer: Buffer) -> Any:
        """Read object from buffer"""
        try:
            # Read schema hash
            remote_schema_hash = buffer.read_int32()
            local_schema_hash = self._type_def.schema_hash
            
            field_values = {}
            
            if remote_schema_hash == local_schema_hash:
                # Same schema - read all fields in order
                for field in self._type_def.field_infos:
                    field_values[field.name] = self._read_field_value(buffer, field)
            else:
                # Different schema - try to read and fill defaults
                logger.debug(f"Schema mismatch: remote={remote_schema_hash}, local={local_schema_hash}")
                for field in self._type_def.field_infos:
                    try:
                        field_values[field.name] = self._read_field_value(buffer, field)
                    except:
                        field_values[field.name] = self._get_default_value(field)
            
            return self._create_object(field_values)
            
        except Exception as e:
            logger.error(f"Failed to deserialize {self._type_cls.__name__}: {e}")
            raise
    
    def _write_field_value(self, buffer: Buffer, field: FieldInfo, value: Any):
        """Write individual field value"""
        if field.nullable and value is None:
            buffer.write_bool(False)
            return
        elif field.nullable:
            buffer.write_bool(True)
        
        # Write based on field classification
        if field.classification in (FieldClassification.PRIMITIVE, FieldClassification.PRIMITIVE_NULLABLE):
            if field.field_type is int:
                buffer.write_varint64(value)
            elif field.field_type is float:
                buffer.write_double(value)
            elif field.field_type is bool:
                buffer.write_bool(value)
        elif field.classification in (FieldClassification.STRING, FieldClassification.STRING_NULLABLE):
            buffer.write_string(value)
        else:
            # Object type - use Fory's serialization (not implemented for now)
            raise NotImplementedError("Object field serialization not implemented")
    
    def _read_field_value(self, buffer: Buffer, field: FieldInfo) -> Any:
        """Read individual field value"""
        if field.nullable:
            is_present = buffer.read_bool()
            if not is_present:
                return None
        
        # Read based on field classification
        if field.classification in (FieldClassification.PRIMITIVE, FieldClassification.PRIMITIVE_NULLABLE):
            if field.field_type is int:
                return buffer.read_varint64()
            elif field.field_type is float:
                return buffer.read_double()
            elif field.field_type is bool:
                return buffer.read_bool()
        elif field.classification in (FieldClassification.STRING, FieldClassification.STRING_NULLABLE):
            return buffer.read_string()
        else:
            # Object type
            raise NotImplementedError("Object field deserialization not implemented")
    
    def _get_default_value(self, field: FieldInfo) -> Any:
        """Get default value for field"""
        if field.default_value is not MISSING:
            if callable(field.default_value):
                try:
                    return field.default_value()
                except:
                    pass
            else:
                return field.default_value
        elif field.nullable:
            return None
        elif field.classification in (FieldClassification.PRIMITIVE, FieldClassification.PRIMITIVE_NULLABLE):
            if field.field_type is int:
                return 0
            elif field.field_type is float:
                return 0.0
            elif field.field_type is bool:
                return False
        elif field.classification in (FieldClassification.STRING, FieldClassification.STRING_NULLABLE):
            return ""
        else:
            return None
    
    def _create_object(self, field_values: Dict[str, Any]) -> Any:
        """Create object from field values"""
        try:
            if is_dataclass(self._type_cls):
                return self._type_cls(**field_values)
            else:
                # Try constructor with known parameters
                sig = inspect.signature(self._type_cls.__init__)
                constructor_args = {}
                
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                    if param_name in field_values:
                        constructor_args[param_name] = field_values[param_name]
                    elif param.default is not param.empty:
                        constructor_args[param_name] = param.default
                        
                obj = self._type_cls(**constructor_args)
                
                # Set remaining attributes
                for name, value in field_values.items():
                    if name not in constructor_args:
                        setattr(obj, name, value)
                        
                return obj
        except Exception as e:
            logger.error(f"Failed to create object {self._type_cls.__name__}: {e}")
            raise


# Import mmh3 for hashing
try:
    from pyfory.lib import mmh3
except ImportError:
    # Fallback implementation
    import hashlib
    class _MMH3Fallback:
        @staticmethod
        def hash_buffer(data: bytes, signed=True) -> tuple:
            h = hashlib.md5(data).digest()
            result = int.from_bytes(h[:8], 'little', signed=False)
            return (result if not signed else result - 2**64 if result >= 2**63 else result, 0)
    mmh3 = _MMH3Fallback()
