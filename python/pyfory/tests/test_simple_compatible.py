#!/usr/bin/env python3
"""
Simple test for compatible serializers
"""

import pytest
from dataclasses import dataclass
from typing import Optional
import pyfory
from pyfory.compatible_serializer_clean import CompatibleSerializer
from pyfory.java_compatible_serializer import CompatibleSerializer as JavaCompatibleSerializer


@dataclass
class Person:
    name: str
    age: int
    email: str


@dataclass
class PersonOptional:
    name: str
    age: int
    email: Optional[str] = None


def test_compatible_serializer_clean():
    """Test the clean compatible serializer"""
    person = Person(name="Alice", age=30, email="alice@test.com")
    
    fory_instance = pyfory.Fory()
    serializer = CompatibleSerializer(fory_instance, Person)
    
    # Test serialization
    buffer = pyfory.Buffer(bytearray())
    serializer.write(buffer, person)
    
    # Test deserialization
    buffer.reader_index = 0
    result = serializer.read(buffer)
    
    assert result.name == person.name
    assert result.age == person.age
    assert result.email == person.email


def test_java_compatible_serializer():
    """Test the Java compatible serializer"""
    person = Person(name="Bob", age=25, email="bob@test.com")
    
    fory_instance = pyfory.Fory()
    serializer = JavaCompatibleSerializer(fory_instance, Person)
    
    # Test serialization
    buffer = bytearray()
    serializer.write(buffer, person)
    
    # Test deserialization
    result = serializer.read(bytes(buffer))
    
    assert result.name == person.name
    assert result.age == person.age
    assert result.email == person.email


def test_both_serializers_round_trip():
    """Test that both serializers work independently"""
    person1 = Person(name="Charlie", age=35, email="charlie@test.com")
    person2 = PersonOptional(name="Dave", age=40, email="dave@test.com")
    
    fory_instance = pyfory.Fory()
    
    # Test clean serializer
    clean_serializer = CompatibleSerializer(fory_instance, Person)
    buffer1 = pyfory.Buffer(bytearray())
    clean_serializer.write(buffer1, person1)
    buffer1.reader_index = 0
    result1 = clean_serializer.read(buffer1)
    
    assert result1.name == person1.name
    assert result1.age == person1.age
    assert result1.email == person1.email
    
    # Test Java serializer
    java_serializer = JavaCompatibleSerializer(fory_instance, PersonOptional)
    buffer2 = bytearray()
    java_serializer.write(buffer2, person2)
    result2 = java_serializer.read(bytes(buffer2))
    
    assert result2.name == person2.name
    assert result2.age == person2.age
    assert result2.email == person2.email


if __name__ == "__main__":
    test_compatible_serializer_clean()
    test_java_compatible_serializer()
    test_both_serializers_round_trip()
    print("✅ All tests passed!")
