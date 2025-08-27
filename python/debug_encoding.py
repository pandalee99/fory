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

def debug_field_encoding():
    """Debug field encoding"""
    
    print("=== PersonV1 Field Encoding ===")
    class_info_v1 = ClassInfo(PersonV1)
    for field in class_info_v1.field_infos:
        print(f"Field: {field.name}, Type: {field.type_hint}, FieldType: {field.field_type}, Encoded: {field.encoded_field_info}")
    
    print(f"\nV1 Hash: {class_info_v1.schema_hash}")
    print(f"V1 Embedded 4: {[f.name for f in class_info_v1.embedded_4_fields]}")
    print(f"V1 Embedded 9: {[f.name for f in class_info_v1.embedded_9_fields]}")
    print(f"V1 Embedded Hash: {[f.name for f in class_info_v1.embedded_hash_fields]}")
    print(f"V1 Separate Hash: {[f.name for f in class_info_v1.separate_hash_fields]}")
    
    print("\n=== PersonV2 Field Encoding ===")
    class_info_v2 = ClassInfo(PersonV2)
    for field in class_info_v2.field_infos:
        print(f"Field: {field.name}, Type: {field.type_hint}, FieldType: {field.field_type}, Encoded: {field.encoded_field_info}")
    
    print(f"\nV2 Hash: {class_info_v2.schema_hash}")
    print(f"V2 Embedded 4: {[f.name for f in class_info_v2.embedded_4_fields]}")
    print(f"V2 Embedded 9: {[f.name for f in class_info_v2.embedded_9_fields]}")  
    print(f"V2 Embedded Hash: {[f.name for f in class_info_v2.embedded_hash_fields]}")
    print(f"V2 Separate Hash: {[f.name for f in class_info_v2.separate_hash_fields]}")

if __name__ == "__main__":
    debug_field_encoding()
