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
import sys
import os

# Add the parent directory to the Python path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

try:
    from pyfory.nanobind_extensions import math_ops
    EXTENSIONS_AVAILABLE = True
except ImportError:
    EXTENSIONS_AVAILABLE = False
    math_ops = None


@pytest.mark.skipif(not EXTENSIONS_AVAILABLE, reason="Nanobind extensions not built")
class TestMathOps:
    """Test cases for the math_ops nanobind extension."""
    
    def test_add_basic(self):
        """Test basic addition functionality."""
        assert math_ops.add(1, 2) == 3
        assert math_ops.add(0, 0) == 0
        assert math_ops.add(-1, 1) == 0
        assert math_ops.add(100, 200) == 300
    
    def test_add_default_argument(self):
        """Test addition with default argument."""
        assert math_ops.add(5) == 6  # 5 + 1 (default)
        assert math_ops.add(0) == 1  # 0 + 1 (default)
        assert math_ops.add(-1) == 0  # -1 + 1 (default)
    
    def test_add_keyword_arguments(self):
        """Test addition with keyword arguments."""
        assert math_ops.add(a=3, b=4) == 7
        assert math_ops.add(b=5, a=2) == 7
        assert math_ops.add(a=10, b=0) == 10
    
    def test_add_mixed_arguments(self):
        """Test addition with mixed positional and keyword arguments."""
        assert math_ops.add(3, b=4) == 7
        # Note: math_ops.add(a=3, 4) would be invalid syntax in Python
    
    def test_multiply_integers(self):
        """Test integer multiplication."""
        assert math_ops.multiply(2, 3) == 6
        assert math_ops.multiply(0, 5) == 0
        assert math_ops.multiply(-2, 3) == -6
        assert math_ops.multiply(-2, -3) == 6
    
    def test_multiply_floats(self):
        """Test floating point multiplication."""
        assert math_ops.multiply(2.5, 4.0) == 10.0
        assert math_ops.multiply(0.0, 3.14) == 0.0
        assert math_ops.multiply(-1.5, 2.0) == -3.0
        assert abs(math_ops.multiply(3.14159, 2.0) - 6.28318) < 1e-5
    
    def test_multiply_keyword_arguments(self):
        """Test multiplication with keyword arguments."""
        assert math_ops.multiply(a=4, b=5) == 20
        assert math_ops.multiply(b=3.0, a=2.5) == 7.5
    
    def test_module_attributes(self):
        """Test module-level attributes."""
        assert hasattr(math_ops, 'VERSION')
        assert hasattr(math_ops, 'AUTHOR')
        assert math_ops.VERSION == "1.0.0"
        assert math_ops.AUTHOR == "PyFory Team"
    
    def test_function_docstrings(self):
        """Test that functions have proper docstrings."""
        assert math_ops.add.__doc__ is not None
        assert "Add two integers" in math_ops.add.__doc__
        assert math_ops.multiply.__doc__ is not None


@pytest.mark.skipif(not EXTENSIONS_AVAILABLE, reason="Nanobind extensions not built")
class TestCalculator:
    """Test cases for the Calculator class."""
    
    def test_calculator_creation(self):
        """Test Calculator creation."""
        calc1 = math_ops.Calculator()
        assert calc1.get_value() == 0
        
        calc2 = math_ops.Calculator(10)
        assert calc2.get_value() == 10
        
        calc3 = math_ops.Calculator(initial_value=42)
        assert calc3.get_value() == 42
    
    def test_calculator_add(self):
        """Test Calculator addition method."""
        calc = math_ops.Calculator(5)
        assert calc.add(3) == 8
        assert calc.get_value() == 8
        
        assert calc.add(-2) == 6
        assert calc.get_value() == 6
    
    def test_calculator_subtract(self):
        """Test Calculator subtraction method."""
        calc = math_ops.Calculator(10)
        assert calc.subtract(3) == 7
        assert calc.get_value() == 7
        
        assert calc.subtract(-2) == 9
        assert calc.get_value() == 9
    
    def test_calculator_set_value(self):
        """Test Calculator set_value method."""
        calc = math_ops.Calculator()
        calc.set_value(42)
        assert calc.get_value() == 42
        
        calc.set_value(-10)
        assert calc.get_value() == -10
    
    def test_calculator_repr(self):
        """Test Calculator string representation."""
        calc = math_ops.Calculator(123)
        repr_str = repr(calc)
        assert "<Calculator value=123>" == repr_str
        
        calc.set_value(-5)
        repr_str = repr(calc)
        assert "<Calculator value=-5>" == repr_str
    
    def test_calculator_chaining(self):
        """Test method chaining with Calculator."""
        calc = math_ops.Calculator(0)
        result = calc.add(5)
        assert result == 5
        
        result = calc.subtract(2)
        assert result == 3
        
        result = calc.add(10)
        assert result == 13
        
        assert calc.get_value() == 13


class TestImportFallback:
    """Test import fallback behavior when extensions are not available."""
    
    @pytest.mark.skipif(EXTENSIONS_AVAILABLE, reason="Extensions are available")
    def test_import_warning(self):
        """Test that appropriate warning is issued when extensions can't be imported."""
        with pytest.warns(ImportWarning, match="Failed to import nanobind extensions"):
            # This would normally trigger the warning in __init__.py
            pass
    
    def test_module_structure(self):
        """Test that the package structure is correct regardless of extension availability."""
        import pyfory.nanobind_extensions
        assert hasattr(pyfory.nanobind_extensions, '__version__')
        assert hasattr(pyfory.nanobind_extensions, '__author__')
        assert pyfory.nanobind_extensions.__version__ == "1.0.0"
        assert pyfory.nanobind_extensions.__author__ == "PyFory Team"


if __name__ == "__main__":
    pytest.main([__file__])
