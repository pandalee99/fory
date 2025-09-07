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

import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.reflect.Field;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.BitSet;
import java.util.Collection;
import java.util.Collections;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.PriorityQueue;
import java.util.Set;
import java.util.SortedSet;
import java.util.TreeSet;
import java.util.Vector;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentSkipListSet;
import java.util.concurrent.CopyOnWriteArrayList;
import org.apache.fory.Fory;
import org.apache.fory.exception.ForyException;
import org.apache.fory.memory.MemoryBuffer;
import org.apache.fory.memory.Platform;
import org.apache.fory.reflect.ReflectionUtils;
import org.apache.fory.resolver.ClassInfo;
import org.apache.fory.resolver.ClassInfoHolder;
import org.apache.fory.resolver.ClassResolver;
import org.apache.fory.resolver.RefResolver;
import org.apache.fory.serializer.ReplaceResolveSerializer;
import org.apache.fory.serializer.Serializer;
import org.apache.fory.serializer.Serializers;
import org.apache.fory.util.Preconditions;
import org.apache.fory.util.unsafe._JDKAccess;

/**
 * Serializers for classes implements {@link Collection}. All collection serializers should extend
 * {@link CollectionSerializer}.
 */
@SuppressWarnings({"unchecked", "rawtypes"})
public class CollectionSerializers {

  public static final class ArrayListSerializer extends CollectionSerializer<ArrayList> {
    public ArrayListSerializer(Fory fory) {
      super(fory, ArrayList.class, true);
    }

    @Override
    public ArrayList newCollection(MemoryBuffer buffer) {
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      ArrayList arrayList = new ArrayList(numElements);
      fory.getRefResolver().reference(arrayList);
      return arrayList;
    }
  }

  public static final class ArraysAsListSerializer extends CollectionSerializer<List<?>> {
    // Make offset compatible with graalvm native image.
    private static final long arrayFieldOffset;

    static {
      try {
        Field arrayField = Class.forName("java.util.Arrays$ArrayList").getDeclaredField("a");
        arrayFieldOffset = Platform.objectFieldOffset(arrayField);
      } catch (final Exception e) {
        throw new RuntimeException(e);
      }
    }

    public ArraysAsListSerializer(Fory fory, Class<List<?>> cls) {
      super(fory, cls, fory.isCrossLanguage());
    }

    @Override
    public List<?> copy(List<?> originCollection) {
      Object[] elements = new Object[originCollection.size()];
      List<?> newCollection = Arrays.asList(elements);
      if (needToCopyRef) {
        fory.reference(originCollection, newCollection);
      }
      copyElements(originCollection, elements);
      return newCollection;
    }

    @Override
    public void write(MemoryBuffer buffer, List<?> value) {
      try {
        final Object[] array = (Object[]) Platform.getObject(value, arrayFieldOffset);
        fory.writeRef(buffer, array);
      } catch (Exception e) {
        throw new RuntimeException(e);
      }
    }

    @Override
    public List<?> read(MemoryBuffer buffer) {
      final Object[] array = (Object[]) fory.readRef(buffer);
      Preconditions.checkNotNull(array);
      return Arrays.asList(array);
    }

    @Override
    public void xwrite(MemoryBuffer buffer, List<?> value) {
      super.write(buffer, value);
    }

    @Override
    public List<?> xread(MemoryBuffer buffer) {
      return super.read(buffer);
    }

    @Override
    public ArrayList newCollection(MemoryBuffer buffer) {
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      ArrayList arrayList = new ArrayList(numElements);
      fory.getRefResolver().reference(arrayList);
      return arrayList;
    }
  }

  public static final class HashSetSerializer extends CollectionSerializer<HashSet> {
    public HashSetSerializer(Fory fory) {
      super(fory, HashSet.class, true);
    }

    @Override
    public HashSet newCollection(MemoryBuffer buffer) {
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      HashSet hashSet = new HashSet(numElements);
      fory.getRefResolver().reference(hashSet);
      return hashSet;
    }
  }

  public static final class LinkedHashSetSerializer extends CollectionSerializer<LinkedHashSet> {
    public LinkedHashSetSerializer(Fory fory) {
      super(fory, LinkedHashSet.class, true);
    }

    @Override
    public LinkedHashSet newCollection(MemoryBuffer buffer) {
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      LinkedHashSet hashSet = new LinkedHashSet(numElements);
      fory.getRefResolver().reference(hashSet);
      return hashSet;
    }
  }

  public static class SortedSetSerializer<T extends SortedSet> extends CollectionSerializer<T> {
    private MethodHandle constructor;

    public SortedSetSerializer(Fory fory, Class<T> cls) {
      super(fory, cls, true);
      if (cls != TreeSet.class) {
        try {
          constructor = ReflectionUtils.getCtrHandle(cls, Comparator.class);
        } catch (Exception e) {
          throw new UnsupportedOperationException(e);
        }
      }
    }

    @Override
    public Collection onCollectionWrite(MemoryBuffer buffer, T value) {
      buffer.writeVarUint32Small7(value.size());
      if (!fory.isCrossLanguage()) {
        fory.writeRef(buffer, value.comparator());
      }
      return value;
    }

    @SuppressWarnings("unchecked")
    @Override
    public T newCollection(MemoryBuffer buffer) {
      assert !fory.isCrossLanguage();
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      T collection;
      Comparator comparator = (Comparator) fory.readRef(buffer);
      if (type == TreeSet.class) {
        collection = (T) new TreeSet(comparator);
      } else {
        try {
          collection = (T) constructor.invoke(comparator);
        } catch (Throwable e) {
          throw new RuntimeException(e);
        }
      }
      fory.getRefResolver().reference(collection);
      return collection;
    }

    @Override
    public Collection newCollection(Collection originCollection) {
      Collection collection;
      Comparator comparator = fory.copyObject(((SortedSet) originCollection).comparator());
      if (Objects.equals(type, TreeSet.class)) {
        collection = new TreeSet(comparator);
      } else {
        try {
          collection = (T) constructor.invoke(comparator);
        } catch (Throwable e) {
          throw new RuntimeException(e);
        }
      }
      return collection;
    }
  }

  // ------------------------------ collections serializers ------------------------------ //
  // For cross-language serialization, if the data is passed from python, the data will be
  // deserialized by `MapSerializers` and `CollectionSerializers`.
  // But if the data is serialized by following collections serializers, we need to ensure the real
  // type of `xread` is the same as the type when serializing.
  public static final class EmptyListSerializer extends CollectionSerializer<List<?>> {

    public EmptyListSerializer(Fory fory, Class<List<?>> cls) {
      super(fory, cls, false, true);
    }

    @Override
    public void write(MemoryBuffer buffer, List<?> value) {}

    @Override
    public void xwrite(MemoryBuffer buffer, List<?> value) {
      // write length
      buffer.writeVarUint32Small7(0);
    }

    @Override
    public List<?> read(MemoryBuffer buffer) {
      return Collections.EMPTY_LIST;
    }

    @Override
    public List<?> xread(MemoryBuffer buffer) {
      buffer.readVarUint32Small7();
      return Collections.EMPTY_LIST;
    }
  }

  public static class CopyOnWriteArrayListSerializer
      extends CollectionSerializer<CopyOnWriteArrayList> {

    public CopyOnWriteArrayListSerializer(Fory fory, Class<CopyOnWriteArrayList> type) {
      super(fory, type);
    }

    @Override
    public Collection newCollection(MemoryBuffer buffer) {
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      return new CollectionContainer<>(numElements);
    }

    @Override
    public CopyOnWriteArrayList onCollectionRead(Collection collection) {
      Object[] elements = ((CollectionContainer) collection).elements;
      return new CopyOnWriteArrayList(elements);
    }
  }

  public static final class EmptySetSerializer extends CollectionSerializer<Set<?>> {

    public EmptySetSerializer(Fory fory, Class<Set<?>> cls) {
      super(fory, cls, fory.isCrossLanguage(), true);
    }

    @Override
    public void write(MemoryBuffer buffer, Set<?> value) {}

    @Override
    public void xwrite(MemoryBuffer buffer, Set<?> value) {
      super.write(buffer, value);
    }

    @Override
    public Set<?> read(MemoryBuffer buffer) {
      return Collections.EMPTY_SET;
    }

    @Override
    public Set<?> xread(MemoryBuffer buffer) {
      throw new UnsupportedOperationException();
    }
  }

  public static final class EmptySortedSetSerializer extends CollectionSerializer<SortedSet<?>> {

    public EmptySortedSetSerializer(Fory fory, Class<SortedSet<?>> cls) {
      super(fory, cls, fory.isCrossLanguage(), true);
    }

    @Override
    public void write(MemoryBuffer buffer, SortedSet<?> value) {}

    @Override
    public SortedSet<?> read(MemoryBuffer buffer) {
      return Collections.emptySortedSet();
    }

    @Override
    public void xwrite(MemoryBuffer buffer, SortedSet<?> value) {
      super.write(buffer, value);
    }

    @Override
    public SortedSet<?> xread(MemoryBuffer buffer) {
      throw new UnsupportedOperationException();
    }
  }

  public static final class CollectionsSingletonListSerializer
      extends CollectionSerializer<List<?>> {

    public CollectionsSingletonListSerializer(Fory fory, Class<List<?>> cls) {
      super(fory, cls, fory.isCrossLanguage());
    }

    @Override
    public List<?> copy(List<?> originCollection) {
      return Collections.singletonList(fory.copyObject(originCollection.get(0)));
    }

    @Override
    public void write(MemoryBuffer buffer, List<?> value) {
      fory.writeRef(buffer, value.get(0));
    }

    @Override
    public void xwrite(MemoryBuffer buffer, List<?> value) {
      super.write(buffer, value);
    }

    @Override
    public List<?> read(MemoryBuffer buffer) {
      return Collections.singletonList(fory.readRef(buffer));
    }

    @Override
    public List<?> xread(MemoryBuffer buffer) {
      throw new UnsupportedOperationException();
    }
  }

  public static final class CollectionsSingletonSetSerializer extends CollectionSerializer<Set<?>> {

    public CollectionsSingletonSetSerializer(Fory fory, Class<Set<?>> cls) {
      super(fory, cls, fory.isCrossLanguage());
    }

    @Override
    public Set<?> copy(Set<?> originCollection) {
      return Collections.singleton(fory.copyObject(originCollection.iterator().next()));
    }

    @Override
    public void write(MemoryBuffer buffer, Set<?> value) {
      fory.writeRef(buffer, value.iterator().next());
    }

    @Override
    public void xwrite(MemoryBuffer buffer, Set<?> value) {
      super.write(buffer, value);
    }

    @Override
    public Set<?> read(MemoryBuffer buffer) {
      return Collections.singleton(fory.readRef(buffer));
    }

    @Override
    public Set<?> xread(MemoryBuffer buffer) {
      throw new UnsupportedOperationException();
    }
  }

  public static final class ConcurrentSkipListSetSerializer
      extends SortedSetSerializer<ConcurrentSkipListSet> {

    public ConcurrentSkipListSetSerializer(Fory fory, Class<ConcurrentSkipListSet> cls) {
      super(fory, cls);
    }

    @Override
    public ConcurrentSkipListSet newCollection(MemoryBuffer buffer) {
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      assert !fory.isCrossLanguage();
      RefResolver refResolver = fory.getRefResolver();
      int refId = refResolver.lastPreservedRefId();
      // It's possible that comparator/elements has circular ref to set.
      Comparator comparator = (Comparator) fory.readRef(buffer);
      ConcurrentSkipListSet skipListSet = new ConcurrentSkipListSet(comparator);
      refResolver.setReadObject(refId, skipListSet);
      return skipListSet;
    }
  }

  public static final class SetFromMapSerializer extends CollectionSerializer<Set<?>> {

    private static final long MAP_FIELD_OFFSET;
    private static final List EMPTY_COLLECTION_STUB = new ArrayList<>();

    private static final MethodHandle m;

    private static final MethodHandle s;

    static {
      try {
        Class<?> type = Class.forName("java.util.Collections$SetFromMap");
        Field mapField = type.getDeclaredField("m");
        MAP_FIELD_OFFSET = Platform.objectFieldOffset(mapField);
        MethodHandles.Lookup lookup = _JDKAccess._trustedLookup(type);
        m = lookup.findSetter(type, "m", Map.class);
        s = lookup.findSetter(type, "s", Set.class);
      } catch (final Exception e) {
        throw new RuntimeException(e);
      }
    }

    public SetFromMapSerializer(Fory fory, Class<Set<?>> type) {
      super(fory, type, true);
    }

    @Override
    public Collection newCollection(MemoryBuffer buffer) {
      final ClassInfo mapClassInfo = fory.getClassResolver().readClassInfo(buffer);
      final MapLikeSerializer mapSerializer = (MapLikeSerializer) mapClassInfo.getSerializer();
      RefResolver refResolver = fory.getRefResolver();
      // It's possible that elements or nested fields has circular ref to set.
      int refId = refResolver.lastPreservedRefId();
      Set set;
      if (buffer.readBoolean()) {
        refResolver.preserveRefId();
        set = Collections.newSetFromMap(mapSerializer.newMap(buffer));
        setNumElements(mapSerializer.getAndClearNumElements());
      } else {
        Map map = (Map) mapSerializer.read(buffer);
        try {
          set = Platform.newInstance(type);
          m.invoke(set, map);
          s.invoke(set, map.keySet());
        } catch (Throwable e) {
          throw new RuntimeException(e);
        }
        setNumElements(0);
      }
      refResolver.setReadObject(refId, set);
      return set;
    }

    @Override
    public Collection newCollection(Collection originCollection) {
      assert !fory.isCrossLanguage();
      Map<?, Boolean> map =
          (Map<?, Boolean>) Platform.getObject(originCollection, MAP_FIELD_OFFSET);
      MapLikeSerializer mapSerializer =
          (MapLikeSerializer) fory.getClassResolver().getSerializer(map.getClass());
      Map newMap = mapSerializer.newMap(map);
      return Collections.newSetFromMap(newMap);
    }

    @Override
    public Collection onCollectionWrite(MemoryBuffer buffer, Set<?> value) {
      final Map<?, Boolean> map = (Map<?, Boolean>) Platform.getObject(value, MAP_FIELD_OFFSET);
      final ClassInfo classInfo = fory.getClassResolver().getClassInfo(map.getClass());
      MapLikeSerializer mapSerializer = (MapLikeSerializer) classInfo.getSerializer();
      fory.getClassResolver().writeClassInfo(buffer, classInfo);
      if (mapSerializer.supportCodegenHook) {
        buffer.writeBoolean(true);
        mapSerializer.onMapWrite(buffer, map);
        return value;
      } else {
        buffer.writeBoolean(false);
        mapSerializer.write(buffer, map);
        return EMPTY_COLLECTION_STUB;
      }
    }
  }

  public static final class ConcurrentHashMapKeySetViewSerializer
      extends CollectionSerializer<ConcurrentHashMap.KeySetView> {
    private final ClassInfoHolder mapClassInfoHolder;
    private final ClassInfoHolder valueClassInfoHolder;

    public ConcurrentHashMapKeySetViewSerializer(
        Fory fory, Class<ConcurrentHashMap.KeySetView> type) {
      super(fory, type, false);
      mapClassInfoHolder = fory.getClassResolver().nilClassInfoHolder();
      valueClassInfoHolder = fory.getClassResolver().nilClassInfoHolder();
    }

    @Override
    public void write(MemoryBuffer buffer, ConcurrentHashMap.KeySetView value) {
      fory.writeRef(buffer, value.getMap(), mapClassInfoHolder);
      fory.writeRef(buffer, value.getMappedValue(), valueClassInfoHolder);
    }

    @Override
    public ConcurrentHashMap.KeySetView read(MemoryBuffer buffer) {
      ConcurrentHashMap map = (ConcurrentHashMap) fory.readRef(buffer, mapClassInfoHolder);
      Object value = fory.readRef(buffer, valueClassInfoHolder);
      return map.keySet(value);
    }

    @Override
    public ConcurrentHashMap.KeySetView copy(ConcurrentHashMap.KeySetView value) {
      ConcurrentHashMap newMap = fory.copyObject(value.getMap());
      return newMap.keySet(fory.copyObject(value.getMappedValue()));
    }

    @Override
    public Collection newCollection(MemoryBuffer buffer) {
      throw new IllegalStateException(
          "Should not be invoked since we set supportCodegenHook to false");
    }
  }

  public static final class VectorSerializer extends CollectionSerializer<Vector> {

    public VectorSerializer(Fory fory, Class<Vector> cls) {
      super(fory, cls, true);
    }

    @Override
    public Vector newCollection(MemoryBuffer buffer) {
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      Vector<Object> vector = new Vector<>(numElements);
      fory.getRefResolver().reference(vector);
      return vector;
    }
  }

  public static final class ArrayDequeSerializer extends CollectionSerializer<ArrayDeque> {

    public ArrayDequeSerializer(Fory fory, Class<ArrayDeque> cls) {
      super(fory, cls, true);
    }

    @Override
    public ArrayDeque newCollection(MemoryBuffer buffer) {
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      ArrayDeque deque = new ArrayDeque(numElements);
      fory.getRefResolver().reference(deque);
      return deque;
    }
  }

  public static class EnumSetSerializer extends CollectionSerializer<EnumSet> {
    public EnumSetSerializer(Fory fory, Class<EnumSet> type) {
      // getElementType(EnumSet.class) will be `E` without Enum as bound.
      // so no need to infer generics in init.
      super(fory, type, false);
    }

    @Override
    public void write(MemoryBuffer buffer, EnumSet object) {
      Class<?> elemClass;
      if (object.isEmpty()) {
        EnumSet tmp = EnumSet.complementOf(object);
        if (tmp.isEmpty()) {
          throw new ForyException("An EnumSet must have a defined Enum to be serialized.");
        }
        elemClass = tmp.iterator().next().getClass();
      } else {
        elemClass = object.iterator().next().getClass();
      }
      fory.getClassResolver().writeClassAndUpdateCache(buffer, elemClass);
      Serializer serializer = fory.getClassResolver().getSerializer(elemClass);
      buffer.writeVarUint32Small7(object.size());
      for (Object element : object) {
        serializer.write(buffer, element);
      }
    }

    @Override
    public EnumSet read(MemoryBuffer buffer) {
      Class elemClass = fory.getClassResolver().readClassInfo(buffer).getCls();
      EnumSet object = EnumSet.noneOf(elemClass);
      Serializer elemSerializer = fory.getClassResolver().getSerializer(elemClass);
      int length = buffer.readVarUint32Small7();
      for (int i = 0; i < length; i++) {
        object.add(elemSerializer.read(buffer));
      }
      return object;
    }

    @Override
    public EnumSet copy(EnumSet originCollection) {
      return EnumSet.copyOf(originCollection);
    }
  }

  public static class BitSetSerializer extends Serializer<BitSet> {
    public BitSetSerializer(Fory fory, Class<BitSet> type) {
      super(fory, type);
    }

    @Override
    public void write(MemoryBuffer buffer, BitSet set) {
      long[] values = set.toLongArray();
      buffer.writePrimitiveArrayWithSize(
          values, Platform.LONG_ARRAY_OFFSET, Math.multiplyExact(values.length, 8));
    }

    @Override
    public BitSet copy(BitSet originCollection) {
      return BitSet.valueOf(originCollection.toLongArray());
    }

    @Override
    public BitSet read(MemoryBuffer buffer) {
      long[] values = buffer.readLongs(buffer.readVarUint32Small7());
      return BitSet.valueOf(values);
    }
  }

  public static class PriorityQueueSerializer extends CollectionSerializer<PriorityQueue> {
    public PriorityQueueSerializer(Fory fory, Class<PriorityQueue> cls) {
      super(fory, cls, true);
    }

    public Collection onCollectionWrite(MemoryBuffer buffer, PriorityQueue value) {
      buffer.writeVarUint32Small7(value.size());
      if (!fory.isCrossLanguage()) {
        fory.writeRef(buffer, value.comparator());
      }
      return value;
    }

    @Override
    public Collection newCollection(Collection collection) {
      return new PriorityQueue(
          collection.size(), fory.copyObject(((PriorityQueue) collection).comparator()));
    }

    @Override
    public PriorityQueue newCollection(MemoryBuffer buffer) {
      assert !fory.isCrossLanguage();
      int numElements = buffer.readVarUint32Small7();
      setNumElements(numElements);
      Comparator comparator = (Comparator) fory.readRef(buffer);
      PriorityQueue queue = new PriorityQueue(comparator);
      fory.getRefResolver().reference(queue);
      return queue;
    }
  }

  /**
   * Java serializer to serialize all fields of a collection implementation. Note that this
   * serializer won't use element generics and doesn't support JIT, performance won't be the best,
   * but the correctness can be ensured.
   */
  public static final class DefaultJavaCollectionSerializer<T> extends CollectionLikeSerializer<T> {
    private Serializer<T> dataSerializer;

    public DefaultJavaCollectionSerializer(Fory fory, Class<T> cls) {
      super(fory, cls, false);
      Preconditions.checkArgument(
          !fory.isCrossLanguage(),
          "Fory cross-language default collection serializer should use "
              + CollectionSerializer.class);
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
    public Collection onCollectionWrite(MemoryBuffer buffer, T value) {
      throw new IllegalStateException();
    }

    @Override
    public T onCollectionRead(Collection collection) {
      throw new IllegalStateException();
    }

    @Override
    public void write(MemoryBuffer buffer, T value) {
      dataSerializer.write(buffer, value);
    }

    @Override
    public T copy(T originCollection) {
      return fory.copyObject(originCollection, dataSerializer);
    }

    @Override
    public T read(MemoryBuffer buffer) {
      return dataSerializer.read(buffer);
    }
  }

  /** Collection serializer for class with JDK custom serialization methods defined. */
  public static final class JDKCompatibleCollectionSerializer<T>
      extends CollectionLikeSerializer<T> {
    private final Serializer serializer;

    public JDKCompatibleCollectionSerializer(Fory fory, Class<T> cls) {
      super(fory, cls, false);
      // Collection which defined `writeReplace` may use this serializer, so check replace/resolve
      // is necessary.
      Class<? extends Serializer> serializerType =
          ClassResolver.useReplaceResolveSerializer(cls)
              ? ReplaceResolveSerializer.class
              : fory.getDefaultJDKStreamSerializerType();
      serializer = Serializers.newSerializer(fory, cls, serializerType);
    }

    @Override
    public Collection onCollectionWrite(MemoryBuffer buffer, T value) {
      throw new IllegalStateException();
    }

    @SuppressWarnings("unchecked")
    @Override
    public T read(MemoryBuffer buffer) {
      return (T) serializer.read(buffer);
    }

    @Override
    public T onCollectionRead(Collection collection) {
      throw new IllegalStateException();
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

  // TODO add JDK11:JdkImmutableListSerializer,JdkImmutableMapSerializer,JdkImmutableSetSerializer
  //  by jit codegen those constructor for compiling in jdk8.
  // TODO Support ArraySubListSerializer, SubListSerializer

  public static void registerDefaultSerializers(Fory fory) {
    ClassResolver resolver = fory.getClassResolver();
    resolver.registerSerializer(ArrayList.class, new ArrayListSerializer(fory));
    Class arrayAsListClass = Arrays.asList(1, 2).getClass();
    resolver.registerSerializer(
        arrayAsListClass, new ArraysAsListSerializer(fory, arrayAsListClass));
    resolver.registerSerializer(
        LinkedList.class, new CollectionSerializer(fory, LinkedList.class, true));
    resolver.registerSerializer(HashSet.class, new HashSetSerializer(fory));
    resolver.registerSerializer(LinkedHashSet.class, new LinkedHashSetSerializer(fory));
    resolver.registerSerializer(TreeSet.class, new SortedSetSerializer<>(fory, TreeSet.class));
    resolver.registerSerializer(
        Collections.EMPTY_LIST.getClass(),
        new EmptyListSerializer(fory, (Class<List<?>>) Collections.EMPTY_LIST.getClass()));
    resolver.registerSerializer(
        Collections.emptySortedSet().getClass(),
        new EmptySortedSetSerializer(
            fory, (Class<SortedSet<?>>) Collections.emptySortedSet().getClass()));
    resolver.registerSerializer(
        Collections.EMPTY_SET.getClass(),
        new EmptySetSerializer(fory, (Class<Set<?>>) Collections.EMPTY_SET.getClass()));
    resolver.registerSerializer(
        Collections.singletonList(null).getClass(),
        new CollectionsSingletonListSerializer(
            fory, (Class<List<?>>) Collections.singletonList(null).getClass()));
    resolver.registerSerializer(
        Collections.singleton(null).getClass(),
        new CollectionsSingletonSetSerializer(
            fory, (Class<Set<?>>) Collections.singleton(null).getClass()));
    resolver.registerSerializer(
        ConcurrentSkipListSet.class,
        new ConcurrentSkipListSetSerializer(fory, ConcurrentSkipListSet.class));
    resolver.registerSerializer(Vector.class, new VectorSerializer(fory, Vector.class));
    resolver.registerSerializer(ArrayDeque.class, new ArrayDequeSerializer(fory, ArrayDeque.class));
    resolver.registerSerializer(BitSet.class, new BitSetSerializer(fory, BitSet.class));
    resolver.registerSerializer(
        PriorityQueue.class, new PriorityQueueSerializer(fory, PriorityQueue.class));
    resolver.registerSerializer(
        CopyOnWriteArrayList.class,
        new CopyOnWriteArrayListSerializer(fory, CopyOnWriteArrayList.class));
    final Class setFromMapClass = Collections.newSetFromMap(new HashMap<>()).getClass();
    resolver.registerSerializer(setFromMapClass, new SetFromMapSerializer(fory, setFromMapClass));
    resolver.registerSerializer(
        ConcurrentHashMap.KeySetView.class,
        new ConcurrentHashMapKeySetViewSerializer(fory, ConcurrentHashMap.KeySetView.class));
  }
}
