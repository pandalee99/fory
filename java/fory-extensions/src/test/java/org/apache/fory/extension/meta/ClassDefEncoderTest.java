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

package org.apache.fory.extension.meta;

import static org.apache.fory.meta.ClassDefEncoder.buildFieldsInfo;
import static org.apache.fory.meta.ClassDefEncoder.getClassFields;

import java.util.List;
import org.apache.fory.Fory;
import org.apache.fory.memory.MemoryBuffer;
import org.apache.fory.meta.ClassDef;
import org.apache.fory.meta.ClassDefEncoder;
import org.testng.Assert;
import org.testng.annotations.Test;

public class ClassDefEncoderTest {

  static class TestFieldsOrderClass1 {
    private int intField2;
    private boolean booleanField;
    private Object objField;
    private long longField;
  }

  @Test
  public void testBasicClassDef_zstdMetaCompressor() throws Exception {
    Fory fory =
        Fory.builder().withMetaShare(true).withMetaCompressor(new ZstdMetaCompressor()).build();
    Class<TestFieldsOrderClass1> type = TestFieldsOrderClass1.class;
    List<ClassDef.FieldInfo> fieldsInfo = buildFieldsInfo(fory.getClassResolver(), type);
    MemoryBuffer buffer =
        ClassDefEncoder.encodeClassDef(
            fory.getClassResolver(), type, getClassFields(type, fieldsInfo), true);
    ClassDef classDef = ClassDef.readClassDef(fory, buffer);
    Assert.assertEquals(classDef.getClassName(), type.getName());
    Assert.assertEquals(classDef.getFieldsInfo().size(), type.getDeclaredFields().length);
    Assert.assertEquals(classDef.getFieldsInfo(), fieldsInfo);
  }
}
