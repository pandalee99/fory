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

use crate::object::{derive_enum, misc, read, write};
use crate::util::sorted_fields;
use proc_macro::TokenStream;
use quote::quote;

pub fn derive_serializer(ast: &syn::DeriveInput) -> TokenStream {
    let name = &ast.ident;
    let (
        type_def_token_stream,
        write_token_stream,
        read_token_stream,
        read_compatible_token_stream,
        read_nullable_token_stream,
    ) = match &ast.data {
        syn::Data::Struct(s) => {
            let fields = sorted_fields(&s.fields);
            (
                misc::gen_in_struct_impl(&fields),
                write::gen(&fields),
                read::gen(&fields, name),
                read::gen_read_compatible(&fields, name),
                read::gen_nullable(&fields),
            )
        }
        syn::Data::Enum(s) => (
            derive_enum::gen_type_def(s),
            derive_enum::gen_write(s),
            derive_enum::gen_read(s),
            quote! {},
            quote! {},
        ),
        syn::Data::Union(_) => {
            panic!("Union is not supported")
        }
    };

    let misc_token_stream = misc::gen();

    let gen = quote! {
        impl fory_core::serializer::StructSerializer for #name {
            #type_def_token_stream
        }
        impl fory_core::types::ForyGeneralList for #name {}
        impl fory_core::serializer::Serializer for #name {
            #misc_token_stream
            #write_token_stream
            #read_token_stream
        }
        impl #name {
            #read_compatible_token_stream
            #read_nullable_token_stream
        }
    };
    gen.into()
}
