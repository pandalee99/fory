#!/usr/bin/env python3
"""
详细的性能分析工具，用于调查nanobind为什么比Cython慢
"""

import time
import sys
import os
import cProfile
import pstats
import io
from typing import Callable, List, Dict, Any

# 添加路径以导入模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# 导入nanobind实现
try:
    import buffer_ops as nanobind_buffer
    NANOBIND_AVAILABLE = True
    print("✅ Nanobind Buffer 已导入")
except ImportError as e:
    print(f"❌ 无法导入nanobind buffer: {e}")
    NANOBIND_AVAILABLE = False

# 导入Cython实现  
try:
    from pyfory._util import Buffer as CythonBuffer
    CYTHON_AVAILABLE = True
    print("✅ Cython Buffer 已导入")
except ImportError as e:
    print(f"❌ 无法导入Cython buffer: {e}")
    CYTHON_AVAILABLE = False


class DetailedPerformanceAnalyzer:
    """详细的性能分析器"""
    
    def __init__(self):
        self.results = {}
    
    def profile_function(self, func: Callable, name: str, iterations: int = 1000) -> Dict[str, Any]:
        """使用cProfile分析函数性能"""
        pr = cProfile.Profile()
        
        # 预热
        for _ in range(10):
            func()
        
        # 开始分析
        pr.enable()
        start_time = time.perf_counter()
        
        for _ in range(iterations):
            func()
            
        end_time = time.perf_counter()
        pr.disable()
        
        # 收集统计数据
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats(10)  # 显示前10个函数
        
        return {
            'total_time': end_time - start_time,
            'avg_time': (end_time - start_time) / iterations,
            'profile_stats': s.getvalue(),
            'iterations': iterations
        }
    
    def analyze_basic_operations(self):
        """分析基础操作的性能差异"""
        print("\n🔍 分析基础操作性能差异")
        print("=" * 60)
        
        if not (NANOBIND_AVAILABLE and CYTHON_AVAILABLE):
            print("❌ 需要同时有nanobind和Cython实现")
            return
        
        # 测试写入操作
        def nanobind_write():
            buf = nanobind_buffer.Buffer.allocate(1000)
            for i in range(100):
                buf.write_int32(i)
                buf.write_float(i * 1.1)
                buf.write_bool(i % 2 == 0)
        
        def cython_write():
            buf = CythonBuffer.allocate(1000)
            for i in range(100):
                buf.write_int32(i)
                buf.write_float(i * 1.1)
                buf.write_bool(i % 2 == 0)
        
        print("🚀 分析Nanobind写入操作:")
        nanobind_results = self.profile_function(nanobind_write, "nanobind_write", 1000)
        print(f"平均时间: {nanobind_results['avg_time']*1000:.3f}ms")
        
        print("\n🐍 分析Cython写入操作:")
        cython_results = self.profile_function(cython_write, "cython_write", 1000)
        print(f"平均时间: {cython_results['avg_time']*1000:.3f}ms")
        
        print(f"\n📊 性能对比:")
        speedup = nanobind_results['avg_time'] / cython_results['avg_time']
        print(f"Cython比Nanobind快 {speedup:.2f}x")
        
        # 显示详细的性能分析
        print(f"\n📈 Nanobind详细分析:")
        print(nanobind_results['profile_stats'][:500] + "...")
        
        print(f"\n📈 Cython详细分析:")
        print(cython_results['profile_stats'][:500] + "...")
    
    def analyze_memory_allocation(self):
        """分析内存分配开销"""
        print("\n🧠 分析内存分配开销")
        print("=" * 60)
        
        if not (NANOBIND_AVAILABLE and CYTHON_AVAILABLE):
            return
        
        def nanobind_allocation():
            for _ in range(100):
                buf = nanobind_buffer.Buffer.allocate(1000)
                del buf
        
        def cython_allocation():
            for _ in range(100):
                buf = CythonBuffer.allocate(1000)
                del buf
        
        nanobind_results = self.profile_function(nanobind_allocation, "nanobind_allocation", 1000)
        cython_results = self.profile_function(cython_allocation, "cython_allocation", 1000)
        
        print(f"Nanobind分配: {nanobind_results['avg_time']*1000:.3f}ms")
        print(f"Cython分配: {cython_results['avg_time']*1000:.3f}ms")
        print(f"分配开销差异: {nanobind_results['avg_time'] / cython_results['avg_time']:.2f}x")
    
    def analyze_type_conversion_overhead(self):
        """分析类型转换开销"""
        print("\n🔄 分析类型转换开销")
        print("=" * 60)
        
        if not (NANOBIND_AVAILABLE and CYTHON_AVAILABLE):
            return
        
        # 字节操作转换开销
        test_data = b"hello" * 100
        
        def nanobind_bytes():
            buf = nanobind_buffer.Buffer.allocate(10000)
            for _ in range(50):
                buf.write_bytes(list(test_data))  # 需要转换为list
        
        def cython_bytes():
            buf = CythonBuffer.allocate(10000)
            for _ in range(50):
                buf.write_bytes(test_data)  # 直接使用bytes
        
        nanobind_results = self.profile_function(nanobind_bytes, "nanobind_bytes", 500)
        cython_results = self.profile_function(cython_bytes, "cython_bytes", 500)
        
        print(f"Nanobind字节操作: {nanobind_results['avg_time']*1000:.3f}ms")
        print(f"Cython字节操作: {cython_results['avg_time']*1000:.3f}ms")
        conversion_overhead = nanobind_results['avg_time'] / cython_results['avg_time']
        print(f"类型转换开销: {conversion_overhead:.2f}x")
        
        # 字符串操作
        test_string = "hello world test string" * 10
        
        def nanobind_string():
            buf = nanobind_buffer.Buffer.allocate(10000)
            for _ in range(100):
                buf.write_string(test_string)
        
        def cython_string():
            buf = CythonBuffer.allocate(10000)
            for _ in range(100):
                buf.write_string(test_string)
        
        nanobind_results = self.profile_function(nanobind_string, "nanobind_string", 500)
        cython_results = self.profile_function(cython_string, "cython_string", 500)
        
        print(f"Nanobind字符串操作: {nanobind_results['avg_time']*1000:.3f}ms")
        print(f"Cython字符串操作: {cython_results['avg_time']*1000:.3f}ms")
        string_overhead = nanobind_results['avg_time'] / cython_results['avg_time']
        print(f"字符串转换开销: {string_overhead:.2f}x")
    
    def analyze_function_call_overhead(self):
        """分析函数调用开销"""
        print("\n📞 分析函数调用开销")
        print("=" * 60)
        
        if not (NANOBIND_AVAILABLE and CYTHON_AVAILABLE):
            return
        
        # 创建buffer实例
        nanobind_buf = nanobind_buffer.Buffer.allocate(10000)
        cython_buf = CythonBuffer.allocate(10000)
        
        def nanobind_calls():
            for _ in range(1000):
                nanobind_buf.write_int32(42)
        
        def cython_calls():
            for _ in range(1000):
                cython_buf.write_int32(42)
        
        nanobind_results = self.profile_function(nanobind_calls, "nanobind_calls", 1000)
        cython_results = self.profile_function(cython_calls, "cython_calls", 1000)
        
        print(f"Nanobind函数调用: {nanobind_results['avg_time']*1000:.3f}ms (每次调用: {nanobind_results['avg_time']*1000000:.1f}ns)")
        print(f"Cython函数调用: {cython_results['avg_time']*1000:.3f}ms (每次调用: {cython_results['avg_time']*1000000:.1f}ns)")
        call_overhead = nanobind_results['avg_time'] / cython_results['avg_time']
        print(f"函数调用开销: {call_overhead:.2f}x")
    
    def run_comprehensive_analysis(self):
        """运行全面性能分析"""
        print("🔬 PyFory Buffer性能深度分析")
        print("=" * 60)
        print("目标: 调查nanobind为什么比Cython慢")
        print("=" * 60)
        
        self.analyze_basic_operations()
        self.analyze_memory_allocation() 
        self.analyze_type_conversion_overhead()
        self.analyze_function_call_overhead()
        
        print("\n🎯 结论和建议")
        print("=" * 60)
        print("基于以上分析，nanobind可能比Cython慢的原因：")
        print("1. 类型转换开销 - bytes和字符串需要额外转换")
        print("2. 函数调用开销 - nanobind的Python-C++调用可能有额外开销")
        print("3. 内存管理开销 - 不同的内存分配策略")
        print("4. 编译优化 - Cython针对Python操作做了特殊优化")


def main():
    analyzer = DetailedPerformanceAnalyzer()
    analyzer.run_comprehensive_analysis()


if __name__ == "__main__":
    main()
