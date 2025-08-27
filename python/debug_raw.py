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

def test_raw_serialization():
    """Test raw serialization to see what's written"""
    
    fory_v1 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory_v1.register_type(PersonV1)
    
    person_v1 = PersonV1(name="Alice", age=25)
    serialized = fory_v1.serialize(person_v1)
    
    print(f"Serialized data: {len(serialized)} bytes")
    print(f"Raw bytes: {serialized.hex()}")
    
    # Let's also look at the individual bytes in groups
    for i in range(0, len(serialized), 8):
        chunk = serialized[i:i+8]
        print(f"Bytes {i}-{i+7}: {chunk.hex()} ({list(chunk)})")

if __name__ == "__main__":
    test_raw_serialization()
