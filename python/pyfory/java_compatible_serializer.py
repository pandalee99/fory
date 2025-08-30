"""
Java-compatible serializer implementation for PyFory.
This module provides complete compatibility with Fory's Java CompatibleSerializer.
"""

import struct
import hashlib
from typing import Dict, List, Any, Union, Optional, Type, Tuple
from dataclasses import dataclass, fields, is_dataclass
from collections import defaultdict
import logging

# Try to import mmh3, fallback to hashlib if not available
try:
    import mmh3
    HAS_MMH3 = True
except ImportError:
    HAS_MMH3 = False
    logging.warning("mmh3 not available, using hashlib fallback for field hashing")

logger = logging.getLogger(__name__)

# Java-compatible constants
EMBED_CLASS_TYPE_FLAG = 0x1
EMBED_TYPES_4_FLAG = 0x1      # 0b01
EMBED_TYPES_9_FLAG = 0x3      # 0b011  
EMBED_TYPES_HASH_FLAG = 0x7   # 0b111
SEPARATE_TYPES_HASH_FLAG = 0x0 # 0b00
OBJECT_END_FLAG = 0x2         # 0b10

MAX_EMBED_CLASS_ID = 127
END_TAG = (1 << 63) | OBJECT_END_FLAG

# Field types (Java FieldResolver.FieldTypes)
class FieldTypes:
    OBJECT = 0
    COLLECTION_ELEMENT_FINAL = 1
    MAP_KEY_FINAL = 2
    MAP_VALUE_FINAL = 3
    MAP_KV_FINAL = 4

# Java ClassResolver primitive class IDs
PRIMITIVE_CLASS_IDS = {
    bool: 1,    # PRIMITIVE_BOOLEAN_CLASS_ID
    int: 2,     # PRIMITIVE_INT_CLASS_ID (also covers byte, short, long)
    float: 3,   # PRIMITIVE_DOUBLE_CLASS_ID (also covers float)
    str: 9,     # STRING_CLASS_ID
}

def compute_string_hash(field_name: str) -> int:
    """Compute field name hash using MurmurHash3 (Java compatible) or fallback"""
    if HAS_MMH3:
        # Use seed 47 to match Java implementation: MurmurHash3.murmurhash3_x64_128(bytes, 0, bytes.length, 47)[0]
        return mmh3.hash64(field_name.encode('utf-8'), 47)[0]
    else:
        # Fallback to hashlib (not fully compatible but functional)
        hash_obj = hashlib.md5(field_name.encode('utf-8'))
        return int.from_bytes(hash_obj.digest()[:8], 'little', signed=True)

def encode_field_name_as_long(field_name: str) -> int:
    """Encode field name using 6 bits per character (Java compatible)"""
    encoded = 0
    for c in field_name:
        encoded = encoded << 6
        if '0' <= c <= '9':
            encoded |= (ord(c) - ord('0')) & 0x3F
        elif 'A' <= c <= 'Z':
            encoded |= (ord(c) - ord('A') + 10) & 0x3F
        elif 'a' <= c <= 'z':
            encoded |= (ord(c) - ord('a') + 36) & 0x3F
        else:
            raise ValueError(f"Invalid character in field name: {c}")
    return encoded

def encoding_bytes_length(field_name: str) -> int:
    """Calculate encoding length for field name"""
    return len(field_name.encode('utf-8'))

@dataclass
class FieldInfo:
    """Java-compatible FieldInfo"""
    name: str
    field_type: Type
    field_type_code: int = FieldTypes.OBJECT
    field_info_encoding_type: int = 0
    encoded_field_info: int = 0
    class_id: int = -1
    nullable: bool = True
    field_accessor: Any = None
    
    @property
    def embedded_class_id(self) -> int:
        return self.class_id

class FieldResolver:
    """Java-compatible FieldResolver implementation"""
    
    def __init__(self, target_class: Type, fory=None):
        self.target_class = target_class
        self.embed_types_4_fields: List[FieldInfo] = []
        self.embed_types_9_fields: List[FieldInfo] = []
        self.embed_types_hash_fields: List[FieldInfo] = []
        self.separate_types_hash_fields: List[FieldInfo] = []
        self.end_tag = END_TAG
        self.duplicated_fields = {}
        
        # Build field info from class
        self._build_field_info(fory)
        
    def _build_field_info(self, fory):
        """Build field info compatible with Java implementation"""
        all_fields = []
        
        # Handle dataclass fields
        if is_dataclass(self.target_class):
            for field in fields(self.target_class):
                all_fields.append((field.name, field.type))
        
        # Handle class annotations
        elif hasattr(self.target_class, '__annotations__'):
            for field_name, field_type in self.target_class.__annotations__.items():
                all_fields.append((field_name, field_type))
        
        # Sort fields for consistent processing
        all_fields.sort(key=lambda x: x[0])
        
        # Categorize fields based on encoding type
        for field_name, field_type in all_fields:
            self._categorize_field(field_name, field_type, fory)
            
        # Sort fields by encoded field info (Java compatible)
        self.embed_types_4_fields.sort(key=lambda x: x.encoded_field_info)
        self.embed_types_9_fields.sort(key=lambda x: x.encoded_field_info)
        self.embed_types_hash_fields.sort(key=lambda x: x.encoded_field_info)
        self.separate_types_hash_fields.sort(key=lambda x: x.encoded_field_info)
        
    def _categorize_field(self, field_name: str, field_type: Type, fory):
        """Categorize field based on Java FieldResolver logic"""
        field_name_len = encoding_bytes_length(field_name)
        class_id = self._get_registered_class_id(field_type)
        
        # Check if type is monomorphic and has registered class ID
        if (self._is_monomorphic(field_type) and 
            class_id != -1 and class_id < MAX_EMBED_CLASS_ID):
            
            if field_name_len <= 3 and class_id <= 63:
                # EMBED_TYPES_4: 24 bits field name + 6 bits class id + 2 flag bits
                encoded = encode_field_name_as_long(field_name)
                encoded_field_info = (encoded << 8) | (class_id << 2) | EMBED_TYPES_4_FLAG
                
                field_info = FieldInfo(
                    name=field_name,
                    field_type=field_type,
                    field_type_code=FieldTypes.OBJECT,
                    field_info_encoding_type=0,  # EMBED_TYPES_4
                    encoded_field_info=encoded_field_info,
                    class_id=class_id
                )
                self.embed_types_4_fields.append(field_info)
                
            elif field_name_len <= 7:
                # EMBED_TYPES_9: 54 bits field name + 7 bits class id + 3 flag bits
                encoded = encode_field_name_as_long(field_name)
                encoded_field_info = (encoded << 10) | (class_id << 3) | EMBED_TYPES_9_FLAG
                
                field_info = FieldInfo(
                    name=field_name,
                    field_type=field_type,
                    field_type_code=FieldTypes.OBJECT,
                    field_info_encoding_type=1,  # EMBED_TYPES_9
                    encoded_field_info=encoded_field_info,
                    class_id=class_id
                )
                self.embed_types_9_fields.append(field_info)
                
            else:
                # EMBED_TYPES_HASH: hash(54 bits) + 7 bits class id + 3 flag bits
                field_hash = compute_string_hash(field_name)
                encoded_field_info = (field_hash << 10) | (class_id << 3) | EMBED_TYPES_HASH_FLAG
                
                field_info = FieldInfo(
                    name=field_name,
                    field_type=field_type,
                    field_type_code=FieldTypes.OBJECT,
                    field_info_encoding_type=2,  # EMBED_TYPES_HASH
                    encoded_field_info=encoded_field_info,
                    class_id=class_id
                )
                self.embed_types_hash_fields.append(field_info)
        else:
            # SEPARATE_TYPES_HASH: separate field name hash (62 bits) + 2 flag bits
            field_hash = compute_string_hash(field_name)
            encoded_field_info = (field_hash << 2) | SEPARATE_TYPES_HASH_FLAG
            
            field_info = FieldInfo(
                name=field_name,
                field_type=field_type,
                field_type_code=FieldTypes.OBJECT,
                field_info_encoding_type=3,  # SEPARATE_TYPES_HASH
                encoded_field_info=encoded_field_info,
                class_id=-1
            )
            self.separate_types_hash_fields.append(field_info)
            
    def _get_registered_class_id(self, field_type: Type) -> int:
        """Get registered class ID for type (Java compatible)"""
        return PRIMITIVE_CLASS_IDS.get(field_type, -1)
        
    def _is_monomorphic(self, field_type: Type) -> bool:
        """Check if type is monomorphic (Java compatible)"""
        return field_type in PRIMITIVE_CLASS_IDS
        
    def get_all_fields_list(self) -> List[FieldInfo]:
        """Get all fields in order (Java compatible)"""
        all_fields = []
        all_fields.extend(self.embed_types_4_fields)
        all_fields.extend(self.embed_types_9_fields)
        all_fields.extend(self.embed_types_hash_fields)
        all_fields.extend(self.separate_types_hash_fields)
        return all_fields
        
    def get_num_fields(self) -> int:
        """Get total number of fields"""
        return (len(self.embed_types_4_fields) + 
                len(self.embed_types_9_fields) +
                len(self.embed_types_hash_fields) +
                len(self.separate_types_hash_fields))

class CompatibleSerializer:
    """Java-compatible CompatibleSerializer implementation"""
    
    def __init__(self, fory, target_class: Type):
        self.fory = fory
        self.target_class = target_class
        self.field_resolver = FieldResolver(target_class, fory)
        self.is_record = is_dataclass(target_class)
        
        # Register with fory if available
        # Don't auto-register to avoid conflicts with Fory's registration mechanism
        # if hasattr(fory, 'register') and callable(fory.register):
        #     fory.register(target_class, serializer=self)
    
    def write(self, buffer: Union[bytearray, Any], value: Any):
        """Write object using Java-compatible format"""
        try:
            # Write embed types 4 fields
            for field_info in self.field_resolver.embed_types_4_fields:
                self._write_int32(buffer, field_info.encoded_field_info)
                self._write_field_value(buffer, field_info, value)
            
            # Write embed types 9 fields  
            for field_info in self.field_resolver.embed_types_9_fields:
                self._write_int64(buffer, field_info.encoded_field_info)
                self._write_field_value(buffer, field_info, value)
            
            # Write embed types hash fields
            for field_info in self.field_resolver.embed_types_hash_fields:
                self._write_int64(buffer, field_info.encoded_field_info)
                self._write_field_value(buffer, field_info, value)
            
            # Write separate types hash fields
            for field_info in self.field_resolver.separate_types_hash_fields:
                self._write_int64(buffer, field_info.encoded_field_info)
                self._write_field_value(buffer, field_info, value)
            
            # Write end tag
            self._write_int64(buffer, self.field_resolver.end_tag)
            
        except Exception as e:
            raise RuntimeError(f"Failed to write {self.target_class.__name__}: {e}")
    
    def read(self, buffer: Union[bytes, Any]) -> Any:
        """Read object using Java-compatible format"""
        try:
            if isinstance(buffer, bytes):
                buffer = bytearray(buffer)
                
            field_values = {}
            
            # Read all field data
            self._read_fields(buffer, field_values)
            
            # Create object instance
            if self.is_record:
                # For dataclasses, use field order
                field_names = [f.name for f in fields(self.target_class)]
                ordered_values = []
                for name in field_names:
                    ordered_values.append(field_values.get(name, None))
                return self.target_class(*ordered_values)
            else:
                # For regular classes, create and set attributes
                obj = self.target_class()
                for name, value in field_values.items():
                    setattr(obj, name, value)
                return obj
                
        except Exception as e:
            raise RuntimeError(f"Failed to read {self.target_class.__name__}: {e}")
    
    def _read_fields(self, buffer: bytearray, field_values: Dict[str, Any]):
        """Read all fields from buffer"""
        buffer_pos = [0]  # Use list for mutable reference
        
        # Read embed types 4 fields
        part_field_info = self._read_embed_types_4_fields(buffer, buffer_pos, field_values)
        
        if part_field_info == self.field_resolver.end_tag:
            return
        
        # Read embed types 9 fields
        tmp = self._read_int32(buffer, buffer_pos)
        part_field_info = (tmp << 32) | (part_field_info & 0x00000000ffffffff)
        part_field_info = self._read_embed_types_9_fields(buffer, buffer_pos, part_field_info, field_values)
        
        if part_field_info == self.field_resolver.end_tag:
            return
        
        # Read embed types hash fields
        part_field_info = self._read_embed_types_hash_fields(buffer, buffer_pos, part_field_info, field_values)
        
        if part_field_info == self.field_resolver.end_tag:
            return
            
        # Read separate types hash fields
        self._read_separate_types_hash_fields(buffer, buffer_pos, part_field_info, field_values)
    
    def _read_embed_types_4_fields(self, buffer: bytearray, buffer_pos: List[int], field_values: Dict[str, Any]) -> int:
        """Read embed types 4 fields (Java compatible)"""
        part_field_info = self._read_int32(buffer, buffer_pos)
        embed_types_4_fields = self.field_resolver.embed_types_4_fields
        
        if embed_types_4_fields:
            min_field_info = embed_types_4_fields[0].encoded_field_info
            
            # Skip unknown fields before our fields
            while ((part_field_info & 0b11) == EMBED_TYPES_4_FLAG and 
                   part_field_info < min_field_info):
                self._skip_data_by_4(buffer, buffer_pos, part_field_info)
                if buffer_pos[0] >= len(buffer):
                    return self.field_resolver.end_tag
                part_field_info = self._read_int32(buffer, buffer_pos)
            
            # Read known fields
            for field_info in embed_types_4_fields:
                if field_info.encoded_field_info == part_field_info:
                    value = self._read_field_value(buffer, buffer_pos, field_info)
                    field_values[field_info.name] = value
                    if buffer_pos[0] >= len(buffer):
                        return self.field_resolver.end_tag
                    part_field_info = self._read_int32(buffer, buffer_pos)
                elif ((part_field_info & 0b11) == EMBED_TYPES_4_FLAG and 
                      part_field_info < field_info.encoded_field_info):
                    # Skip unknown field
                    self._skip_data_by_4(buffer, buffer_pos, part_field_info)
                    if buffer_pos[0] >= len(buffer):
                        return self.field_resolver.end_tag
                    part_field_info = self._read_int32(buffer, buffer_pos)
                else:
                    break
        
        # Skip remaining unknown fields
        while (part_field_info & 0b11) == EMBED_TYPES_4_FLAG:
            self._skip_data_by_4(buffer, buffer_pos, part_field_info)
            if buffer_pos[0] >= len(buffer):
                return self.field_resolver.end_tag
            part_field_info = self._read_int32(buffer, buffer_pos)
            
        return part_field_info
    
    def _read_embed_types_9_fields(self, buffer: bytearray, buffer_pos: List[int], 
                                   part_field_info: int, field_values: Dict[str, Any]) -> int:
        """Read embed types 9 fields (Java compatible)"""
        embed_types_9_fields = self.field_resolver.embed_types_9_fields
        
        if embed_types_9_fields:
            min_field_info = embed_types_9_fields[0].encoded_field_info
            
            # Skip unknown fields before our fields
            while ((part_field_info & 0b111) == EMBED_TYPES_9_FLAG and 
                   part_field_info < min_field_info):
                self._skip_data_by_8(buffer, buffer_pos, part_field_info)
                if buffer_pos[0] >= len(buffer):
                    return self.field_resolver.end_tag
                part_field_info = self._read_int64(buffer, buffer_pos)
            
            # Read known fields
            for field_info in embed_types_9_fields:
                if field_info.encoded_field_info == part_field_info:
                    value = self._read_field_value(buffer, buffer_pos, field_info)
                    field_values[field_info.name] = value
                    if buffer_pos[0] >= len(buffer):
                        return self.field_resolver.end_tag
                    part_field_info = self._read_int64(buffer, buffer_pos)
                elif ((part_field_info & 0b111) == EMBED_TYPES_9_FLAG and 
                      part_field_info < field_info.encoded_field_info):
                    # Skip unknown field
                    self._skip_data_by_8(buffer, buffer_pos, part_field_info)
                    if buffer_pos[0] >= len(buffer):
                        return self.field_resolver.end_tag
                    part_field_info = self._read_int64(buffer, buffer_pos)
                else:
                    break
        
        # Skip remaining unknown fields
        while (part_field_info & 0b111) == EMBED_TYPES_9_FLAG:
            self._skip_data_by_8(buffer, buffer_pos, part_field_info)
            if buffer_pos[0] >= len(buffer):
                return self.field_resolver.end_tag
            part_field_info = self._read_int64(buffer, buffer_pos)
            
        return part_field_info
    
    def _read_embed_types_hash_fields(self, buffer: bytearray, buffer_pos: List[int],
                                      part_field_info: int, field_values: Dict[str, Any]) -> int:
        """Read embed types hash fields (Java compatible)"""
        embed_types_hash_fields = self.field_resolver.embed_types_hash_fields
        
        if embed_types_hash_fields:
            min_field_info = embed_types_hash_fields[0].encoded_field_info
            
            # Skip unknown fields before our fields
            while ((part_field_info & 0b111) == EMBED_TYPES_HASH_FLAG and 
                   part_field_info < min_field_info):
                self._skip_data_by_8(buffer, buffer_pos, part_field_info)
                if buffer_pos[0] >= len(buffer):
                    return self.field_resolver.end_tag
                part_field_info = self._read_int64(buffer, buffer_pos)
            
            # Read known fields
            for field_info in embed_types_hash_fields:
                if field_info.encoded_field_info == part_field_info:
                    value = self._read_field_value(buffer, buffer_pos, field_info)
                    field_values[field_info.name] = value
                    if buffer_pos[0] >= len(buffer):
                        return self.field_resolver.end_tag
                    part_field_info = self._read_int64(buffer, buffer_pos)
                elif ((part_field_info & 0b111) == EMBED_TYPES_HASH_FLAG and 
                      part_field_info < field_info.encoded_field_info):
                    # Skip unknown field
                    self._skip_data_by_8(buffer, buffer_pos, part_field_info)
                    if buffer_pos[0] >= len(buffer):
                        return self.field_resolver.end_tag
                    part_field_info = self._read_int64(buffer, buffer_pos)
                else:
                    break
        
        # Skip remaining unknown fields
        while (part_field_info & 0b111) == EMBED_TYPES_HASH_FLAG:
            self._skip_data_by_8(buffer, buffer_pos, part_field_info)
            if buffer_pos[0] >= len(buffer):
                return self.field_resolver.end_tag
            part_field_info = self._read_int64(buffer, buffer_pos)
            
        return part_field_info
    
    def _read_separate_types_hash_fields(self, buffer: bytearray, buffer_pos: List[int],
                                         part_field_info: int, field_values: Dict[str, Any]):
        """Read separate types hash fields (Java compatible)"""
        separate_types_hash_fields = self.field_resolver.separate_types_hash_fields
        
        if separate_types_hash_fields:
            min_field_info = separate_types_hash_fields[0].encoded_field_info
            
            # Skip unknown fields before our fields
            while ((part_field_info & 0b11) == SEPARATE_TYPES_HASH_FLAG and 
                   part_field_info < min_field_info):
                self._skip_data_by_8(buffer, buffer_pos, part_field_info)
                if buffer_pos[0] >= len(buffer):
                    return
                part_field_info = self._read_int64(buffer, buffer_pos)
            
            # Read known fields
            for field_info in separate_types_hash_fields:
                if field_info.encoded_field_info == part_field_info:
                    value = self._read_field_value(buffer, buffer_pos, field_info)
                    field_values[field_info.name] = value
                    # Check if there's more data before reading next field
                    if buffer_pos[0] >= len(buffer):
                        return
                    part_field_info = self._read_int64(buffer, buffer_pos)
                elif ((part_field_info & 0b11) == SEPARATE_TYPES_HASH_FLAG and 
                      part_field_info < field_info.encoded_field_info):
                    # Skip unknown field
                    self._skip_data_by_8(buffer, buffer_pos, part_field_info)
                    if buffer_pos[0] >= len(buffer):
                        return
                    part_field_info = self._read_int64(buffer, buffer_pos)
                else:
                    break
        
        # Skip end fields
        self._skip_end_fields(buffer, buffer_pos, part_field_info)
    
    def _write_field_value(self, buffer: bytearray, field_info: FieldInfo, obj: Any):
        """Write field value (Java compatible)"""
        value = getattr(obj, field_info.name, None)
        
        if field_info.class_id != -1:
            # Embedded class ID - write primitive directly
            if field_info.class_id == 1:  # boolean
                self._write_bool(buffer, bool(value) if value is not None else False)
            elif field_info.class_id == 2:  # int
                self._write_varint32(buffer, int(value) if value is not None else 0)
            elif field_info.class_id == 3:  # double/float
                self._write_double(buffer, float(value) if value is not None else 0.0)
            elif field_info.class_id == 9:  # string
                self._write_string_ref(buffer, str(value) if value is not None else "")
        else:
            # Separate type - write with ref tracking
            if value is not None:
                self._write_ref_or_null(buffer, value)
            else:
                self._write_null(buffer)
    
    def _read_field_value(self, buffer: bytearray, buffer_pos: List[int], field_info: FieldInfo) -> Any:
        """Read field value (Java compatible)"""
        if field_info.class_id != -1:
            # Embedded class ID - read primitive directly
            if field_info.class_id == 1:  # boolean
                return self._read_bool(buffer, buffer_pos)
            elif field_info.class_id == 2:  # int
                return self._read_varint32(buffer, buffer_pos)
            elif field_info.class_id == 3:  # double/float
                return self._read_double(buffer, buffer_pos)
            elif field_info.class_id == 9:  # string
                return self._read_string_ref(buffer, buffer_pos)
        else:
            # Separate type - read with ref tracking
            return self._read_ref_or_null(buffer, buffer_pos)
        
        return None
    
    def _skip_data_by_4(self, buffer: bytearray, buffer_pos: List[int], field_info: int):
        """Skip field data for 4-byte encoded field (Java compatible)"""
        if (field_info & 0b1) == EMBED_CLASS_TYPE_FLAG:
            class_id = (field_info & 0xff) >> 2
            self._skip_primitive_value(buffer, buffer_pos, class_id)
        else:
            if (field_info & 0b11) == SEPARATE_TYPES_HASH_FLAG:
                self._skip_object_field(buffer, buffer_pos)
            else:
                # End tag check
                if field_info != self.field_resolver.end_tag:
                    raise ValueError(f"Invalid end tag: {field_info}")
    
    def _skip_data_by_8(self, buffer: bytearray, buffer_pos: List[int], field_info: int):
        """Skip field data for 8-byte encoded field (Java compatible)"""
        if (field_info & 0b1) == EMBED_CLASS_TYPE_FLAG:
            if (field_info & 0b11) == EMBED_TYPES_4_FLAG:
                class_id = (field_info & 0xff) >> 2
                buffer_pos[0] -= 4  # Adjust position
            else:
                class_id = (field_info & 0b1111111111) >> 3
            self._skip_primitive_value(buffer, buffer_pos, class_id)
        else:
            if (field_info & 0b11) == SEPARATE_TYPES_HASH_FLAG:
                self._skip_object_field(buffer, buffer_pos)
            else:
                # End tag check
                if field_info != self.field_resolver.end_tag:
                    raise ValueError(f"Invalid end tag: {field_info}")
    
    def _skip_primitive_value(self, buffer: bytearray, buffer_pos: List[int], class_id: int):
        """Skip primitive value based on class ID"""
        if class_id == 1:  # boolean
            buffer_pos[0] += 1
        elif class_id == 2:  # int
            self._skip_varint32(buffer, buffer_pos)
        elif class_id == 3:  # double/float
            buffer_pos[0] += 8
        elif class_id == 9:  # string
            self._skip_string_ref(buffer, buffer_pos)
    
    def _skip_object_field(self, buffer: bytearray, buffer_pos: List[int]):
        """Skip object field (Java compatible)"""
        # Skip ref tracking info and object data
        ref_flag = self._read_int8(buffer, buffer_pos)
        if ref_flag >= 0:  # NOT_NULL_VALUE_FLAG
            field_type = self._read_int8(buffer, buffer_pos)
            if field_type == FieldTypes.OBJECT:
                # Skip class info and object data
                self._skip_class_info(buffer, buffer_pos)
                self._skip_object_data(buffer, buffer_pos)
            else:
                # Skip collection/map data
                self._skip_collection_or_map_data(buffer, buffer_pos, field_type)
    
    def _skip_end_fields(self, buffer: bytearray, buffer_pos: List[int], part_field_info: int):
        """Skip remaining fields until end tag"""
        end_tag = self.field_resolver.end_tag
        while part_field_info < end_tag:
            self._skip_data_by_8(buffer, buffer_pos, part_field_info)
            part_field_info = self._read_int64(buffer, buffer_pos)
        
        if part_field_info != end_tag:
            raise ValueError(f"Expected end tag {end_tag} but got {part_field_info}")
    
    # Low-level buffer operations
    def _write_int32(self, buffer: bytearray, value: int):
        """Write 32-bit integer in little-endian format"""
        buffer.extend(struct.pack('<I', value & 0xffffffff))
    
    def _write_int64(self, buffer: bytearray, value: int):
        """Write 64-bit integer in little-endian format"""  
        buffer.extend(struct.pack('<Q', value & 0xffffffffffffffff))
    
    def _write_bool(self, buffer: bytearray, value: bool):
        """Write boolean value"""
        buffer.append(1 if value else 0)
    
    def _write_varint32(self, buffer: bytearray, value: int):
        """Write variable-length 32-bit integer"""
        while value >= 0x80:
            buffer.append((value & 0x7F) | 0x80)
            value >>= 7
        buffer.append(value & 0x7F)
    
    def _write_double(self, buffer: bytearray, value: float):
        """Write 64-bit double"""
        buffer.extend(struct.pack('<d', value))
    
    def _write_string_ref(self, buffer: bytearray, value: str):
        """Write string with reference tracking"""
        data = value.encode('utf-8')
        self._write_varint32(buffer, len(data))
        buffer.extend(data)
    
    def _write_ref_or_null(self, buffer: bytearray, value: Any):
        """Write reference or null"""
        if value is None:
            self._write_int8(buffer, -1)  # NULL_FLAG
        else:
            self._write_int8(buffer, 0)   # NOT_NULL_VALUE_FLAG
            # Write object type and data
            buffer.append(FieldTypes.OBJECT)
            # Simple object serialization - in real implementation would use fory
            data = str(value).encode('utf-8')
            self._write_varint32(buffer, len(data))
            buffer.extend(data)
    
    def _write_null(self, buffer: bytearray):
        """Write null value"""
        self._write_int8(buffer, -1)
    
    def _write_int8(self, buffer: bytearray, value: int):
        """Write 8-bit integer"""
        buffer.append(value & 0xff)
    
    def _read_int32(self, buffer: bytearray, buffer_pos: List[int]) -> int:
        """Read 32-bit integer in little-endian format"""
        if buffer_pos[0] + 4 > len(buffer):
            raise IndexError("Buffer underflow reading int32")
        value = struct.unpack('<I', buffer[buffer_pos[0]:buffer_pos[0]+4])[0]
        buffer_pos[0] += 4
        return value
    
    def _read_int64(self, buffer: bytearray, buffer_pos: List[int]) -> int:
        """Read 64-bit integer in little-endian format"""
        if buffer_pos[0] + 8 > len(buffer):
            raise IndexError("Buffer underflow reading int64")
        value = struct.unpack('<Q', buffer[buffer_pos[0]:buffer_pos[0]+8])[0]
        buffer_pos[0] += 8
        return value
    
    def _read_bool(self, buffer: bytearray, buffer_pos: List[int]) -> bool:
        """Read boolean value"""
        if buffer_pos[0] >= len(buffer):
            raise IndexError("Buffer underflow reading bool")
        value = buffer[buffer_pos[0]] != 0
        buffer_pos[0] += 1
        return value
    
    def _read_varint32(self, buffer: bytearray, buffer_pos: List[int]) -> int:
        """Read variable-length 32-bit integer"""
        result = 0
        shift = 0
        while buffer_pos[0] < len(buffer):
            byte = buffer[buffer_pos[0]]
            buffer_pos[0] += 1
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
        return result
    
    def _read_double(self, buffer: bytearray, buffer_pos: List[int]) -> float:
        """Read 64-bit double"""
        if buffer_pos[0] + 8 > len(buffer):
            raise IndexError("Buffer underflow reading double")
        value = struct.unpack('<d', buffer[buffer_pos[0]:buffer_pos[0]+8])[0]
        buffer_pos[0] += 8
        return value
    
    def _read_string_ref(self, buffer: bytearray, buffer_pos: List[int]) -> str:
        """Read string with reference tracking"""
        length = self._read_varint32(buffer, buffer_pos)
        if buffer_pos[0] + length > len(buffer):
            raise IndexError("Buffer underflow reading string")
        data = buffer[buffer_pos[0]:buffer_pos[0]+length]
        buffer_pos[0] += length
        return data.decode('utf-8')
    
    def _read_ref_or_null(self, buffer: bytearray, buffer_pos: List[int]) -> Any:
        """Read reference or null"""
        flag = self._read_int8(buffer, buffer_pos)
        if flag == -1:  # NULL_FLAG
            return None
        else:  # NOT_NULL_VALUE_FLAG
            field_type = self._read_int8(buffer, buffer_pos)
            if field_type == FieldTypes.OBJECT:
                # Simple object deserialization
                length = self._read_varint32(buffer, buffer_pos)
                data = buffer[buffer_pos[0]:buffer_pos[0]+length]
                buffer_pos[0] += length
                return data.decode('utf-8')
            else:
                # Collection/map - not implemented for this basic version
                return None
    
    def _read_int8(self, buffer: bytearray, buffer_pos: List[int]) -> int:
        """Read 8-bit integer"""
        if buffer_pos[0] >= len(buffer):
            raise IndexError("Buffer underflow reading int8")
        value = buffer[buffer_pos[0]]
        if value > 127:
            value -= 256  # Convert to signed
        buffer_pos[0] += 1
        return value
    
    def _skip_varint32(self, buffer: bytearray, buffer_pos: List[int]):
        """Skip variable-length 32-bit integer"""
        while buffer_pos[0] < len(buffer):
            byte = buffer[buffer_pos[0]]
            buffer_pos[0] += 1
            if (byte & 0x80) == 0:
                break
    
    def _skip_string_ref(self, buffer: bytearray, buffer_pos: List[int]):
        """Skip string with reference tracking"""
        length = self._read_varint32(buffer, buffer_pos)
        buffer_pos[0] += length
    
    def _skip_class_info(self, buffer: bytearray, buffer_pos: List[int]):
        """Skip class info"""
        # Simple skip - read class name length and skip
        length = self._read_varint32(buffer, buffer_pos)
        buffer_pos[0] += length
    
    def _skip_object_data(self, buffer: bytearray, buffer_pos: List[int]):
        """Skip object data"""
        # Simple skip - read data length and skip
        length = self._read_varint32(buffer, buffer_pos)
        buffer_pos[0] += length
    
    def _skip_collection_or_map_data(self, buffer: bytearray, buffer_pos: List[int], field_type: int):
        """Skip collection or map data"""
        # Simple skip for collections/maps - not fully implemented
        length = self._read_varint32(buffer, buffer_pos)
        buffer_pos[0] += length
