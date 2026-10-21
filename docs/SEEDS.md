<a id="chinese"></a>

# 小屋种子数据

中文 | [English](#english)

共收录 **623 个不同的种子—坐标组合**，最低可刷怪高度为 −55 至 −59。按适用版本分别归档后共有 9155 条记录。以下数量均来自[数据文件索引](../data/huts/index.json)：

| 适用版本 | −55 | −56 | −57 | −58 | −59 |
|---|---:|---:|---:|---:|---:|
| [1.19.3](../data/huts/1.19.3/) | 101 | 101 | 222 | 168 | 28 |
| [1.19.4](../data/huts/1.19.4/) | 101 | 101 | 222 | 168 | 28 |
| [1.20–1.20.1](../data/huts/1.20-1.20.1/) | 101 | 101 | 222 | 168 | 28 |
| [1.20.2](../data/huts/1.20.2/) | 101 | 101 | 222 | 168 | 28 |
| [1.20.3–1.20.4](../data/huts/1.20.3-1.20.4/) | 101 | 101 | 222 | 168 | 28 |
| [1.20.5–1.20.6](../data/huts/1.20.5-1.20.6/) | 101 | 101 | 222 | 168 | 28 |
| [1.21–1.21.1](../data/huts/1.21-1.21.1/) | 100 | 97 | 220 | 161 | 26 |
| [1.21.2–1.21.3](../data/huts/1.21.2-1.21.3/) | 100 | 98 | 220 | 161 | 26 |
| [1.21.4](../data/huts/1.21.4/) | 100 | 98 | 221 | 160 | 26 |
| [1.21.5](../data/huts/1.21.5/) | 100 | 98 | 221 | 161 | 26 |
| [1.21.6–1.21.8](../data/huts/1.21.6-1.21.8/) | 100 | 98 | 221 | 161 | 26 |
| [1.21.9–1.21.11](../data/huts/1.21.9-1.21.11/) | 100 | 98 | 221 | 161 | 26 |
| [26.1–26.1.2](../data/huts/26.1-26.1.2/) | 99 | 98 | 222 | 161 | 26 |
| [26.2](../data/huts/26.2/) | 102 | 97 | 217 | 159 | 24 |
| [26.3](../data/huts/26.3/) | 102 | 97 | 217 | 158 | 24 |

点击版本进入对应目录，再选择 `y-55.jsonl` 至 `y-59.jsonl`。每行记录：

```json
{"seed":"-7942261308732107398","x":-27136480,"z":-9937872}
```

`seed` 是完整世界种子的十进制字符串；`x`、`z` 是小屋起始方块坐标；文件名中的 Y 表示最低可刷怪高度 HPos。该示例在 1.21 和 26.3 的高度均为 −59。

同一[严格互通区间](VERSIONS.md)内的版本共享数据文件。原版验证使用默认主世界；各代表版本的验证统计见 [verification.json](../data/huts/verification.json)。这些小屋有小概率受区块加载顺序影响，[复核命令](VERIFICATION.md)支持比较不同接近方向。

---

<a id="english"></a>

[中文](#chinese) | English

# Hut seed data

The catalog contains **623 distinct seed-position combinations**, with lowest spawning heights from −55 to −59. Listing applicable versions separately produces 9155 records. Counts come from the [data index](../data/huts/index.json):

| Applicable versions | −55 | −56 | −57 | −58 | −59 |
|---|---:|---:|---:|---:|---:|
| [1.19.3](../data/huts/1.19.3/) | 101 | 101 | 222 | 168 | 28 |
| [1.19.4](../data/huts/1.19.4/) | 101 | 101 | 222 | 168 | 28 |
| [1.20–1.20.1](../data/huts/1.20-1.20.1/) | 101 | 101 | 222 | 168 | 28 |
| [1.20.2](../data/huts/1.20.2/) | 101 | 101 | 222 | 168 | 28 |
| [1.20.3–1.20.4](../data/huts/1.20.3-1.20.4/) | 101 | 101 | 222 | 168 | 28 |
| [1.20.5–1.20.6](../data/huts/1.20.5-1.20.6/) | 101 | 101 | 222 | 168 | 28 |
| [1.21–1.21.1](../data/huts/1.21-1.21.1/) | 100 | 97 | 220 | 161 | 26 |
| [1.21.2–1.21.3](../data/huts/1.21.2-1.21.3/) | 100 | 98 | 220 | 161 | 26 |
| [1.21.4](../data/huts/1.21.4/) | 100 | 98 | 221 | 160 | 26 |
| [1.21.5](../data/huts/1.21.5/) | 100 | 98 | 221 | 161 | 26 |
| [1.21.6–1.21.8](../data/huts/1.21.6-1.21.8/) | 100 | 98 | 221 | 161 | 26 |
| [1.21.9–1.21.11](../data/huts/1.21.9-1.21.11/) | 100 | 98 | 221 | 161 | 26 |
| [26.1–26.1.2](../data/huts/26.1-26.1.2/) | 99 | 98 | 222 | 161 | 26 |
| [26.2](../data/huts/26.2/) | 102 | 97 | 217 | 159 | 24 |
| [26.3](../data/huts/26.3/) | 102 | 97 | 217 | 158 | 24 |

Open a version directory, then select `y-55.jsonl` through `y-59.jsonl`. Each line contains the decimal-string world `seed` and hut-start block coordinates `x` and `z`, as in the example above. The filename gives HPos, the lowest spawning height. The example has HPos −59 in both 1.21 and 26.3.

Versions within an [exact compatibility interval](VERSIONS.md) share files. Vanilla verification uses the default Overworld; representative-version counts are in [verification.json](../data/huts/verification.json). These huts have a small chance of depending on chunk loading order. The [recheck commands](VERIFICATION.md) support different approach directions.
