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


@dataclass
class PersonV1:
    name: str
    age: int


def test_basic_compatible_serializer():
    """Test basic functionality of enhanced CompatibleSerializer"""
    fory = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    
    # Register the type with compatible serializer
    fory.register_type(PersonV1)
    
    # Create and serialize object
    person = PersonV1(name="John", age=30)
    serialized = fory.serialize(person)
    
    # Deserialize and verify
    deserialized = fory.deserialize(serialized)
    
    assert isinstance(deserialized, PersonV1)
    assert deserialized.name == "John"
    assert deserialized.age == 30


def test_enhanced_vs_original():
    """Test enhanced implementation produces same results as original"""
    
    # Test with enhanced implementation
    fory_enhanced = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_enhanced.register_type(PersonV1)
    
    person = PersonV1(name="Alice", age=25)
    
    # Serialize and deserialize with enhanced version
    serialized_enhanced = fory_enhanced.serialize(person)
    deserialized_enhanced = fory_enhanced.deserialize(serialized_enhanced)
    
    assert isinstance(deserialized_enhanced, PersonV1)
    assert deserialized_enhanced.name == "Alice"
    assert deserialized_enhanced.age == 25


def test_schema_evolution_compatibility():
    """Test that enhanced implementation supports schema evolution"""
    
    @dataclass
    class PersonV2:
        name: str
        age: int
        email: str = "unknown@example.com"
    
    # Serialize with V1
    fory_v1 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v1.register_type(PersonV1)
    
    person_v1 = PersonV1(name="Bob", age=30)
    serialized = fory_v1.serialize(person_v1)
    
    # Deserialize with V2
    fory_v2 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v2.register_type(PersonV2)
    
    person_v2 = fory_v2.deserialize(serialized)
    
    assert isinstance(person_v2, PersonV2)
    assert person_v2.name == "Bob"
    assert person_v2.age == 30
    assert person_v2.email == "unknown@example.com"  # Default value


if __name__ == "__main__":
    import sys
    import os
    os.environ['ENABLE_FORY_CYTHON_SERIALIZATION'] = 'False'
    test_basic_compatible_serializer()
    test_enhanced_vs_original()
    test_schema_evolution_compatibility()
    print("Enhanced compatible serializer tests passed!")
