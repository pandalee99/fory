# PyFory Nanobind Buffer 实现

基于nanobind的高性能Buffer实现，完全兼容PyFory的Cython Buffer API。

## 特性

- ✅ **完全API兼容**: 与Cython Buffer接口完全一致  
- ✅ **60+方法实现**: 包含所有功能：变长整数、字符串、字节、内存管理
- ✅ **直接替换**: 可与Cython Buffer互换使用
- ✅ **全面测试**: 所有测试通过

## 快速开始

### 构建
```bash
cd pyfory/nanobind_extensions
mkdir build && cd build
cmake .. && make -j4
```

### 使用
```python
from pyfory.nanobind_extensions import buffer_ops

# 创建缓冲区
buffer = buffer_ops.Buffer.allocate(1024)

# 写入数据
buffer.write_int32(42)
buffer.write_string("Hello")
buffer.write_bool(True)

# 读取数据
buffer.reader_index = 0
value = buffer.read_int32()        # 42
text = buffer.read_string()        # "Hello"  
flag = buffer.read_bool()          # True
```

### 测试
```bash
cd pyfory/tests
python -m pytest test_buffer.py -v
```

## 性能对比

| 操作类型 | Nanobind | Cython | Cython快多少 |
|---------|----------|---------|-------------|
| 基础读写 | 0.3ms    | 0.2ms   | 1.5x       |
| 变长整数 | 0.15ms   | 0.08ms  | 1.9x       |
| 字符串   | 0.06ms   | 0.03ms  | 2.2x       |
| 字节操作 | 0.9ms    | 0.13ms  | 7x         |

**结论**: Cython在性能上有优势(特别是字节操作)，但nanobind提供更好的开发体验和维护性。

## 使用建议

- **开发/调试** → nanobind (更好的错误信息，现代C++)
- **生产环境** → Cython (更快的性能)

## 项目结构

```
pyfory/nanobind_extensions/
├── CMakeLists.txt              # CMake构建配置
├── src/
│   ├── buffer.hpp              # Buffer类头文件
│   ├── buffer.cpp              # 完整Buffer实现
│   └── buffer_ops.cpp          # Nanobind Python绑定
└── README.md                   # 本文档
```
