#!/usr/bin/env python3
"""Detailed debugging of JavaCompatibleSerializer write operations"""

from dataclasses import dataclass
from typing import Optional
import struct
import pyfory
from pyfory.java_compatible_serializer import FieldResolver, CompatibleSerializer as JavaSerializer

@dataclass
class Person:
    name: str
    age: int
    email: Optional[str] = None

def debug_buffer_operations():
    """Debug individual buffer write operations"""
    print("Debug Buffer Operations")
    print("="*50)
    
    # Create test data
    person = Person(name="Bob", age=25, email="bob@example.com")
    print(f"Test person: {person}")
    
    # Create Fory instance and serializer
    fory_instance = pyfory.Fory()
    serializer = JavaSerializer(fory_instance, Person)
    
    # Debug individual write operations
    test_buffer = bytearray(100)
    print(f"\nInitial buffer length: {len(test_buffer)}")
    print(f"Initial buffer content: {' '.join(f'{b:02x}' for b in test_buffer[:20])}")
    
    # Test basic buffer operations
    print("\nTesting basic buffer operations:")
    
    # Test _write_int32
    print("1. Testing _write_int32(123)...")
    initial_len = len(test_buffer)
    serializer._write_int32(test_buffer, 123)
    final_len = len(test_buffer)
    print(f"   Buffer grew by {final_len - initial_len} bytes")
    print(f"   Last 4 bytes: {' '.join(f'{b:02x}' for b in test_buffer[-4:])}")
    
    # Test _write_int64
    print("\n2. Testing _write_int64(456)...")
    initial_len = len(test_buffer)
    serializer._write_int64(test_buffer, 456)
    final_len = len(test_buffer)
    print(f"   Buffer grew by {final_len - initial_len} bytes")
    print(f"   Last 8 bytes: {' '.join(f'{b:02x}' for b in test_buffer[-8:])}")
    
    print(f"\nFinal test buffer length: {len(test_buffer)}")
    print(f"Final buffer content: {' '.join(f'{b:02x}' for b in test_buffer)}")

def debug_field_writing():
    """Debug field-by-field writing process"""
    print("\n" + "="*50)
    print("Debug Field Writing Process")
    print("="*50)
    
    # Create test data
    person = Person(name="Bob", age=25, email="bob@example.com")
    fory_instance = pyfory.Fory()
    serializer = JavaSerializer(fory_instance, Person)
    
    # Create a fresh buffer
    buffer = bytearray()
    print(f"Starting with empty buffer: {len(buffer)} bytes")
    
    # Manually execute write steps with logging
    print("\nWriting embed_types_4_fields...")
    for i, field_info in enumerate(serializer.field_resolver.embed_types_4_fields):
        print(f"  Field {i}: encoded_field_info={field_info.encoded_field_info}")
        print(f"  Field {i}: field_name='{field_info.name}'")
        
        before_len = len(buffer)
        serializer._write_int32(buffer, field_info.encoded_field_info)
        after_header = len(buffer)
        print(f"  Wrote header: {after_header - before_len} bytes")
        
        serializer._write_field_value(buffer, field_info, person)
        after_value = len(buffer)
        print(f"  Wrote value: {after_value - after_header} bytes")
        print(f"  Total so far: {len(buffer)} bytes")
        print(f"  Buffer content: {' '.join(f'{b:02x}' for b in buffer[-12:])}")
    
    print(f"\nBuffer after embed_types_4_fields: {len(buffer)} bytes")
    
    print("\nWriting embed_types_9_fields...")
    for i, field_info in enumerate(serializer.field_resolver.embed_types_9_fields):
        print(f"  Field {i}: encoded_field_info={field_info.encoded_field_info}")
        print(f"  Field {i}: field_name='{field_info.name}'")
        
        before_len = len(buffer)
        serializer._write_int64(buffer, field_info.encoded_field_info)
        after_header = len(buffer)
        print(f"  Wrote header: {after_header - before_len} bytes")
        
        serializer._write_field_value(buffer, field_info, person)
        after_value = len(buffer)
        print(f"  Wrote value: {after_value - after_header} bytes")
        print(f"  Total so far: {len(buffer)} bytes")
    
    print(f"\nBuffer after embed_types_9_fields: {len(buffer)} bytes")
    
    print("\nWriting separate_types_hash_fields...")
    for i, field_info in enumerate(serializer.field_resolver.separate_types_hash_fields):
        print(f"  Field {i}: encoded_field_info={field_info.encoded_field_info}")
        print(f"  Field {i}: field_name='{field_info.name}'")
        
        before_len = len(buffer)
        serializer._write_int64(buffer, field_info.encoded_field_info)
        after_header = len(buffer)
        print(f"  Wrote header: {after_header - before_len} bytes")
        
        serializer._write_field_value(buffer, field_info, person)
        after_value = len(buffer)
        print(f"  Wrote value: {after_value - after_header} bytes")
        print(f"  Total so far: {len(buffer)} bytes")
    
    print(f"\nWriting end tag: {serializer.field_resolver.end_tag}")
    before_len = len(buffer)
    serializer._write_int64(buffer, serializer.field_resolver.end_tag)
    after_len = len(buffer)
    print(f"Wrote end tag: {after_len - before_len} bytes")
    
    print(f"\nFinal buffer: {len(buffer)} bytes")
    print(f"Final buffer content: {' '.join(f'{b:02x}' for b in buffer)}")
    
    return buffer

if __name__ == "__main__":
    debug_buffer_operations()
    final_buffer = debug_field_writing()
    
    # Try to read it back
    print("\n" + "="*50)
    print("Testing Read Back")
    print("="*50)
    
    try:
        fory_instance = pyfory.Fory()
        serializer = JavaSerializer(fory_instance, Person)
        result = serializer.read(bytes(final_buffer))
        print(f"✓ Successfully read back: {result}")
    except Exception as e:
        print(f"✗ Read failed: {e}")
