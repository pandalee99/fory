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

package org.apache.fory.type;

import static org.apache.fory.util.Preconditions.checkArgument;

import com.google.common.cache.Cache;
import com.google.common.cache.CacheBuilder;
import java.lang.reflect.Field;
import java.lang.reflect.Member;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.SortedMap;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ForkJoinPool;
import java.util.concurrent.atomic.AtomicBoolean;
import org.apache.fory.annotation.Expose;
import org.apache.fory.annotation.ForyField;
import org.apache.fory.annotation.Ignore;
import org.apache.fory.annotation.Internal;
import org.apache.fory.collection.Collections;
import org.apache.fory.collection.Tuple2;
import org.apache.fory.memory.Platform;
import org.apache.fory.reflect.TypeRef;
import org.apache.fory.util.Preconditions;
import org.apache.fory.util.StringUtils;
import org.apache.fory.util.record.RecordComponent;
import org.apache.fory.util.record.RecordUtils;

/**
 * Build descriptors for a class.
 *
 * @see Ignore
 */
public class Descriptor {
  private static Cache<
          Class<?>, Tuple2<SortedMap<Member, Descriptor>, SortedMap<Member, Descriptor>>>
      descCache = CacheBuilder.newBuilder().weakKeys().softValues().concurrencyLevel(64).build();
  private static final Map<Class<?>, AtomicBoolean> flags = Collections.newClassKeyCacheMap();

  @Internal
  public static void clearDescriptorCache() {
    descCache.cleanUp();
    descCache = CacheBuilder.newBuilder().weakKeys().softValues().concurrencyLevel(64).build();
  }

  // All fields should not be mutable except as lazy load,
  // because Descriptor is cached in `descCache`.
  // And mutable fields may make some serializer read wrong field
  // value such as `typeName`.
  private TypeRef<?> typeRef;
  private Class<?> type;
  private final String typeName;
  private final String name;
  private String snakeCaseName;
  private final int modifier;
  private final String declaringClass;
  private final Field field;
  private final Method readMethod;
  private final Method writeMethod;
  private ForyField foryField;
  private boolean nullable;
  private boolean trackingRef;

  public Descriptor(Field field, TypeRef<?> typeRef, Method readMethod, Method writeMethod) {
    this.field = field;
    this.typeName = field.getType().getName();
    this.name = field.getName();
    this.modifier = field.getModifiers();
    this.declaringClass = field.getDeclaringClass().getName();
    this.readMethod = readMethod;
    this.writeMethod = writeMethod;
    this.typeRef = typeRef;
    this.foryField = this.field.getAnnotation(ForyField.class);
    if (!typeRef.isPrimitive()) {
      this.nullable = foryField == null || foryField.nullable();
    }
  }

  public Descriptor(TypeRef<?> typeRef, String name, int modifier, String declaringClass) {
    this.field = null;
    this.typeName = typeRef.getRawType().getName();
    this.name = name;
    this.modifier = modifier;
    this.declaringClass = declaringClass;
    this.typeRef = typeRef;
    this.readMethod = null;
    this.writeMethod = null;
    this.foryField = null;
    this.nullable = !typeRef.isPrimitive();
  }

  private Descriptor(Field field, Method readMethod) {
    this.field = field;
    this.typeName = field.getType().getName();
    this.name = field.getName();
    this.modifier = field.getModifiers();
    this.declaringClass = field.getDeclaringClass().getName();
    this.readMethod = readMethod;
    this.writeMethod = null;
    this.typeRef = null;
    this.foryField = this.field.getAnnotation(ForyField.class);
    if (!field.getType().isPrimitive()) {
      this.nullable = foryField == null || foryField.nullable();
    }
  }

  private Descriptor(Method readMethod) {
    this.field = null;
    this.typeName = readMethod.getReturnType().getName();
    this.name = readMethod.getName();
    this.modifier = readMethod.getModifiers();
    this.declaringClass = readMethod.getDeclaringClass().getName();
    this.readMethod = readMethod;
    this.writeMethod = null;
    this.typeRef = TypeRef.of(readMethod.getGenericReturnType());
    this.foryField = readMethod.getAnnotation(ForyField.class);
    if (!readMethod.getReturnType().isPrimitive()) {
      this.nullable = foryField == null || foryField.nullable();
    }
  }

  private Descriptor(
      TypeRef<?> typeRef,
      String typeName,
      String name,
      int modifier,
      String declaringClass,
      Field field,
      Method readMethod,
      Method writeMethod) {
    this.typeRef = typeRef;
    this.typeName = typeName;
    this.name = name;
    this.modifier = modifier;
    this.declaringClass = declaringClass;
    this.field = field;
    this.readMethod = readMethod;
    this.writeMethod = writeMethod;
    this.foryField = this.field == null ? null : this.field.getAnnotation(ForyField.class);
    if (!typeRef.isPrimitive()) {
      this.nullable = foryField == null || foryField.nullable();
    }
  }

  public Descriptor(DescriptorBuilder builder) {
    this(
        builder.typeRef,
        builder.typeName,
        builder.name,
        builder.modifier,
        builder.declaringClass,
        builder.field,
        builder.readMethod,
        builder.writeMethod);
    this.nullable = builder.nullable;
    this.trackingRef = builder.trackingRef;
    this.type = builder.type;
    this.foryField = builder.foryField;
  }

  public DescriptorBuilder copyBuilder() {
    return new DescriptorBuilder(this);
  }

  public Descriptor copy(Method readMethod, Method writeMethod) {
    return new DescriptorBuilder(this).readMethod(readMethod).writeMethod(writeMethod).build();
  }

  public Descriptor copyWithTypeName(String typeName) {
    return new DescriptorBuilder(this).typeName(typeName).build();
  }

  public Field getField() {
    return field;
  }

  public String getName() {
    return name;
  }

  public Class<?> getType() {
    return type;
  }

  public boolean isNullable() {
    return nullable;
  }

  public boolean isTrackingRef() {
    return trackingRef;
  }

  public int getModifier() {
    return modifier;
  }

  public String getSnakeCaseName() {
    if (snakeCaseName == null) {
      snakeCaseName = StringUtils.lowerCamelToLowerUnderscore(name);
    }
    return snakeCaseName;
  }

  public int getModifiers() {
    return modifier;
  }

  public boolean isFinalField() {
    return Modifier.isFinal(modifier);
  }

  public String getDeclaringClass() {
    return declaringClass;
  }

  public Method getReadMethod() {
    return readMethod;
  }

  public Method getWriteMethod() {
    return writeMethod;
  }

  public String getTypeName() {
    return typeName;
  }

  public ForyField getForyField() {
    return foryField;
  }

  /** Try not use {@link TypeRef#getRawType()} since it's expensive. */
  public Class<?> getRawType() {
    Class<?> type = this.type;
    if (type == null) {
      if (field != null) {
        return this.type = field.getType();
      } else {
        return this.type = TypeUtils.getRawType(getTypeRef());
      }
    }
    return Objects.requireNonNull(type);
  }

  public TypeRef<?> getTypeRef() {
    TypeRef<?> typeRef = this.typeRef;
    if (typeRef == null && field != null) {
      this.typeRef = typeRef = TypeRef.of(field.getGenericType());
    }
    return typeRef;
  }

  @Override
  public String toString() {
    final StringBuilder sb = new StringBuilder("Descriptor{");
    sb.append("typeName=").append(typeName);
    sb.append(", name=").append(name);
    sb.append(", modifier=").append(modifier);
    if (field != null) {
      sb.append(", declaringClass=").append(field.getDeclaringClass().getSimpleName());
    }
    if (readMethod != null) {
      sb.append(", readMethod=").append(readMethod);
    }
    if (writeMethod != null) {
      sb.append(", writeMethod=").append(writeMethod);
    }
    if (typeRef != null) {
      sb.append(", typeRef=").append(typeRef);
    }
    sb.append(", foryField=").append(foryField);
    sb.append('}');
    return sb.toString();
  }

  /**
   * Returns descriptors non-transient/non-static fields of class. If super class and sub class have
   * same field, use subclass field.
   */
  public static List<Descriptor> getDescriptors(Class<?> clz) {
    // TODO(chaokunyang) add cache by weak class key, see java.io.ObjectStreamClass.WeakClassKey.
    SortedMap<Member, Descriptor> allDescriptorsMap = getAllDescriptorsMap(clz);
    Map<String, List<Member>> duplicateNameFields = getDuplicateNames(allDescriptorsMap);
    checkArgument(
        duplicateNameFields.size() == 0, "%s has duplicate fields %s", clz, duplicateNameFields);
    return new ArrayList<>(allDescriptorsMap.values());
  }

  /**
   * Returns descriptors map non-transient/non-static fields of class. Super class and sub class are
   * not allowed to have duplicate name field.
   */
  public static SortedMap<String, Descriptor> getDescriptorsMap(Class<?> clz) {
    SortedMap<Member, Descriptor> allDescriptorsMap = getAllDescriptorsMap(clz);
    Map<String, List<Member>> duplicateNameFields = getDuplicateNames(allDescriptorsMap);
    Preconditions.checkArgument(
        duplicateNameFields.size() == 0, "%s has duplicate fields %s", clz, duplicateNameFields);
    TreeMap<String, Descriptor> map = new TreeMap<>();
    allDescriptorsMap.forEach((k, v) -> map.put(k.getName(), v));
    return map;
  }

  private static final ClassValue<Map<String, List<Member>>> sortedDuplicatedMembers =
      new ClassValue<Map<String, List<Member>>>() {
        @Override
        protected Map<String, List<Member>> computeValue(Class<?> type) {
          SortedMap<Member, Descriptor> allFields = Descriptor.getAllDescriptorsMap(type);
          Map<String, List<Member>> duplicated = Descriptor.getDuplicateNames(allFields);
          Map<String, List<Member>> map = new HashMap<>();
          for (Map.Entry<String, List<Member>> e : duplicated.entrySet()) {
            e.getValue()
                .sort(
                    (f1, f2) -> {
                      if (f1.getDeclaringClass() == f2.getDeclaringClass()) {
                        return 0;
                      } else {
                        return f1.getDeclaringClass().isAssignableFrom(f2.getDeclaringClass())
                            ? -1
                            : 1;
                      }
                    });
            if (map.put(e.getKey(), e.getValue()) != null) {
              throw new IllegalStateException("Duplicate key");
            }
          }
          return map;
        }
      };

  public static Map<String, List<Member>> getDuplicateNames(
      SortedMap<Member, Descriptor> allDescriptorsMap) {
    Map<String, List<Member>> duplicateNames = new HashMap<>();
    for (Member member : allDescriptorsMap.keySet()) {
      duplicateNames.compute(
          member.getName(),
          (memberName, members) -> {
            if (members == null) {
              members = new ArrayList<>();
            }
            members.add(member);
            return members;
          });
    }
    Map<String, List<Member>> map = new HashMap<>();
    for (Map.Entry<String, List<Member>> e : duplicateNames.entrySet()) {
      if (Objects.requireNonNull(e.getValue()).size() > 1) {
        map.put(e.getKey(), e.getValue());
      }
    }
    return map;
  }

  public static Map<String, List<Member>> getSortedDuplicatedMembers(Class<?> cls) {
    return sortedDuplicatedMembers.get(cls);
  }

  public static boolean hasDuplicateNameFields(Class<?> clz) {
    return !getSortedDuplicatedMembers(clz).isEmpty();
  }

  /**
   * Return all non-transient/non-static fields of {@code clz} in a deterministic order with field
   * name first and declaring class second. Super class and sub class can have same name field.
   */
  public static Set<Field> getFields(Class<?> clz) {
    Set<Field> fields = new TreeSet<>(memberComparator);
    for (Member member : getAllDescriptorsMap(clz).keySet()) {
      if (member instanceof Field) {
        fields.add((Field) member);
      }
    }
    return fields;
  }

  /**
   * Returns descriptors map non-transient/non-static fields of class in a deterministic order with
   * field name first and declaring class second. Super class and subclass can have same names
   * field.
   */
  public static SortedMap<Member, Descriptor> getAllDescriptorsMap(Class<?> clz) {
    return getAllDescriptorsMap(clz, true);
  }

  private static final Comparator<Member> memberComparator =
      ((Member m1, Member m2) -> {
        int compare = m1.getName().compareTo(m2.getName());
        if (compare == 0) { // class and super classes have same named field
          return m1.getDeclaringClass().getName().compareTo(m2.getDeclaringClass().getName());
        } else {
          return compare;
        }
      });

  public static SortedMap<Member, Descriptor> getAllDescriptorsMap(
      Class<?> clz, boolean searchParent) {
    try {
      Tuple2<SortedMap<Member, Descriptor>, SortedMap<Member, Descriptor>> tuple2 =
          descCache.get(clz, () -> createAllDescriptorsMap(clz));
      if (searchParent) {
        return tuple2.f0;
      } else {
        return tuple2.f1;
      }
    } catch (ExecutionException e) {
      throw new RuntimeException(e);
    }
  }

  private static Tuple2<SortedMap<Member, Descriptor>, SortedMap<Member, Descriptor>>
      createAllDescriptorsMap(Class<?> clz) {
    // use TreeMap to sort to fix field order
    TreeMap<Member, Descriptor> descriptorMap = new TreeMap<>(memberComparator);
    TreeMap<Member, Descriptor> currentDescriptorMap = new TreeMap<>(memberComparator);
    Class<?> clazz = clz;
    // TODO(chaokunyang) use fory compiler thread pool
    ExecutorService compilationService = ForkJoinPool.commonPool();
    if (RecordUtils.isRecord(clz)) {
      RecordComponent[] components = RecordUtils.getRecordComponents(clazz);
      assert components != null;
      try {
        for (RecordComponent component : components) {
          Field field = clz.getDeclaredField(component.getName());
          descriptorMap.put(field, new Descriptor(field, component.getAccessor()));
        }
      } catch (NoSuchFieldException e) {
        // impossible
        Platform.throwException(e);
      }
      currentDescriptorMap = new TreeMap<>(descriptorMap);
      return Tuple2.of(descriptorMap, currentDescriptorMap);
    }
    if (clazz.isInterface()) {
      for (Method method : clazz.getMethods()) {
        if (method.getParameterCount() == 0
            && method.getReturnType() != void.class
            && !Modifier.isStatic(method.getModifiers())) {
          descriptorMap.put(method, new Descriptor(method));
        }
      }

      currentDescriptorMap = new TreeMap<>(descriptorMap);
      return Tuple2.of(descriptorMap, currentDescriptorMap);
    }
    do {
      Field[] fields = clazz.getDeclaredFields();
      boolean haveExpose = false, haveIgnore = false;
      for (Field field : fields) {
        warmField(clz, field, compilationService);
        if (field.isAnnotationPresent(Expose.class)) {
          haveExpose = true;
        }
        if (field.isAnnotationPresent(Ignore.class)) {
          haveIgnore = true;
        }
        if (haveExpose && haveIgnore) {
          throw new RuntimeException(
              "Fields of a Class are not allowed to have both the Ignore and Expose annotations simultaneously.");
        }
      }
      for (Field field : fields) {
        int modifiers = field.getModifiers();
        // final and non-private field validation left to {@link isBean(clz)}
        if (!Modifier.isTransient(modifiers) && !Modifier.isStatic(modifiers)) {
          if (haveExpose) {
            if (field.isAnnotationPresent(Expose.class)) {
              descriptorMap.put(field, new Descriptor(field, null));
            }
          } else {
            if (!field.isAnnotationPresent(Ignore.class)) {
              descriptorMap.put(field, new Descriptor(field, null));
            }
          }
        }
      }
      if (clazz == clz) {
        currentDescriptorMap = new TreeMap<>(descriptorMap);
      }
      clazz = clazz.getSuperclass();
    } while (clazz != null);
    return Tuple2.of(descriptorMap, currentDescriptorMap);
  }

  /**
   * Speedup generics resolve by multi-thread since {@link Field#getGenericType()} is slow and
   * nested Descriptor is slow in single thread.
   */
  static void warmField(Class<?> context, Field field, ExecutorService compilationService) {
    Class<?> fieldRawType = field.getType();
    if (fieldRawType.isPrimitive()
        || fieldRawType == String.class
        || fieldRawType == Object.class) {
      return;
    }
    if (TypeUtils.isBoxed(fieldRawType)) {
      return;
    }
    if (fieldRawType == context) {
      // avoid duplicate build.
      return;
    }
    if (!fieldRawType.getName().startsWith("java")) {
      compilationService.submit(
          () -> {
            // use a flag to avoid blocking thread.
            AtomicBoolean flag = flags.computeIfAbsent(fieldRawType, k -> new AtomicBoolean(false));
            if (flag.compareAndSet(false, true)) {
              getAllDescriptorsMap(fieldRawType);
            }
          });
    } else if (TypeUtils.isCollection(fieldRawType) || TypeUtils.isMap(fieldRawType)) {
      // warm up generic type, sun.reflect.generics.repository.FieldRepository
      // is expensive.
      compilationService.submit(() -> warmGenericTask(TypeRef.of(field.getGenericType())));
    } else if (fieldRawType.isArray()) {
      Class<?> componentType = fieldRawType.getComponentType();
      if (!componentType.isPrimitive()) {
        compilationService.submit(() -> warmGenericTask(TypeRef.of(field.getGenericType())));
      }
    }
  }

  // this method should b executed in background thread pool.
  static void warmGenericTask(TypeRef<?> typeRef) {
    Class<?> rawType = TypeUtils.getRawType(typeRef);
    if (rawType.isPrimitive() || rawType == String.class || rawType == Object.class) {
      return;
    }
    if (TypeUtils.isBoxed(rawType)) {
      return;
    }
    if (!rawType.getName().startsWith("java")) {
      getAllDescriptorsMap(rawType);
    } else if (TypeUtils.isCollection(rawType)) {
      TypeRef<?> elementType = TypeUtils.getElementType(typeRef);
      warmGenericTask(elementType);
    } else if (TypeUtils.isMap(rawType)) {
      Tuple2<TypeRef<?>, TypeRef<?>> mapKeyValueType = TypeUtils.getMapKeyValueType(typeRef);
      warmGenericTask(mapKeyValueType.f0);
      warmGenericTask(mapKeyValueType.f1);
    } else if (rawType.isArray()) {
      warmGenericTask(typeRef.getComponentType());
    }
  }

  static SortedMap<Field, Descriptor> buildBeanedDescriptorsMap(
      Class<?> clz, boolean searchParent) {
    List<Field> fieldList = new ArrayList<>();
    Class<?> clazz = clz;
    Map<Tuple2<Class<?>, String>, Method> methodMap = new HashMap<>();
    do {
      Field[] fields = clazz.getDeclaredFields();
      for (Field field : fields) {
        int modifiers = field.getModifiers();
        // final and non-private field validation left to {@link isBean(clz)}
        if (!Modifier.isTransient(modifiers)
            && !Modifier.isStatic(modifiers)
            && !field.isAnnotationPresent(Ignore.class)) {
          fieldList.add(field);
        }
      }
      Arrays.stream(clazz.getDeclaredMethods())
          .filter(m -> !Modifier.isPrivate(m.getModifiers()))
          // if override, use subClass method; getter/setter method won't overload
          .forEach(m -> methodMap.put(Tuple2.of(m.getDeclaringClass(), m.getName()), m));
      clazz = clazz.getSuperclass();
    } while (clazz != null && searchParent);

    for (Class<?> anInterface : clz.getInterfaces()) {
      Method[] methods = anInterface.getDeclaredMethods();
      for (Method method : methods) {
        if (method.isDefault()) {
          methodMap.put(Tuple2.of(method.getDeclaringClass(), method.getName()), method);
        }
      }
    }

    // use TreeMap to sort to fix field order
    TreeMap<Field, Descriptor> descriptorMap = new TreeMap<>(memberComparator);
    for (Field field : fieldList) {
      Class<?> fieldDeclaringClass = field.getDeclaringClass();
      String fieldName = field.getName();
      String cap = StringUtils.capitalize(fieldName);
      Method getter;
      if ("boolean".equalsIgnoreCase(field.getType().getSimpleName())) {
        getter = methodMap.get(Tuple2.of(fieldDeclaringClass, "is" + cap));
      } else {
        getter = methodMap.get(Tuple2.of(fieldDeclaringClass, "get" + cap));
      }
      if (getter != null) {
        if (getter.getParameterCount() != 0
            || !getter
                .getGenericReturnType()
                .getTypeName()
                .equals(field.getGenericType().getTypeName())) {
          getter = null;
        }
      }
      Method setter = methodMap.get(Tuple2.of(fieldDeclaringClass, "set" + cap));
      if (setter != null) {
        if (setter.getParameterCount() != 1
            || !setter
                .getGenericParameterTypes()[0]
                .getTypeName()
                .equals(field.getGenericType().getTypeName())) {
          setter = null;
        }
      }
      TypeRef<?> fieldType = TypeRef.of(field.getGenericType());
      descriptorMap.put(field, new Descriptor(field, fieldType, getter, setter));
    }
    // Don't cache descriptors using a static `WeakHashMap<Class<?>, SortedMap<Field, Descriptor>>`，
    // otherwise classes can't be gc.
    return descriptorMap;
  }
}
