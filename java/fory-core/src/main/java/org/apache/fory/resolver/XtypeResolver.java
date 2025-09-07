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

package org.apache.fory.resolver;

import static org.apache.fory.Fory.NOT_SUPPORT_XLANG;
import static org.apache.fory.builder.Generated.GeneratedSerializer;
import static org.apache.fory.meta.Encoders.GENERIC_ENCODER;
import static org.apache.fory.meta.Encoders.PACKAGE_DECODER;
import static org.apache.fory.meta.Encoders.PACKAGE_ENCODER;
import static org.apache.fory.meta.Encoders.TYPE_NAME_DECODER;
import static org.apache.fory.resolver.ClassResolver.NO_CLASS_ID;
import static org.apache.fory.serializer.collection.MapSerializers.HashMapSerializer;
import static org.apache.fory.type.TypeUtils.qualifiedName;

import java.lang.reflect.Type;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import org.apache.fory.Fory;
import org.apache.fory.collection.IdentityMap;
import org.apache.fory.collection.IdentityObjectIntMap;
import org.apache.fory.collection.LongMap;
import org.apache.fory.collection.ObjectMap;
import org.apache.fory.config.Config;
import org.apache.fory.exception.ClassUnregisteredException;
import org.apache.fory.exception.SerializerUnregisteredException;
import org.apache.fory.logging.Logger;
import org.apache.fory.logging.LoggerFactory;
import org.apache.fory.memory.MemoryBuffer;
import org.apache.fory.memory.Platform;
import org.apache.fory.meta.ClassDef;
import org.apache.fory.meta.Encoders;
import org.apache.fory.meta.MetaString;
import org.apache.fory.reflect.ReflectionUtils;
import org.apache.fory.reflect.TypeRef;
import org.apache.fory.serializer.ArraySerializers;
import org.apache.fory.serializer.EnumSerializer;
import org.apache.fory.serializer.LazySerializer;
import org.apache.fory.serializer.NonexistentClass;
import org.apache.fory.serializer.NonexistentClassSerializers;
import org.apache.fory.serializer.ObjectSerializer;
import org.apache.fory.serializer.SerializationUtils;
import org.apache.fory.serializer.Serializer;
import org.apache.fory.serializer.Serializers;
import org.apache.fory.serializer.collection.CollectionLikeSerializer;
import org.apache.fory.serializer.collection.CollectionSerializer;
import org.apache.fory.serializer.collection.CollectionSerializers.ArrayListSerializer;
import org.apache.fory.serializer.collection.CollectionSerializers.HashSetSerializer;
import org.apache.fory.serializer.collection.MapLikeSerializer;
import org.apache.fory.serializer.collection.MapSerializer;
import org.apache.fory.type.GenericType;
import org.apache.fory.type.Generics;
import org.apache.fory.type.TypeUtils;
import org.apache.fory.type.Types;
import org.apache.fory.util.Preconditions;

@SuppressWarnings({"unchecked", "rawtypes"})
// TODO(chaokunyang) Abstract type resolver for java/xlang type resolution.
public class XtypeResolver implements TypeResolver {
  private static final Logger LOG = LoggerFactory.getLogger(XtypeResolver.class);

  private static final float loadFactor = 0.5f;
  // Most systems won't have so many types for serialization.
  private static final int MAX_TYPE_ID = 4096;

  private final Config config;
  private final Fory fory;
  private final ClassResolver classResolver;
  private final ClassInfoHolder classInfoCache = new ClassInfoHolder(ClassResolver.NIL_CLASS_INFO);
  private final MetaStringResolver metaStringResolver;
  // IdentityMap has better lookup performance, when loadFactor is 0.05f, performance is better
  private final IdentityMap<Class<?>, ClassInfo> classInfoMap = new IdentityMap<>(64, loadFactor);
  // Every deserialization for unregistered class will query it, performance is important.
  private final ObjectMap<TypeNameBytes, ClassInfo> compositeClassNameBytes2ClassInfo =
      new ObjectMap<>(16, loadFactor);
  private final ObjectMap<String, ClassInfo> qualifiedType2ClassInfo =
      new ObjectMap<>(16, loadFactor);
  private final Map<Class<?>, ClassDef> classDefMap = new HashMap<>();
  private final boolean shareMeta;
  private int xtypeIdGenerator = 64;

  // Use ClassInfo[] or LongMap?
  // ClassInfo[] is faster, but we can't have bigger type id.
  private final LongMap<ClassInfo> xtypeIdToClassMap = new LongMap<>(8, loadFactor);
  private final Set<Integer> registeredTypeIds = new HashSet<>();
  private final Generics generics;

  public XtypeResolver(Fory fory) {
    this.config = fory.getConfig();
    this.fory = fory;
    this.classResolver = fory.getClassResolver();
    classResolver.xtypeResolver = this;
    shareMeta = fory.getConfig().isMetaShareEnabled();
    this.generics = fory.getGenerics();
    this.metaStringResolver = fory.getMetaStringResolver();
  }

  @Override
  public void initialize() {
    registerDefaultTypes();
  }

  public void register(Class<?> type) {
    while (registeredTypeIds.contains(xtypeIdGenerator)) {
      xtypeIdGenerator++;
    }
    register(type, xtypeIdGenerator++);
  }

  public void register(Class<?> type, int typeId) {
    // ClassInfo[] has length of max type id. If the type id is too big, Fory will waste many
    // memory.
    // We can relax this limit in the future.
    Preconditions.checkArgument(typeId < MAX_TYPE_ID, "Too big type id %s", typeId);
    ClassInfo classInfo = classInfoMap.get(type);
    if (type.isArray()) {
      buildClassInfo(type);
      return;
    }
    Serializer<?> serializer = null;
    if (classInfo != null) {
      serializer = classInfo.serializer;
      if (classInfo.xtypeId != 0) {
        throw new IllegalArgumentException(
            String.format("Type %s has been registered with id %s", type, classInfo.xtypeId));
      }
      String prevNamespace = classInfo.decodeNamespace();
      String prevTypeName = classInfo.decodeTypeName();
      if (!type.getSimpleName().equals(prevTypeName)) {
        throw new IllegalArgumentException(
            String.format(
                "Type %s has been registered with namespace %s type %s",
                type, prevNamespace, prevTypeName));
      }
    }
    int xtypeId = typeId;
    if (type.isEnum()) {
      xtypeId = (xtypeId << 8) + Types.ENUM;
    } else {
      if (serializer != null) {
        if (isStructType(serializer)) {
          xtypeId = (xtypeId << 8) + Types.STRUCT;
        } else {
          xtypeId = (xtypeId << 8) + Types.EXT;
        }
      }
    }
    register(
        type,
        serializer,
        ReflectionUtils.getPackage(type),
        ReflectionUtils.getClassNameWithoutPackage(type),
        xtypeId);
  }

  public void register(Class<?> type, String namespace, String typeName) {
    Preconditions.checkArgument(
        !typeName.contains("."),
        "Typename %s should not contains `.`, please put it into namespace",
        typeName);
    ClassInfo classInfo = classInfoMap.get(type);
    Serializer<?> serializer = null;
    if (classInfo != null) {
      serializer = classInfo.serializer;
      if (classInfo.typeNameBytes != null) {
        String prevNamespace = classInfo.decodeNamespace();
        String prevTypeName = classInfo.decodeTypeName();
        if (!namespace.equals(prevNamespace) || typeName.equals(prevTypeName)) {
          throw new IllegalArgumentException(
              String.format(
                  "Type %s has been registered with namespace %s type %s",
                  type, prevNamespace, prevTypeName));
        }
      }
    }
    short xtypeId;
    if (serializer != null) {
      if (isStructType(serializer)) {
        xtypeId = Types.NAMED_STRUCT;
      } else if (serializer instanceof EnumSerializer) {
        xtypeId = Types.NAMED_ENUM;
      } else {
        xtypeId = Types.NAMED_EXT;
      }
    } else {
      if (type.isEnum()) {
        xtypeId = Types.NAMED_ENUM;
      } else {
        xtypeId = Types.NAMED_STRUCT;
      }
    }
    register(type, serializer, namespace, typeName, xtypeId);
  }

  private void register(
      Class<?> type, Serializer<?> serializer, String namespace, String typeName, int xtypeId) {
    ClassInfo classInfo = newClassInfo(type, serializer, namespace, typeName, (short) xtypeId);
    qualifiedType2ClassInfo.put(qualifiedName(namespace, typeName), classInfo);
    if (serializer == null) {
      if (type.isEnum()) {
        classInfo.serializer = new EnumSerializer(fory, (Class<Enum>) type);
      } else {
        classInfo.serializer =
            new LazySerializer.LazyObjectSerializer(
                fory, type, () -> new ObjectSerializer<>(fory, type));
      }
    }
    classInfoMap.put(type, classInfo);
    registeredTypeIds.add(xtypeId);
    xtypeIdToClassMap.put(xtypeId, classInfo);
  }

  private boolean isStructType(Serializer serializer) {
    if (serializer instanceof ObjectSerializer || serializer instanceof GeneratedSerializer) {
      return true;
    }
    return serializer instanceof LazySerializer.LazyObjectSerializer;
  }

  private ClassInfo newClassInfo(Class<?> type, Serializer<?> serializer, short xtypeId) {
    return newClassInfo(
        type,
        serializer,
        ReflectionUtils.getPackage(type),
        ReflectionUtils.getClassNameWithoutPackage(type),
        xtypeId);
  }

  private ClassInfo newClassInfo(
      Class<?> type, Serializer<?> serializer, String namespace, String typeName, short xtypeId) {
    MetaStringBytes fullClassNameBytes =
        metaStringResolver.getOrCreateMetaStringBytes(
            GENERIC_ENCODER.encode(type.getName(), MetaString.Encoding.UTF_8));
    MetaStringBytes nsBytes =
        metaStringResolver.getOrCreateMetaStringBytes(Encoders.encodePackage(namespace));
    MetaStringBytes classNameBytes =
        metaStringResolver.getOrCreateMetaStringBytes(Encoders.encodeTypeName(typeName));
    return new ClassInfo(
        type, fullClassNameBytes, nsBytes, classNameBytes, false, serializer, NO_CLASS_ID, xtypeId);
  }

  public <T> void registerSerializer(Class<T> type, Class<? extends Serializer> serializerClass) {
    ClassInfo classInfo = checkClassRegistration(type);
    if (!serializerClass.getPackage().getName().startsWith("org.apache.fory")) {
      SerializationUtils.validate(type, serializerClass);
    }
    classInfo.serializer = Serializers.newSerializer(fory, type, serializerClass);
  }

  public void registerSerializer(Class<?> type, Serializer<?> serializer) {
    ClassInfo classInfo = checkClassRegistration(type);
    if (!serializer.getClass().getPackage().getName().startsWith("org.apache.fory")) {
      SerializationUtils.validate(type, serializer.getClass());
    }
    classInfo.serializer = serializer;
  }

  private ClassInfo checkClassRegistration(Class<?> type) {
    ClassInfo classInfo = classInfoMap.get(type);
    Preconditions.checkArgument(
        classInfo != null
            && (classInfo.xtypeId != 0 || !type.getSimpleName().equals(classInfo.decodeTypeName())),
        "Type %s should be registered with id or namespace+typename before register serializer",
        type);
    return classInfo;
  }

  @Override
  public boolean isRegistered(Class<?> cls) {
    return classInfoMap.get(cls) != null;
  }

  @Override
  public boolean isRegisteredById(Class<?> cls) {
    ClassInfo classInfo = classInfoMap.get(cls);
    if (classInfo == null) {
      return false;
    }
    byte xtypeId = (byte) classInfo.xtypeId;
    if (xtypeId <= 0) {
      return false;
    }
    switch (xtypeId) {
      case Types.NAMED_COMPATIBLE_STRUCT:
      case Types.NAMED_ENUM:
      case Types.NAMED_STRUCT:
      case Types.NAMED_EXT:
        return false;
      default:
        return true;
    }
  }

  @Override
  public boolean isRegisteredByName(Class<?> cls) {
    ClassInfo classInfo = classInfoMap.get(cls);
    if (classInfo == null) {
      return false;
    }
    byte xtypeId = (byte) classInfo.xtypeId;
    if (xtypeId <= 0) {
      return false;
    }
    switch (xtypeId) {
      case Types.NAMED_COMPATIBLE_STRUCT:
      case Types.NAMED_ENUM:
      case Types.NAMED_STRUCT:
      case Types.NAMED_EXT:
        return true;
      default:
        return false;
    }
  }

  @Override
  public boolean isMonomorphic(Class<?> clz) {
    return classResolver.isMonomorphic(clz);
  }

  @Override
  public ClassInfo getClassInfo(Class<?> cls) {
    ClassInfo classInfo = classInfoMap.get(cls);
    if (classInfo == null) {
      classInfo = buildClassInfo(cls);
    }
    return classInfo;
  }

  @Override
  public ClassInfo getClassInfo(Class<?> cls, boolean createIfAbsent) {
    if (createIfAbsent) {
      return getClassInfo(cls);
    }
    return classInfoMap.get(cls);
  }

  public ClassInfo getClassInfo(Class<?> cls, ClassInfoHolder classInfoHolder) {
    ClassInfo classInfo = classInfoHolder.classInfo;
    if (classInfo.getCls() != cls) {
      classInfo = classInfoMap.get(cls);
      if (classInfo == null) {
        classInfo = buildClassInfo(cls);
      }
      classInfoHolder.classInfo = classInfo;
    }
    assert classInfo.serializer != null;
    return classInfo;
  }

  public ClassInfo getXtypeInfo(int typeId) {
    return xtypeIdToClassMap.get(typeId);
  }

  public ClassInfo getUserTypeInfo(String namespace, String typeName) {
    String name = qualifiedName(namespace, typeName);
    return qualifiedType2ClassInfo.get(name);
  }

  public ClassInfo getUserTypeInfo(int userTypeId) {
    Preconditions.checkArgument((byte) (userTypeId) < Types.UNKNOWN);
    return xtypeIdToClassMap.get(userTypeId);
  }

  @Override
  public boolean needToWriteRef(TypeRef<?> typeRef) {
    ClassInfo classInfo = classInfoMap.get(typeRef.getRawType());
    if (classInfo == null) {
      return fory.trackingRef();
    }
    return classInfo.serializer.needToWriteRef();
  }

  @Override
  public GenericType buildGenericType(TypeRef<?> typeRef) {
    return classResolver.buildGenericType(typeRef);
  }

  @Override
  public GenericType buildGenericType(Type type) {
    return classResolver.buildGenericType(type);
  }

  private ClassInfo buildClassInfo(Class<?> cls) {
    Serializer serializer;
    int xtypeId;
    if (classResolver.isSet(cls)) {
      if (cls.isAssignableFrom(HashSet.class)) {
        cls = HashSet.class;
        serializer = new HashSetSerializer(fory);
      } else {
        serializer = getCollectionSerializer(cls);
      }
      xtypeId = Types.SET;
    } else if (classResolver.isCollection(cls)) {
      if (cls.isAssignableFrom(ArrayList.class)) {
        cls = ArrayList.class;
        serializer = new ArrayListSerializer(fory);
      } else {
        serializer = getCollectionSerializer(cls);
      }
      xtypeId = Types.LIST;
    } else if (cls.isArray() && !cls.getComponentType().isPrimitive()) {
      serializer = new ArraySerializers.ObjectArraySerializer(fory, cls);
      xtypeId = Types.LIST;
    } else if (classResolver.isMap(cls)) {
      if (cls.isAssignableFrom(HashMap.class)) {
        cls = HashMap.class;
        serializer = new HashMapSerializer(fory);
      } else {
        ClassInfo classInfo = classResolver.getClassInfo(cls, false);
        if (classInfo != null && classInfo.serializer != null) {
          if (classInfo.serializer instanceof MapLikeSerializer
              && ((MapLikeSerializer) classInfo.serializer).supportCodegenHook()) {
            serializer = classInfo.serializer;
          } else {
            serializer = new MapSerializer(fory, cls);
          }
        } else {
          serializer = new MapSerializer(fory, cls);
        }
      }
      xtypeId = Types.MAP;
    } else {
      Class<Enum> enclosingClass = (Class<Enum>) cls.getEnclosingClass();
      if (enclosingClass != null && enclosingClass.isEnum()) {
        serializer = new EnumSerializer(fory, (Class<Enum>) cls);
        xtypeId = getClassInfo(enclosingClass).xtypeId;
      } else {
        throw new ClassUnregisteredException(cls);
      }
    }
    ClassInfo info = newClassInfo(cls, serializer, (short) xtypeId);
    classInfoMap.put(cls, info);
    return info;
  }

  private Serializer<?> getCollectionSerializer(Class<?> cls) {
    ClassInfo classInfo = classResolver.getClassInfo(cls, false);
    if (classInfo != null && classInfo.serializer != null) {
      if (classInfo.serializer instanceof CollectionLikeSerializer
          && ((CollectionLikeSerializer) (classInfo.serializer)).supportCodegenHook()) {
        return classInfo.serializer;
      }
    }
    return new CollectionSerializer(fory, cls);
  }

  private void registerDefaultTypes() {
    registerDefaultTypes(Types.BOOL, Boolean.class, boolean.class, AtomicBoolean.class);
    registerDefaultTypes(Types.INT8, Byte.class, byte.class);
    registerDefaultTypes(Types.INT16, Short.class, short.class);
    registerDefaultTypes(Types.INT32, Integer.class, int.class, AtomicInteger.class);
    registerDefaultTypes(Types.INT64, Long.class, long.class, AtomicLong.class);
    registerDefaultTypes(Types.FLOAT32, Float.class, float.class);
    registerDefaultTypes(Types.FLOAT64, Double.class, double.class);
    registerDefaultTypes(Types.STRING, String.class, StringBuilder.class, StringBuffer.class);
    registerDefaultTypes(Types.DURATION, Duration.class);
    registerDefaultTypes(
        Types.TIMESTAMP,
        Instant.class,
        Date.class,
        java.sql.Date.class,
        Timestamp.class,
        LocalDateTime.class);
    registerDefaultTypes(Types.DECIMAL, BigDecimal.class, BigInteger.class);
    registerDefaultTypes(
        Types.BINARY,
        byte[].class,
        Platform.HEAP_BYTE_BUFFER_CLASS,
        Platform.DIRECT_BYTE_BUFFER_CLASS);
    registerDefaultTypes(Types.BOOL_ARRAY, boolean[].class);
    registerDefaultTypes(Types.INT16_ARRAY, short[].class);
    registerDefaultTypes(Types.INT32_ARRAY, int[].class);
    registerDefaultTypes(Types.INT64_ARRAY, long[].class);
    registerDefaultTypes(Types.FLOAT32_ARRAY, float[].class);
    registerDefaultTypes(Types.FLOAT64_ARRAY, double[].class);
    registerDefaultTypes(Types.LIST, ArrayList.class, Object[].class);
    registerDefaultTypes(Types.SET, HashSet.class, LinkedHashSet.class);
    registerDefaultTypes(Types.MAP, HashMap.class, LinkedHashMap.class);
    registerDefaultTypes(Types.LOCAL_DATE, LocalDate.class);
  }

  private void registerDefaultTypes(int xtypeId, Class<?> defaultType, Class<?>... otherTypes) {
    ClassInfo classInfo =
        newClassInfo(defaultType, classResolver.getSerializer(defaultType), (short) xtypeId);
    classInfoMap.put(defaultType, classInfo);
    xtypeIdToClassMap.put(xtypeId, classInfo);
    for (Class<?> otherType : otherTypes) {
      classInfo = newClassInfo(otherType, classResolver.getSerializer(otherType), (short) xtypeId);
      classInfoMap.put(otherType, classInfo);
    }
  }

  public ClassInfo writeClassInfo(MemoryBuffer buffer, Object obj) {
    ClassInfo classInfo = getClassInfo(obj.getClass(), classInfoCache);
    writeClassInfo(buffer, classInfo);
    return classInfo;
  }

  @Override
  public void writeClassInfo(MemoryBuffer buffer, ClassInfo classInfo) {
    int xtypeId = classInfo.getXtypeId();
    byte internalTypeId = (byte) xtypeId;
    buffer.writeVarUint32Small7(xtypeId);
    switch (internalTypeId) {
      case Types.NAMED_ENUM:
      case Types.NAMED_STRUCT:
      case Types.NAMED_COMPATIBLE_STRUCT:
      case Types.NAMED_EXT:
        if (shareMeta) {
          writeSharedClassMeta(buffer, classInfo);
          return;
        }
        assert classInfo.namespaceBytes != null;
        metaStringResolver.writeMetaStringBytes(buffer, classInfo.namespaceBytes);
        assert classInfo.typeNameBytes != null;
        metaStringResolver.writeMetaStringBytes(buffer, classInfo.typeNameBytes);
        break;
      default:
        break;
    }
  }

  public void writeSharedClassMeta(MemoryBuffer buffer, ClassInfo classInfo) {
    MetaContext metaContext = fory.getSerializationContext().getMetaContext();
    assert metaContext != null : ClassResolver.SET_META__CONTEXT_MSG;
    IdentityObjectIntMap<Class<?>> classMap = metaContext.classMap;
    int newId = classMap.size;
    int id = classMap.putOrGet(classInfo.cls, newId);
    if (id >= 0) {
      buffer.writeVarUint32(id);
    } else {
      buffer.writeVarUint32(newId);
      ClassDef classDef = classInfo.classDef;
      if (classDef == null) {
        classDef = buildClassDef(classInfo);
      }
      metaContext.writingClassDefs.add(classDef);
    }
  }

  private ClassDef buildClassDef(ClassInfo classInfo) {
    ClassDef classDef =
        classDefMap.computeIfAbsent(classInfo.cls, cls -> ClassDef.buildClassDef(fory, cls));
    classInfo.classDef = classDef;
    return classDef;
  }

  @Override
  public <T> Serializer<T> getSerializer(Class<T> cls) {
    return (Serializer) getClassInfo(cls).serializer;
  }

  @Override
  public ClassInfo nilClassInfo() {
    return classResolver.nilClassInfo();
  }

  @Override
  public ClassInfoHolder nilClassInfoHolder() {
    return classResolver.nilClassInfoHolder();
  }

  @Override
  public ClassInfo readClassInfo(MemoryBuffer buffer, ClassInfoHolder classInfoHolder) {
    return readClassInfo(buffer);
  }

  @Override
  public ClassInfo readClassInfo(MemoryBuffer buffer, ClassInfo classInfoCache) {
    // TODO support type cache to speed up lookup
    return readClassInfo(buffer);
  }

  public ClassInfo readClassInfo(MemoryBuffer buffer) {
    long xtypeId = buffer.readVarUint32Small14();
    byte internalTypeId = (byte) xtypeId;
    switch (internalTypeId) {
      case Types.NAMED_ENUM:
      case Types.NAMED_STRUCT:
      case Types.NAMED_COMPATIBLE_STRUCT:
      case Types.NAMED_EXT:
        if (shareMeta) {
          return readSharedClassMeta(buffer);
        }
        MetaStringBytes packageBytes = metaStringResolver.readMetaStringBytes(buffer);
        MetaStringBytes simpleClassNameBytes = metaStringResolver.readMetaStringBytes(buffer);
        return loadBytesToClassInfo(internalTypeId, packageBytes, simpleClassNameBytes);
      case Types.LIST:
        return getListClassInfo();
      case Types.TIMESTAMP:
        return getGenericClassInfo();
      default:
        ClassInfo classInfo = xtypeIdToClassMap.get(xtypeId);
        if (classInfo == null) {
          throwUnexpectTypeIdException(xtypeId);
        }
        return classInfo;
    }
  }

  private ClassInfo readSharedClassMeta(MemoryBuffer buffer) {
    MetaContext metaContext = fory.getSerializationContext().getMetaContext();
    assert metaContext != null : ClassResolver.SET_META__CONTEXT_MSG;
    int id = buffer.readVarUint32Small14();
    ClassInfo classInfo = metaContext.readClassInfos.get(id);
    if (classInfo == null) {
      classInfo = classResolver.readClassInfoWithMetaShare(metaContext, id);
    }
    return classInfo;
  }

  private void throwUnexpectTypeIdException(long xtypeId) {
    throw new IllegalStateException(String.format("Type id %s not registered", xtypeId));
  }

  private ClassInfo getListClassInfo() {
    fory.incReadDepth();
    GenericType genericType = generics.nextGenericType();
    fory.decDepth();
    if (genericType != null) {
      return getOrBuildClassInfo(genericType.getCls());
    }
    return xtypeIdToClassMap.get(Types.LIST);
  }

  private ClassInfo getGenericClassInfo() {
    fory.incReadDepth();
    GenericType genericType = generics.nextGenericType();
    fory.decDepth();
    if (genericType != null) {
      return getOrBuildClassInfo(genericType.getCls());
    }
    return xtypeIdToClassMap.get(Types.TIMESTAMP);
  }

  private ClassInfo getOrBuildClassInfo(Class<?> cls) {
    ClassInfo classInfo = classInfoMap.get(cls);
    if (classInfo == null) {
      classInfo = buildClassInfo(cls);
      classInfoMap.put(cls, classInfo);
    }
    return classInfo;
  }

  private ClassInfo loadBytesToClassInfo(
      int internalTypeId, MetaStringBytes packageBytes, MetaStringBytes simpleClassNameBytes) {
    TypeNameBytes typeNameBytes =
        new TypeNameBytes(packageBytes.hashCode, simpleClassNameBytes.hashCode);
    ClassInfo classInfo = compositeClassNameBytes2ClassInfo.get(typeNameBytes);
    if (classInfo == null) {
      classInfo =
          populateBytesToClassInfo(
              internalTypeId, typeNameBytes, packageBytes, simpleClassNameBytes);
    }
    return classInfo;
  }

  private ClassInfo populateBytesToClassInfo(
      int typeId,
      TypeNameBytes typeNameBytes,
      MetaStringBytes packageBytes,
      MetaStringBytes simpleClassNameBytes) {
    String namespace = packageBytes.decode(PACKAGE_DECODER);
    String typeName = simpleClassNameBytes.decode(TYPE_NAME_DECODER);
    String qualifiedName = qualifiedName(namespace, typeName);
    ClassInfo classInfo = qualifiedType2ClassInfo.get(qualifiedName);
    if (classInfo == null) {
      String msg = String.format("Class %s not registered", qualifiedName);
      Class<?> type = null;
      if (config.deserializeNonexistentClass()) {
        LOG.warn(msg);
        switch (typeId) {
          case Types.NAMED_ENUM:
          case Types.NAMED_STRUCT:
          case Types.NAMED_COMPATIBLE_STRUCT:
            type =
                NonexistentClass.getNonexistentClass(
                    qualifiedName, isEnum(typeId), 0, config.isMetaShareEnabled());
            break;
          case Types.NAMED_EXT:
            throw new SerializerUnregisteredException(qualifiedName);
          default:
            break;
        }
      } else {
        throw new ClassUnregisteredException(qualifiedName);
      }
      MetaStringBytes fullClassNameBytes =
          metaStringResolver.getOrCreateMetaStringBytes(
              PACKAGE_ENCODER.encode(qualifiedName, MetaString.Encoding.UTF_8));
      classInfo =
          new ClassInfo(
              type,
              fullClassNameBytes,
              packageBytes,
              simpleClassNameBytes,
              false,
              null,
              NO_CLASS_ID,
              NOT_SUPPORT_XLANG);
      if (NonexistentClass.class.isAssignableFrom(TypeUtils.getComponentIfArray(type))) {
        classInfo.serializer = NonexistentClassSerializers.getSerializer(fory, qualifiedName, type);
      }
    }
    compositeClassNameBytes2ClassInfo.put(typeNameBytes, classInfo);
    return classInfo;
  }

  private boolean isEnum(int internalTypeId) {
    return internalTypeId == Types.ENUM || internalTypeId == Types.NAMED_ENUM;
  }

  @Override
  public Fory getFory() {
    return fory;
  }
}
