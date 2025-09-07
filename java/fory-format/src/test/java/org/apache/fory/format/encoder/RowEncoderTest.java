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

package org.apache.fory.format.encoder;

import static org.apache.fory.collection.Collections.ofHashMap;
import static org.apache.fory.format.encoder.CodecBuilderTest.testStreamingEncode;

import com.google.common.collect.ImmutableMap;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;
import lombok.Data;
import org.apache.fory.format.row.binary.BinaryRow;
import org.apache.fory.memory.MemoryBuffer;
import org.apache.fory.memory.MemoryUtils;
import org.apache.fory.test.bean.BeanA;
import org.apache.fory.test.bean.BeanB;
import org.testng.Assert;
import org.testng.annotations.Test;

public class RowEncoderTest {

  @Test
  public void testEncoder() {
    Encoders.bean(AtomicLong.class);
    {
      RowEncoder<BeanA> encoder = Encoders.bean(BeanA.class);
      BeanA beanA = BeanA.createBeanA(2);
      for (int i = 0; i < 3; i++) {
        BinaryRow row = encoder.toRow(beanA);
        BeanA newBean = encoder.fromRow(row);
        Assert.assertEquals(beanA, newBean);
      }
      testStreamingEncode(encoder, beanA);
    }
    {
      RowEncoder<BeanB> encoder = Encoders.bean(BeanB.class);
      BeanB beanB = BeanB.createBeanB(2);
      for (int i = 0; i < 3; i++) {
        BinaryRow row = encoder.toRow(beanB);
        BeanB newBean = encoder.fromRow(row);
        Assert.assertEquals(beanB, newBean);
      }
      testStreamingEncode(encoder, beanB);
    }
  }

  @Data
  public static class Foo {
    public Foo() {
      f1 = 2;
      f2 = "str";
      f3 = Arrays.asList("a", "b", "c");
      f4 = new HashMap<>(ImmutableMap.of("k1", 1, "k2", 2));
      f5 = new Bar();
    }

    public int f1;
    public String f2;
    public List<String> f3;
    public Map<String, Integer> f4;
    public Bar f5;
  }

  @Data
  public static class Bar {
    public Bar() {
      f1 = 1;
      f2 = "str";
    }

    public int f1;
    public String f2;
  }

  @Test
  public void testImportInnerClass() {
    Foo foo = new Foo();
    RowEncoder<Foo> encoder = Encoders.bean(Foo.class);
    BinaryRow row = encoder.toRow(foo);
    MemoryBuffer buffer = MemoryUtils.wrap(row.toBytes());
    row.pointTo(buffer, 0, buffer.size());
    Foo deserializedFoo = encoder.fromRow(row);
    Assert.assertEquals(foo, deserializedFoo);
  }

  private static class PrivateStruct {
    java.util.Map<Long, Long> f1;
    java.util.Map<String, String> f2;
  }

  @Test
  public void testPrivateBean() {
    RowEncoder<PrivateStruct> encoder = Encoders.bean(PrivateStruct.class);
    PrivateStruct s = new PrivateStruct();
    s.f1 = ofHashMap(10L, 100L);
    s.f2 = ofHashMap("k", "v");
    PrivateStruct s1 = encoder.decode(encoder.encode(s));
    Assert.assertEquals(s1.f1, s.f1);
    Assert.assertEquals(s1.f2, s.f2);
  }

  @Test
  public void testNullClearOffset() {
    RowEncoder<Bar> encoder = Encoders.bean(Bar.class);
    Bar bar = new Bar();
    bar.f1 = 42;
    bar.f2 = null;
    byte[] nullBefore = encoder.encode(bar);

    bar.f2 = "not null";
    // write offset and size
    encoder.encode(bar);

    bar.f2 = null;
    byte[] nullAfter = encoder.encode(bar);
    Assert.assertEquals(nullAfter, nullBefore);
  }
}
