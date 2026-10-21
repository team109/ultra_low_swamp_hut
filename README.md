<a id="chinese"></a>

# Ultra Low Hut：超低沼泽小屋

中文 | [English](#english)

除本句外，本仓库全部由 GPT-6 Astra 编写。

在 Linux 和 NVIDIA GPU 上搜索最低可刷怪高度低于 Y=−54 的自然沼泽小屋，支持 **1.19.3–26.3 的全部正式版**。候选由原版世界生成代码验证。最低可刷怪高度记为 **HPos**。

仓库包含两个流程：

- **筛选矿井布局**：枚举布局、计算挖掘量、测量 −59 产率。已附带 [101 个布局的结果](data/mineshafts/1.21/layouts.jsonl)和[完整搜索模板](data/mineshafts/1.21/templates.json)。
- **根据布局搜索小屋**：反解种子与坐标，进行 GPU 地形筛选和原版生成验证，实时输出种子、坐标和高度。

本项目搜索单座普通矿井的起始房间与小屋位于同一区块的情况。**101 个布局来自完整枚举，覆盖这一搜索模型下所有可能产生 −59 小屋的布局。** 矿井布局和小屋选址都由种子的低 48 位决定；先固定有利布局，再反解种子，可把后续地形计算集中在有机会形成超低小屋的位置。布局在自然地形上的产率不同，结果表按产率排序。

## 安装

需要 Python 3.10+、Git、CMake 3.20+、C/C++17 编译器、NVIDIA 驱动和 CUDA Toolkit。Python 只使用标准库。查询服务使用 Java：1.19.3–1.21.11 选 Java 21，26.x 选 Java 25。

在仓库根目录执行：

```bash
python3 tools/fetch_dependencies.py
cmake -S . -B build-cpu -DCMAKE_BUILD_TYPE=Release
cmake --build build-cpu -j 4
python3 tools/build_search.py --version 1.21 --arch sm_80
python3 tools/prepare_version_verifier.py --version 1.21 --java java
```

`sm_80` 适用于 A100/A800；A10 使用 `sm_86`。准备命令会下载依赖和所选版本的服务端文件。

## 搜索小屋

选择布局并启动单卡搜索：

```bash
python3 tools/select_layout.py --seed 270840896143627 --output runs/layout.json
python3 tools/search_huts.py --version 1.21 --layout-template runs/layout.json --root runs/my-search --devices 0 --java java --record-height -55 --target-height -59 --accept-eula
```

八卡搜索使用 `--devices 0,1,2,3,4,5,6,7`。`--record-height` 设置记录阈值，`--target-height` 设置停止阈值；加入 `--exhaust` 可遍历该布局的完整搜索域。Ctrl+C 停止后恢复：

```bash
python3 tools/search_huts.py --root runs/my-search --resume --java java --accept-eula
```

搜索其他版本时，同时修改构建、服务端准备和搜索命令的 `--version`，并选择对应的 Java。版本互通关系见 [版本说明](docs/VERSIONS.md)。

## 读取结果

输出位于 `--root` 指定的目录：

| 文件 | 内容 |
|---|---|
| `results.jsonl` | 实时验证结果：`seed`、`x`、`z`、`spawn_y`、`excavation`、`versions`，以及时间和筛选量 |
| `progress.jsonl` | 每 30 秒更新的进度与吞吐 |
| `first-hits.jsonl` | 首次达到各个高度时的结果与筛选计数 |

种子使用十进制字符串；X、Z 是小屋起始方块坐标；`spawn_y` 是 HPos。筛选量按完整世界种子与位置的组合计数。`excavation` 是小屋 7×9 范围在 Y=−54 平坦参考地形上的理想高度下降总量。

这些小屋有小概率受区块加载顺序影响。

## 文档与数据

- [矿井布局筛选与产率测量](docs/LAYOUT_SEARCH.md)
- [已发现的小屋与适用版本](docs/SEEDS.md)
- [搜索算法](docs/ALGORITHM.md)
- [复核小屋与同时验证多个版本](docs/VERIFICATION.md)
- [数据目录](data/README.md) · [源码打包](docs/PACKAGING.md)

许可证：[MIT](LICENSE)。依赖与署名见 [THIRD_PARTY.md](THIRD_PARTY.md)。

---

<a id="english"></a>

[中文](#chinese) | English

# Ultra Low Hut

Except for this sentence, this repository was written entirely by GPT-6 Astra.

Search on Linux and NVIDIA GPUs for naturally generated swamp huts whose lowest spawning height is below Y=−54. Supports **every release from 1.19.3 through 26.3**. Candidates are verified using vanilla world generation. **HPos** denotes the lowest witch spawning Y.

The repository provides two workflows:

- **Screen mineshaft layouts**: enumerate layouts, calculate excavation and measure −59 yield. Includes [101 layout results](data/mineshafts/1.21/layouts.jsonl) and [complete search templates](data/mineshafts/1.21/templates.json).
- **Search for huts from a layout**: invert seeds and coordinates, screen terrain on GPUs and verify with vanilla generation. Results stream world seeds, positions and heights.

The search models excavation by a single normal mineshaft whose starting room shares the hut chunk. **The 101 layouts come from exhaustive enumeration and cover every layout capable of producing a −59 hut within this search model.** Both layout and hut placement depend on the lower 48 seed bits. Fixing a promising layout before seed inversion concentrates terrain computation on positions capable of producing ultra-low huts. Natural yields differ between layouts; the catalog ranks them by yield.

## Install

Requires Python 3.10+, Git, CMake 3.20+, C/C++17 compilers, an NVIDIA driver and CUDA Toolkit. Python uses only the standard library. The query service needs Java 21 for 1.19.3–1.21.11 and Java 25 for 26.x.

Run the installation commands above from the repository root. Use `sm_80` for A100/A800 or `sm_86` for A10. Preparation downloads the dependencies and the selected server files.

## Search for huts

Use the selection and search commands above for a single GPU. For eight GPUs, set `--devices 0,1,2,3,4,5,6,7`. `--record-height` selects the recording threshold; `--target-height` selects the stopping threshold. Add `--exhaust` to traverse the layout's entire search domain. After Ctrl+C, resume with the command above.

For another game version, change `--version` in the build, server preparation and search commands together, and select its Java runtime. See [version compatibility](docs/VERSIONS.md).

## Read the results

Files are written beneath `--root`:

| File | Contents |
|---|---|
| `results.jsonl` | Live verified results: `seed`, `x`, `z`, `spawn_y`, `excavation`, `versions`, timing and trial counts |
| `progress.jsonl` | Progress and throughput every 30 seconds |
| `first-hits.jsonl` | First discovery at each height and its screening counts |

Seeds are decimal strings. X/Z are the hut's starting block coordinates; `spawn_y` is HPos. Trials count full world-seed and position combinations. `excavation` is the ideal sum of height reductions within the 7×9 hut footprint on flat Y=−54 reference terrain.

These huts have a small chance of depending on chunk loading order.

## Documentation and data

- [Layout screening and yield measurement](docs/LAYOUT_SEARCH.md)
- [Discovered huts and applicable versions](docs/SEEDS.md)
- [Search algorithm](docs/ALGORITHM.md)
- [Recheck huts and verify multiple versions](docs/VERIFICATION.md)
- [Data directory](data/README.md) · [Source packaging](docs/PACKAGING.md)

License: [MIT](LICENSE). See [THIRD_PARTY.md](THIRD_PARTY.md) for dependencies and attribution.
