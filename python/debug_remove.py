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

def test_remove_field_scenario():
    """Debug V2 -> V1 scenario"""
    
    print("=== Test: V2 -> V1 (remove field) ===")
    
    # Serialize with V2
    fory_v2 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v2.register_type(PersonV2)
    
    person_v2 = PersonV2(name="Bob", age=35, email="bob@example.com")
    print(f"Original V2: {person_v2}")
    serialized_v2 = fory_v2.serialize(person_v2)
    print(f"Serialized V2: {len(serialized_v2)} bytes")
    
    # Deserialize with V1
    fory_v1 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v1.register_type(PersonV1)
    
    print("\nDeserializing V2 data with V1 schema...")
    try:
        person_v1 = fory_v1.deserialize(serialized_v2)
        print(f"Result V1: {person_v1}")
        print(f"Name: {person_v1.name}, Age: {person_v1.age}")
    except Exception as e:
        print(f"Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_remove_field_scenario()
