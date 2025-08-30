#!/usr/bin/env python3
"""
Debug Java serializer to understand the buffer underflow issue
"""

import sys
sys.path.insert(0, '/Users/bilibili/code/my/exp/meta/fory/python')

from dataclasses import dataclass
from typing import Optional
import pyfory
from pyfory.java_compatible_serializer import FieldResolver, CompatibleSerializer as JavaSerializer

@dataclass
class Person:
    name: str
    age: int
    email: Optional[str] = None

def debug_java_serializer():
    """Debug the Java serializer to understand the issue"""
    print("Debug Java Serializer")
    print("="*50)
    
    # Create test data
    person = Person(name="Bob", age=25, email="bob@example.com")
    print(f"Test person: {person}")
    
    # Create Fory instance and serializer
    fory_instance = pyfory.Fory()
    serializer = JavaSerializer(fory_instance, Person)
    
    # Debug field resolver
    print(f"Field resolver fields:")
    print(f"  embed_types_4_fields: {len(serializer.field_resolver.embed_types_4_fields)}")
    print(f"  embed_types_9_fields: {len(serializer.field_resolver.embed_types_9_fields)}")
    print(f"  embed_types_hash_fields: {len(serializer.field_resolver.embed_types_hash_fields)}")
    print(f"  separate_types_hash_fields: {len(serializer.field_resolver.separate_types_hash_fields)}")
    print(f"  end_tag: {serializer.field_resolver.end_tag}")
    
    # Create buffer for writing
    buffer = bytearray(1024)
    
    try:
        # Write to buffer
        initial_len = len(buffer)
        written_bytes = serializer.write(buffer, person)
        final_len = len(buffer)
        actual_bytes_written = final_len - initial_len
        print(f"✓ Write method returned: {written_bytes}")
        print(f"✓ Actually wrote {actual_bytes_written} bytes to buffer")
        
        # Show first 60 bytes of buffer content in hex
        print("\nBuffer content (first 60 bytes):")
        # Show from the beginning where data should be
        hex_content = ' '.join(f'{b:02x}' for b in buffer[1024-actual_bytes_written:1024+10])
        print("From end-51 to end+10:", hex_content)
        
        # Show buffer content where data actually is (the appended part)
        actual_data_start = len(buffer) - actual_bytes_written
        print(f"\nActual data at position {actual_data_start}:")
        hex_content = ' '.join(f'{b:02x}' for b in buffer[actual_data_start:actual_data_start+60])
        print(hex_content)
        
        # Try to read back
        # Fix: Extract the actual data from the end of buffer where it was appended
        actual_data_start = len(buffer) - actual_bytes_written
        actual_data = buffer[actual_data_start:]
        read_buffer = bytes(actual_data)  # Convert to bytes for reading
        print(f"\nReading from buffer of {len(read_buffer)} bytes...")
        
        result = serializer.read(read_buffer)
        print(f"✓ Successfully read: {result}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Show debug info about buffer position and content
        print(f"\nBuffer length: {len(buffer)}")
        print("Buffer content (hex):")
        hex_content = ' '.join(f'{b:02x}' for b in buffer[:60])
        print(hex_content)

if __name__ == "__main__":
    debug_java_serializer()
