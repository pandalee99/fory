#include <benchmark/benchmark.h>
#include "simdutf.h"

#include <chrono>
#include <codecvt>
#include <iostream>
#include <locale>
#include <random>

#include "string_util.h"

#include <string>
#include <cstring>



// Function to generate a random UTF-16 string
std::u16string generateRandomUTF16String2(size_t length) {
  const char charset[] = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  std::default_random_engine rng(std::random_device{}());
  std::uniform_int_distribution<> dist(0, sizeof(charset) - 2);

  std::u16string result;
  result.reserve(length);
  for (size_t i = 0; i < length; ++i) {
    result += static_cast<char16_t>(charset[dist(rng)]);
  }

  return result;
}

std::vector<std::u16string> generate(size_t num_tests){
  std::vector<std::u16string> test_strings;
    for (size_t i = 0; i < num_tests; ++i) {
      test_strings.push_back(generateRandomUTF16String2(num_tests));  // Generate random UTF-16 strings
    }
    return test_strings;
}


const  std::vector<std::u16string> test_strings = generate(1000);

// UTF16 to UTF8 using the standard library
std::string utf16ToUtf8StandardLibrary2(const std::u16string &utf16) {
  std::wstring_convert<std::codecvt_utf8_utf16<char16_t>, char16_t> convert;
  return convert.to_bytes(utf16);
}

// UTF16 to UTF8 baseline conversion (without SIMD)
std::string utf16ToUtf8BaseLine2(const std::u16string &utf16, bool is_little_endian = true) {
  size_t utf16_length = utf16.length();
  size_t utf8_length = utf16_length * 3;
  std::string utf8_result(utf8_length, '\0');

  size_t i = 0, j = 0;
  while (i < utf16_length) {
    char16_t utf16_char = utf16[i++];
    if (utf16_char < 0x80) {
      utf8_result[j++] = static_cast<char>(utf16_char);
    } else if (utf16_char < 0x800) {
      utf8_result[j++] = static_cast<char>(0xC0 | (utf16_char >> 6));
      utf8_result[j++] = static_cast<char>(0x80 | (utf16_char & 0x3F));
    } else {
      utf8_result[j++] = static_cast<char>(0xE0 | (utf16_char >> 12));
      utf8_result[j++] = static_cast<char>(0x80 | ((utf16_char >> 6) & 0x3F));
      utf8_result[j++] = static_cast<char>(0x80 | (utf16_char & 0x3F));
    }
  }

  utf8_result.resize(j);
  return utf8_result;
}

// UTF16 to UTF8 using SIMD
std::string utf16ToUtf8WithSIMDUTF2(const std::u16string &utf16) {
  size_t utf16_length = utf16.length();
  size_t utf8_length = simdutf::utf8_length_from_utf16le(reinterpret_cast<const char16_t *>(utf16.data()), utf16_length);

  std::string utf8_result(utf8_length, '\0');
  size_t written_bytes = simdutf::convert_utf16le_to_utf8(reinterpret_cast<const char16_t *>(utf16.data()), utf16_length, utf8_result.data());

  utf8_result.resize(written_bytes);
  return utf8_result;
}

// Benchmark function for Standard Library UTF-16 to UTF-8 conversion
static void BM_StandardLibrary(benchmark::State& state) {
  for (auto _ : state) {
    for (const auto &str : test_strings) {
      std::string utf8 = utf16ToUtf8StandardLibrary2(str);
    }
  }
}

// Benchmark function for Baseline UTF-16 to UTF-8 conversion
static void BM_BaseLine(benchmark::State& state) {
  for (auto _ : state) {
    for (const auto &str : test_strings) {
      std::string utf8 = utf16ToUtf8BaseLine2(str, true);
    }
  }
}

// Benchmark function for SIMD-based UTF-16 to UTF-8 conversion
static void BM_SIMD(benchmark::State& state) {
  for (auto _ : state) {
    for (const auto &str : test_strings) {
      std::string utf8 = fury::utf16ToUtf8(str, true);
    }
  }
}

// Benchmark function for SIMD-UTF conversion using SIMDUTF library
static void BM_SIMD_UTF(benchmark::State& state) {
  for (auto _ : state) {
    for (const auto &str : test_strings) {
      std::string utf8 = utf16ToUtf8WithSIMDUTF2(str);
    }
  }
}




BENCHMARK(BM_StandardLibrary);
BENCHMARK(BM_BaseLine);
BENCHMARK(BM_SIMD);
BENCHMARK(BM_SIMD_UTF);
BENCHMARK_MAIN();


