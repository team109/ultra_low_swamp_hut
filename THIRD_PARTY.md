<a id="chinese"></a>

# 依赖与署名

中文 | [English](#english)

| 依赖 | 版本或提交 | 用途 | 许可证 |
|---|---|---|---|
| [LowYSwampHut](https://github.com/M33Galaxy/LowYSwampHut) | `bfb1a27c0083f766a067d9521206ac902d97964b` | CPU 地形参考实现 | [MIT](LICENSES/LowYSwampHut-MIT.txt)，Copyright (c) 2026 M33Galaxy, SunnySlopes |
| [cubiomes](https://github.com/xpple/cubiomes) | LowYSwampHut 内嵌版本 | 生物群系树及查询算法 | [MIT](LICENSES/cubiomes-MIT.txt)，Copyright (c) 2020 Cubitect |
| SpecialSource | 1.11.4 | 服务端字节码映射 | [BSD-3-Clause](https://repo.maven.apache.org/maven2/net/md-5/SpecialSource/1.11.4/SpecialSource-1.11.4.pom) |
| Eclipse ECJ | 3.44.0 | Java 代理编译 | [EPL-2.0](https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.44.0/ecj-3.44.0.pom) |
| ASM | 9.9 | Java 代理字节码插桩 | [BSD-3-Clause](LICENSES/ASM-BSD-3-Clause.txt) |
| Gson | 所选服务端附带版本 | JSON 请求与响应 | [Apache-2.0](https://github.com/google/gson/blob/main/LICENSE) |
| Authlib | 所选服务端附带版本 | 查询服务启动 | 上游 JAR 和 [POM](https://libraries.minecraft.net/com/mojang/authlib/6.0.54/authlib-6.0.54.pom) 未声明许可证 |


原生源码依赖的版本与文件校验值见 [sources.lock.json](sources.lock.json)。世界生成实现参考 Minecraft Java 版，源码版本见 [source-commits.json](data/versions/source-commits.json)。

---

<a id="english"></a>

[中文](#chinese) | English

# Dependencies and attribution

| Dependency | Version or revision | Use | License |
|---|---|---|---|
| [LowYSwampHut](https://github.com/M33Galaxy/LowYSwampHut) | `bfb1a27c0083f766a067d9521206ac902d97964b` | CPU terrain reference | [MIT](LICENSES/LowYSwampHut-MIT.txt), Copyright (c) 2026 M33Galaxy, SunnySlopes |
| [cubiomes](https://github.com/xpple/cubiomes) | Included in LowYSwampHut | Biome trees and lookup algorithms | [MIT](LICENSES/cubiomes-MIT.txt), Copyright (c) 2020 Cubitect |
| SpecialSource | 1.11.4 | Server bytecode remapping | [BSD-3-Clause](https://repo.maven.apache.org/maven2/net/md-5/SpecialSource/1.11.4/SpecialSource-1.11.4.pom) |
| Eclipse ECJ | 3.44.0 | Java agent compilation | [EPL-2.0](https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.44.0/ecj-3.44.0.pom) |
| ASM | 9.9 | Java agent bytecode instrumentation | [BSD-3-Clause](LICENSES/ASM-BSD-3-Clause.txt) |
| Gson | Version supplied by the selected server | JSON requests and responses | [Apache-2.0](https://github.com/google/gson/blob/main/LICENSE) |
| Authlib | Version supplied by the selected server | Query-service bootstrap | No license declared in the upstream JAR or [POM](https://libraries.minecraft.net/com/mojang/authlib/6.0.54/authlib-6.0.54.pom) |


The revision and file checksums for the native source dependency are in [sources.lock.json](sources.lock.json). World generation implementations reference Minecraft Java Edition; source revisions are in [source-commits.json](data/versions/source-commits.json).
