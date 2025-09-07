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

use fory_core::buffer::{Reader, Writer};

#[test]
fn test_var_int32() {
    let test_data: Vec<i32> = vec![
        // 1 byte(0..127)
        0,
        1,
        127,
        // 2 byte(128..16_383)
        128,
        300,
        16_383,
        // 3 byte(16_384..2_097_151)
        16_384,
        20_000,
        2_097_151,
        // 4 byte(2_097_152..268_435_455)
        2_097_152,
        100_000_000,
        268_435_455,
        // 5 byte(268_435_456..i32::MAX)
        268_435_456,
        i32::MAX,
    ];
    for &data in &test_data {
        let mut writer = Writer::default();
        writer.var_int32(data);
        let binding = writer.dump();
        let mut reader = Reader::new(binding.as_slice());
        let res = reader.var_int32();
        assert_eq!(res, data);
    }
    for &data in &test_data {
        let mut writer = Writer::default();
        writer.var_uint32(data as u32);
        let binding = writer.dump();
        let mut reader = Reader::new(binding.as_slice());
        let res = reader.var_uint32();
        assert_eq!(res, data as u32);
    }
}
