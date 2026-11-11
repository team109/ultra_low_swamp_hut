<a id="chinese"></a>

# 矿井布局数据

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

本目录包含适用于 1.19.3–26.3 全部正式版的 101 个矿井布局。“布局”指矿井起始房间、通道、交叉口和楼梯的形状与相对位置；搜索器使用这些形状寻找能够把小屋挖低的种子。这些布局使用原版主世界高度和海平面，只考虑一座普通（`NORMAL`）矿井，保持其自然生成高度，且起始房间与小屋位于同一区块。正常、大型群系和沼泽单群系世界共用这些布局；最终小屋高度仍按版本和世界配置验证。

[enumeration.json](enumeration.json) 的 `complete=true` 表示已完成其中 `model` 所限定的 1,125,902,188,544 个矿井构造状态的枚举；这个范围内共有 101 个通过挖掘量筛选的布局。`source_version` 记录枚举依据 1.21，`supported_versions` 列出布局适用的 26 个版本，`supported_world_types` 列出适用的世界类型。

[layouts.jsonl](layouts.jsonl) 收录上述条件下完整枚举得到的全部 101 个可能产生 −59 小屋的布局，先按 1.21 测得的 −59 产率从高到低排列，产率相同时按挖掘量从大到小排列。“−59 产率”指固定一个矿井布局后，每万亿次完整世界种子—位置筛选预计能找到多少个最低可刷怪高度不高于 −59 的小屋。每行包含以下字段：

| 字段 | 含义 |
|---|---|
| `layout_seed` | 决定矿井部件形状的 48 位随机数种子，以十进制字符串保存 |
| `excavation` | 假设小屋 7×9 范围的 63 列原本都位于 Y=−54，且矿井挖掘全部成功，各列高度下降格数的总和；平均降到 −59 需达到 `63 × 5 = 315`，因此以 315 为门槛筛选有可能生成 −59 小屋的布局 |
| `expected59_per_trillion_trials` | 固定该布局后，每万亿次完整世界种子—位置筛选中，预期产生 HPos≤−59 小屋的数量 |

[templates.json](templates.json) 保存这 101 个布局的搜索输入，称为“模板”：其中记录布局种子、小屋占地范围、上述挖掘量，以及可以用于搜索的坐标范围。使用 `scripts/layouts/select.py` 选取一份后，可直接交给小屋搜索器的 `--layout-template`。

原版计算矿井房间顶部时使用单精度浮点数，远坐标的舍入会改变能挖掉的方块。X、Z 各分成三类：浮点数能表示的相邻坐标间隔小于一格、等于一格或等于两格；两轴组合成九类，称为“坐标精度区域”。程序分别测量符合筛选条件的组合。具体坐标范围、九种组合和版本适用范围见[坐标精度说明](../../docs/ALGORITHM.md#九种坐标精度组合及范围)。

主清单为每个布局选择测得产率最高的一类坐标，产率相同时选择挖掘量较大的一类。每行的挖掘量与产率使用同一个代表坐标。[reference-positions.json](reference-positions.json) 记录对应的 X、Z。

[regions/](regions/) 保留全部 348 组布局—坐标精度区域测量，每行使用相同的三个字段；文件名依次表示 X、Z 的坐标类别：`sub-block` 为小于一格，`one-block` 为一格，`two-block` 为两格。[index.json](index.json) 列出各文件、参考坐标和记录数。

产率通过在一批 1.21 原版自然地形上多次运行矿井放置代码来估算，统计小屋最低可刷怪高度达到 −59 或更低的次数。测量保留水和岩浆导致部件不生成、群系、基岩与木质支撑等实际影响；各份地形按它们在种子—位置尝试中所占比例计入总产率。布局形状适用于上述全部版本，产率数字对应这里的 1.21 地形和测量配置。

[yield-measurement.json](yield-measurement.json) 保存实际采样配置和测量汇总：[yield-panel.json](yield-panel.json) 列出 411 份地形的种子、坐标与权重，采样基数为 2,199,023,255,552 次种子—位置尝试；每份符合条件的地形放置 256 次，348 组组合共实际放置 674,304 次。[yield-results.jsonl](yield-results.jsonl) 保存每组的放置数与成功次数。地形快照由原版服务按该列表重新生成。

测量与搜索方法见[布局搜索](../../docs/LAYOUT_SEARCH.md)。

---

<a id="english"></a>

# Mineshaft layout data

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

This directory contains 101 mineshaft layouts shared across every release from 1.19.3 through 26.3. A layout describes the shape and relative positions of the starting room, corridors, crossings and stairs. The searcher uses these shapes to find seeds where mineshafts can lower huts. The layouts use vanilla Overworld height and sea-level settings, one normal (`NORMAL`) mineshaft at its natural height, and a starting room in the hut chunk. Normal, large-biome and single-swamp worlds share these templates. Final hut heights still require verification for each version and world configuration.

In [enumeration.json](enumeration.json), `complete=true` means all 1,125,902,188,544 mineshaft constructor states within its `model` have been enumerated, yielding 101 layouts that pass the excavation filter. `source_version` records 1.21 as the enumeration basis, `supported_versions` lists the 26 supported releases, and `supported_world_types` lists the applicable world types.

[layouts.jsonl](layouts.jsonl) contains all 101 layouts capable of producing −59 huts in the exhaustively enumerated single-normal-mineshaft, same-starting-chunk search model, sorted by descending −59 yield measured in 1.21, then descending excavation. Yield means the expected number of huts whose lowest spawning height is −59 or lower per trillion complete world-seed and position trials, with the mineshaft layout fixed. Each row contains these fields:

| Field | Meaning |
|---|---|
| `layout_seed` | The 48-bit random seed determining mineshaft piece shapes, stored as a decimal string |
| `excavation` | Total height reduction across the 63 hut columns, assuming every column starts at Y=−54 and all mineshaft clearing succeeds; lowering the average to −59 requires `63 × 5 = 315`, the cutoff for selecting layouts that could produce −59 huts |
| `expected59_per_trillion_trials` | Expected HPos≤−59 huts per trillion complete world-seed and position screening trials with this layout fixed |

[templates.json](templates.json) contains search inputs for these 101 layouts, called templates: the layout seed, hut footprint, excavation score defined above, and allowed coordinate ranges. Select one with `scripts/layouts/select.py`, then pass it to the hut searcher with `--layout-template`.

Vanilla calculates the room roof with single-precision floating-point numbers. Rounding at distant coordinates changes which blocks it clears. Each axis has three classes where representable coordinate values are spaced less than one block, one block or two blocks apart. Their nine X/Z combinations are called coordinate-precision regions, and eligible combinations are measured separately. See [coordinate precision](../../docs/ALGORITHM.md#nine-coordinate-precision-combinations-and-their-ranges) for exact ranges, all nine combinations and version compatibility.

The main catalog selects each layout's highest measured yield among these coordinate classes; ties prefer larger excavation. Both metrics in a row use the same representative position. [reference-positions.json](reference-positions.json) records its X/Z coordinates.

[regions/](regions/) preserves all 348 layout–coordinate-region measurements with the same three fields. Filenames identify the X and Z coordinate classes, in that order: `sub-block`, `one-block` and `two-block` describe spacing of less than one block, one block and two blocks. [index.json](index.json) lists files, reference positions and record counts.

Yield is estimated by repeatedly running mineshaft placement on a set of vanilla 1.21 terrains and counting huts with a lowest spawning height of −59 or lower. Placement can be cancelled by water or lava and retains the effects of biomes, bedrock and wooden supports. Each terrain contributes according to its share of the seed-position trials. Layout shapes are shared across the supported versions; these yield values describe the 1.21 terrain and measurement configuration used here.

[yield-measurement.json](yield-measurement.json) preserves the sampling configuration and measurement summary. [yield-panel.json](yield-panel.json) lists 411 terrain seeds, coordinates and weights, with 2,199,023,255,552 seed-position trials as the sampling base. Each eligible terrain receives 256 placements; the 348 combinations used 674,304 actual placements. [yield-results.jsonl](yield-results.jsonl) records placements and successes per combination. The vanilla service regenerates terrain snapshots from this list.

See [layout search](../../docs/LAYOUT_SEARCH.md#english) for measurement and search commands.
