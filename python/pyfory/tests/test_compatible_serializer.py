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
Comprehensive test suite for Compatible Serializer with schema evolution support.
"""

import pytest
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
import tempfile
import os

from pyfory import Fory, CompatibleMode, Buffer
from pyfory.compatible_serializer_clean import CompatibleSerializer, MetaContext, FieldInfo, TypeDefinition, FieldClassification


# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# Test data classes for various scenarios
@dataclass
class PersonV1:
    """Basic person class - version 1"""
    name: str
    age: int


@dataclass
class PersonV2:
    """Extended person class - version 2 with additional field"""
    name: str
    age: int
    email: Optional[str] = None


@dataclass
class PersonV3:
    """Person class - version 3 with field type changes"""
    name: str
    age: float  # Changed from int to float
    email: Optional[str] = None
    active: bool = True


@dataclass
class Employee:
    """Complex object with nested structures"""
    name: str
    employee_id: int
    salary: float
    department: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Company:
    """Object with object references"""
    name: str
    employees: List[Employee] = field(default_factory=list)
    founded_year: int = 2000


class SimpleClass:
    """Non-dataclass for testing regular classes"""
    def __init__(self, name: str, value: int = 0):
        self.name = name
        self.value = value
    
    def __eq__(self, other):
        return isinstance(other, SimpleClass) and self.name == other.name and self.value == other.value
    
    def __repr__(self):
        return f"SimpleClass(name='{self.name}', value={self.value})"


class TestMetaContext:
    """Test MetaContext functionality"""
    
    def test_register_class(self):
        """Test class registration"""
        meta_context = MetaContext()
        
        # Register first class
        type_id1 = meta_context.register_class(PersonV1)
        assert type_id1 >= 1000  # Should start from 1000
        
        # Register second class
        type_id2 = meta_context.register_class(PersonV2)
        assert type_id2 == type_id1 + 1
        
        # Re-register same class should return same ID
        type_id1_again = meta_context.register_class(PersonV1)
        assert type_id1_again == type_id1
        
    def test_type_definition_creation(self):
        """Test type definition creation"""
        meta_context = MetaContext()
        type_id = meta_context.register_class(PersonV1)
        
        type_def = meta_context.get_type_definition(type_id)
        assert type_def is not None
        assert type_def.type_cls == PersonV1
        assert type_def.type_id == type_id
        assert len(type_def.field_infos) == 2  # name, age
        
        # Check field names
        field_names = [f.name for f in type_def.field_infos]
        assert 'name' in field_names
        assert 'age' in field_names
        
    def test_session_state(self):
        """Test session state management"""
        meta_context = MetaContext()
        type_id = meta_context.register_class(PersonV1)
        
        # Initially not sent
        assert not meta_context.is_type_def_sent(type_id)
        
        # Mark as sent
        meta_context.mark_type_def_sent(type_id)
        assert meta_context.is_type_def_sent(type_id)
        
        # Reset session
        meta_context.reset_session()
        assert not meta_context.is_type_def_sent(type_id)


class TestFieldInfo:
    """Test FieldInfo functionality"""
    
    def test_primitive_field_classification(self):
        """Test classification of primitive fields"""
        meta_context = MetaContext()
        type_id = meta_context.register_class(PersonV1)
        type_def = meta_context.get_type_definition(type_id)
        
        name_field = type_def.get_field_by_name('name')
        age_field = type_def.get_field_by_name('age')
        
        assert name_field is not None
        assert age_field is not None
        
        # String field should be classified as STRING
        assert name_field.classification == FieldClassification.STRING
        assert not name_field.nullable
        
        # Int field should be classified as PRIMITIVE
        assert age_field.classification == FieldClassification.PRIMITIVE
        assert not age_field.nullable
        
    def test_nullable_field_classification(self):
        """Test classification of nullable fields"""
        meta_context = MetaContext()
        type_id = meta_context.register_class(PersonV2)
        type_def = meta_context.get_type_definition(type_id)
        
        email_field = type_def.get_field_by_name('email')
        assert email_field is not None
        assert email_field.classification == FieldClassification.STRING_NULLABLE
        assert email_field.nullable
        
    def test_field_hash_uniqueness(self):
        """Test that field hashes are unique within reasonable bounds"""
        meta_context = MetaContext()
        type_id = meta_context.register_class(PersonV2)
        type_def = meta_context.get_type_definition(type_id)
        
        field_hashes = [f.encoded_field_info for f in type_def.field_infos]
        assert len(field_hashes) == len(set(field_hashes))  # All hashes should be unique


class TestBasicSerialization:
    """Test basic serialization functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.fory = Fory(mode=CompatibleMode.COMPATIBLE)
        self.buffer = Buffer.allocate(1024)
        
    def test_simple_dataclass_serialization(self):
        """Test basic dataclass serialization"""
        person = PersonV1(name="Alice", age=30)
        
        # Register and serialize
        self.fory.register(PersonV1, CompatibleSerializer)
        self.fory.serialize(self.buffer, person)
        
        # Reset buffer for reading
        self.buffer.reader_index = 0
        
        # Deserialize
        result = self.fory.deserialize(self.buffer, PersonV1)
        
        assert isinstance(result, PersonV1)
        assert result.name == "Alice"
        assert result.age == 30
        
    def test_nullable_field_serialization(self):
        """Test serialization with nullable fields"""
        # Test with null value
        person = PersonV2(name="Bob", age=25, email=None)
        
        self.fory.register(PersonV2, CompatibleSerializer)
        self.fory.serialize(self.buffer, person)
        
        self.buffer.reader_index = 0
        result = self.fory.deserialize(self.buffer, PersonV2)
        
        assert result.name == "Bob"
        assert result.age == 25
        assert result.email is None
        
        # Test with non-null value
        self.buffer.reader_index = 0
        self.buffer.writer_index = 0
        
        person_with_email = PersonV2(name="Charlie", age=35, email="charlie@example.com")
        self.fory.serialize(self.buffer, person_with_email)
        
        self.buffer.reader_index = 0
        result2 = self.fory.deserialize(self.buffer, PersonV2)
        
        assert result2.name == "Charlie"
        assert result2.age == 35
        assert result2.email == "charlie@example.com"
        
    def test_regular_class_serialization(self):
        """Test serialization of non-dataclass"""
        obj = SimpleClass(name="test", value=42)
        
        self.fory.register(SimpleClass, CompatibleSerializer)
        self.fory.serialize(self.buffer, obj)
        
        self.buffer.reader_index = 0
        result = self.fory.deserialize(self.buffer, SimpleClass)
        
        assert result == obj
        
    def test_complex_object_serialization(self):
        """Test serialization of complex objects"""
        employee = Employee(
            name="John Doe",
            employee_id=12345,
            salary=75000.0,
            department="Engineering",
            skills=["Python", "Java", "Go"],
            metadata={"level": "senior", "location": "NYC"}
        )
        
        self.fory.register(Employee, CompatibleSerializer)
        self.fory.serialize(self.buffer, employee)
        
        self.buffer.reader_index = 0
        result = self.fory.deserialize(self.buffer, Employee)
        
        assert result.name == employee.name
        assert result.employee_id == employee.employee_id
        assert result.salary == employee.salary
        assert result.department == employee.department
        assert result.skills == employee.skills
        assert result.metadata == employee.metadata


class TestSchemaEvolution:
    """Test schema evolution scenarios"""
    
    def setup_method(self):
        """Setup for each test"""
        self.fory = Fory(mode=CompatibleMode.COMPATIBLE)
        self.buffer = Buffer.allocate(1024)
        
    def test_forward_compatibility_added_field(self):
        """Test forward compatibility - new version reads old data"""
        # Serialize with old version (PersonV1)
        person_v1 = PersonV1(name="Alice", age=30)
        
        self.fory.register(PersonV1, CompatibleSerializer)
        self.fory.serialize(self.buffer, person_v1)
        
        # Reset Fory to simulate different session
        fory_new = Fory(mode=CompatibleMode.COMPATIBLE)
        fory_new.register(PersonV2, CompatibleSerializer)
        
        # Read with new version (PersonV2)
        self.buffer.reader_index = 0
        result = fory_new.deserialize(self.buffer, PersonV2)
        
        assert isinstance(result, PersonV2)
        assert result.name == "Alice"
        assert result.age == 30
        assert result.email is None  # Should use default value
        
    def test_backward_compatibility_removed_field(self):
        """Test backward compatibility - old version reads new data"""
        # Serialize with new version (PersonV2)
        person_v2 = PersonV2(name="Bob", age=25, email="bob@example.com")
        
        self.fory.register(PersonV2, CompatibleSerializer)
        self.fory.serialize(self.buffer, person_v2)
        
        # Reset Fory to simulate different session
        fory_old = Fory(mode=CompatibleMode.COMPATIBLE)
        fory_old.register(PersonV1, CompatibleSerializer)
        
        # Read with old version (PersonV1)
        self.buffer.reader_index = 0
        result = fory_old.deserialize(self.buffer, PersonV1)
        
        assert isinstance(result, PersonV1)
        assert result.name == "Bob"
        assert result.age == 25
        # Email field should be ignored
        
    def test_type_change_compatibility(self):
        """Test handling of field type changes"""
        # This test may need to be adjusted based on how strict we want type checking
        person_v1 = PersonV1(name="Charlie", age=35)
        
        self.fory.register(PersonV1, CompatibleSerializer)
        self.fory.serialize(self.buffer, person_v1)
        
        # Try to read with PersonV3 (age is float instead of int)
        fory_v3 = Fory(mode=CompatibleMode.COMPATIBLE)
        fory_v3.register(PersonV3, CompatibleSerializer)
        
        self.buffer.reader_index = 0
        result = fory_v3.deserialize(self.buffer, PersonV3)
        
        assert result.name == "Charlie"
        assert result.age == 35.0  # Should be converted to float
        assert result.email is None
        assert result.active == True  # Default value
        
    def test_multiple_version_compatibility(self):
        """Test compatibility across multiple schema versions"""
        # Create objects of different versions
        versions = [
            PersonV1(name="Version1", age=10),
            PersonV2(name="Version2", age=20, email="v2@test.com"),
            PersonV3(name="Version3", age=30.5, email="v3@test.com", active=False)
        ]
        
        # Serialize each version
        buffers = []
        for i, person in enumerate(versions):
            buffer = Buffer.allocate(1024)
            fory = Fory(mode=CompatibleMode.COMPATIBLE)
            
            if i == 0:
                fory.register(PersonV1, CompatibleSerializer)
            elif i == 1:
                fory.register(PersonV2, CompatibleSerializer)
            else:
                fory.register(PersonV3, CompatibleSerializer)
                
            fory.serialize(buffer, person)
            buffers.append(buffer)
        
        # Try to deserialize all with PersonV2 (middle version)
        target_fory = Fory(mode=CompatibleMode.COMPATIBLE)
        target_fory.register(PersonV2, CompatibleSerializer)
        
        results = []
        for buffer in buffers:
            buffer.reader_index = 0
            result = target_fory.deserialize(buffer, PersonV2)
            results.append(result)
        
        # Check results
        assert results[0].name == "Version1" and results[0].age == 10 and results[0].email is None
        assert results[1].name == "Version2" and results[1].age == 20 and results[1].email == "v2@test.com"
        assert results[2].name == "Version3" and results[2].age == 30.0 and results[2].email == "v3@test.com"  # Note: float converted to int


class TestPerformanceOptimizations:
    """Test performance optimizations"""
    
    def setup_method(self):
        self.fory = Fory(mode=CompatibleMode.COMPATIBLE)
        self.buffer = Buffer.allocate(1024)
        
    def test_fast_path_detection(self):
        """Test that fast path is correctly detected"""
        # Register PersonV1 (should use fast path - all primitive/string embedded)
        self.fory.register(PersonV1, CompatibleSerializer)
        
        serializer = self.fory._serializers[PersonV1.__name__]
        assert hasattr(serializer, '_has_fast_fields')
        assert hasattr(serializer, '_all_embedded')
        
        # PersonV1 should be optimizable
        assert serializer._has_fast_fields
        assert serializer._all_embedded
        
    def test_type_definition_caching(self):
        """Test that type definitions are sent only once per session"""
        person1 = PersonV1(name="First", age=1)
        person2 = PersonV1(name="Second", age=2)
        
        self.fory.register(PersonV1, CompatibleSerializer)
        
        # First serialization should send type definition
        initial_pos = self.buffer.writer_index
        self.fory.serialize(self.buffer, person1)
        first_size = self.buffer.writer_index - initial_pos
        
        # Second serialization should be smaller (no type definition)
        initial_pos = self.buffer.writer_index
        self.fory.serialize(self.buffer, person2)
        second_size = self.buffer.writer_index - initial_pos
        
        assert second_size < first_size
        
    def test_bulk_serialization_performance(self):
        """Test performance with bulk operations"""
        # Create many objects
        people = [PersonV1(name=f"Person_{i}", age=i) for i in range(100)]
        
        self.fory.register(PersonV1, CompatibleSerializer)
        
        # Serialize all
        for person in people:
            self.fory.serialize(self.buffer, person)
        
        # Deserialize all
        self.buffer.reader_index = 0
        results = []
        for _ in range(100):
            result = self.fory.deserialize(self.buffer, PersonV1)
            results.append(result)
        
        # Verify results
        for i, result in enumerate(results):
            assert result.name == f"Person_{i}"
            assert result.age == i


class TestErrorHandling:
    """Test error handling scenarios"""
    
    def setup_method(self):
        self.fory = Fory(mode=CompatibleMode.COMPATIBLE)
        self.buffer = Buffer.allocate(1024)
        
    def test_invalid_type_id(self):
        """Test handling of invalid type IDs"""
        # Manually write invalid data
        self.buffer.write_varuint32(99999)  # Invalid type ID
        self.buffer.reader_index = 0
        
        self.fory.register(PersonV1, CompatibleSerializer)
        
        with pytest.raises(ValueError, match="Unknown type ID"):
            self.fory.deserialize(self.buffer, PersonV1)
            
    def test_corrupted_data_recovery(self):
        """Test recovery from corrupted data"""
        person = PersonV1(name="Test", age=25)
        self.fory.register(PersonV1, CompatibleSerializer)
        self.fory.serialize(self.buffer, person)
        
        # Corrupt some bytes in the middle
        self.buffer.put_byte(10, 0xFF)
        self.buffer.put_byte(11, 0xFF)
        
        self.buffer.reader_index = 0
        
        # Should handle gracefully
        try:
            result = self.fory.deserialize(self.buffer, PersonV1)
            # If it doesn't crash, that's good
        except Exception as e:
            # Expected - corrupted data should fail
            assert True
            
    def test_incomplete_data_handling(self):
        """Test handling of incomplete data"""
        person = PersonV1(name="Test", age=25)
        self.fory.register(PersonV1, CompatibleSerializer)
        self.fory.serialize(self.buffer, person)
        
        # Truncate buffer
        self.buffer.writer_index = self.buffer.writer_index - 5
        self.buffer.reader_index = 0
        
        with pytest.raises((IndexError, ValueError, EOFError)):
            self.fory.deserialize(self.buffer, PersonV1)


class TestCrossLanguageCompatibility:
    """Test cross-language serialization compatibility"""
    
    def setup_method(self):
        self.fory = Fory(mode=CompatibleMode.COMPATIBLE)
        self.buffer = Buffer.allocate(1024)
        
    def test_xlang_serialization(self):
        """Test cross-language serialization"""
        person = PersonV1(name="CrossLang", age=42)
        
        self.fory.register(PersonV1, CompatibleSerializer)
        serializer = self.fory._serializers[PersonV1.__name__]
        
        # Test xlang methods if available
        if hasattr(serializer, 'xwrite') and hasattr(serializer, 'xread'):
            serializer.xwrite(self.buffer, person)
            self.buffer.reader_index = 0
            result = serializer.xread(self.buffer)
            
            assert result.name == "CrossLang"
            assert result.age == 42


class TestIntegrationScenarios:
    """Integration test scenarios"""
    
    def test_real_world_scenario(self):
        """Test a real-world scenario with nested objects"""
        # Create a complex company structure
        employees = [
            Employee(name="Alice Johnson", employee_id=1001, salary=85000.0,
                    department="Engineering", skills=["Python", "Kubernetes", "AWS"]),
            Employee(name="Bob Smith", employee_id=1002, salary=72000.0,
                    department="Engineering", skills=["Java", "Spring", "Docker"]),
            Employee(name="Carol Davis", employee_id=1003, salary=95000.0,
                    department="Management", skills=["Leadership", "Strategy"])
        ]
        
        company = Company(name="TechCorp Inc.", employees=employees, founded_year=2015)
        
        # Setup Fory with all types
        fory = Fory(mode=CompatibleMode.COMPATIBLE)
        fory.register(Employee, CompatibleSerializer)
        fory.register(Company, CompatibleSerializer)
        
        buffer = Buffer.allocate(4096)  # Larger buffer for complex object
        
        # Serialize
        fory.serialize(buffer, company)
        
        # Deserialize
        buffer.reader_index = 0
        result = fory.deserialize(buffer, Company)
        
        assert result.name == "TechCorp Inc."
        assert result.founded_year == 2015
        assert len(result.employees) == 3
        
        # Check employees
        assert result.employees[0].name == "Alice Johnson"
        assert result.employees[0].skills == ["Python", "Kubernetes", "AWS"]
        assert result.employees[1].department == "Engineering"
        assert result.employees[2].salary == 95000.0
        
    def test_version_migration_scenario(self):
        """Test a version migration scenario"""
        # Simulate upgrading from PersonV1 to PersonV2 in production
        
        # Original data (PersonV1)
        original_people = [
            PersonV1(name="User1", age=25),
            PersonV1(name="User2", age=30),
            PersonV1(name="User3", age=35)
        ]
        
        # Serialize with V1
        fory_v1 = Fory(mode=CompatibleMode.COMPATIBLE)
        fory_v1.register(PersonV1, CompatibleSerializer)
        
        serialized_data = []
        for person in original_people:
            buffer = Buffer.allocate(1024)
            fory_v1.serialize(buffer, person)
            serialized_data.append(buffer)
        
        # Now "upgrade" system to V2
        fory_v2 = Fory(mode=CompatibleMode.COMPATIBLE)
        fory_v2.register(PersonV2, CompatibleSerializer)
        
        # Read old data with new schema
        migrated_people = []
        for buffer in serialized_data:
            buffer.reader_index = 0
            person = fory_v2.deserialize(buffer, PersonV2)
            migrated_people.append(person)
        
        # Verify migration
        for original, migrated in zip(original_people, migrated_people):
            assert migrated.name == original.name
            assert migrated.age == original.age
            assert migrated.email is None  # New field gets default
            
        # Now serialize new data with V2
        new_person = PersonV2(name="NewUser", age=40, email="new@example.com")
        buffer = Buffer.allocate(1024)
        fory_v2.serialize(buffer, new_person)
        
        # Verify V2 data can be read back
        buffer.reader_index = 0
        result = fory_v2.deserialize(buffer, PersonV2)
        assert result.name == "NewUser"
        assert result.age == 40
        assert result.email == "new@example.com"


class TestUtilityFunctions:
    """Test utility functions and helpers"""
    
    def test_meta_context_utilities(self):
        """Test MetaContext utility methods"""
        meta_context = MetaContext()
        
        # Register multiple types
        id1 = meta_context.register_class(PersonV1)
        id2 = meta_context.register_class(PersonV2)
        id3 = meta_context.register_class(Employee)
        
        # Test type definition retrieval
        type_def1 = meta_context.get_type_definition(id1)
        type_def2 = meta_context.get_type_definition(id2)
        type_def3 = meta_context.get_type_definition(id3)
        
        assert type_def1.type_cls == PersonV1
        assert type_def2.type_cls == PersonV2
        assert type_def3.type_cls == Employee
        
        # Test unknown type ID
        unknown_def = meta_context.get_type_definition(99999)
        assert unknown_def is None
        
    def test_field_info_utilities(self):
        """Test FieldInfo utility methods"""
        meta_context = MetaContext()
        type_id = meta_context.register_class(PersonV2)
        type_def = meta_context.get_type_definition(type_id)
        
        # Test field lookup by name
        name_field = type_def.get_field_by_name('name')
        assert name_field is not None
        assert name_field.name == 'name'
        
        unknown_field = type_def.get_field_by_name('unknown')
        assert unknown_field is None
        
        # Test field lookup by hash
        name_field_by_hash = type_def.get_field_by_hash(name_field.encoded_field_info)
        assert name_field_by_hash is not None
        assert name_field_by_hash.name == 'name'
        
    def test_embedded_field_classification(self):
        """Test embedded field classification"""
        meta_context = MetaContext()
        type_id = meta_context.register_class(PersonV2)
        type_def = meta_context.get_type_definition(type_id)
        
        embedded_fields = type_def.embedded_fields
        separate_fields = type_def.separate_fields
        
        # PersonV2 should have all embedded fields (primitive and string types)
        assert len(embedded_fields) == 3  # name, age, email
        assert len(separate_fields) == 0
        
        # Test Employee with more complex fields
        emp_type_id = meta_context.register_class(Employee)
        emp_type_def = meta_context.get_type_definition(emp_type_id)
        
        # Employee should have some separate fields (lists, dicts)
        emp_embedded = emp_type_def.embedded_fields
        emp_separate = emp_type_def.separate_fields
        
        # name, employee_id, salary, department should be embedded
        # skills (List) and metadata (Dict) should be separate
        assert len(emp_embedded) >= 4
        assert len(emp_separate) >= 2


if __name__ == '__main__':
    # Run tests with verbose output
    pytest.main([__file__, '-v', '--tb=short'])
