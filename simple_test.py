#!/usr/bin/env python3
"""Simple debug version to understand the exact issue"""

import sys
sys.path.append("python")

from dataclasses import dataclass
import pyfory
from pyfory.java_compatible_serializer import CompatibleSerializer

@dataclass
class Person:
    name: str
    age: int
    email: str

def simple_test():
    """Simple test focusing on one issue at a time"""
    print("Simple Java Serializer Test")
    print("=" * 40)
    
    # Create test data
    person = Person(name="Alice", age=30, email="alice@test.com")
    print(f"Test person: {person}")
    
    # Create serializer
    fory_instance = pyfory.Fory()
    serializer = CompatibleSerializer(fory_instance, Person)
    
    print("\nField categorization:")
    print(f"embed_types_4_fields: {len(serializer.field_resolver.embed_types_4_fields)}")
    for field in serializer.field_resolver.embed_types_4_fields:
        print(f"  - {field.name}: class_id={field.class_id}, encoded=0x{field.encoded_field_info:08x}")
        
    print(f"embed_types_9_fields: {len(serializer.field_resolver.embed_types_9_fields)}")  
    for field in serializer.field_resolver.embed_types_9_fields:
        print(f"  - {field.name}: class_id={field.class_id}, encoded=0x{field.encoded_field_info:016x}")
        
    print(f"separate_types_hash_fields: {len(serializer.field_resolver.separate_types_hash_fields)}")
    for field in serializer.field_resolver.separate_types_hash_fields:
        print(f"  - {field.name}: class_id={field.class_id}, encoded=0x{field.encoded_field_info:016x}")
    
    print(f"End tag: 0x{serializer.field_resolver.end_tag:016x}")
    
    # Test serialization
    print("\nSerialization:")
    buffer = bytearray()
    try:
        serializer.write(buffer, person)
        print(f"✓ Serialized to {len(buffer)} bytes")
        print(f"Buffer: {buffer.hex()}")
        
        # Test deserialization
        print("\nDeserialization:")
        result = serializer.read(bytes(buffer))
        print(f"✓ Deserialized: {result}")
        
        # Verify
        if (result.name == person.name and 
            result.age == person.age and 
            result.email == person.email):
            print("✓ Round-trip successful!")
        else:
            print("✗ Round-trip failed!")
            print(f"Expected: {person}")
            print(f"Got: {result}")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simple_test()
