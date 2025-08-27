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

use super::meta_string::MetaStringEncoder;
use crate::buffer::{Reader, Writer};
use crate::error::Error;
use crate::meta::murmurhash3_x64_128;
use crate::meta::{Encoding, MetaStringDecoder};
use crate::types::TypeId;
use anyhow::anyhow;
use std::cmp::min;

static SMALL_NUM_FIELDS_THRESHOLD: usize = 0b11111;
static REGISTER_BY_NAME_FLAG: u8 = 0b100000;
static FIELD_NAME_SIZE_THRESHOLD: usize = 0b1111;

static META_SIZE_MASK: u64 = 0xfff;
static COMPRESS_META_FLAG: u64 = 0b1 << 13;
static HAS_FIELDS_META_FLAG: u64 = 0b1 << 12;
static NUM_HASH_BITS: i8 = 50;

static ENCODING_OPTIONS: &[Encoding] = &[
    Encoding::Utf8,
    Encoding::AllToLowerSpecial,
    Encoding::LowerUpperDigitSpecial,
];

#[derive(Debug, PartialEq, Eq)]
pub struct FieldType {
    pub type_id: i16,
    generics: Vec<FieldType>,
}

impl FieldType {
    pub fn new(type_id: i16, generics: Vec<FieldType>) -> Self {
        FieldType { type_id, generics }
    }

    fn to_bytes(&self, writer: &mut Writer, write_flag: bool, nullable: bool) -> Result<(), Error> {
        if self.type_id == TypeId::ForyOption.into() {
            self.generics
                .first()
                .unwrap()
                .to_bytes(writer, write_flag, true)?;
            return Ok(());
        }
        let mut header: i32 = self.type_id as i32;
        if write_flag {
            header <<= 2;
            // let ref_tracking = false;
            if nullable {
                header |= 2;
            }
        }
        writer.var_int32(header);
        match self.type_id {
            x if x == TypeId::ARRAY as i16 || x == TypeId::SET as i16 => {
                let generic = self.generics.first().unwrap();
                generic.to_bytes(writer, true, false)?;
            }
            x if x == TypeId::MAP as i16 => {
                let key_generic = self.generics.first().unwrap();
                let val_generic = self.generics.get(1).unwrap();
                key_generic.to_bytes(writer, true, false)?;
                val_generic.to_bytes(writer, true, false)?;
            }
            _ => {}
        }
        Ok(())
    }

    #[allow(clippy::needless_late_init)]
    fn from_bytes(reader: &mut Reader, read_flag: bool, nullable: Option<bool>) -> Self {
        let header = reader.var_int32();
        let type_id;
        let _nullable;
        if read_flag {
            type_id = (header >> 2) as i16;
            // let tracking_ref = (header & 1) != 0;
            _nullable = (header & 2) != 0;
        } else {
            type_id = header as i16;
            _nullable = nullable.unwrap();
        }
        let field_type = match type_id {
            x if x == TypeId::ARRAY.into() || x == TypeId::SET.into() => {
                let generic = Self::from_bytes(reader, true, None);
                Self {
                    type_id,
                    generics: vec![generic],
                }
            }
            x if x == TypeId::MAP.into() => {
                let key_generic = Self::from_bytes(reader, true, None);
                let val_generic = Self::from_bytes(reader, true, None);
                Self {
                    type_id,
                    generics: vec![key_generic, val_generic],
                }
            }
            _ => Self {
                type_id,
                generics: vec![],
            },
        };
        if _nullable {
            Self {
                type_id: TypeId::ForyOption.into(),
                generics: vec![field_type],
            }
        } else {
            field_type
        }
    }
}

#[derive(Debug, PartialEq, Eq)]
pub struct FieldInfo {
    pub field_name: String,
    pub field_type: FieldType,
}

impl FieldInfo {
    pub fn new(field_name: &str, field_type: FieldType) -> FieldInfo {
        FieldInfo {
            field_name: field_name.to_string(),
            field_type,
        }
    }

    fn u8_to_encoding(value: u8) -> Result<Encoding, Error> {
        match value {
            0x00 => Ok(Encoding::Utf8),
            0x01 => Ok(Encoding::AllToLowerSpecial),
            0x02 => Ok(Encoding::LowerUpperDigitSpecial),
            _ => Err(anyhow!(
                "Unsupported encoding of field name in type meta, value:{value}"
            ))?,
        }
    }

    pub fn from_bytes(reader: &mut Reader) -> FieldInfo {
        let header = reader.u8();
        let nullable = (header & 2) != 0;
        // let ref_tracking = (header & 1) != 0;
        let encoding = Self::u8_to_encoding((header >> 6) & 0b11).unwrap();
        let mut name_size = ((header >> 2) & FIELD_NAME_SIZE_THRESHOLD as u8) as usize;
        if name_size == FIELD_NAME_SIZE_THRESHOLD {
            name_size += reader.var_int32() as usize;
        }
        name_size += 1;

        let field_type = FieldType::from_bytes(reader, false, Option::from(nullable));

        let field_name_bytes = reader.bytes(name_size);

        let field_name = MetaStringDecoder::new()
            .decode(field_name_bytes, encoding)
            .unwrap();
        FieldInfo {
            field_name,
            field_type,
        }
    }

    fn to_bytes(&self) -> Result<Vec<u8>, Error> {
        // field_bytes: | header | type_info | field_name |
        let mut writer = Writer::default();
        // header: | field_name_encoding:2bits | size:4bits | nullability:1bit | ref_tracking:1bit |
        let meta_string = MetaStringEncoder::new()
            .set_options(Some(ENCODING_OPTIONS))
            .encode(&self.field_name)?;
        let name_encoded = meta_string.bytes.as_slice();
        let name_size = name_encoded.len() - 1;
        let mut header: u8 = (min(FIELD_NAME_SIZE_THRESHOLD, name_size) as u8) << 2;
        // let ref_tracking = false;
        let nullable = self.field_type.type_id == TypeId::ForyOption.into();
        // if ref_tracking {
        //     header |= 1;
        // }
        if nullable {
            header |= 2;
        }
        let encoding_idx = ENCODING_OPTIONS
            .iter()
            .position(|x| *x == meta_string.encoding)
            .unwrap() as u8;
        header |= encoding_idx << 6;
        writer.u8(header);
        if name_size >= FIELD_NAME_SIZE_THRESHOLD {
            writer.var_int32((name_size - FIELD_NAME_SIZE_THRESHOLD) as i32);
        }
        self.field_type.to_bytes(&mut writer, false, nullable)?;
        // write field_name
        writer.bytes(name_encoded);
        Ok(writer.dump())
    }
}

#[derive(Debug)]
pub struct TypeMetaLayer {
    type_id: u32,
    field_infos: Vec<FieldInfo>,
}

impl TypeMetaLayer {
    pub fn new(type_id: u32, field_infos: Vec<FieldInfo>) -> TypeMetaLayer {
        TypeMetaLayer {
            type_id,
            field_infos,
        }
    }

    pub fn get_type_id(&self) -> u32 {
        self.type_id
    }

    pub fn get_field_infos(&self) -> &Vec<FieldInfo> {
        &self.field_infos
    }

    fn to_bytes(&self) -> Result<Vec<u8>, Error> {
        // layer_bytes:| meta_header | fields meta |
        let mut writer = Writer::default();
        let num_fields = self.field_infos.len() - 1;
        let is_register_by_name = false;
        // meta_header: | unuse:2 bits | is_register_by_id:1 bit | num_fields:4 bits |
        let mut meta_header: u8 = min(num_fields, SMALL_NUM_FIELDS_THRESHOLD) as u8;
        if is_register_by_name {
            meta_header |= REGISTER_BY_NAME_FLAG;
        }
        writer.u8(meta_header);
        if num_fields >= SMALL_NUM_FIELDS_THRESHOLD {
            writer.var_int32((num_fields - SMALL_NUM_FIELDS_THRESHOLD) as i32);
        }
        if is_register_by_name {
            todo!()
        } else {
            writer.var_int32(self.type_id as i32);
        }
        for field in self.field_infos.iter() {
            writer.bytes(field.to_bytes()?.as_slice());
        }
        Ok(writer.dump())
    }

    fn from_bytes(reader: &mut Reader) -> TypeMetaLayer {
        let meta_header = reader.u8();
        // let is_register_by_name = (meta_header & REGISTER_BY_NAME_FLAG) == 1;
        let is_register_by_name = false;
        let mut num_fields = meta_header as usize & SMALL_NUM_FIELDS_THRESHOLD;
        if num_fields == SMALL_NUM_FIELDS_THRESHOLD {
            num_fields += reader.var_int32() as usize;
        }
        num_fields += 1;
        let type_id;
        if is_register_by_name {
            todo!()
        } else {
            type_id = reader.var_int32() as u32;
        }
        let mut field_infos = Vec::with_capacity(num_fields);
        for _ in 0..num_fields {
            field_infos.push(FieldInfo::from_bytes(reader));
        }

        TypeMetaLayer::new(type_id, field_infos)
    }
}

#[derive(Debug)]
pub struct TypeMeta {
    // hash: u64,
    layers: Vec<TypeMetaLayer>,
}

impl TypeMeta {
    pub fn get_field_infos(&self) -> &Vec<FieldInfo> {
        self.layers.first().unwrap().get_field_infos()
    }

    pub fn get_type_id(&self) -> u32 {
        self.layers.first().unwrap().get_type_id()
    }

    pub fn from_fields(type_id: u32, field_infos: Vec<FieldInfo>) -> TypeMeta {
        TypeMeta {
            // hash: 0,
            layers: vec![TypeMetaLayer::new(type_id, field_infos)],
        }
    }
    #[allow(unused_assignments)]
    pub fn from_bytes(reader: &mut Reader) -> TypeMeta {
        let header = reader.u64();
        let mut meta_size = header & META_SIZE_MASK;
        if meta_size == META_SIZE_MASK {
            meta_size += reader.var_int32() as u64;
        }

        // let write_fields_meta = (header & HAS_FIELDS_META_FLAG) != 0;
        // let is_compressed: bool = (header & COMPRESS_META_FLAG) != 0;
        // let meta_hash = header >> (64 - NUM_HASH_BITS);

        let mut layers = Vec::new();
        // let current_meta_size = 0;
        // while current_meta_size < meta_size {}
        let layer = TypeMetaLayer::from_bytes(reader);
        layers.push(layer);
        TypeMeta { layers }
    }

    pub fn to_bytes(&self) -> Result<Vec<u8>, Error> {
        // | global_binary_header | layers_bytes |
        let mut result = Writer::default();
        let mut layers_writer = Writer::default();
        // for layer in self.layers.iter() {
        //     layers_writer.bytes(layer.to_bytes()?.as_slice());
        // }
        layers_writer.bytes(self.layers.first().unwrap().to_bytes()?.as_slice());
        // global_binary_header:| hash:50bits | is_compressed:1bit | write_fields_meta:1bit | meta_size:12bits |
        let meta_size = layers_writer.len() as u64;
        let mut header: u64 = min(META_SIZE_MASK, meta_size);
        let write_meta_fields_flag = true;
        if write_meta_fields_flag {
            header |= HAS_FIELDS_META_FLAG;
        }
        let is_compressed = false;
        if is_compressed {
            header |= COMPRESS_META_FLAG;
        }
        let meta_hash = murmurhash3_x64_128(layers_writer.dump().as_slice(), 47).0;
        header |= meta_hash << (64 - NUM_HASH_BITS);
        result.u64(header);
        if meta_size >= META_SIZE_MASK {
            result.var_int32((meta_size - META_SIZE_MASK) as i32);
        }
        result.bytes(layers_writer.dump().as_slice());
        Ok(result.dump())
    }
}
