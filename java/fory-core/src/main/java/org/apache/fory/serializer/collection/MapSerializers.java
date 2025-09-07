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

package org.apache.fory.serializer.collection;

import java.util.Collection;
import java.util.Collections;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Map.Entry;
import java.util.SortedMap;
import java.util.TreeMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentSkipListMap;
import org.apache.fory.Fory;
import org.apache.fory.collection.LazyMap;
import org.apache.fory.memory.MemoryBuffer;
import org.apache.fory.memory.Platform;
import org.apache.fory.reflect.ReflectionUtils;
import org.apache.fory.resolver.ClassInfo;
import org.apache.fory.resolver.ClassResolver;
import org.apache.fory.serializer.ReplaceResolveSerializer;
import org.apache.fory.serializer.Serializer;
import org.apache.fory.serializer.Serializers;
import org.apache.fory.serializer.StringSerializer;
import org.apache.fory.util.Preconditions;

/**
 * Serializers for classes implements {@link Collection}. All map serializers must extends {@link
 * MapSerializer}.
 */
@SuppressWarnings({"unchecked", "rawtypes"})
public class MapSerializers {

  public static final class HashMapSerializer extends MapSerializer<HashMap> {
    public HashMapSerializer(Fory fory) {
      super(fory, HashMap.class, true);
    }

    @Override
    public HashMap newMap(MemoryBuffer buffer) {
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      HashMap hashMap = new HashMap(numElements);
      fory.getRefResolver().reference(hashMap);
      return hashMap;
    }

    @Override
    public Map newMap(Map map) {
      return new HashMap(map.size());
    }
  }

  public static final class LinkedHashMapSerializer extends MapSerializer<LinkedHashMap> {
    public LinkedHashMapSerializer(Fory fory) {
      super(fory, LinkedHashMap.class, true);
    }

    @Override
    public LinkedHashMap newMap(MemoryBuffer buffer) {
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      LinkedHashMap hashMap = new LinkedHashMap(numElements);
      fory.getRefResolver().reference(hashMap);
      return hashMap;
    }

    @Override
    public Map newMap(Map map) {
      return new LinkedHashMap(map.size());
    }
  }

  public static final class LazyMapSerializer extends MapSerializer<LazyMap> {
    public LazyMapSerializer(Fory fory) {
      super(fory, LazyMap.class, true);
    }

    @Override
    public LazyMap newMap(MemoryBuffer buffer) {
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      LazyMap map = new LazyMap(numElements);
      fory.getRefResolver().reference(map);
      return map;
    }

    @Override
    public Map newMap(Map map) {
      return new LazyMap(map.size());
    }
  }

  public static class SortedMapSerializer<T extends SortedMap> extends MapSerializer<T> {

    public SortedMapSerializer(Fory fory, Class<T> cls) {
      super(fory, cls, true);
      if (cls != TreeMap.class) {
        this.constructor = ReflectionUtils.getCtrHandle(cls, Comparator.class);
      }
    }

    @Override
    public Map onMapWrite(MemoryBuffer buffer, T value) {
      buffer.writeVarUint32Small7(value.size());
      if (!fory.isCrossLanguage()) {
        fory.writeRef(buffer, value.comparator());
      }
      return value;
    }

    @SuppressWarnings("unchecked")
    @Override
    public Map newMap(MemoryBuffer buffer) {
      assert !fory.isCrossLanguage();
      setNumElements(buffer.readVarUint32Small7());
      T map;
      Comparator comparator = (Comparator) fory.readRef(buffer);
      if (type == TreeMap.class) {
        map = (T) new TreeMap(comparator);
      } else {
        try {
          map = (T) constructor.invoke(comparator);
        } catch (Throwable e) {
          throw new RuntimeException(e);
        }
      }
      fory.getRefResolver().reference(map);
      return map;
    }

    @Override
    public Map newMap(Map originMap) {
      Comparator comparator = fory.copyObject(((SortedMap) originMap).comparator());
      Map map;
      if (type == TreeMap.class) {
        map = new TreeMap(comparator);
      } else {
        try {
          map = (Map) constructor.invoke(comparator);
        } catch (Throwable e) {
          throw new RuntimeException(e);
        }
      }
      return map;
    }
  }

  public static final class EmptyMapSerializer extends MapSerializer<Map<?, ?>> {

    public EmptyMapSerializer(Fory fory, Class<Map<?, ?>> cls) {
      super(fory, cls, fory.isCrossLanguage(), true);
    }

    @Override
    public void write(MemoryBuffer buffer, Map<?, ?> value) {}

    @Override
    public void xwrite(MemoryBuffer buffer, Map<?, ?> value) {
      super.write(buffer, value);
    }

    @Override
    public Map<?, ?> read(MemoryBuffer buffer) {
      return Collections.EMPTY_MAP;
    }

    @Override
    public Map<?, ?> xread(MemoryBuffer buffer) {
      throw new IllegalStateException();
    }
  }

  public static final class EmptySortedMapSerializer extends MapSerializer<SortedMap<?, ?>> {
    public EmptySortedMapSerializer(Fory fory, Class<SortedMap<?, ?>> cls) {
      super(fory, cls, fory.isCrossLanguage(), true);
    }

    @Override
    public void write(MemoryBuffer buffer, SortedMap<?, ?> value) {}

    @Override
    public SortedMap<?, ?> read(MemoryBuffer buffer) {
      return Collections.emptySortedMap();
    }
  }

  public static final class SingletonMapSerializer extends MapSerializer<Map<?, ?>> {

    public SingletonMapSerializer(Fory fory, Class<Map<?, ?>> cls) {
      super(fory, cls, fory.isCrossLanguage());
    }

    @Override
    public Map<?, ?> copy(Map<?, ?> originMap) {
      Entry<?, ?> entry = originMap.entrySet().iterator().next();
      return Collections.singletonMap(
          fory.copyObject(entry.getKey()), fory.copyObject(entry.getValue()));
    }

    @Override
    public void write(MemoryBuffer buffer, Map<?, ?> value) {
      Map.Entry entry = value.entrySet().iterator().next();
      fory.writeRef(buffer, entry.getKey());
      fory.writeRef(buffer, entry.getValue());
    }

    @Override
    public Map<?, ?> read(MemoryBuffer buffer) {
      Object key = fory.readRef(buffer);
      Object value = fory.readRef(buffer);
      return Collections.singletonMap(key, value);
    }

    @Override
    public void xwrite(MemoryBuffer buffer, Map<?, ?> value) {
      super.write(buffer, value);
    }

    @Override
    public Map<?, ?> xread(MemoryBuffer buffer) {
      throw new UnsupportedOperationException();
    }
  }

  public static final class ConcurrentHashMapSerializer extends MapSerializer<ConcurrentHashMap> {

    public ConcurrentHashMapSerializer(Fory fory, Class<ConcurrentHashMap> type) {
      super(fory, type, true);
    }

    @Override
    public ConcurrentHashMap newMap(MemoryBuffer buffer) {
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      ConcurrentHashMap map = new ConcurrentHashMap(numElements);
      fory.getRefResolver().reference(map);
      return map;
    }

    @Override
    public Map newMap(Map map) {
      return new ConcurrentHashMap(map.size());
    }
  }

  public static final class ConcurrentSkipListMapSerializer
      extends SortedMapSerializer<ConcurrentSkipListMap> {

    public ConcurrentSkipListMapSerializer(Fory fory, Class<ConcurrentSkipListMap> cls) {
      super(fory, cls);
    }

    @Override
    public ConcurrentSkipListMap newMap(MemoryBuffer buffer) {
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      Comparator comparator = (Comparator) fory.readRef(buffer);
      ConcurrentSkipListMap map = new ConcurrentSkipListMap(comparator);
      fory.getRefResolver().reference(map);
      return map;
    }

    @Override
    public Map newMap(Map originMap) {
      Comparator comparator = fory.copyObject(((ConcurrentSkipListMap) originMap).comparator());
      return new ConcurrentSkipListMap(comparator);
    }
  }

  public static class EnumMapSerializer extends MapSerializer<EnumMap> {
    // Make offset compatible with graalvm native image.
    private static final long keyTypeFieldOffset;

    static {
      try {
        keyTypeFieldOffset = Platform.objectFieldOffset(EnumMap.class.getDeclaredField("keyType"));
      } catch (final Exception e) {
        throw new RuntimeException(e);
      }
    }

    public EnumMapSerializer(Fory fory) {
      // getMapKeyValueType(EnumMap.class) will be `K, V` without Enum as key bound.
      // so no need to infer key generics in init.
      super(fory, EnumMap.class, true);
    }

    @Override
    public Map onMapWrite(MemoryBuffer buffer, EnumMap value) {
      buffer.writeVarUint32Small7(value.size());
      Class keyType = (Class) Platform.getObject(value, keyTypeFieldOffset);
      fory.getClassResolver().writeClassAndUpdateCache(buffer, keyType);
      return value;
    }

    @Override
    public EnumMap newMap(MemoryBuffer buffer) {
      setNumElements(buffer.readVarUint32Small7());
      Class<?> keyType = fory.getClassResolver().readClassInfo(buffer).getCls();
      return new EnumMap(keyType);
    }

    @Override
    public EnumMap copy(EnumMap originMap) {
      return new EnumMap(originMap);
    }
  }

  public static class StringKeyMapSerializer<T> extends MapSerializer<Map<String, T>> {

    public StringKeyMapSerializer(Fory fory, Class<Map<String, T>> cls) {
      super(fory, cls, false);
      setKeySerializer(new StringSerializer(fory));
    }

    @Override
    public void write(MemoryBuffer buffer, Map<String, T> value) {
      buffer.writeVarUint32Small7(value.size());
      for (Map.Entry<String, T> e : value.entrySet()) {
        fory.writeJavaStringRef(buffer, e.getKey());
        // If value is a collection, the `newCollection` method will record itself to
        // reference map, which may get wrong index if this value is written without index.
        fory.writeRef(buffer, e.getValue());
      }
    }

    @Override
    public Map<String, T> read(MemoryBuffer buffer) {
      Map map = newMap(buffer);
      int numElements = getAndClearNumElements();
      for (int i = 0; i < numElements; i++) {
        map.put(fory.readJavaStringRef(buffer), fory.readRef(buffer));
      }
      return (Map<String, T>) map;
    }

    @Override
    protected <K, V> void copyEntry(Map<K, V> originMap, Map<K, V> newMap) {
      ClassResolver classResolver = fory.getClassResolver();
      for (Entry<K, V> entry : originMap.entrySet()) {
        V value = entry.getValue();
        if (value != null) {
          ClassInfo classInfo =
              classResolver.getClassInfo(value.getClass(), valueClassInfoWriteCache);
          if (!classInfo.getSerializer().isImmutable()) {
            value = fory.copyObject(value, classInfo.getClassId());
          }
        }
        newMap.put(entry.getKey(), value);
      }
    }
  }

  /**
   * Java serializer to serialize all fields of a map implementation. Note that this serializer
   * won't use element generics and doesn't support JIT, performance won't be the best, but the
   * correctness can be ensured.
   */
  public static final class DefaultJavaMapSerializer<T> extends MapLikeSerializer<T> {
    private Serializer<T> dataSerializer;

    public DefaultJavaMapSerializer(Fory fory, Class<T> cls) {
      super(fory, cls, false);
      Preconditions.checkArgument(
          !fory.isCrossLanguage(),
          "Fory cross-language default map serializer should use " + MapSerializer.class);
      fory.getClassResolver().setSerializer(cls, this);
      Class<? extends Serializer> serializerClass =
          fory.getClassResolver()
              .getObjectSerializerClass(
                  cls, sc -> dataSerializer = Serializers.newSerializer(fory, cls, sc));
      dataSerializer = Serializers.newSerializer(fory, cls, serializerClass);
      // No need to set object serializer to this, it will be set in class resolver later.
      // fory.getClassResolver().setSerializer(cls, this);
    }

    @Override
    public Map onMapWrite(MemoryBuffer buffer, T value) {
      throw new IllegalStateException();
    }

    @Override
    public T onMapCopy(Map map) {
      throw new IllegalStateException();
    }

    @Override
    public T onMapRead(Map map) {
      throw new IllegalStateException();
    }

    @Override
    public void write(MemoryBuffer buffer, T value) {
      dataSerializer.write(buffer, value);
    }

    @Override
    public T copy(T value) {
      return fory.copyObject(value, dataSerializer);
    }

    @Override
    public T read(MemoryBuffer buffer) {
      return dataSerializer.read(buffer);
    }
  }

  /** Map serializer for class with JDK custom serialization methods defined. */
  public static class JDKCompatibleMapSerializer<T> extends MapLikeSerializer<T> {
    private final Serializer serializer;

    public JDKCompatibleMapSerializer(Fory fory, Class<T> cls) {
      super(fory, cls, false);
      // Map which defined `writeReplace` may use this serializer, so check replace/resolve
      // is necessary.
      Class<? extends Serializer> serializerType =
          ClassResolver.useReplaceResolveSerializer(cls)
              ? ReplaceResolveSerializer.class
              : fory.getDefaultJDKStreamSerializerType();
      serializer = Serializers.newSerializer(fory, cls, serializerType);
    }

    @Override
    public Map onMapWrite(MemoryBuffer buffer, T value) {
      throw new IllegalStateException();
    }

    @Override
    public T onMapCopy(Map map) {
      throw new IllegalStateException();
    }

    @Override
    public T onMapRead(Map map) {
      throw new IllegalStateException();
    }

    @SuppressWarnings("unchecked")
    @Override
    public T read(MemoryBuffer buffer) {
      return (T) serializer.read(buffer);
    }

    @Override
    public void write(MemoryBuffer buffer, T value) {
      serializer.write(buffer, value);
    }

    @Override
    public T copy(T value) {
      return fory.copyObject(value, (Serializer<T>) serializer);
    }
  }

  // TODO(chaokunyang) support ConcurrentSkipListMap.SubMap mo efficiently.
  public static void registerDefaultSerializers(Fory fory) {
    ClassResolver resolver = fory.getClassResolver();
    resolver.registerSerializer(HashMap.class, new HashMapSerializer(fory));
    fory.getClassResolver()
        .registerSerializer(LinkedHashMap.class, new LinkedHashMapSerializer(fory));
    resolver.registerSerializer(TreeMap.class, new SortedMapSerializer<>(fory, TreeMap.class));
    resolver.registerSerializer(
        Collections.EMPTY_MAP.getClass(),
        new EmptyMapSerializer(fory, (Class<Map<?, ?>>) Collections.EMPTY_MAP.getClass()));
    resolver.registerSerializer(
        Collections.emptySortedMap().getClass(),
        new EmptySortedMapSerializer(
            fory, (Class<SortedMap<?, ?>>) Collections.emptySortedMap().getClass()));
    resolver.registerSerializer(
        Collections.singletonMap(null, null).getClass(),
        new SingletonMapSerializer(
            fory, (Class<Map<?, ?>>) Collections.singletonMap(null, null).getClass()));
    resolver.registerSerializer(
        ConcurrentHashMap.class, new ConcurrentHashMapSerializer(fory, ConcurrentHashMap.class));
    resolver.registerSerializer(
        ConcurrentSkipListMap.class,
        new ConcurrentSkipListMapSerializer(fory, ConcurrentSkipListMap.class));
    resolver.registerSerializer(EnumMap.class, new EnumMapSerializer(fory));
    resolver.registerSerializer(LazyMap.class, new LazyMapSerializer(fory));
  }
}
