#!/usr/bin/env python3
"""Debug field encoding to find the issue"""

import sys
sys.path.append("python")

from dataclasses import dataclass
import pyfory
from pyfory.java_compatible_serializer import FieldResolver, FieldInfo

@dataclass
class Person:
    name: str
    age: int
    email: str

def debug_field_encoding():
    print("Field Encoding Debug")
    print("=" * 30)
    
    # Create fory instance
    fory_instance = pyfory.Fory()
    
    # Create resolver
    resolver = FieldResolver(Person, fory_instance)
    
    print("Expected field encodings:")
    print(f"  age (embed_types_4): should be 38447113")
    print(f"  name (embed_types_9): should be 13307519051") 
    print(f"  email (separate_types_hash): should be 21341900997102275632")
    print()
    
    print("Actual field encodings:")
    for field in resolver.embed_types_4_fields:
        print(f"  {field.name}: {field.encoded_field_info} (0x{field.encoded_field_info:08x})")
        
    for field in resolver.embed_types_9_fields:
        print(f"  {field.name}: {field.encoded_field_info} (0x{field.encoded_field_info:016x})")
        
    for field in resolver.separate_types_hash_fields:
        print(f"  {field.name}: {field.encoded_field_info} (0x{field.encoded_field_info:016x})")
    
    print(f"End tag: {resolver.end_tag} (0x{resolver.end_tag:016x})")
    
    # Let's verify the email field hash
    print()
    print("Manual hash calculation for 'email':")
    
    # Using the same hash function as the resolver
    try:
        import mmh3
        hash_func = lambda s: mmh3.hash64(s.encode('utf-8'), 47)[0] & 0x7fffffffffffffff
        print("Using mmh3 hash")
    except ImportError:
        import hashlib
        def hash_func(s):
            h = hashlib.sha256(s.encode('utf-8')).hexdigest()
            return int(h[:16], 16) & 0x7fffffffffffffff
        print("Using hashlib fallback")
    
    email_hash = hash_func("email")
    print(f"Raw hash for 'email': {email_hash} (0x{email_hash:016x})")
    
    # Calculate encoded field info
    encoded = (email_hash << 2) | 0  # SEPARATE_TYPES_HASH_FLAG = 0
    print(f"Encoded field info: {encoded} (0x{encoded:016x})")
    
    if encoded == 21341900997102275632:
        print("✓ Hash calculation matches expected value")
    else:
        print("✗ Hash calculation doesn't match expected value")
        print(f"Expected: 21341900997102275632 (0x{21341900997102275632:016x})")
        print(f"Got: {encoded} (0x{encoded:016x})")

if __name__ == "__main__":
    debug_field_encoding()
