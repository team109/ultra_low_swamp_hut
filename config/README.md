<a id="chinese"></a>

# 运行配置

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

| 文件 | 用途 |
|---|---|
| [search/screening.json](search/screening.json) | GPU 初步筛选的阈值、优化开关及每批处理数量 |
| [search/runtime.json](search/runtime.json) | 默认矿井布局与小屋的相对位置、搜索坐标范围、每次查找该布局对应种子的任务大小，以及 CPU 参考实现的筛选参数 |
| [versions/profiles.json](versions/profiles.json) | 每组游戏版本使用的筛选参数、实际运行生成服务的版本及所需 Java 版本 |
| [versions/compatibility.json](versions/compatibility.json) | 哪些游戏版本共用矿井、搜索或验证实现，以及版本关系图的配置 |
| [verification/loading-orders.txt](verification/loading-orders.txt) | 原版验证实际执行的加载顺序，每行一个九区块顺序 |

这些文件提供新任务的默认参数。`scripts/build/search.py` 将搜索参数写入构建配置；已有搜索目录恢复时沿用该任务保存的配置。加载顺序列表由验证服务直接读取；程序根据文件内容计算列表标识，用它区分采用不同顺序列表的测量结果。接口见[原版验证](../docs/VERIFICATION.md)。

GPU 噪声参数位于 [data/noises/seed-specs26.json](../data/noises/seed-specs26.json)。已发布的小屋与矿井布局位于 [data/](../data/README.md)。

---

<a id="english"></a>

# Runtime configuration

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

| File | Purpose |
|---|---|
| [search/screening.json](search/screening.json) | GPU screening thresholds, optimization switches and items processed per batch |
| [search/runtime.json](search/runtime.json) | Default mineshaft geometry and hut-relative position, coordinate bounds, task sizes for finding seeds that produce that layout, and CPU reference screening parameters |
| [versions/profiles.json](versions/profiles.json) | Screening parameters, the version used to run generation services, and Java requirements for each group of game versions |
| [versions/compatibility.json](versions/compatibility.json) | Game versions sharing mineshaft, search or verification implementations, and diagram configuration |
| [verification/loading-orders.txt](verification/loading-orders.txt) | Decoration orders executed by vanilla verification, one nine-chunk order per line |

These files provide defaults for new tasks. `scripts/build/search.py` copies search settings into its build configuration. Resumed searches retain their saved configuration. The verification service reads the direction list directly; it calculates a list identifier from the file contents to distinguish measurements made with different order lists. See [verification](../docs/VERIFICATION.md#english).

GPU noise parameters are in [data/noises/seed-specs26.json](../data/noises/seed-specs26.json). Published hut and mineshaft catalogs are under [data/](../data/README.md#english).
