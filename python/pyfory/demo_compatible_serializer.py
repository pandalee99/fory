#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""
Demonstration of Python Fury CompatibleSerializer for schema evolution.

This script shows how the CompatibleSerializer provides forward and backward
compatibility by handling schema changes between serialization and deserialization.
"""

import sys
import os
from dataclasses import dataclass
from typing import List

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(__file__))

try:
    import pyfory
    from pyfory._fory import CompatibleMode
    from pyfory.compatible_serializer import CompatibleSerializer, MetaContext
except ImportError as e:
    print(f"Error importing pyfory modules: {e}")
    print("Please ensure pyfory is properly installed and PYTHONPATH is set correctly.")
    sys.exit(1)


@dataclass
class UserV1:
    """Version 1: Basic user with name and age"""
    name: str
    age: int


@dataclass  
class UserV2:
    """Version 2: User with additional email field"""
    name: str
    age: int
    email: str = "noemail@example.com"


@dataclass
class UserV3:
    """Version 3: User with email and city, but age removed"""
    name: str
    email: str = "noemail@example.com" 
    city: str = "Unknown"


def demo_basic_compatibility():
    """Demonstrate basic CompatibleSerializer functionality"""
    print("=== Demo: Basic CompatibleSerializer ===")
    
    try:
        # Create Fury instance with compatible mode
        fory = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
        print(f"Created Fury instance with compatible_mode={fory.compatible_mode}")
        
        # Register the user type
        fory.register_type(UserV1)
        print("Registered UserV1 type")
        
        # Create and serialize a user
        user = UserV1(name="Alice", age=30)
        print(f"Original user: {user}")
        
        serialized = fory.serialize(user)
        print(f"Serialized data size: {len(serialized)} bytes")
        
        # Deserialize and verify
        deserialized = fory.deserialize(serialized)
        print(f"Deserialized user: {deserialized}")
        
        assert deserialized.name == user.name
        assert deserialized.age == user.age
        print("✓ Basic serialization/deserialization successful!")
        
    except Exception as e:
        print(f"✗ Error in basic compatibility demo: {e}")
        import traceback
        traceback.print_exc()


def demo_forward_compatibility():
    """Demonstrate forward compatibility - old data, new schema"""
    print("\n=== Demo: Forward Compatibility (Old Data → New Schema) ===")
    
    try:
        # Step 1: Serialize with V1 schema (older version)
        fory_v1 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
        fory_v1.register_type(UserV1)
        
        user_v1 = UserV1(name="Bob", age=25)
        print(f"V1 User: {user_v1}")
        
        serialized_data = fory_v1.serialize(user_v1)
        print(f"Serialized V1 data: {len(serialized_data)} bytes")
        
        # Step 2: Deserialize with V2 schema (newer version with additional field)
        fory_v2 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE) 
        fory_v2.register_type(UserV2)
        
        user_v2 = fory_v2.deserialize(serialized_data)
        print(f"V2 User: {user_v2}")
        
        # Verify old fields preserved and new field has default value
        assert user_v2.name == "Bob"
        assert user_v2.age == 25
        assert user_v2.email == "noemail@example.com"  # Default value
        print("✓ Forward compatibility successful!")
        
    except Exception as e:
        print(f"✗ Error in forward compatibility demo: {e}")
        import traceback
        traceback.print_exc()


def demo_backward_compatibility():
    """Demonstrate backward compatibility - new data, old schema"""
    print("\n=== Demo: Backward Compatibility (New Data → Old Schema) ===")
    
    try:
        # Step 1: Serialize with V2 schema (newer version)
        fory_v2 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
        fory_v2.register_type(UserV2)
        
        user_v2 = UserV2(name="Charlie", age=35, email="charlie@example.com")
        print(f"V2 User: {user_v2}")
        
        serialized_data = fory_v2.serialize(user_v2)
        print(f"Serialized V2 data: {len(serialized_data)} bytes")
        
        # Step 2: Deserialize with V1 schema (older version)
        fory_v1 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
        fory_v1.register_type(UserV1)
        
        user_v1 = fory_v1.deserialize(serialized_data) 
        print(f"V1 User: {user_v1}")
        
        # Verify common fields preserved, extra fields ignored
        assert user_v1.name == "Charlie"
        assert user_v1.age == 35
        print("✓ Backward compatibility successful!")
        
    except Exception as e:
        print(f"✗ Error in backward compatibility demo: {e}")
        import traceback
        traceback.print_exc()


def demo_complex_evolution():
    """Demonstrate complex schema evolution with field changes"""
    print("\n=== Demo: Complex Schema Evolution ===")
    
    try:
        # Step 1: Serialize with V2 schema 
        fory_v2 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
        fory_v2.register_type(UserV2)
        
        user_v2 = UserV2(name="Diana", age=28, email="diana@example.com")
        print(f"V2 User: {user_v2}")
        
        serialized_data = fory_v2.serialize(user_v2)
        print(f"Serialized V2 data: {len(serialized_data)} bytes")
        
        # Step 2: Deserialize with V3 schema (age removed, city added)
        fory_v3 = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
        fory_v3.register_type(UserV3)
        
        user_v3 = fory_v3.deserialize(serialized_data)
        print(f"V3 User: {user_v3}")
        
        # Verify field evolution
        assert user_v3.name == "Diana"  # Preserved
        assert user_v3.email == "diana@example.com"  # Preserved 
        assert user_v3.city == "Unknown"  # New field with default
        print("✓ Complex schema evolution successful!")
        
    except Exception as e:
        print(f"✗ Error in complex evolution demo: {e}")
        import traceback
        traceback.print_exc()


def demo_meta_context():
    """Demonstrate MetaContext functionality"""
    print("\n=== Demo: MetaContext Usage ===")
    
    try:
        # Create meta context
        meta_context = MetaContext()
        print("Created MetaContext")
        
        # Register class definition
        type_id = meta_context.register_class_def(
            UserV1,
            ["name", "age"], 
            {"name": str, "age": int}
        )
        print(f"Registered UserV1 with type_id: {type_id}")
        
        # Retrieve class definition
        class_def = meta_context.get_class_def(type_id)
        print(f"Retrieved ClassDef: {class_def}")
        
        assert class_def.type_cls == UserV1
        assert class_def.field_names == ["name", "age"]
        print("✓ MetaContext functionality verified!")
        
    except Exception as e:
        print(f"✗ Error in meta context demo: {e}")
        import traceback
        traceback.print_exc()


def compare_modes():
    """Compare compatible mode vs schema consistent mode"""
    print("\n=== Demo: Mode Comparison ===")
    
    try:
        user = UserV1(name="Eve", age=22)
        
        # Serialize in schema consistent mode
        fory_consistent = pyfory.Fory(compatible_mode=CompatibleMode.SCHEMA_CONSISTENT)
        fory_consistent.register_type(UserV1)
        data_consistent = fory_consistent.serialize(user)
        
        # Serialize in compatible mode
        fory_compatible = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
        fory_compatible.register_type(UserV1)
        data_compatible = fory_compatible.serialize(user)
        
        print(f"Schema consistent mode: {len(data_consistent)} bytes")
        print(f"Compatible mode: {len(data_compatible)} bytes")
        print(f"Overhead: {len(data_compatible) - len(data_consistent)} bytes "
              f"({((len(data_compatible) - len(data_consistent)) / len(data_consistent) * 100):.1f}%)")
        
        # Both should deserialize correctly
        user_consistent = fory_consistent.deserialize(data_consistent)
        user_compatible = fory_compatible.deserialize(data_compatible)
        
        assert user_consistent.name == user_compatible.name == "Eve"
        assert user_consistent.age == user_compatible.age == 22
        print("✓ Both modes work correctly!")
        
    except Exception as e:
        print(f"✗ Error in mode comparison: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all demonstrations"""
    print("Python Fury CompatibleSerializer Demonstration")
    print("=" * 50)
    
    # Check if we can import required modules
    try:
        demo_basic_compatibility()
        demo_forward_compatibility() 
        demo_backward_compatibility()
        demo_complex_evolution()
        demo_meta_context()
        compare_modes()
        
    except Exception as e:
        print(f"\nUnexpected error during demonstration: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 50)
    print("All demonstrations completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
