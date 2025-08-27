#!/usr/bin/env python3
import logging
import os
import sys
import dataclasses
import pyfory
from pyfory import CompatibleMode
from pyfory.compatible_serializer import CompatibleSerializer

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s %(name)s:%(filename)s:%(lineno)d %(message)s')

@dataclasses.dataclass
class PersonV1:
    name: str
    age: int

@dataclasses.dataclass
class PersonV2:
    name: str
    age: int
    email: str

def debug_v2_to_v1():
    print("=" * 60)
    print("DEBUG: V2 -> V1 Schema Evolution")
    print("=" * 60)
    
    # Serialize with V2
    fory_v2 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v2.register_type(PersonV2)
    
    person_v2 = PersonV2(name="Bob", age=35, email="bob@example.com")
    print(f"V2 Person: {person_v2}")
    
    serialized_v2 = fory_v2.serialize(person_v2)
    print(f"Serialized V2 length: {len(serialized_v2)} bytes")
    
    # Check what was serialized
    serializer_v2 = fory_v2.type_resolver.get_serializer(PersonV2)
    class_info_v2 = serializer_v2.class_info
    print(f"\nV2 ClassInfo fields:")
    for field in class_info_v2.field_infos:
        print(f"  {field.name}: encoding={field.encoded_field_info:08x}, type={field.field_type}")
    
    # Deserialize with V1  
    fory_v1 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v1.register_type(PersonV1)
    
    serializer_v1 = fory_v1.type_resolver.get_serializer(PersonV1)
    class_info_v1 = serializer_v1.class_info
    print(f"\nV1 ClassInfo fields:")
    for field in class_info_v1.field_infos:
        print(f"  {field.name}: encoding={field.encoded_field_info:08x}, type={field.field_type}")
    
    print("\nDeserializing V2 data with V1 schema...")
    try:
        person_v1 = fory_v1.deserialize(serialized_v2)
        print(f"Success: {person_v1}")
    except Exception as e:
        print(f"Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_v2_to_v1()
