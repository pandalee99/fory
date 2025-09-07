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

package org.apache.fory.memory;

/** Interface for customizing memory allocation strategies in MemoryBuffer. */
public interface MemoryAllocator {
  /**
   * Allocates a new MemoryBuffer with the specified initial capacity.
   *
   * @param initialCapacity the initial capacity for the buffer
   * @return a new MemoryBuffer instance
   */
  MemoryBuffer allocate(int initialCapacity);

  /**
   * Grows an existing buffer to accommodate the new capacity. The implementation must grow the
   * buffer in-place by modifying the existing buffer instance.
   *
   * @param buffer the existing buffer to grow
   * @param newCapacity the required new capacity
   * @return the same MemoryBuffer instance with at least the new capacity
   */
  MemoryBuffer grow(MemoryBuffer buffer, int newCapacity);
}
