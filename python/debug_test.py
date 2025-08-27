import logging
import pytest
from dataclasses import dataclass
import pyfory
from pyfory._fory import CompatibleMode
from pyfory.compatible_serializer import CompatibleSerializer, MetaContext

# Set up debug logging
logging.basicConfig(level=logging.DEBUG)

@dataclass 
class PersonV1:
    """Version 1 of Person class with basic fields"""
    name: str
    age: int

def test_simple_serialization():
    """Simple debug test"""
    fory = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    fory.register_type(PersonV1)
    
    person = PersonV1(name="John", age=30)
    print(f"Original person: {person}")
    
    serialized = fory.serialize(person)
    print(f"Serialized bytes: {len(serialized)} bytes")
    
    deserialized = fory.deserialize(serialized)
    print(f"Deserialized person: {deserialized}")
    print(f"Has name attr: {hasattr(deserialized, 'name')}")
    print(f"Has age attr: {hasattr(deserialized, 'age')}")
    if hasattr(deserialized, 'name'):
        print(f"Name: {deserialized.name}")
    if hasattr(deserialized, 'age'):
        print(f"Age: {deserialized.age}")

if __name__ == "__main__":
    test_simple_serialization()
