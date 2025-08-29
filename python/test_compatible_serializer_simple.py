#!/usr/bin/env python3
"""
Simple test runner for Compatible Serializer
"""

import sys
import os
import traceback
from dataclasses import dataclass
from typing import Optional

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyfory import Fory, CompatibleMode, Buffer
from pyfory.compatible_serializer_clean import CompatibleSerializer, MetaContext, FieldInfo, TypeDefinition


@dataclass
class PersonV1:
    """Basic person class - version 1"""
    name: str
    age: int


@dataclass
class PersonV2:
    """Extended person class - version 2 with additional field"""
    name: str
    age: int
    email: Optional[str] = None


def test_meta_context():
    """Test MetaContext functionality"""
    print("Testing MetaContext...")
    
    meta_context = MetaContext()
    
    # Test class registration
    type_id1 = meta_context.register_class(PersonV1)
    print(f"PersonV1 registered with ID: {type_id1}")
    
    type_id2 = meta_context.register_class(PersonV2)
    print(f"PersonV2 registered with ID: {type_id2}")
    
    # Test type definition retrieval
    type_def1 = meta_context.get_type_definition(type_id1)
    print(f"PersonV1 type definition: {len(type_def1.field_infos)} fields")
    
    type_def2 = meta_context.get_type_definition(type_id2)
    print(f"PersonV2 type definition: {len(type_def2.field_infos)} fields")
    
    print("MetaContext test passed ✓")


def test_basic_serialization():
    """Test basic serialization"""
    print("\nTesting basic serialization...")
    
    try:
        # Create Fory instance
        fory = Fory(compatible_mode=CompatibleMode.COMPATIBLE)
        fory.register(PersonV1, serializer=CompatibleSerializer)
        
        # Create test object
        person = PersonV1(name="Alice", age=30)
        print(f"Original: {person}")
        
        # Serialize
        serialized = fory.serialize(person)
        print(f"Serialized to {len(serialized)} bytes")
        
        # Deserialize
        result = fory.deserialize(serialized)
        print(f"Deserialized: {result}")
        
        # Verify
        assert result.name == person.name
        assert result.age == person.age
        print("Basic serialization test passed ✓")
        
    except Exception as e:
        print(f"Basic serialization test failed: {e}")
        traceback.print_exc()
        return False
    
    return True


def test_nullable_fields():
    """Test nullable fields"""
    print("\nTesting nullable fields...")
    
    try:
        fory = Fory(compatible_mode=CompatibleMode.COMPATIBLE)
        fory.register(PersonV2, serializer=CompatibleSerializer)
        
        # Test with null value
        person_null = PersonV2(name="Bob", age=25, email=None)
        print(f"Person with null email: {person_null}")
        
        serialized_null = fory.serialize(person_null)
        result_null = fory.deserialize(serialized_null)
        print(f"Deserialized null: {result_null}")
        
        assert result_null.name == "Bob"
        assert result_null.age == 25
        assert result_null.email is None
        
        # Test with non-null value
        person_email = PersonV2(name="Charlie", age=35, email="charlie@example.com")
        print(f"Person with email: {person_email}")
        
        serialized_email = fory.serialize(person_email)
        result_email = fory.deserialize(serialized_email)
        print(f"Deserialized with email: {result_email}")
        
        assert result_email.name == "Charlie"
        assert result_email.age == 35
        assert result_email.email == "charlie@example.com"
        
        print("Nullable fields test passed ✓")
        
    except Exception as e:
        print(f"Nullable fields test failed: {e}")
        traceback.print_exc()
        return False
    
    return True


def test_schema_evolution():
    """Test schema evolution"""
    print("\nTesting schema evolution...")
    
    try:
        # Serialize with PersonV1
        fory_v1 = Fory(compatible_mode=CompatibleMode.COMPATIBLE)
        fory_v1.register(PersonV1, serializer=CompatibleSerializer)
        
        person_v1 = PersonV1(name="Alice", age=30)
        print(f"V1 Person: {person_v1}")
        
        serialized = fory_v1.serialize(person_v1)
        print(f"V1 serialized to {len(serialized)} bytes")
        
        # Try to deserialize with PersonV2
        fory_v2 = Fory(compatible_mode=CompatibleMode.COMPATIBLE)
        fory_v2.register(PersonV2, serializer=CompatibleSerializer)
        
        result = fory_v2.deserialize(serialized)
        print(f"V2 deserialized: {result}")
        
        assert result.name == "Alice"
        assert result.age == 30
        assert result.email is None  # Should get default value
        
        print("Schema evolution test passed ✓")
        
    except Exception as e:
        print(f"Schema evolution test failed: {e}")
        traceback.print_exc()
        return False
    
    return True


def test_multiple_objects():
    """Test multiple object serialization"""
    print("\nTesting multiple objects...")
    
    try:
        fory = Fory(compatible_mode=CompatibleMode.COMPATIBLE)
        fory.register(PersonV1, serializer=CompatibleSerializer)
        
        people = [
            PersonV1(name="Person1", age=20),
            PersonV1(name="Person2", age=30),
            PersonV1(name="Person3", age=40)
        ]
        
        # Serialize all
        serialized_data = []
        for person in people:
            serialized = fory.serialize(person)
            serialized_data.append(serialized)
        
        total_bytes = sum(len(s) for s in serialized_data)
        print(f"Serialized {len(people)} objects to {total_bytes} bytes")
        
        # Deserialize all
        results = []
        for serialized in serialized_data:
            result = fory.deserialize(serialized)
            results.append(result)
        
        print(f"Deserialized {len(results)} objects")
        
        # Verify
        for original, result in zip(people, results):
            assert original.name == result.name
            assert original.age == result.age
        
        print("Multiple objects test passed ✓")
        
    except Exception as e:
        print(f"Multiple objects test failed: {e}")
        traceback.print_exc()
        return False
    
    return True


def main():
    """Run all tests"""
    print("=== Compatible Serializer Test Suite ===\n")
    
    tests = [
        test_meta_context,
        test_basic_serialization,
        test_nullable_fields,
        test_schema_evolution,
        test_multiple_objects
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"Test {test_func.__name__} crashed: {e}")
            traceback.print_exc()
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("All tests passed! 🎉")
        return 0
    else:
        print("Some tests failed 😞")
        return 1


if __name__ == "__main__":
    sys.exit(main())
