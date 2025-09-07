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

package org.apache.fory.serializer;

import java.util.Arrays;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.apache.fory.Fory;
import org.apache.fory.memory.MemoryBuffer;
import org.apache.fory.memory.Platform;
import org.apache.fory.reflect.FieldAccessor;
import org.apache.fory.resolver.ClassInfo;
import org.apache.fory.resolver.ClassResolver;
import org.apache.fory.resolver.FieldResolver;
import org.apache.fory.serializer.collection.CollectionLikeSerializer;
import org.apache.fory.serializer.collection.MapLikeSerializer;
import org.apache.fory.util.Preconditions;
import org.apache.fory.util.record.RecordInfo;
import org.apache.fory.util.record.RecordUtils;

/**
 * This Serializer provides both forward and backward compatibility: fields can be added or removed
 * without invalidating previously serialized bytes.
 *
 * @see FieldResolver
 */
// TODO(chaokunyang) support generics optimization for {@code SomeClass<T>}
// TODO(chaokunyang) support generics optimization for nested collection/map fields.
@SuppressWarnings({"unchecked", "rawtypes"})
public final class CompatibleSerializer<T> extends CompatibleSerializerBase<T> {
  private static final int INDEX_FOR_SKIP_FILL_VALUES = -1;
  private final FieldResolver fieldResolver;
  private final RecordInfo recordInfo;

  public CompatibleSerializer(Fory fory, Class<T> cls) {
    super(fory, cls);
    // Use `setSerializerIfAbsent` to avoid overwriting existing serializer for class when used
    // as data serializer.
    classResolver.setSerializerIfAbsent(cls, this);
    fieldResolver = classResolver.getFieldResolver(cls);
    if (isRecord) {
      List<String> fieldNames =
          fieldResolver.getAllFieldsList().stream()
              .map(FieldResolver.FieldInfo::getName)
              .collect(Collectors.toList());
      recordInfo = new RecordInfo(cls, fieldNames);
    } else {
      recordInfo = null;
    }
  }

  public CompatibleSerializer(Fory fory, Class<T> cls, FieldResolver fieldResolver) {
    super(fory, cls, null);
    Preconditions.checkArgument(!isRecord, cls);
    recordInfo = null;
    this.fieldResolver = fieldResolver;
  }

  @Override
  public void write(MemoryBuffer buffer, T value) {
    for (FieldResolver.FieldInfo fieldInfo : fieldResolver.getEmbedTypes4Fields()) {
      buffer.writeInt32((int) fieldInfo.getEncodedFieldInfo());
      readAndWriteFieldValue(buffer, fieldInfo, value);
    }
    for (FieldResolver.FieldInfo fieldInfo : fieldResolver.getEmbedTypes9Fields()) {
      buffer.writeInt64(fieldInfo.getEncodedFieldInfo());
      readAndWriteFieldValue(buffer, fieldInfo, value);
    }
    for (FieldResolver.FieldInfo fieldInfo : fieldResolver.getEmbedTypesHashFields()) {
      buffer.writeInt64(fieldInfo.getEncodedFieldInfo());
      readAndWriteFieldValue(buffer, fieldInfo, value);
    }
    for (FieldResolver.FieldInfo fieldInfo : fieldResolver.getSeparateTypesHashFields()) {
      buffer.writeInt64(fieldInfo.getEncodedFieldInfo());
      readAndWriteFieldValue(buffer, fieldInfo, value);
    }
    buffer.writeInt64(fieldResolver.getEndTag());
  }

  public void writeFieldsValues(MemoryBuffer buffer, Object[] vals) {
    FieldResolver fieldResolver = this.fieldResolver;
    Fory fory = this.fory;
    int index = 0;
    for (FieldResolver.FieldInfo fieldInfo : fieldResolver.getEmbedTypes4Fields()) {
      buffer.writeInt32((int) fieldInfo.getEncodedFieldInfo());
      writeFieldValue(fieldInfo, buffer, vals[index++]);
    }
    for (FieldResolver.FieldInfo fieldInfo : fieldResolver.getEmbedTypes9Fields()) {
      buffer.writeInt64(fieldInfo.getEncodedFieldInfo());
      writeFieldValue(fieldInfo, buffer, vals[index++]);
    }
    for (FieldResolver.FieldInfo fieldInfo : fieldResolver.getEmbedTypesHashFields()) {
      buffer.writeInt64(fieldInfo.getEncodedFieldInfo());
      writeFieldValue(fieldInfo, buffer, vals[index++]);
    }
    for (FieldResolver.FieldInfo fieldInfo : fieldResolver.getSeparateTypesHashFields()) {
      buffer.writeInt64(fieldInfo.getEncodedFieldInfo());
      Object value = vals[index++];
      if (!fory.getRefResolver().writeRefOrNull(buffer, value)) {
        byte fieldType = fieldInfo.getFieldType();
        buffer.writeByte(fieldType);
        Preconditions.checkArgument(fieldType == FieldResolver.FieldTypes.OBJECT);
        ClassInfo classInfo = fieldInfo.getClassInfo(value.getClass());
        fory.writeNonRef(buffer, value, classInfo);
      }
    }
    buffer.writeInt64(fieldResolver.getEndTag());
  }

  private void readAndWriteFieldValue(
      MemoryBuffer buffer, FieldResolver.FieldInfo fieldInfo, Object targetObject) {
    FieldAccessor fieldAccessor = fieldInfo.getFieldAccessor();
    boolean nullable = fieldInfo.isNullable();
    short classId = fieldInfo.getEmbeddedClassId();
    if (AbstractObjectSerializer.writePrimitiveFieldValueFailed(
        fory, buffer, targetObject, fieldAccessor, classId)) {
      Object fieldValue;
      fieldValue = fieldAccessor.getObject(targetObject);
      boolean writeBasicObjectResult =
          nullable
              ? AbstractObjectSerializer.writeBasicNullableObjectFieldValueFailed(
                  fory, buffer, fieldValue, classId)
              : AbstractObjectSerializer.writeBasicObjectFieldValueFailed(
                  fory, buffer, fieldValue, classId);
      if (writeBasicObjectResult) {
        if (classId == ClassResolver.NO_CLASS_ID) { // SEPARATE_TYPES_HASH
          writeSeparateFieldValue(fieldInfo, buffer, fieldValue);
        } else {
          ClassInfo classInfo = fieldInfo.getClassInfo(classId);
          Serializer<Object> serializer = classInfo.getSerializer();
          fory.writeRef(buffer, fieldValue, serializer);
        }
      }
    }
  }

  private void writeFieldValue(
      FieldResolver.FieldInfo fieldInfo, MemoryBuffer buffer, Object fieldValue) {
    short classId = fieldInfo.getEmbeddedClassId();
    // PRIMITIVE fields, not need for null check.
    switch (classId) {
      case ClassResolver.PRIMITIVE_BOOLEAN_CLASS_ID:
        buffer.writeBoolean((Boolean) fieldValue);
        return;
      case ClassResolver.PRIMITIVE_BYTE_CLASS_ID:
        buffer.writeByte((Byte) fieldValue);
        return;
      case ClassResolver.PRIMITIVE_CHAR_CLASS_ID:
        buffer.writeChar((Character) fieldValue);
        return;
      case ClassResolver.PRIMITIVE_SHORT_CLASS_ID:
        buffer.writeInt16((Short) fieldValue);
        return;
      case ClassResolver.PRIMITIVE_INT_CLASS_ID:
        if (fory.compressInt()) {
          buffer.writeVarInt32((Integer) fieldValue);
        } else {
          buffer.writeInt32((Integer) fieldValue);
        }
        return;
      case ClassResolver.PRIMITIVE_FLOAT_CLASS_ID:
        buffer.writeFloat32((Float) fieldValue);
        return;
      case ClassResolver.PRIMITIVE_LONG_CLASS_ID:
        fory.writeInt64(buffer, (Long) fieldValue);
        return;
      case ClassResolver.PRIMITIVE_DOUBLE_CLASS_ID:
        buffer.writeFloat64((Double) fieldValue);
        return;
      case ClassResolver.STRING_CLASS_ID:
        fory.writeJavaStringRef(buffer, (String) fieldValue);
        break;
      case ClassResolver.NO_CLASS_ID: // SEPARATE_TYPES_HASH
        writeSeparateFieldValue(fieldInfo, buffer, fieldValue);
        break;
      default:
        {
          ClassInfo classInfo = fieldInfo.getClassInfo(classId);
          Serializer<Object> serializer = classInfo.getSerializer();
          fory.writeRef(buffer, fieldValue, serializer);
        }
    }
  }

  private void writeSeparateFieldValue(
      FieldResolver.FieldInfo fieldInfo, MemoryBuffer buffer, Object fieldValue) {
    if (!refResolver.writeRefOrNull(buffer, fieldValue)) {
      byte fieldType = fieldInfo.getFieldType();
      buffer.writeByte(fieldType);
      if (fieldType == FieldResolver.FieldTypes.OBJECT) {
        ClassInfo classInfo = fieldInfo.getClassInfo(fieldValue.getClass());
        fory.writeNonRef(buffer, fieldValue, classInfo);
      } else {
        if (fieldType == FieldResolver.FieldTypes.COLLECTION_ELEMENT_FINAL) {
          writeCollectionField(
              buffer, (FieldResolver.CollectionFieldInfo) fieldInfo, (Collection) fieldValue);
        } else if (fieldType == FieldResolver.FieldTypes.MAP_KV_FINAL) {
          writeMapKVFinal(buffer, (FieldResolver.MapFieldInfo) fieldInfo, (Map) fieldValue);
        } else if (fieldType == FieldResolver.FieldTypes.MAP_KEY_FINAL) {
          writeMapKeyFinal(buffer, (FieldResolver.MapFieldInfo) fieldInfo, (Map) fieldValue);
        } else {
          Preconditions.checkArgument(fieldType == FieldResolver.FieldTypes.MAP_VALUE_FINAL);
          writeMapValueFinal(buffer, (FieldResolver.MapFieldInfo) fieldInfo, (Map) fieldValue);
        }
      }
    }
  }

  private void writeCollectionField(
      MemoryBuffer buffer, FieldResolver.CollectionFieldInfo fieldInfo, Collection fieldValue) {
    ClassInfo elementClassInfo = fieldInfo.getElementClassInfo();
    classResolver.writeClassInfo(buffer, elementClassInfo);
    // following write is consistent with `BaseSeqCodecBuilder.serializeForCollection`
    ClassInfo classInfo = fieldInfo.getClassInfo(fieldValue.getClass());
    classResolver.writeClassInfo(buffer, classInfo);
    CollectionLikeSerializer collectionSerializer =
        (CollectionLikeSerializer) classInfo.getSerializer();
    try {
      collectionSerializer.setElementSerializer(elementClassInfo.getSerializer());
      collectionSerializer.write(buffer, fieldValue);
    } finally {
      // Some collectionSerializer may overwrite write/read method, then clear element serializer
      // may not got invoked.
      collectionSerializer.setElementSerializer(null);
    }
  }

  private void writeMapKVFinal(
      MemoryBuffer buffer, FieldResolver.MapFieldInfo fieldInfo, Map fieldValue) {
    ClassInfo keyClassInfo = fieldInfo.getKeyClassInfo();
    ClassInfo valueClassInfo = fieldInfo.getValueClassInfo();
    classResolver.writeClassInfo(buffer, keyClassInfo);
    classResolver.writeClassInfo(buffer, valueClassInfo);
    // following write is consistent with `BaseSeqCodecBuilder.serializeForMap`
    ClassInfo classInfo = fieldInfo.getClassInfo(fieldValue.getClass());
    classResolver.writeClassInfo(buffer, classInfo);
    MapLikeSerializer mapSerializer = (MapLikeSerializer) classInfo.getSerializer();
    try {
      mapSerializer.setKeySerializer(keyClassInfo.getSerializer());
      mapSerializer.setValueSerializer(valueClassInfo.getSerializer());
      mapSerializer.write(buffer, fieldValue);
    } finally {
      // Some mmapSerializer may overwrite write/read method, then clear serializer
      // may not got invoked.
      mapSerializer.setKeySerializer(null);
      mapSerializer.setValueSerializer(null);
    }
  }

  private void writeMapKeyFinal(
      MemoryBuffer buffer, FieldResolver.MapFieldInfo fieldInfo, Map fieldValue) {
    ClassInfo keyClassInfo = fieldInfo.getKeyClassInfo();
    classResolver.writeClassInfo(buffer, keyClassInfo);
    // following write is consistent with `BaseSeqCodecBuilder.serializeForMap`
    ClassInfo classInfo = fieldInfo.getClassInfo(fieldValue.getClass());
    classResolver.writeClassInfo(buffer, classInfo);
    MapLikeSerializer mapSerializer = (MapLikeSerializer) classInfo.getSerializer();
    try {
      mapSerializer.setKeySerializer(keyClassInfo.getSerializer());
      mapSerializer.write(buffer, fieldValue);
    } finally {
      // Some mmapSerializer may overwrite write/read method, then clear serializer
      // may not got invoked.
      mapSerializer.setKeySerializer(null);
    }
  }

  private void writeMapValueFinal(
      MemoryBuffer buffer, FieldResolver.MapFieldInfo fieldInfo, Map fieldValue) {
    ClassInfo valueClassInfo = fieldInfo.getValueClassInfo();
    classResolver.writeClassInfo(buffer, valueClassInfo);
    // following write is consistent with `BaseSeqCodecBuilder.serializeForMap`
    ClassInfo classInfo = fieldInfo.getClassInfo(fieldValue.getClass());
    classResolver.writeClassInfo(buffer, classInfo);
    MapLikeSerializer mapSerializer = (MapLikeSerializer) classInfo.getSerializer();
    try {
      mapSerializer.setValueSerializer(valueClassInfo.getSerializer());
      mapSerializer.write(buffer, fieldValue);
    } finally {
      // Some mmapSerializer may overwrite write/read method, then clear serializer
      // may not got invoked.
      mapSerializer.setValueSerializer(null);
    }
  }

  @SuppressWarnings("unchecked")
  @Override
  public T read(MemoryBuffer buffer) {
    if (isRecord) {
      Object[] fieldValues = new Object[fieldResolver.getNumFields()];
      readFields(buffer, fieldValues);
      fieldValues = RecordUtils.remapping(recordInfo, fieldValues);
      assert constructor != null;
      try {
        T t = (T) constructor.invokeWithArguments(fieldValues);
        Arrays.fill(recordInfo.getRecordComponents(), null);
        return t;
      } catch (Throwable e) {
        Platform.throwException(e);
      }
    }
    T obj = (T) newBean();
    refResolver.reference(obj);
    return readAndSetFields(buffer, obj);
  }

  @Override
  public T readAndSetFields(MemoryBuffer buffer, T obj) {
    long partFieldInfo = readEmbedTypes4Fields(buffer, obj, null, INDEX_FOR_SKIP_FILL_VALUES);
    long endTag = fieldResolver.getEndTag();
    if (partFieldInfo == endTag) {
      return obj;
    }
    long tmp = buffer.readInt32();
    partFieldInfo = tmp << 32 | (partFieldInfo & 0x00000000ffffffffL);
    partFieldInfo =
        readEmbedTypes9Fields(buffer, partFieldInfo, obj, null, INDEX_FOR_SKIP_FILL_VALUES);
    if (partFieldInfo == endTag) {
      return obj;
    }
    partFieldInfo =
        readEmbedTypesHashFields(buffer, partFieldInfo, obj, null, INDEX_FOR_SKIP_FILL_VALUES);
    if (partFieldInfo == endTag) {
      return obj;
    }
    readSeparateTypesHashField(buffer, partFieldInfo, obj, null, INDEX_FOR_SKIP_FILL_VALUES);
    return obj;
  }

  public void readFields(MemoryBuffer buffer, Object[] vals) {
    int startIndex = 0;
    long partFieldInfo = readEmbedTypes4Fields(buffer, null, vals, startIndex);
    long endTag = fieldResolver.getEndTag();
    if (partFieldInfo == endTag) {
      return;
    }
    startIndex += fieldResolver.getEmbedTypes4Fields().length;
    long tmp = buffer.readInt32();
    partFieldInfo = tmp << 32 | (partFieldInfo & 0x00000000ffffffffL);
    partFieldInfo = readEmbedTypes9Fields(buffer, partFieldInfo, null, vals, startIndex);
    if (partFieldInfo == endTag) {
      return;
    }
    startIndex += fieldResolver.getEmbedTypes9Fields().length;
    partFieldInfo = readEmbedTypesHashFields(buffer, partFieldInfo, null, vals, startIndex);
    if (partFieldInfo == endTag) {
      return;
    }
    startIndex += fieldResolver.getEmbedTypesHashFields().length;
    readSeparateTypesHashField(buffer, partFieldInfo, null, vals, startIndex);
  }

  private long readEmbedTypes4Fields(
      MemoryBuffer buffer, Object obj, Object[] vals, int startIndex) {
    long partFieldInfo = buffer.readInt32();
    FieldResolver.FieldInfo[] embedTypes4Fields = fieldResolver.getEmbedTypes4Fields();
    if (embedTypes4Fields.length > 0) {
      long minFieldInfo = embedTypes4Fields[0].getEncodedFieldInfo();
      while ((partFieldInfo & 0b11) == FieldResolver.EMBED_TYPES_4_FLAG
          && partFieldInfo < minFieldInfo) {
        long part = fieldResolver.skipDataBy4(buffer, (int) partFieldInfo);
        if (part != partFieldInfo) {
          return part;
        }
        partFieldInfo = buffer.readInt32();
      }
      for (int i = 0; i < embedTypes4Fields.length; i++) {
        FieldResolver.FieldInfo fieldInfo = embedTypes4Fields[i];
        long encodedFieldInfo = fieldInfo.getEncodedFieldInfo();
        if (encodedFieldInfo == partFieldInfo) {
          if (obj != null) {
            readAndSetFieldValue(fieldInfo, buffer, obj);
          } else {
            vals[startIndex + i] = readFieldValue(fieldInfo, buffer);
          }
          partFieldInfo = buffer.readInt32();
        } else {
          if ((partFieldInfo & 0b11) == FieldResolver.EMBED_TYPES_4_FLAG) {
            if (partFieldInfo < encodedFieldInfo) {
              long part = fieldResolver.skipDataBy4(buffer, (int) partFieldInfo);
              if (part != partFieldInfo) {
                return part;
              }
              partFieldInfo = buffer.readInt32();
              i--;
            }
          } else {
            break;
          }
        }
      }
    }
    while ((partFieldInfo & 0b11) == FieldResolver.EMBED_TYPES_4_FLAG) {
      long part = fieldResolver.skipDataBy4(buffer, (int) partFieldInfo);
      if (part != partFieldInfo) {
        return part;
      }
      partFieldInfo = buffer.readInt32();
    }
    return partFieldInfo;
  }

  private long readEmbedTypes9Fields(
      MemoryBuffer buffer, long partFieldInfo, Object obj, Object[] vals, int startIndex) {
    FieldResolver.FieldInfo[] embedTypes9Fields = fieldResolver.getEmbedTypes9Fields();
    if (embedTypes9Fields.length > 0) {
      long minFieldInfo = embedTypes9Fields[0].getEncodedFieldInfo();
      while ((partFieldInfo & 0b111) == FieldResolver.EMBED_TYPES_9_FLAG
          && partFieldInfo < minFieldInfo) {
        long part = fieldResolver.skipDataBy8(buffer, partFieldInfo);
        if (part != partFieldInfo) {
          return part;
        }
        partFieldInfo = buffer.readInt64();
      }

      for (int i = 0; i < embedTypes9Fields.length; i++) {
        FieldResolver.FieldInfo fieldInfo = embedTypes9Fields[i];
        long encodedFieldInfo = fieldInfo.getEncodedFieldInfo();
        if (encodedFieldInfo == partFieldInfo) {
          if (obj != null) {
            readAndSetFieldValue(fieldInfo, buffer, obj);
          } else {
            vals[startIndex + i] = readFieldValue(fieldInfo, buffer);
          }
          partFieldInfo = buffer.readInt64();
        } else {
          if ((partFieldInfo & 0b111) == FieldResolver.EMBED_TYPES_9_FLAG) {
            if (partFieldInfo < encodedFieldInfo) {
              long part = fieldResolver.skipDataBy8(buffer, partFieldInfo);
              if (part != partFieldInfo) {
                return part;
              }
              partFieldInfo = buffer.readInt64();
              i--;
            }
          } else {
            break;
          }
        }
      }
    }
    while ((partFieldInfo & 0b111) == FieldResolver.EMBED_TYPES_9_FLAG) {
      long part = fieldResolver.skipDataBy8(buffer, partFieldInfo);
      if (part != partFieldInfo) {
        return part;
      }
      partFieldInfo = buffer.readInt64();
    }
    return partFieldInfo;
  }

  private long readEmbedTypesHashFields(
      MemoryBuffer buffer, long partFieldInfo, Object obj, Object[] vals, int startIndex) {
    FieldResolver.FieldInfo[] embedTypesHashFields = fieldResolver.getEmbedTypesHashFields();
    if (embedTypesHashFields.length > 0) {
      long minFieldInfo = embedTypesHashFields[0].getEncodedFieldInfo();
      while ((partFieldInfo & 0b111) == FieldResolver.EMBED_TYPES_HASH_FLAG
          && partFieldInfo < minFieldInfo) {
        long part = fieldResolver.skipDataBy8(buffer, partFieldInfo);
        if (part != partFieldInfo) {
          return part;
        }
        partFieldInfo = buffer.readInt64();
      }

      for (int i = 0; i < embedTypesHashFields.length; i++) {
        FieldResolver.FieldInfo fieldInfo = embedTypesHashFields[i];
        long encodedFieldInfo = fieldInfo.getEncodedFieldInfo();
        if (encodedFieldInfo == partFieldInfo) {
          if (obj != null) {
            readAndSetFieldValue(fieldInfo, buffer, obj);
          } else {
            vals[startIndex + i] = readFieldValue(fieldInfo, buffer);
          }
          partFieldInfo = buffer.readInt64();
        } else {
          if ((partFieldInfo & 0b111) == FieldResolver.EMBED_TYPES_HASH_FLAG) {
            if (partFieldInfo < encodedFieldInfo) {
              long part = fieldResolver.skipDataBy8(buffer, partFieldInfo);
              if (part != partFieldInfo) {
                return part;
              }
              partFieldInfo = buffer.readInt64();
              i--;
            }
          } else {
            break;
          }
        }
      }
    }
    while ((partFieldInfo & 0b111) == FieldResolver.EMBED_TYPES_HASH_FLAG) {
      long part = fieldResolver.skipDataBy8(buffer, partFieldInfo);
      if (part != partFieldInfo) {
        return part;
      }
      partFieldInfo = buffer.readInt64();
    }
    return partFieldInfo;
  }

  private void readSeparateTypesHashField(
      MemoryBuffer buffer, long partFieldInfo, Object obj, Object[] vals, int startIndex) {
    FieldResolver.FieldInfo[] separateTypesHashFields = fieldResolver.getSeparateTypesHashFields();
    if (separateTypesHashFields.length > 0) {
      long minFieldInfo = separateTypesHashFields[0].getEncodedFieldInfo();
      while ((partFieldInfo & 0b11) == FieldResolver.SEPARATE_TYPES_HASH_FLAG
          && partFieldInfo < minFieldInfo) {
        long part = fieldResolver.skipDataBy8(buffer, partFieldInfo);
        if (part != partFieldInfo) {
          return;
        }
        partFieldInfo = buffer.readInt64();
      }
      for (int i = 0; i < separateTypesHashFields.length; i++) {
        FieldResolver.FieldInfo fieldInfo = separateTypesHashFields[i];
        long encodedFieldInfo = fieldInfo.getEncodedFieldInfo();
        if (encodedFieldInfo == partFieldInfo) {
          if (obj != null) {
            readAndSetFieldValue(fieldInfo, buffer, obj);
          } else {
            vals[startIndex + i] = readFieldValue(fieldInfo, buffer);
          }
          partFieldInfo = buffer.readInt64();
        } else {
          if ((partFieldInfo & 0b11) == FieldResolver.SEPARATE_TYPES_HASH_FLAG) {
            if (partFieldInfo < encodedFieldInfo) {
              long part = fieldResolver.skipDataBy8(buffer, partFieldInfo);
              if (part != partFieldInfo) {
                return;
              }
              partFieldInfo = buffer.readInt64();
              i--;
            }
          } else {
            break;
          }
        }
      }
    }
    fieldResolver.skipEndFields(buffer, partFieldInfo);
  }

  private void readAndSetFieldValue(
      FieldResolver.FieldInfo fieldInfo, MemoryBuffer buffer, Object targetObject) {
    FieldAccessor fieldAccessor = fieldInfo.getFieldAccessor();
    short classId = fieldInfo.getEmbeddedClassId();
    boolean nullable = fieldInfo.isNullable();
    if (AbstractObjectSerializer.readPrimitiveFieldValueFailed(
            fory, buffer, targetObject, fieldAccessor, classId)
        && (nullable
            ? AbstractObjectSerializer.readBasicNullableObjectFieldValueFailed(
                fory, buffer, targetObject, fieldAccessor, classId)
            : AbstractObjectSerializer.readBasicObjectFieldValueFailed(
                fory, buffer, targetObject, fieldAccessor, classId))) {
      if (classId == ClassResolver.NO_CLASS_ID) {
        // SEPARATE_TYPES_HASH
        Object fieldValue = fieldResolver.readObjectField(buffer, fieldInfo);
        fieldAccessor.putObject(targetObject, fieldValue);
      } else {
        ClassInfo classInfo = fieldInfo.getClassInfo(classId);
        Serializer<Object> serializer = classInfo.getSerializer();
        fieldAccessor.putObject(targetObject, fory.readRef(buffer, serializer));
      }
    }
  }

  private Object readFieldValue(FieldResolver.FieldInfo fieldInfo, MemoryBuffer buffer) {
    short classId = fieldInfo.getEmbeddedClassId();
    // PRIMITIVE fields, not need for null check.
    switch (classId) {
      case ClassResolver.PRIMITIVE_BOOLEAN_CLASS_ID:
        return buffer.readBoolean();
      case ClassResolver.PRIMITIVE_BYTE_CLASS_ID:
        return buffer.readByte();
      case ClassResolver.PRIMITIVE_CHAR_CLASS_ID:
        return buffer.readChar();
      case ClassResolver.PRIMITIVE_SHORT_CLASS_ID:
        return buffer.readInt16();
      case ClassResolver.PRIMITIVE_INT_CLASS_ID:
        if (fory.compressInt()) {
          return buffer.readVarInt32();
        } else {
          return buffer.readInt32();
        }
      case ClassResolver.PRIMITIVE_FLOAT_CLASS_ID:
        return buffer.readFloat32();
      case ClassResolver.PRIMITIVE_LONG_CLASS_ID:
        return fory.readInt64(buffer);
      case ClassResolver.PRIMITIVE_DOUBLE_CLASS_ID:
        return buffer.readFloat64();
      case ClassResolver.STRING_CLASS_ID:
        return fory.readJavaStringRef(buffer);
      case ClassResolver.NO_CLASS_ID:
        return fieldResolver.readObjectField(buffer, fieldInfo);
      default:
        {
          ClassInfo classInfo = fieldInfo.getClassInfo(classId);
          Serializer<Object> serializer = classInfo.getSerializer();
          return fory.readRef(buffer, serializer);
        }
    }
  }
}
