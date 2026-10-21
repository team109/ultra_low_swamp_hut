<a id="chinese"></a>

# 版本与种子互通

中文 | [English](#english)

当前搜索覆盖 **1.19.3–26.3 的全部正式版**。

![版本与种子互通](images/version-compatibility-zh.svg)

图中两行使用同一条版本轴。蓝色表示**通常互通**：1.19.3–1.20.6 共用小屋、矿井与洞穴筛选核心，1.21–26.3 增加试炼密室处理。试炼密室能直接抬高小屋，因此 1.21 是这一层的分界。苍白之园等远离沼泽的新增群系归入同一段。

绿色表示**严格互通**：默认主世界、新生成区块、相同种子、坐标和生成顺序下，同一色块内的小屋结果互通。1.21.9–1.21.11 的小屋、矿井与含水层计算等效，环境属性和类名改动归入查询服务适配。

## 查询服务

所有支持版本共用一个 `query-service.jar`，启动时选择对应的世界上下文适配器。准备一个版本会将其适配器加入共享 JAR。准备各验证版本的服务端文件后，`prepare_terrain_service.py --all` 将全部适配器打包。1.19.3–1.21.11 使用 Java 21，26.x 使用 Java 25。

## 区块生成顺序

这些小屋有小概率受区块加载顺序影响，同一种子和坐标的小屋高度可能随加载顺序变化。[独立验证](VERIFICATION.md)支持从中心、东侧和西侧接近小屋。

[hut.json](../data/versions/hut.json)选择筛选参数与验证版本；[compatibility.json](../data/versions/compatibility.json)记录图中的两类互通区间；[source-commits.json](../data/versions/source-commits.json)记录复核的源码版本。

---

<a id="english"></a>

[中文](#chinese) | English

# Versions and seed compatibility

The search covers **every release from 1.19.3 through 26.3**.

![Version and seed compatibility](images/version-compatibility-en.svg)

Both rows use the same release axis. Blue shows **usual seed transfer**: 1.19.3–1.20.6 share the hut, mineshaft, and cave screening core; 1.21–26.3 add trial-chamber handling. Trial chambers can directly raise hut height, making 1.21 the boundary at this layer. New biomes far from swamps, including the pale garden, stay within one group.

Green shows **exact equivalence**: hut results transfer within one bar for the default Overworld, newly generated chunks, and the same seed, coordinates, and generation order. Hut, mineshaft, and aquifer calculations are equivalent across 1.21.9–1.21.11; environmental attributes and class renames are handled by the query adapter. 

## Query service

All supported versions share one `query-service.jar`, which selects the matching world-context adapter at startup. Preparing a version adds its adapter to the shared JAR. After preparing the server files for each verifier version, `prepare_terrain_service.py --all` bundles every adapter. Use Java 21 for 1.19.3–1.21.11 and Java 25 for 26.x.

## Chunk generation order

These huts have a small chance of depending on chunk loading order: the hut height at the same seed and coordinates may vary with that order. [Independent verification](VERIFICATION.md) supports approaching from the center, east, and west.

[hut.json](../data/versions/hut.json) selects screening parameters and verification versions; [compatibility.json](../data/versions/compatibility.json) records the two seed-compatibility partitions shown in the diagram; [source-commits.json](../data/versions/source-commits.json) records reviewed source revisions.
