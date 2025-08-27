import logging
from dataclasses import dataclass
import pyfory
from pyfory._fory import CompatibleMode
from pyfory.compatible_serializer import ClassInfo

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

def test_serialization_details():
    """Test serialization order details"""
    
    print("=== V2 Class Info at Serialization ===")
    fory_v2 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v2.register_type(PersonV2)
    
    # Get the serializer to check its class_info
    type_info = fory_v2.type_resolver._type_to_typeinfo[PersonV2]
    serializer = type_info.serializer
    
    print(f"V2 Serializer class_info.field_infos:")
    for field in serializer.class_info.field_infos:
        print(f"  {field.name}: encoded={field.encoded_field_info}, type={field.field_type}")
    
    print(f"V2 Embedded 4: {[f.name for f in serializer.class_info.embedded_4_fields]}")
    print(f"V2 Embedded 9: {[f.name for f in serializer.class_info.embedded_9_fields]}")
    
    print("\n=== V1 Class Info at Deserialization ===")
    fory_v1 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v1.register_type(PersonV1)
    
    type_info = fory_v1.type_resolver._type_to_typeinfo[PersonV1]
    serializer = type_info.serializer
    
    print(f"V1 Serializer class_info.field_infos:")
    for field in serializer.class_info.field_infos:
        print(f"  {field.name}: encoded={field.encoded_field_info}, type={field.field_type}")
    
    print(f"V1 Embedded 4: {[f.name for f in serializer.class_info.embedded_4_fields]}")
    print(f"V1 Embedded 9: {[f.name for f in serializer.class_info.embedded_9_fields]}")

if __name__ == "__main__":
    test_serialization_details()
