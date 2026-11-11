<a id="chinese"></a>

# 小屋种子数据

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

HPos 表示小屋内女巫可生成的最低 Y 坐标。正式列表收录正常世界中所测加载顺序的最低 HPos≤−55 的小屋，覆盖 1.19.3–26.3 的 26 个正式版。结果按 16 个实际运行验证的游戏版本分组，目录与适用版本以[文件索引](../data/huts/index.json)为准。

发布记录共 **9,940 条**；按种子与坐标去重，−59 小屋共 **29 个**。其中 **1,224 条记录**带有加载顺序影响标记，即改变周围区块的生成先后顺序会改变小屋高度或使小屋无法生成，对应 **89 个不同位置**。下表按组统计已发布的小屋，同一位置可在多个版本组出现。

| 版本 | 小屋总数 | −59 | −58 | −57 | −56 | −55 | 受加载顺序影响 |
|---|---:|---:|---:|---:|---:|---:|---:|
| [1.19.3](../data/huts/1.19.3/) | 622 | 29 | 168 | 223 | 101 | 101 | 77 |
| [1.19.4](../data/huts/1.19.4/) | 622 | 29 | 168 | 223 | 101 | 101 | 77 |
| [1.20–1.20.1](../data/huts/1.20-1.20.1/) | 622 | 29 | 168 | 223 | 101 | 101 | 77 |
| [1.20.2](../data/huts/1.20.2/) | 622 | 29 | 168 | 223 | 101 | 101 | 78 |
| [1.20.3–1.20.4](../data/huts/1.20.3-1.20.4/) | 622 | 29 | 168 | 223 | 101 | 101 | 78 |
| [1.20.5–1.20.6](../data/huts/1.20.5-1.20.6/) | 622 | 29 | 168 | 223 | 101 | 101 | 78 |
| [1.21–1.21.1](../data/huts/1.21-1.21.1/) | 620 | 29 | 167 | 223 | 100 | 101 | 77 |
| [1.21.2–1.21.3](../data/huts/1.21.2-1.21.3/) | 621 | 29 | 167 | 223 | 101 | 101 | 78 |
| [1.21.4](../data/huts/1.21.4/) | 621 | 29 | 167 | 223 | 101 | 101 | 77 |
| [1.21.5](../data/huts/1.21.5/) | 621 | 29 | 167 | 223 | 101 | 101 | 77 |
| [1.21.6–1.21.8](../data/huts/1.21.6-1.21.8/) | 621 | 29 | 167 | 223 | 101 | 101 | 77 |
| [1.21.9–1.21.10](../data/huts/1.21.9-1.21.10/) | 621 | 29 | 167 | 223 | 101 | 101 | 77 |
| [1.21.11](../data/huts/1.21.11/) | 621 | 29 | 167 | 223 | 101 | 101 | 77 |
| [26.1–26.1.2](../data/huts/26.1-26.1.2/) | 621 | 29 | 167 | 223 | 101 | 101 | 77 |
| [26.2](../data/huts/26.2/) | 621 | 29 | 167 | 222 | 102 | 101 | 72 |
| [26.3](../data/huts/26.3/) | 620 | 28 | 167 | 222 | 102 | 101 | 70 |

文件名表示所检查加载顺序中的最低 HPos，例如 `y-59.jsonl`。每行包含十进制字符串 `seed`、小屋起始方块坐标 `x`、`z` 和 `loading_order_affected`。该标记为 `true` 表示不同顺序下的小屋高度或能否生成不同，`false` 表示这些顺序下的小屋高度及能否生成均一致。

```json
{"seed":"4933497139849227798","x":-20856992,"z":23067648,"loading_order_affected":true,"min_hpos_order":"C"}
```

受顺序影响的记录另带 `min_hpos_order`，给出达到标称高度的一条已测装饰顺序，方向以中心 `C` 结束。上例只需先装饰中心。具体请求见[顺序复现](VERIFICATION.md#reproduce-order)。

加载顺序及高度判定见[原版验证](VERIFICATION.md#current-order-policy)；所用加载顺序、发布条件与统计见[测量元数据](../data/huts/verification.json)。

---

<a id="english"></a>

# Hut seed data

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

HPos is the lowest Y coordinate at which witches can spawn inside a hut. The catalog contains normal-world huts with minimum HPos≤−55 across tested loading orders, covering all 26 releases from 1.19.3 through 26.3. Results are grouped by the 16 game versions used to run verification; the [file index](../data/huts/index.json) defines directories and applicable versions.

The catalog contains **9,940 records**, including **29 distinct −59 huts** after deduplication by seed and coordinates. **1,224 records at 89 distinct positions** carry a loading-order flag: changing the order in which surrounding chunks generate changes the hut height or prevents hut generation. The table lists published huts by version group and height; the same position can appear in multiple groups.

| Version | Total huts | −59 | −58 | −57 | −56 | −55 | Affected by loading order |
|---|---:|---:|---:|---:|---:|---:|---:|
| [1.19.3](../data/huts/1.19.3/) | 622 | 29 | 168 | 223 | 101 | 101 | 77 |
| [1.19.4](../data/huts/1.19.4/) | 622 | 29 | 168 | 223 | 101 | 101 | 77 |
| [1.20–1.20.1](../data/huts/1.20-1.20.1/) | 622 | 29 | 168 | 223 | 101 | 101 | 77 |
| [1.20.2](../data/huts/1.20.2/) | 622 | 29 | 168 | 223 | 101 | 101 | 78 |
| [1.20.3–1.20.4](../data/huts/1.20.3-1.20.4/) | 622 | 29 | 168 | 223 | 101 | 101 | 78 |
| [1.20.5–1.20.6](../data/huts/1.20.5-1.20.6/) | 622 | 29 | 168 | 223 | 101 | 101 | 78 |
| [1.21–1.21.1](../data/huts/1.21-1.21.1/) | 620 | 29 | 167 | 223 | 100 | 101 | 77 |
| [1.21.2–1.21.3](../data/huts/1.21.2-1.21.3/) | 621 | 29 | 167 | 223 | 101 | 101 | 78 |
| [1.21.4](../data/huts/1.21.4/) | 621 | 29 | 167 | 223 | 101 | 101 | 77 |
| [1.21.5](../data/huts/1.21.5/) | 621 | 29 | 167 | 223 | 101 | 101 | 77 |
| [1.21.6–1.21.8](../data/huts/1.21.6-1.21.8/) | 621 | 29 | 167 | 223 | 101 | 101 | 77 |
| [1.21.9–1.21.10](../data/huts/1.21.9-1.21.10/) | 621 | 29 | 167 | 223 | 101 | 101 | 77 |
| [1.21.11](../data/huts/1.21.11/) | 621 | 29 | 167 | 223 | 101 | 101 | 77 |
| [26.1–26.1.2](../data/huts/26.1-26.1.2/) | 621 | 29 | 167 | 223 | 101 | 101 | 77 |
| [26.2](../data/huts/26.2/) | 621 | 29 | 167 | 222 | 102 | 101 | 72 |
| [26.3](../data/huts/26.3/) | 620 | 28 | 167 | 222 | 102 | 101 | 70 |

Filenames identify minimum HPos across the checked loading orders, such as `y-59.jsonl`. Each JSONL row contains a decimal-string `seed`, hut-start block coordinates `x` and `z`, and `loading_order_affected`. The flag is `true` when checked orders differ in height or hut existence and `false` when both height and hut existence agree.

```json
{"seed":"4933497139849227798","x":-20856992,"z":23067648,"loading_order_affected":true,"min_hpos_order":"C"}
```

Affected records also include `min_hpos_order`, one measured decoration order attaining the published height, ending at center `C`. The example attains it by decorating the center first. See [order reproduction](VERIFICATION.md#reproduce-order-en) for a request example.

See [vanilla verification](VERIFICATION.md#order-list) for loading orders and height measurement, and [measurement metadata](../data/huts/verification.json) for the loading orders used, publication criteria and statistics.
