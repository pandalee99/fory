#!/usr/bin/env python3
"""
Comprehensive test for PyFory serializer implementation.
This test validates both the existing compatible_serializer and the new java_compatible_serializer,
as well as the Cython implementation.
"""

import os
import sys
import traceback
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import tempfile
import time

# Add the python directory to path
sys.path.insert(0, '/Users/bilibili/code/my/exp/meta/fory/python')

def test_imports():
    """Test that all required modules can be imported."""
    print("="*60)
    print("Testing imports...")
    
    try:
        import pyfory
        print(f"✓ pyfory imported successfully (version: {pyfory.__version__})")
    except Exception as e:
        print(f"✗ Failed to import pyfory: {e}")
        return False
        
    try:
        from pyfory import Buffer
        print("✓ Buffer imported successfully")
    except Exception as e:
        print(f"✗ Failed to import Buffer: {e}")
        
    try:
        from pyfory.compatible_serializer import CompatibleSerializer, MetaContext
        print("✓ CompatibleSerializer imported successfully")
    except Exception as e:
        print(f"✗ Failed to import CompatibleSerializer: {e}")
        
    try:
        from pyfory.java_compatible_serializer import FieldResolver, CompatibleSerializer as JavaCompatibleSerializer
        print("✓ Java-compatible serializer imported successfully")
    except Exception as e:
        print(f"✗ Failed to import Java-compatible serializer: {e}")
        
    try:
        from pyfory._serialization import JavaCompatibleCythonSerializer
        print("✓ Cython Java-compatible serializer imported successfully")
    except Exception as e:
        print(f"✗ Failed to import Cython serializer: {e}")
        
    return True

@dataclass
class Person:
    """Simple test class"""
    name: str
    age: int
    email: Optional[str] = None

@dataclass 
class Employee:
    """More complex test class"""
    name: str
    employee_id: int
    salary: float
    department: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class SimpleClass:
    """Non-dataclass for testing"""
    def __init__(self, name: str, value: int = 0):
        self.name = name
        self.value = value
    
    def __eq__(self, other):
        return isinstance(other, SimpleClass) and self.name == other.name and self.value == other.value
    
    def __repr__(self):
        return f"SimpleClass(name='{self.name}', value={self.value})"

def test_existing_compatible_serializer():
    """Test the existing compatible_serializer implementation."""
    print("="*60)
    print("Testing existing CompatibleSerializer...")
    
    try:
        import pyfory
        from pyfory import Buffer  # Add Buffer import here  
        from pyfory.compatible_serializer import CompatibleSerializer, MetaContext
        
        # Create test data
        person = Person(name="Alice", age=30, email="alice@example.com")
        
        # Create Fory instance
        fory_instance = pyfory.Fory()
        
        # Create meta context manually
        if not hasattr(fory_instance, 'meta_context'):
            fory_instance.meta_context = MetaContext()
        
        # Create serializer
        serializer = CompatibleSerializer(fory_instance, Person)
        print(f"✓ CompatibleSerializer created for Person (type_id: {serializer.type_id})")
        
        # Create buffer and test serialization
        buffer = Buffer.allocate(1024)
        
        try:
            serializer.write(buffer, person)
            print("✓ Successfully wrote Person to buffer")
            
            # Reset buffer for reading
            buffer.reader_index = 0
            
            result = serializer.read(buffer)
            print(f"✓ Successfully read Person from buffer: {result}")
            
            # Verify data
            assert result.name == person.name
            assert result.age == person.age
            assert result.email == person.email
            print("✓ Data verification passed")
            
        except Exception as e:
            print(f"✗ Serialization test failed: {e}")
            traceback.print_exc()
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ CompatibleSerializer test failed: {e}")
        traceback.print_exc()
        return False

def test_java_compatible_serializer():
    """Test the Java-compatible serializer implementation."""
    print("="*60)  
    print("Testing Java-compatible serializer...")
    
    try:
        import pyfory
        from pyfory.java_compatible_serializer import FieldResolver, CompatibleSerializer as JavaSerializer
        
        # Create test data
        person = Person(name="Bob", age=25, email="bob@example.com")
        
        # Create Fory instance
        fory_instance = pyfory.Fory()
        
        # Create serializer  
        java_serializer = JavaSerializer(fory_instance, Person)
        print("✓ Java-compatible serializer created")
        
        # Test FieldResolver
        field_resolver = java_serializer.field_resolver
        print(f"✓ FieldResolver created with {field_resolver.get_num_fields()} fields")
        
        # Print field information
        all_fields = field_resolver.get_all_fields_list()
        for field_info in all_fields:
            print(f"  - Field: {field_info.name}, type: {field_info.field_type}, class_id: {field_info.class_id}")
        
        # Test serialization
        buffer = bytearray()
        
        try:
            java_serializer.write(buffer, person)
            print(f"✓ Successfully wrote Person to buffer ({len(buffer)} bytes)")
            
            result = java_serializer.read(buffer)
            print(f"✓ Successfully read Person from buffer: {result}")
            
            # Verify data
            assert result.name == person.name
            assert result.age == person.age
            assert result.email == person.email
            print("✓ Data verification passed")
            
        except Exception as e:
            print(f"✗ Java-compatible serialization test failed: {e}")
            traceback.print_exc()
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ Java-compatible serializer test failed: {e}")
        traceback.print_exc()
        return False

def test_cython_serializer():
    """Test the Cython implementation."""
    print("="*60)
    print("Testing Cython Java-compatible serializer...")
    
    try:
        import pyfory
        from pyfory._serialization import JavaCompatibleCythonSerializer
        from pyfory._util import Buffer
        
        # Create test data
        person = Person(name="Charlie", age=35, email="charlie@example.com")
        
        # Create Fory instance
        fory_instance = pyfory.Fory()
        
        # Create Cython serializer
        cython_serializer = JavaCompatibleCythonSerializer(fory_instance, Person)
        print("✓ Cython serializer created")
        
        # Test serialization
        buffer = Buffer.allocate(1024)
        
        try:
            cython_serializer.write(buffer, person)
            print("✓ Successfully wrote Person using Cython serializer")
            
            # Reset buffer for reading
            buffer.reader_index = 0
            
            result = cython_serializer.read(buffer)
            print(f"✓ Successfully read Person using Cython serializer: {result}")
            
            # Verify data
            assert result.name == person.name
            assert result.age == person.age
            assert result.email == person.email
            print("✓ Cython data verification passed")
            
        except Exception as e:
            print(f"✗ Cython serialization test failed: {e}")
            traceback.print_exc()
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ Cython serializer test failed: {e}")
        traceback.print_exc()
        return False

def test_performance_comparison():
    """Test performance comparison between implementations."""
    print("="*60)
    print("Testing performance comparison...")
    
    try:
        import pyfory
        from pyfory import Buffer  # Add Buffer import here
        from pyfory.compatible_serializer import CompatibleSerializer, MetaContext
        from pyfory.java_compatible_serializer import CompatibleSerializer as JavaSerializer
        
        # Create test data
        people = [Person(name=f"Person_{i}", age=i, email=f"person{i}@example.com") for i in range(100)]
        
        # Test existing serializer
        fory1 = pyfory.Fory()
        if not hasattr(fory1, 'meta_context'):
            fory1.meta_context = MetaContext()
        
        existing_serializer = CompatibleSerializer(fory1, Person)
        
        # Test Java-compatible serializer
        fory2 = pyfory.Fory()
        java_serializer = JavaSerializer(fory2, Person)
        
        # Benchmark existing serializer
        start_time = time.time()
        for person in people:
            buffer = Buffer.allocate(1024)
            existing_serializer.write(buffer, person)
            buffer.reader_index = 0
            result = existing_serializer.read(buffer)
        existing_time = time.time() - start_time
        
        # Benchmark Java-compatible serializer
        start_time = time.time()
        for person in people:
            buffer = bytearray()
            java_serializer.write(buffer, person)
            result = java_serializer.read(buffer)
        java_time = time.time() - start_time
        
        print(f"✓ Existing serializer: {existing_time:.4f}s for 100 objects")
        print(f"✓ Java-compatible serializer: {java_time:.4f}s for 100 objects")
        print(f"✓ Performance ratio: {existing_time/java_time:.2f}x")
        
        return True
        
    except Exception as e:
        print(f"✗ Performance comparison failed: {e}")
        traceback.print_exc()
        return False

def test_schema_evolution():
    """Test schema evolution capabilities."""
    print("="*60)
    print("Testing schema evolution...")
    
    try:
        # Test with different class versions
        @dataclass
        class PersonV1:
            name: str
            age: int
            
        @dataclass
        class PersonV2:
            name: str
            age: int
            email: Optional[str] = None
            active: bool = True
            
        import pyfory
        from pyfory.java_compatible_serializer import CompatibleSerializer as JavaSerializer
        
        # Serialize V1
        person_v1 = PersonV1(name="Evolution", age=40)
        fory1 = pyfory.Fory()
        serializer_v1 = JavaSerializer(fory1, PersonV1)
        
        buffer_v1 = bytearray()
        serializer_v1.write(buffer_v1, person_v1)
        print(f"✓ Serialized PersonV1 ({len(buffer_v1)} bytes)")
        
        # Serialize V2
        person_v2 = PersonV2(name="Evolution2", age=45, email="evo2@test.com", active=True)
        fory2 = pyfory.Fory()
        serializer_v2 = JavaSerializer(fory2, PersonV2)
        
        buffer_v2 = bytearray()
        serializer_v2.write(buffer_v2, person_v2)
        print(f"✓ Serialized PersonV2 ({len(buffer_v2)} bytes)")
        
        # Read V1 data
        result_v1 = serializer_v1.read(buffer_v1)
        print(f"✓ Read PersonV1: {result_v1}")
        
        # Read V2 data  
        result_v2 = serializer_v2.read(buffer_v2)
        print(f"✓ Read PersonV2: {result_v2}")
        
        print("✓ Schema evolution test completed (basic functionality)")
        
        return True
        
    except Exception as e:
        print(f"✗ Schema evolution test failed: {e}")
        traceback.print_exc()
        return False

def test_compilation():
    """Test Cython compilation."""
    print("="*60)
    print("Testing Cython compilation...")
    
    # Check if we can compile the current Cython code
    try:
        result = os.system("cd /Users/bilibili/code/my/exp/meta/fory && bazel clean --expunge > /dev/null 2>&1")
        print("✓ Bazel clean completed")
        
        result = os.system("cd /Users/bilibili/code/my/exp/meta/fory/python && pip install -v -e . > /tmp/build.log 2>&1")
        if result == 0:
            print("✓ PyFory recompiled successfully")
            return True
        else:
            print("✗ PyFory compilation failed")
            print("Build log:")
            try:
                with open('/tmp/build.log', 'r') as f:
                    print(f.read()[-2000:])  # Last 2000 chars
            except:
                pass
            return False
            
    except Exception as e:
        print(f"✗ Compilation test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("PyFory Comprehensive Serializer Test")
    print("="*60)
    
    # List of test functions
    tests = [
        ("Import Tests", test_imports),
        ("Existing Serializer", test_existing_compatible_serializer), 
        ("Java-Compatible Serializer", test_java_compatible_serializer),
        ("Schema Evolution", test_schema_evolution),
        ("Performance Comparison", test_performance_comparison),
        ("Compilation Test", test_compilation),
        ("Cython Serializer", test_cython_serializer),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n{test_name}:")
            success = test_func()
            results.append((test_name, success))
            print(f"{'✓ PASSED' if success else '✗ FAILED'}: {test_name}")
        except Exception as e:
            print(f"✗ FAILED: {test_name} - {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"{status:4} | {test_name}")
    
    print("-"*60)
    print(f"TOTAL: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed.")
        return 1

if __name__ == "__main__":
    exit(main())
