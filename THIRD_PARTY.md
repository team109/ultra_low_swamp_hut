<a id="chinese"></a>

# 依赖与署名

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

本文件列出发布代码实际使用的第三方组件。

| 依赖 | 版本或提交 | 用途 | 许可证 |
|---|---|---|---|
| [LowYSwampHut](https://github.com/M33Galaxy/LowYSwampHut) | `bfb1a27c0083f766a067d9521206ac902d97964b` | 供 CPU 精筛计算地形高度 | [MIT](LICENSES/LowYSwampHut-MIT.txt)，Copyright (c) 2026 M33Galaxy, SunnySlopes |
| [cubiomes](https://github.com/xpple/cubiomes) | LowYSwampHut 内嵌版本 | 按种子和坐标查询生物群系 | [MIT](LICENSES/cubiomes-MIT.txt)，Copyright (c) 2020 Cubitect |
| SpecialSource | 1.11.4 | 转换服务端类与方法名称，供项目代码调用 | [BSD-3-Clause](https://repo.maven.apache.org/maven2/net/md-5/SpecialSource/1.11.4/SpecialSource-1.11.4.pom) |
| Eclipse ECJ | 3.44.0 | 编译调用、观察原版生成过程的 Java 代码 | [EPL-2.0](https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.44.0/ecj-3.44.0.pom) |
| ASM | 9.9 | 在 Java 类加载时加入记录生成顺序等操作 | [BSD-3-Clause](LICENSES/ASM-BSD-3-Clause.txt) |
| Gson | 所选服务端附带版本 | 读取请求字段并写出结果字段 | [Apache-2.0](https://github.com/google/gson/blob/main/LICENSE) |
| Authlib | 所选服务端附带版本 | 满足原版生成代码启动时需要的认证类依赖 | [上游组件信息](https://libraries.minecraft.net/com/mojang/authlib/6.0.54/authlib-6.0.54.pom) |

`external/LowYSwampHut/lysh-c/src` 提供 CPU 地形参考实现，由 [CMake](CMakeLists.txt) 编译进程序库 `libmcsearch.so`，供 [CPU 精筛](src/ultra_low_hut/search/reference/native.py) 调用。所用源码版本见 [sources.lock.json](sources.lock.json)。

---

<a id="english"></a>

# Dependencies and attribution

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

This file lists third-party components used by the published code.

| Dependency | Version or revision | Use | License |
|---|---|---|---|
| [LowYSwampHut](https://github.com/M33Galaxy/LowYSwampHut) | `bfb1a27c0083f766a067d9521206ac902d97964b` | Terrain height calculations for CPU screening | [MIT](LICENSES/LowYSwampHut-MIT.txt), Copyright (c) 2026 M33Galaxy, SunnySlopes |
| [cubiomes](https://github.com/xpple/cubiomes) | Included in LowYSwampHut | Look up biomes from seeds and coordinates | [MIT](LICENSES/cubiomes-MIT.txt), Copyright (c) 2020 Cubitect |
| SpecialSource | 1.11.4 | Translate server class and method names so project code can call them | [BSD-3-Clause](https://repo.maven.apache.org/maven2/net/md-5/SpecialSource/1.11.4/SpecialSource-1.11.4.pom) |
| Eclipse ECJ | 3.44.0 | Compile Java code that calls and observes vanilla generation | [EPL-2.0](https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.44.0/ecj-3.44.0.pom) |
| ASM | 9.9 | Add operations such as recording generation order while Java classes load | [BSD-3-Clause](LICENSES/ASM-BSD-3-Clause.txt) |
| Gson | Version supplied by the selected server | Read request fields and write result fields | [Apache-2.0](https://github.com/google/gson/blob/main/LICENSE) |
| Authlib | Version supplied by the selected server | Provide authentication classes needed when vanilla generation code starts | [Upstream component information](https://libraries.minecraft.net/com/mojang/authlib/6.0.54/authlib-6.0.54.pom) |

`external/LowYSwampHut/lysh-c/src` supplies the CPU terrain reference, compiled by [CMake](CMakeLists.txt) into the library `libmcsearch.so` for [CPU refinement](src/ultra_low_hut/search/reference/native.py). The source version is recorded in [sources.lock.json](sources.lock.json).
