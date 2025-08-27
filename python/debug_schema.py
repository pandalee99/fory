import logging
from dataclasses import dataclass
import pyfory
from pyfory._fory import CompatibleMode

# Set up debug logging
logging.basicConfig(level=logging.DEBUG)

@dataclass 
class PersonV1:
    name: str
    age: int

@dataclass
class PersonV2:
    name: str
    age: int
    email: str = "unknown@example.com"

def test_schema_evolution():
    """Test schema evolution"""
    
    print("=== Test 1: V1 -> V2 (add field) ===")
    # Serialize with V1
    fory_v1 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v1.register_type(PersonV1)
    
    person_v1 = PersonV1(name="Alice", age=25)
    print(f"Original V1: {person_v1}")
    serialized_v1 = fory_v1.serialize(person_v1)
    print(f"Serialized V1: {len(serialized_v1)} bytes")
    
    # Deserialize with V2
    fory_v2 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v2.register_type(PersonV2)
    
    print("\nDeserializing V1 data with V2 schema...")
    try:
        person_v2 = fory_v2.deserialize(serialized_v1)
        print(f"Result V2: {person_v2}")
        print(f"Name: {person_v2.name}, Age: {person_v2.age}, Email: {person_v2.email}")
    except Exception as e:
        print(f"Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_schema_evolution()
