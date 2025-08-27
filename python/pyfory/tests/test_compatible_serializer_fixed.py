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

import pytest
from dataclasses import dataclass
from typing import List, Dict, Optional
import pyfory
from pyfory._fory import CompatibleMode
from pyfory.compatible_serializer import CompatibleSerializer, MetaContext
import os


@dataclass 
class PersonV1:
    """Version 1 of Person class with basic fields"""
    name: str
    age: int


@dataclass
class PersonV2:
    """Version 2 of Person class with additional email field"""
    name: str
    age: int
    email: str = "unknown@example.com"  # New field with default


@dataclass
class PersonV3:
    """Version 3 of Person class with removed age field and new fields"""
    name: str
    email: str = "unknown@example.com"
    city: str = "Unknown City"  # Another new field


@dataclass
class ComplexObjectV1:
    """Complex object with nested collections"""
    id: int
    tags: List[str]
    metadata: Dict[str, str]


@dataclass  
class ComplexObjectV2:
    """Evolved version with new fields and changed types"""
    id: int
    tags: List[str] 
    metadata: Dict[str, str]
    score: float = 0.0  # New field
    is_active: bool = True  # New field


def test_compatible_serializer_basic():
    """Test basic functionality of CompatibleSerializer"""
    fory = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    
    # Register the type with compatible serializer
    fory.register_type(PersonV1)
    
    # Create and serialize object
    person = PersonV1(name="John", age=30)
    serialized = fory.serialize(person)
    
    # Deserialize and verify
    deserialized = fory.deserialize(serialized)
    assert deserialized.name == "John"
    assert deserialized.age == 30


def test_schema_evolution_add_field():
    """Test forward compatibility - old data, new schema"""
    
    # Serialize with V1 schema
    fory_v1 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v1.register_type(PersonV1)
    
    person_v1 = PersonV1(name="Alice", age=25)
    serialized_v1 = fory_v1.serialize(person_v1)
    
    # Deserialize with V2 schema (has additional email field)
    fory_v2 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v2.register_type(PersonV2)
    
    person_v2 = fory_v2.deserialize(serialized_v1)
    assert person_v2.name == "Alice"
    assert person_v2.age == 25
    assert person_v2.email == "unknown@example.com"  # Default value


def test_schema_evolution_remove_field():
    """Test backward compatibility - new data, old schema"""
    
    # Serialize with V2 schema
    fory_v2 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v2.register_type(PersonV2)
    
    person_v2 = PersonV2(name="Bob", age=35, email="bob@example.com")
    serialized_v2 = fory_v2.serialize(person_v2)
    
    # Deserialize with V1 schema (doesn't have email field)
    fory_v1 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v1.register_type(PersonV1)
    
    person_v1 = fory_v1.deserialize(serialized_v2)
    assert person_v1.name == "Bob"
    assert person_v1.age == 35
    # email field is ignored since V1 doesn't have it


def test_meta_context():
    """Test MetaContext functionality"""
    meta_context = MetaContext()
    
    # Test class definition registration
    type_id = meta_context.register_class(PersonV1)
    
    assert type_id >= 1000  # Should start from 1000
    
    # Test getting class definition
    class_info = meta_context.get_class_info(type_id)
    assert class_info is not None
    assert class_info.type_cls == PersonV1
    assert len(class_info.field_infos) == 2
    field_names = [f.name for f in class_info.field_infos]
    assert "name" in field_names
    assert "age" in field_names
    
    # Verify type hints from field_infos
    field_types = {f.name: f.type_hint for f in class_info.field_infos}
    assert field_types["name"] == str
    assert field_types["age"] == int
def test_compatible_vs_schema_consistent_mode():
    """Test difference between compatible and schema consistent modes"""
    
    # Create object with V1 schema
    person_v1 = PersonV1(name="Eve", age=22)
    
    # Serialize in schema consistent mode
    fory_consistent = pyfory.Fory(compatible_mode=CompatibleMode.SCHEMA_CONSISTENT)
    fory_consistent.register_type(PersonV1)
    serialized_consistent = fory_consistent.serialize(person_v1)
    
    # Serialize in compatible mode
    fory_compatible = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_compatible.register_type(PersonV1)
    serialized_compatible = fory_compatible.serialize(person_v1)
    
    # Compatible mode should produce larger serialized data due to metadata
    assert len(serialized_compatible) > len(serialized_consistent)
    
    # Both should deserialize correctly with same schema
    person_consistent = fory_consistent.deserialize(serialized_consistent)
    person_compatible = fory_compatible.deserialize(serialized_compatible)
    
    assert person_consistent.name == person_compatible.name == "Eve"
    assert person_consistent.age == person_compatible.age == 22


if __name__ == "__main__":
    os.environ['ENABLE_FORY_CYTHON_SERIALIZATION'] = '0'
    pytest.main([__file__, "-v"])
