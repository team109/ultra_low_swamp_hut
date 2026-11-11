<a id="chinese"></a>

# Ultra Low Hut：超低沼泽小屋

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

搜索自然生成、最低女巫生成高度低于 Y=−54 的沼泽小屋。这个最低 Y 坐标记为 **HPos**。支持 Minecraft Java **1.19.3–26.3**。

可以直接使用仓库收录的已知小屋，也可以用随附的 101 个矿井模板搜索新种子。模板记录矿井形状及其与小屋的相对位置；矿井挖空地形后，小屋可能生成得更低。

## 使用已知小屋

打开[小屋列表](docs/SEEDS.md)，选择游戏版本和高度，再读取对应的 JSONL 文件。每行是一处已知小屋：`seed` 是世界种子，`x`、`z` 是小屋起始方块坐标；文件名如 `y-59.jsonl` 表示测得最低 HPos 为 −59。

已发布列表使用正常世界。受加载顺序影响的记录带有 `min_hpos_order`，给出达到文件标称高度的区块装饰顺序；用法见[首次生成与顺序复现](docs/VERIFICATION.md#reproduce-order)。字段含义见[数据说明](data/huts/README.md)。

## 搜索新小屋

### 1. 安装与构建

需要 Linux、NVIDIA GPU、Python 3.10+、Git、CMake 3.20+、C 编译器和支持 C++17 的 C++ 编译器、NVIDIA 驱动和 CUDA Toolkit。Python 代码只使用标准库。原版验证需要 Java 21（1.19.3–1.21.11）或 Java 25（26.x）。

下载仓库后，在仓库根目录执行以下命令。示例使用 1.21 和 A100：

```bash
python3 scripts/build/dependencies.py
cmake -S . -B build-cpu-worlds -DCMAKE_BUILD_TYPE=Release
cmake --build build-cpu-worlds -j 4
python3 scripts/build/search.py --version 1.21 --arch sm_80
python3 scripts/verification/artifacts.py --version 1.21 --java java
```

`--arch` 按显卡设置，例如 A100 为 `sm_80`，A10 为 `sm_86`。`java` 应指向 Java 21。准备命令会下载缺失的依赖和官方服务端。搜索其他版本时，同时修改构建、服务端准备和搜索命令的 `--version`，并使用对应的 Java；版本列表见[版本说明](docs/VERSIONS.md)。

### 2. 选择模板并搜索

先选取一个矿井模板，再启动搜索：

```bash
python3 scripts/layouts/select.py --seed 270840896143627 --output runs/layout.json
python3 scripts/search.py --version 1.21 --layout-template runs/layout.json --root runs/my-search --devices 0 --java java --record-height -55 --target-height -59 --accept-eula
```

选择命令的 `--seed` 是矿井布局种子。可选值位于 [templates.json](data/mineshafts/templates.json) 的 `target` 字段。

| 参数 | 作用 |
|---|---|
| `--devices 0` | 使用 GPU 0；多卡用逗号分隔，如 `0,1` |
| `--root runs/my-search` | 保存本次搜索的参数、进度和结果；新任务使用新目录 |
| `--record-height -55` | 记录 HPos≤−55 的结果 |
| `--target-height -59` | 找到 HPos≤−59 的结果时停止 |
| `--exhaust` | 达到目标后继续搜索，直到该模板的配置范围全部完成 |
| `--accept-eula` | 接受 Minecraft EULA，允许启动原版验证服务 |

默认 `--verification on` 会用原版生成代码检查候选及配置的区块加载顺序。只保留 CPU 筛选结果时使用 `--verification off`，可省略 `--java` 和 `--accept-eula`；结果中的 `native_y` 是 CPU 算出的参考高度。

一次提交全部随附模板，按顺序搜索：

```bash
python3 scripts/campaign.py --version 1.21 --layout-pool data/mineshafts/templates.json --root runs/my-pool --devices 0 --java java --stop-when-pool-exhausted --accept-eula
```

### 3. 读取结果与恢复搜索

单模板搜索的结果保存在 `--root` 指定的目录：

| 文件 | 内容 |
|---|---|
| `results.jsonl` | `on` 模式的简明结果，含种子、坐标、`spawn_y` 和适用版本 |
| `verified-huts.jsonl` | `on` 模式的验证记录，高度字段为 `HPos` |
| `low-huts.jsonl` | 达到 `--record-height` 的结果 |
| `shortlist.jsonl` | `off` 模式的候选及参考高度 `native_y` |
| `progress.json` | 当前进度与速度；`on` 模式另有 `progress.jsonl` 进度历史 |
| `first-hits.jsonl` | 首次达到各高度的结果 |

批量搜索在根目录汇总各模板的结果：

| 文件 | 内容 |
|---|---|
| `verified-huts.jsonl` | `on` 模式的全部验证结果，高度字段为 `HPos` |
| `low-huts.jsonl` | 达到 `--record-height` 的结果 |
| `shortlist.jsonl` | `off` 模式的候选，高度字段为 `native_y` |
| `progress.json` | 全部模板的汇总进度 |
| `first-hits.jsonl` | 整批搜索首次达到各高度的结果 |

每个模板的单独结果位于 `phases/phaseXXXXXX/run/`。`spawn_y` 与 `HPos` 都表示所测加载顺序中的最低 HPos。`loading_order_affected=true` 表示改变顺序会改变小屋高度或使小屋无法生成。

按 Ctrl+C 停止后，用原目录恢复。单模板搜索和批量搜索分别使用原来的入口：

```bash
python3 scripts/search.py --root runs/my-search --resume --java java --accept-eula
python3 scripts/campaign.py --root runs/my-pool --resume --java java --stop-when-pool-exhausted --accept-eula
```

恢复时可用 `--verify-workers 8` 调整验证进程数，用 `--verify-java 1.21=/path/to/java` 调整指定版本的 Java 路径。

### 世界类型

构建和搜索时使用相同的世界参数：

| 参数 | 世界类型 |
|---|---|
| `--world-type normal` | 正常世界，默认值 |
| `--world-type large_biomes` | 大型生物群系世界 |
| `--world-type single_biome --biome minecraft:swamp` | 单一沼泽生物群系世界 |

例如搜索单一沼泽生物群系世界，在上述安装步骤完成后执行：

```bash
python3 scripts/build/search.py --version 1.21 --world-type single_biome --biome minecraft:swamp --arch sm_80
python3 scripts/search.py --version 1.21 --world-type single_biome --biome minecraft:swamp --layout-template runs/layout.json --root runs/my-single-swamp --devices 0 --java java --accept-eula
```

大型生物群系将两条命令的世界参数换成 `--world-type large_biomes`，省略 `--biome`。批量搜索入口接受相同参数。每种世界使用独立的结果目录，恢复时沿用已保存的参数。

本项目单群系默认选择沼泽。支持版本中只有沼泽能生成女巫小屋，选择其他合法群系时搜索返回空结果。单群系结果另存 `biome`，所有结果都记录 `world_type`。

## 其他用法

- [自行枚举矿井布局、测量产率](docs/LAYOUT_SEARCH.md)
- [运行原版查询服务、验证多个版本或批量测量加载顺序](docs/VERIFICATION.md)
- [调整搜索参数和加载顺序](config/README.md)
- [CPU 测试与源码打包](docs/PACKAGING.md)
- [了解搜索算法](docs/ALGORITHM.md) · [全部文档](docs/README.md)

许可证：[MIT](LICENSE)。依赖与署名见 [THIRD_PARTY.md](THIRD_PARTY.md)。

---

<a id="english"></a>

# Ultra Low Hut

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

Search for naturally generated swamp huts whose lowest witch-spawning height is below Y=−54. This lowest Y coordinate is called **HPos**. Supports Minecraft Java **1.19.3–26.3**.

Use the known huts included in the repository, or search for new seeds with the supplied 101 mineshaft templates. A template records mineshaft geometry and its position relative to a hut; the mineshaft’s excavation can allow the hut to generate lower.

## Use known huts

Open the [hut catalog](docs/SEEDS.md#english), select a game version and height, then read the corresponding JSONL file. Each line identifies a known hut: `seed` is the world seed and `x`/`z` are its starting block coordinates. A filename such as `y-59.jsonl` indicates a measured minimum HPos of −59.

Published huts use normal worlds. Affected records include `min_hpos_order`, a chunk decoration order attaining the height in the filename; see [first generation and order reproduction](docs/VERIFICATION.md#reproduce-order-en). See the [data guide](data/huts/README.md#english) for field definitions.

## Search for new huts

### 1. Install and build

Requires Linux, an NVIDIA GPU, Python 3.10+, Git, CMake 3.20+, C and C++17 compilers, an NVIDIA driver and CUDA Toolkit. Python uses only the standard library. Vanilla verification requires Java 21 for 1.19.3–1.21.11 or Java 25 for 26.x.

After downloading the repository, run these commands from its root. This example uses 1.21 and an A100:

```bash
python3 scripts/build/dependencies.py
cmake -S . -B build-cpu-worlds -DCMAKE_BUILD_TYPE=Release
cmake --build build-cpu-worlds -j 4
python3 scripts/build/search.py --version 1.21 --arch sm_80
python3 scripts/verification/artifacts.py --version 1.21 --java java
```

Set `--arch` for your GPU, such as `sm_80` for A100 or `sm_86` for A10. Here `java` must select Java 21. Preparation downloads missing dependencies and official server files. For another release, change `--version` in the build, server preparation and search commands together, and use the corresponding Java runtime. See [versions](docs/VERSIONS.md#english).

### 2. Select a template and search

Select a mineshaft template, then start the search:

```bash
python3 scripts/layouts/select.py --seed 270840896143627 --output runs/layout.json
python3 scripts/search.py --version 1.21 --layout-template runs/layout.json --root runs/my-search --devices 0 --java java --record-height -55 --target-height -59 --accept-eula
```

The selection command’s `--seed` is a mineshaft layout seed. Available values are the `target` fields in [templates.json](data/mineshafts/templates.json).

| Option | Effect |
|---|---|
| `--devices 0` | Use GPU 0; separate multiple GPU IDs with commas, such as `0,1` |
| `--root runs/my-search` | Store search settings, progress and results; use a new directory for each new search |
| `--record-height -55` | Record results with HPos≤−55 |
| `--target-height -59` | Stop after finding HPos≤−59 |
| `--exhaust` | Continue after reaching the target until the template’s configured range is exhausted |
| `--accept-eula` | Accept the Minecraft EULA to start vanilla verification |

The default `--verification on` checks candidates and configured chunk loading orders with vanilla generation code. Use `--verification off` to retain CPU-screened candidates, omitting `--java` and `--accept-eula`; `native_y` records the CPU reference height.

To search all supplied templates in order:

```bash
python3 scripts/campaign.py --version 1.21 --layout-pool data/mineshafts/templates.json --root runs/my-pool --devices 0 --java java --stop-when-pool-exhausted --accept-eula
```

### 3. Read results and resume

Single-template search writes these files beneath `--root`:

| File | Contents |
|---|---|
| `results.jsonl` | Compact `on` results: seeds, coordinates, `spawn_y` and applicable versions |
| `verified-huts.jsonl` | `on` verification records, with height stored as `HPos` |
| `low-huts.jsonl` | Results meeting `--record-height` |
| `shortlist.jsonl` | Candidates and reference height `native_y` in `off` mode |
| `progress.json` | Current progress and speed; `on` also writes progress history to `progress.jsonl` |
| `first-hits.jsonl` | First result reaching each height |

Multi-template search aggregates results at its root:

| File | Contents |
|---|---|
| `verified-huts.jsonl` | All `on` verification results, with height stored as `HPos` |
| `low-huts.jsonl` | Results meeting `--record-height` |
| `shortlist.jsonl` | `off` candidates, with height stored as `native_y` |
| `progress.json` | Combined progress across templates |
| `first-hits.jsonl` | First result reaching each height across the campaign |

Individual template outputs live in `phases/phaseXXXXXX/run/`. Both `spawn_y` and `HPos` mean the minimum HPos across measured loading orders. `loading_order_affected=true` means changing the order changes the height or prevents the hut from generating.

After Ctrl+C, resume with the original directory and entry point:

```bash
python3 scripts/search.py --root runs/my-search --resume --java java --accept-eula
python3 scripts/campaign.py --root runs/my-pool --resume --java java --stop-when-pool-exhausted --accept-eula
```

When resuming, use `--verify-workers 8` to change verification concurrency or `--verify-java 1.21=/path/to/java` to change the Java executable for a selected version.

### World types

Use matching world options when building and searching:

| Option | World type |
|---|---|
| `--world-type normal` | Normal world, the default |
| `--world-type large_biomes` | Large-biome world |
| `--world-type single_biome --biome minecraft:swamp` | Single-swamp-biome world |

After the setup above, search a single-swamp world with:

```bash
python3 scripts/build/search.py --version 1.21 --world-type single_biome --biome minecraft:swamp --arch sm_80
python3 scripts/search.py --version 1.21 --world-type single_biome --biome minecraft:swamp --layout-template runs/layout.json --root runs/my-single-swamp --devices 0 --java java --accept-eula
```

For large biomes, replace the world options in both commands with `--world-type large_biomes` and omit `--biome`. Multi-template search accepts the same options. Use a separate result directory for each world and retain its saved settings when resuming.

Single-biome worlds default to swamp in this project. Swamp is the only hut-generating biome in supported versions; other valid biomes return an empty search result. All results record `world_type`, with `biome` additionally recorded for single-biome worlds.

## Other uses

- [Enumerate layouts and measure their yield](docs/LAYOUT_SEARCH.md#english)
- [Run vanilla queries, verify multiple versions or measure loading orders in batches](docs/VERIFICATION.md#english)
- [Adjust search settings and loading orders](config/README.md#english)
- [CPU tests and source packaging](docs/PACKAGING.md#english)
- [Search algorithm](docs/ALGORITHM.md#english) · [All documentation](docs/README.md#english)

License: [MIT](LICENSE). See [THIRD_PARTY.md](THIRD_PARTY.md#english) for dependencies and attribution.
