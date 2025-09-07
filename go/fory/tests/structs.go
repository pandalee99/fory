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

// ValidationDemo is a simple struct for testing code generation
// Contains only basic types since PR1 only supports basic types

// fory:gen
type ValidationDemo struct {
	A int32  `json:"a"` // int32 field
	B string `json:"b"` // string field
	C int64  `json:"c"` // int64 field (instead of array, as arrays are not supported yet)
}
