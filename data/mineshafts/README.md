<a id="chinese"></a>

# 矿井布局数据

中文 | [English](#english)

[1.21/layouts.jsonl](1.21/layouts.jsonl) 收录完整枚举得到的全部 101 个可能产生 −59 小屋的布局，范围为单座普通矿井的起始房间与小屋同区块的搜索模型，按自然 −59 产率、挖掘量降序排列。枚举范围见 [enumeration.json](1.21/enumeration.json)。每行包含三个指标：

| 字段 | 含义 |
|---|---|
| `layout_seed` | 矿井布局的 48 位随机数种子，使用十进制字符串 |
| `excavation` | 在 Y=−54 平坦参考地形上，小屋 7×9 范围内的理想挖掘量 |
| `expected59_per_trillion_trials` | 固定该布局后，每万亿次完整世界种子—位置筛选中，预期产生 HPos≤−59 小屋的数量 |

[templates.json](1.21/templates.json) 保存这 101 个布局的完整搜索模板，包括小屋范围、挖掘评分和可用坐标精度区域。使用 `tools/select_layout.py` 选取一份后，可直接交给小屋搜索器的 `--layout-template`。

主清单为每个布局选择测得自然产率最高的坐标精度区域；产率相同时选择挖掘量较大的区域。每行的挖掘量与产率使用同一参考坐标。[reference-positions.json](1.21/reference-positions.json) 记录对应的 X、Z。

[regions/](1.21/regions/) 保留全部 348 组布局—坐标精度区域测量，每行使用相同的三个字段；文件名依次表示 X、Z 的浮点精度。[index.json](1.21/index.json) 列出各文件、参考坐标和记录数。

产率来自共享的 411 份加权自然地形。每份可行地形使用固定的 256 组装饰随机序列，调用原版矿井部件放置代码，保留流体、群系、基岩和木质支撑的影响。测量版本为 1.21，起始房间与小屋位于同一区块。挖掘量是理想高度下降总量，产率包含实际部件放置的影响。

使用单个布局搜索时，主清单给出最有利坐标条件下的比较值；组合多个坐标区域时，按各区域实际处理量加权。[布局搜索](../../docs/LAYOUT_SEARCH.md)介绍测量方法。

---

<a id="english"></a>

[中文](#chinese) | English

# Mineshaft layout data

[1.21/layouts.jsonl](1.21/layouts.jsonl) contains all 101 layouts capable of producing −59 huts in the exhaustively enumerated single-normal-mineshaft, same-starting-chunk search model, sorted by descending natural −59 yield, then excavation. See [enumeration.json](1.21/enumeration.json) for the enumeration scope. Each line has three metrics:

| Field | Meaning |
|---|---|
| `layout_seed` | The mineshaft's 48-bit layout RNG seed, stored as a decimal string |
| `excavation` | Ideal excavation within the 7×9 hut footprint on flat Y=−54 reference terrain |
| `expected59_per_trillion_trials` | Expected HPos≤−59 huts per trillion complete world-seed and position screening trials with this layout fixed |

[templates.json](1.21/templates.json) contains complete search templates for these 101 layouts, including footprints, excavation scores and allowed coordinate-precision regions. Select one with `tools/select_layout.py`, then pass it to the hut searcher with `--layout-template`.

The main catalog selects each layout's highest measured natural-yield coordinate-precision region; ties prefer larger excavation. Both metrics in a row use the same reference position. [reference-positions.json](1.21/reference-positions.json) records its X/Z coordinates.

[regions/](1.21/regions/) preserves all 348 layout–coordinate-region measurements with the same three fields. Filenames identify X and Z float precision, in that order. [index.json](1.21/index.json) lists files, reference positions and record counts.

Yields use a shared panel of 411 weighted natural terrain fields. Every feasible field receives a fixed budget of 256 decoration streams. Vanilla mineshaft piece placement retains fluids, biomes, bedrock and wooden supports. Measurements use 1.21 with the starting room in the hut chunk. Excavation is an ideal sum of height reductions; yield includes actual placement effects.

For a single layout, the main catalog compares its most favorable coordinate conditions. Searches combining regions weight their yields by actual processing allocation. See [layout search](../../docs/LAYOUT_SEARCH.md) for the measurement method.
