# PyFory Nanobind Extensions

基于nanobind的高效C++扩展示例。Nanobind是一个轻量级的Python C++绑定库，比pybind11更高效。

## 快速开始

### 构建扩展

```bash
cd python
./build_nanobind_extensions.sh
```

### 使用示例

```python
from pyfory.nanobind_extensions import math_ops

# 基础加法运算
result = math_ops.add(1, 2)
print(f"1 + 2 = {result}")  # 输出: 1 + 2 = 3

# 支持关键字参数和默认值
result = math_ops.add(a=5, b=3)
print(f"5 + 3 = {result}")  # 输出: 5 + 3 = 8

# 使用默认值
result = math_ops.add(10)
print(f"10 + 1 = {result}")  # 输出: 10 + 1 = 11

# 函数重载支持
print(math_ops.multiply(4, 5))      # 整数相乘: 20
print(math_ops.multiply(3.14, 2.0)) # 浮点相乘: 6.28

# 类支持
calc = math_ops.Calculator(100)
print(calc)              # <Calculator value=100>
calc.add(50)
print(calc)              # <Calculator value=150>
```

## 功能特性

- ✨ 基础数学运算函数(add, multiply)
- 🔄 函数重载支持(int/double)
- 📦 完整的类绑定示例(Calculator)
- 🚀 高性能: 比pybind11编译快4倍，二进制小5倍，运行时开销低10倍
- ✅ 完整的测试和文档

## 依赖要求

- Python 3.8+
- CMake 3.15+
- C++17兼容编译器
- nanobind库 (自动安装)

## 运行示例和测试

```bash
# 运行示例
python3 pyfory/nanobind_extensions/example.py

# 运行测试
python3 -m pytest pyfory/nanobind_extensions/tests/ -v
```

## 架构说明

```
nanobind_extensions/
├── README.md                    # 本文档
├── __init__.py                  # 包初始化，支持导入失败处理
├── CMakeLists.txt               # CMake构建配置
├── example.py                   # 完整使用示例
├── src/
│   └── math_ops.cpp            # C++源代码实现
└── tests/
    └── test_math_ops.py        # 完整测试套件
```

## 扩展开发

添加新函数的步骤：

1. 在`src/math_ops.cpp`中实现C++函数
2. 在`NB_MODULE`部分添加Python绑定
3. 在`tests/test_math_ops.py`中添加测试
4. 重新构建: `./build_nanobind_extensions.sh`

示例：
```cpp
// 1. 实现C++函数
int subtract(int a, int b) {
    return a - b;
}

// 2. 在NB_MODULE中添加绑定
NB_MODULE(math_ops, m) {
    // ... 其他绑定 ...
    m.def("subtract", &subtract, "a"_a, "b"_a, "Subtract b from a");
}
```

## 技术优势

- **编译性能**: 相比pybind11编译时间减少75%
- **二进制大小**: 生成的扩展文件大小减少80%  
- **运行时性能**: 函数调用开销减少90%
- **现代C++**: 支持C++17特性，类型安全
- **跨平台**: 支持Linux、macOS、Windows

## 故障排除

**构建失败**:
- 确保已安装nanobind: `pip install nanobind`
- 检查CMake版本: `cmake --version` (需要3.15+)
- 检查C++编译器支持C++17

**导入失败**:
- 重新构建扩展
- 检查Python路径设置
- 查看错误信息中的具体原因
