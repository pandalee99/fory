// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.

package fory

import (
	"fmt"
	"github.com/stretchr/testify/require"
	"reflect"
	"testing"
)

func TestTypeResolver(t *testing.T) {
	fory := &Fory{
		refResolver:       newRefResolver(false),
		referenceTracking: false,
		language:          XLANG,
		buffer:            NewByteBuffer(nil),
	}
	typeResolver := newTypeResolver(fory)
	type A struct {
		F1 string
	}
	require.Nil(t, typeResolver.RegisterTypeTag(reflect.ValueOf(A{}), "example.A"))
	require.Error(t, typeResolver.RegisterTypeTag(reflect.ValueOf(A{}), "example.A"))

	var tests = []struct {
		type_    reflect.Type
		typeInfo string
	}{
		{reflect.TypeOf((*int)(nil)), "*int"},
		{reflect.TypeOf((*[10]int)(nil)), "*[10]int"},
		{reflect.TypeOf((*[10]int)(nil)).Elem(), "[10]int"},
		{reflect.TypeOf((*[]map[string][]map[string]*interface{})(nil)).Elem(),
			"[]map[string][]map[string]*interface {}"},
		{reflect.TypeOf((*A)(nil)), "*@example.A"},
		{reflect.TypeOf((*A)(nil)).Elem(), "@example.A"},
		{reflect.TypeOf((*[]map[string]int)(nil)), "*[]map[string]int"},
		{reflect.TypeOf((*[]map[A]int)(nil)), "*[]map[@example.A]int"},
		{reflect.TypeOf((*[]map[string]*A)(nil)), "*[]map[string]*@example.A"},
	}
	for _, test := range tests {
		typeStr, err := typeResolver.encodeType(test.type_)
		require.Nil(t, err)
		require.Equal(t, test.typeInfo, typeStr)
	}
	for _, test := range tests {
		type_, typeStr, err := typeResolver.decodeType(test.typeInfo)
		require.Nil(t, err)
		require.Equal(t, test.typeInfo, typeStr)
		require.Equal(t, test.type_, type_)
	}
}

// Test slice type classification and serialization behavior
func TestSliceTypeClassification(t *testing.T) {
	t.Run("Type reflection properties", func(t *testing.T) {
		// Test []int16 (primitive slice)
		primitiveSlice := []int16{1, 2, 3}
		primitiveType := reflect.TypeOf(primitiveSlice)
		require.Equal(t, "", primitiveType.Name(), "[]int16 should have empty Name()")
		require.Equal(t, reflect.Slice, primitiveType.Kind())
		require.Equal(t, reflect.Int16, primitiveType.Elem().Kind())

		// Test Int16Slice (named type)
		namedSlice := Int16Slice{4, 5, 6}
		namedType := reflect.TypeOf(namedSlice)
		require.Equal(t, "Int16Slice", namedType.Name(), "Int16Slice should have non-empty Name()")
		require.Equal(t, reflect.Slice, namedType.Kind())
		require.Equal(t, reflect.Int16, namedType.Elem().Kind())

		// Test assignment compatibility
		var f12 Int16Slice
		f12 = []int16{-1, 4} // This works because Int16Slice is defined as []int16
		require.Equal(t, Int16Slice{-1, 4}, f12)
		require.Equal(t, "Int16Slice", reflect.TypeOf(f12).Name())
	})

	t.Run("Primitive slice array classification", func(t *testing.T) {
		testCases := []struct {
			name     string
			value    interface{}
			expected bool
			comment  string
		}{
			{"[]int16", []int16{1, 2, 3}, true, "primitive slice -> array"},
			{"Int16Slice", Int16Slice{4, 5, 6}, false, "named type -> list"},
			{"[]int", []int{1, 2, 3}, false, "generic type -> list"},
			{"[]int32", []int32{1, 2}, true, "primitive slice -> array"},
			{"[]float32", []float32{1.0, 2.0}, true, "primitive slice -> array"},
		}

		for _, tc := range testCases {
			t.Run(tc.name, func(t *testing.T) {
				typ := reflect.TypeOf(tc.value)
				result := isPrimitiveSliceOrArrayType(typ)
				require.Equal(t, tc.expected, result,
					fmt.Sprintf("%s: %s", tc.name, tc.comment))
			})
		}
	})
}

// Test serialization behavior of different slice types
func TestPrimitiveSliceArrayMapping(t *testing.T) {
	fory_ := NewFory(true)

	t.Run("Primitive slice serialization", func(t *testing.T) {
		primitiveSlice := []int16{1, 2, 3}
		buffer := NewByteBuffer(nil)
		err := fory_.Serialize(buffer, primitiveSlice, nil)
		require.Nil(t, err, "Primitive slice should serialize successfully")
	})

	t.Run("Named slice serialization", func(t *testing.T) {
		namedSlice := Int16Slice{4, 5, 6}
		buffer := NewByteBuffer(nil)
		err := fory_.Serialize(buffer, namedSlice, nil)
		require.Nil(t, err, "Named slice should serialize successfully")
	})
}
