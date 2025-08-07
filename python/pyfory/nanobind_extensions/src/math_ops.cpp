/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <string>

namespace nb = nanobind;
using namespace nb::literals;

/**
 * Basic addition function demonstrating nanobind functionality.
 * This function adds two integers and returns the result.
 * 
 * @param a First integer
 * @param b Second integer (defaults to 1)
 * @return Sum of a and b
 */
int add(int a, int b = 1) {
    return a + b;
}

/**
 * Multiply two numbers.
 * This demonstrates function overloading support.
 * 
 * @param a First number
 * @param b Second number
 * @return Product of a and b
 */
int multiply(int a, int b) {
    return a * b;
}

/**
 * Double version of multiply function.
 * Demonstrates type overloading.
 */
double multiply(double a, double b) {
    return a * b;
}

/**
 * Simple class to demonstrate object binding.
 */
class Calculator {
public:
    Calculator(int initial_value = 0) : value_(initial_value) {}
    
    int add(int n) {
        value_ += n;
        return value_;
    }
    
    int subtract(int n) {
        value_ -= n;
        return value_;
    }
    
    int get_value() const {
        return value_;
    }
    
    void set_value(int value) {
        value_ = value;
    }
    
    // For Python repr
    std::string repr() const {
        return "<Calculator value=" + std::to_string(value_) + ">";
    }

private:
    int value_;
};

/**
 * Nanobind module definition.
 * This creates a Python module that exposes the C++ functions and classes.
 */
NB_MODULE(math_ops, m) {
    m.doc() = "PyFory nanobind math operations demo module";
    
    // Bind the add function with named arguments and default value
    m.def("add", &add, "a"_a, "b"_a = 1,
          "Add two integers. If only one argument is provided, adds 1 to it.\n\n"
          "Args:\n"
          "    a (int): First integer\n"
          "    b (int, optional): Second integer. Defaults to 1.\n\n"
          "Returns:\n"
          "    int: Sum of a and b\n\n"
          "Example:\n"
          "    >>> math_ops.add(5, 3)\n"
          "    8\n"
          "    >>> math_ops.add(10)  # Uses default b=1\n"
          "    11");
    
    // Bind multiply functions (demonstrating overloading)
    m.def("multiply", static_cast<int(*)(int, int)>(&multiply), "a"_a, "b"_a,
          "Multiply two integers.\n\n"
          "Args:\n"
          "    a (int): First integer\n"
          "    b (int): Second integer\n\n"
          "Returns:\n"
          "    int: Product of a and b");
          
    m.def("multiply", static_cast<double(*)(double, double)>(&multiply), "a"_a, "b"_a,
          "Multiply two floating point numbers.\n\n"
          "Args:\n"
          "    a (float): First number\n"
          "    b (float): Second number\n\n"
          "Returns:\n"
          "    float: Product of a and b");
    
    // Bind the Calculator class
    nb::class_<Calculator>(m, "Calculator")
        .def(nb::init<>(), "Create a calculator with initial value 0")
        .def(nb::init<int>(), "initial_value"_a, "Create a calculator with specified initial value")
        .def("add", &Calculator::add, "n"_a, "Add n to the current value")
        .def("subtract", &Calculator::subtract, "n"_a, "Subtract n from the current value")  
        .def("get_value", &Calculator::get_value, "Get the current value")
        .def("set_value", &Calculator::set_value, "value"_a, "Set the current value")
        .def("__repr__", &Calculator::repr, "String representation of the calculator");
    
    // Export some constants
    m.attr("VERSION") = "1.0.0";
    m.attr("AUTHOR") = "PyFory Team";
}
