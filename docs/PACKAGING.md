<a id="chinese"></a>

# 测试与源码打包

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

```bash
python3 scripts/release/package.py --output dist/ultra-low-hut-source.tar.gz
```

生成包含源码、配置、文档、测试和发布数据的压缩包。小屋结果严格采用 `data/huts/index.json` 列出的文件；工作区中未入索引的旧结果不进入发布包。

## CPU 测试

从仓库根目录执行，Python 仅使用标准库。CPU 构建与测试不需要 GPU、CUDA 或 Java：

```bash
python3 scripts/build/dependencies.py
cmake -S . -B build-cpu-worlds -DCMAKE_BUILD_TYPE=Release
cmake --build build-cpu-worlds --parallel 2
python3 -m unittest discover -s tests
```

测试自动选用 `build-cpu-worlds/libmcsearch.so`，也可通过 `MCSEARCH_LIBRARY` 指定其他构建。未构建 CPU 库时，依赖它的测试会跳过。测试覆盖搜索收尾、完整配置发布、加载顺序、恢复行为和发布包内容。

[CPU CI](../.github/workflows/cpu.yml) 在生成的源码包内准备依赖、构建 CPU 库并执行同一测试命令；因此也会检查打包是否漏掉运行所需文件。

## 已验证环境

| 项目 | 版本或配置 |
|---|---|
| CPU 构建与测试 | Linux，Python 3.13.13，GCC/G++ 11.4.0，CMake 3.31.1 |
| CUDA 源码编译 | CUDA Toolkit 12.6.68，G++ 11.4.0，C++17，`sm_80`，`--fmad=false` |
| Java 运行时 | Temurin 21.0.12.1 / 25.0.4.1，按游戏版本选择 |
| 加载顺序吞吐测量 | 每机 32 个 CPU，32 个单核 JVM，每个最大堆 6 GiB |

CUDA 编译检查不运行 GPU 搜索。加载顺序吞吐及测量范围见[验证说明](VERIFICATION.md#批量测量)。

---

<a id="english"></a>

# Tests and source packaging

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

```bash
python3 scripts/release/package.py --output dist/ultra-low-hut-source.tar.gz
```

Creates an archive containing source, configuration, documentation, tests and published data. Hut results come strictly from `data/huts/index.json`; old, unindexed results in the working tree are excluded.

## CPU tests

Run from the repository root. Python uses only the standard library. CPU builds and tests require no GPU, CUDA or Java:

```bash
python3 scripts/build/dependencies.py
cmake -S . -B build-cpu-worlds -DCMAKE_BUILD_TYPE=Release
cmake --build build-cpu-worlds --parallel 2
python3 -m unittest discover -s tests
```

Tests automatically select `build-cpu-worlds/libmcsearch.so`. Set `MCSEARCH_LIBRARY` to use another build. Tests requiring the CPU library are skipped when it has not been built. Coverage includes final candidate processing, complete config publication, loading orders, resume behavior and package contents.

[CPU CI](../.github/workflows/cpu.yml) prepares dependencies, builds the CPU library and runs the same test command inside the generated source distribution, also checking for missing runtime files.

## Verified environment

| Component | Version or configuration |
|---|---|
| CPU build and tests | Linux, Python 3.13.13, GCC/G++ 11.4.0, CMake 3.31.1 |
| CUDA source compilation | CUDA Toolkit 12.6.68, G++ 11.4.0, C++17, `sm_80`, `--fmad=false` |
| Java runtimes | Temurin 21.0.12.1 / 25.0.4.1, selected for the game version |
| Loading-order throughput measurement | 32 CPUs per machine, 32 single-core JVMs, maximum heap 6 GiB each |

The CUDA compilation check does not run a GPU search. See [verification](VERIFICATION.md#batch-measurement) for loading-order throughput and measurement scope.
