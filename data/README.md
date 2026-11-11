<a id="chinese"></a>

# 数据目录

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

| 目录 | 内容 |
|---|---|
| [huts/](huts/README.md) | 目前已知的正常世界小屋列表，按适用版本和小屋内女巫可生成的最低 Y 坐标（HPos）分类 |
| [mineshafts/](mineshafts/README.md) | 各版本通用的矿井布局、与小屋的相对位置、已检查的布局范围、挖掘量与 −59 小屋产率 |
| noises/ | GPU 计算使用的噪声参数 |

按本仓库采用的矿井挖低小屋的生成方式，并考虑当前搜索的遗漏，估计存在约 **500～1000 个 −59 小屋**；目前已收录 **29 个**不同种子与坐标的 −59 小屋。

小屋的 `seed` 是完整世界种子；矿井的 `layout_seed` 是决定布局的 48 位随机数种子。两者均以十进制字符串保存。

搜索参数、各游戏版本使用的实现和加载顺序位于 [config/](../config/README.md)。

---

<a id="english"></a>

# Data directory

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

| Directory | Contents |
|---|---|
| [huts/](huts/README.md#english) | Currently known normal-world huts, grouped by applicable version and lowest witch spawning Y coordinate (HPos) |
| [mineshafts/](mineshafts/README.md#english) | Layouts shared across versions, hut-relative positions, the range of layouts checked, excavation and −59 hut yield |
| noises/ | Noise parameters used by GPU calculations |

An estimated **500–1000 −59 huts** exist under the mineshaft-based hut-lowering method used by this repository, allowing for cases missed by the current search. The current catalog contains **29 distinct −59 huts**, identified by seed and coordinates.

A hut’s `seed` is a full world seed; a mineshaft’s `layout_seed` is the 48-bit RNG seed determining its layout. Both are stored as decimal strings.

Search parameters, version mappings and loading orders are under [config/](../config/README.md#english).
