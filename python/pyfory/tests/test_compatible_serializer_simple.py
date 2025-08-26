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

import pytest
from dataclasses import dataclass
from typing import List, Dict, Optional

import pyfory
from pyfory._fory import CompatibleMode


@dataclass
class PersonV1:
    name: str
    age: int


def test_basic_compatible_serializer():
    """Test basic functionality of CompatibleSerializer"""
    fory = pyfory.Fory(compatible_mode=CompatibleMode.COMPATIBLE)
    
    # Register the type with compatible serializer
    fory.register_type(PersonV1)
    
    # Create and serialize object
    person = PersonV1(name="John", age=30)
    serialized = fory.serialize(person)
    
    # Deserialize and verify
    deserialized = fory.deserialize(serialized)
    
    assert isinstance(deserialized, PersonV1)
    assert deserialized.name == "John"
    assert deserialized.age == 30


if __name__ == "__main__":
    import sys
    import os
    os.environ['ENABLE_FORY_CYTHON_SERIALIZATION'] = 'False'
    test_basic_compatible_serializer()
    print("Basic compatible serializer test passed!")
