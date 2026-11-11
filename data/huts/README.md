<a id="chinese"></a>

# 小屋数据

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

这里保存目前已知的正常主世界（`world_type=normal`）低矮小屋列表。HPos 表示小屋内女巫可生成的最低 Y 坐标。按适用版本分目录，文件名表示所检查加载顺序中的最低 HPos；例如 `y-59.jsonl` 收录最低 HPos 为 −59 的小屋。

按本仓库采用的矿井挖低小屋的生成方式，并考虑当前搜索的遗漏，估计存在约 **500～1000 个 −59 小屋**。目前列表已收录 **29 个**不同种子与坐标的 −59 小屋。

每行包含十进制字符串 `seed`、小屋起始方块坐标 `x`、`z` 和 `loading_order_affected`，按种子数值、X、Z 升序排列。`loading_order_affected=true` 表示不同顺序下的小屋高度或能否生成不同，`false` 表示这些顺序下的小屋高度及能否生成均一致。受影响的记录另有 `min_hpos_order`：一条达到文件标称高度的已测方向顺序，以中心 `C` 结束；方向与复现方法见[原版验证](../../docs/VERIFICATION.md#reproduce-order)。

[index.json](index.json) 列出正式文件、适用版本和所用加载顺序列表。源码发布包只收录索引中的小屋结果及本目录的说明与元数据。结果按 16 个实际运行验证的游戏版本分组；当前配置将游戏版本分为 14 组、每组共用一个验证实现，具体划分见[版本说明](../../docs/VERSIONS.md)。

- [版本与高度统计及记录示例](../../docs/SEEDS.md)
- [验证元数据](verification.json)：所用加载顺序、适用版本与世界类型，以及测量统计。
- [原版验证](../../docs/VERIFICATION.md) · [其他世界类型](../../README.md#世界类型)

---

<a id="english"></a>

# Hut data

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

This catalog lists currently known low huts in normal Overworlds (`world_type=normal`). HPos is the lowest Y coordinate at which witches can spawn inside a hut. Directories identify applicable versions; filenames give the minimum HPos across checked loading orders. For example, `y-59.jsonl` contains huts whose minimum HPos is −59.

An estimated **500–1000 −59 huts** exist under the mineshaft-based hut-lowering method used by this repository, allowing for cases missed by the current search. This catalog currently contains **29 distinct −59 huts**, identified by seed and coordinates.

Each JSONL row contains a decimal-string `seed`, hut-start block coordinates `x` and `z`, and `loading_order_affected`, sorted by numeric seed, X and Z. The flag is `true` when checked orders differ in height or hut existence and `false` when both height and hut existence agree. Affected records also have `min_hpos_order`: a measured direction sequence attaining the filename’s height, ending at center `C`; see [order reproduction](../../docs/VERIFICATION.md#reproduce-order-en).

[index.json](index.json) lists published files, applicable versions and loading-order lists. Source distributions include only indexed hut results and this directory’s documentation and metadata. Results are grouped by the 16 game versions used to run verification. The current configuration groups game versions into 14 groups, each sharing one verification implementation; see [versions](../../docs/VERSIONS.md#english).

- [Counts by version and height, with a record example](../../docs/SEEDS.md#english)
- [Verification metadata](verification.json): loading orders, applicable game versions and world types, and measurement statistics.
- [Vanilla verification](../../docs/VERIFICATION.md#english) · [Other world types](../../README.md#world-types)
