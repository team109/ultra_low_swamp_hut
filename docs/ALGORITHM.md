<a id="chinese"></a>

# 搜索算法

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

矿井起始房间与相连通道会挖空一部分地形，沼泽小屋因此可能生成在更低的位置。算法分为两大阶段：**先离线筛选矿井布局，再固定布局搜索世界种子与坐标**。第一阶段保存矿井形状及其与小屋的相对位置，称为“布局模板”；后续搜索可以重复使用这些模板。

搜索先检查种子的气候和洞穴噪声数值，只为满足配置阈值的种子进一步计算地形，以减少需要生成区块的种子数量。这些阈值用于加快搜索，也会跳过一部分实际存在低小屋的种子。最终高度由对应版本的原版生成代码确认，记为 HPos，即小屋内女巫可生成的最低 Y 坐标。

## 第一阶段：矿井布局筛选（离线预先筛选）

这一阶段使用原版主世界高度与海平面，考虑一座按自然高度生成的普通矿井（代码类型为 `NORMAL`），要求起始房间与小屋位于同一区块。程序寻找形状和高度适合挖低小屋的布局。

控制矿井部件排列的是一个 48 位随机数种子，称为“布局种子”。给定它，就可以重新计算房间、通道等部件的位置。它与玩家创建世界时输入的完整 64 位世界种子不同。

| 步骤 | 具体处理 | 执行位置 |
|---|---|---|
| A1 找出会生成矿井的随机数状态 | 遍历矿井放置时随机数生成器的可能状态，保留第一次 `nextDouble() < 0.004F` 的状态，再求出对应的布局种子 | GPU |
| A2 生成布局并排除挖掘量不足的布局 | 按原版顺序生成房间、通道、交叉口和楼梯，检查部件碰撞，并按自然规则上下移动整个矿井。用房间和最低部件的高度估算最大可能下降量，不足 315 就排除；还要求低处的矿井部件经过小屋北侧或西侧边缘 | GPU |
| A3 计算小屋每一列能被挖低多少 | 在小屋 7×9、共 63 列范围内，记录矿井部件可能挖空的各个位置。分别计算九种坐标精度组合，至少一种的总下降量 `g54 >= 315` 才保留，并记录满足要求的组合 | GPU |
| A4 保存模板 | 按布局种子去重，保存部件数量、房间尺寸和高度、挖掘量及适用坐标范围，供第二阶段搜索使用 | CPU / Python |
| A5 测量找到 −59 小屋的频率并排序 | 在同一批自然地形上，先计算矿井全部挖空成功时能否达到要求；有机会的样本再调用原版代码实际放置矿井。每份地形默认用 256 组随机数重复放置，比较不同布局时使用相同的这组随机数 | CPU / Python、C++、Java |

`g54` 的计算假定小屋下方 63 列的原始高度都是 −54，并假定矿井在形状允许的位置全部挖空成功。各列的高度下降量相加，就是 `g54`。要让平均高度从 −54 降到 −59，总下降量至少为 `63 × 5 = 315`。**因此，315 是筛选有可能生成 −59 小屋的矿井布局的门槛**：达到该分数的布局进入后续世界种子搜索，再用原版生成确认实际高度。实际生成时，水或岩浆可能使部件取消放置，随机顶板和木支撑也会留下方块，实际高度由后续原版验证确定。

A5 所用的地形样本各自代表一定数量的搜索尝试。统计时按对应权重相加，估算每万亿次世界种子—位置检查能找到多少个 −59 小屋，再据此排列模板的搜索顺序。测量输入与权重字段见[布局测量](LAYOUT_SEARCH.md#测量-59-产率)。

### 九种坐标精度组合及范围

原版计算矿井房间顶部的挖空形状时，用单精度浮点数保存绝对坐标。这种数只有 24 位二进制有效精度：坐标增大到 `2²³ = 8,388,608` 后，相邻可表示数的间隔变成一格；到 `2²⁴ = 16,777,216` 后变成两格。因此，同一矿井移动到远处后，房间顶部可能少挖或多挖一些方块。

以下 `a` 表示小屋起始方块的 X 或 Z 坐标；在当前模型中，它与矿井起始区块一起平移，且按 16 格对齐。每个轴分为三类，表中范围只取实际搜索坐标范围内的部分：

| 类别 | 单轴坐标 `a` 的范围 | 相邻浮点坐标的间隔 | 测量使用的代表坐标 |
|---|---|---|---:|
| 0：`sub-block` | −8,388,608 ≤ a < 8,388,608 | 小于一格 | 0 |
| 1：`one-block` | −16,777,216 ≤ a < −8,388,608，或 8,388,608 ≤ a < 16,777,216 | 一格 | 12,582,912 |
| 2：`two-block` | a < −16,777,216，或 a ≥ 16,777,216 | 两格 | 20,000,000 |

负边界的归属与正边界不同：−8,388,608 归类别 0，−16,777,216 归类别 1。矿井房间从区块起点向 X、Z 正方向延伸，负边界上的房间落在更靠近原点的一侧，所以不能直接按坐标绝对值分类。

X、Z 独立分类，交叉得到下列九种组合。格内是程序和测量文件使用的区域编号，即 `3 × X类别 + Z类别`：

| X 类别 ╲ Z 类别 | 0：小于一格 | 1：一格 | 2：两格 |
|---|---:|---:|---:|
| 0：小于一格 | 0 | 1 | 2 |
| 1：一格 | 3 | 4 | 5 |
| 2：两格 | 6 | 7 | 8 |

例如，组合 5 的 X 取类别 1 的两个坐标范围，Z 取类别 2 的两个坐标范围；其测量代表坐标为 `(12,582,912, 20,000,000)`。

**这九种组合的划分及对应的房间顶部挖空计算，对本项目支持的 1.19.3–26.3 全部 26 个正式版本通用。** 产率测量分别处理合格组合；第二阶段按实际坐标所属组合筛选，并按实际坐标重新计算挖空位置。

## 第二阶段：固定布局搜索小屋

### B1 查找能产生该布局的种子与坐标（GPU）

程序从固定布局出发，反过来求出能生成它的世界种子与矿井坐标，这个过程称为“反解”。先排除世界边界外的位置、不适用的坐标精度范围，以及不符合原版小屋放置规则的位置。再按放置随机数的低位分组，逐步补齐可能的种子位，求出世界种子的低 48 位；最后用原版放置规则正向计算一次，核对矿井布局、小屋位置与朝向。

1.21 起，还会预测附近试炼密室的起始位置。当它与小屋中心的 X 方向距离加 Z 方向距离不超过 96 格，即 `|Δx| + |Δz| ≤ 96` 时，跳过该候选。这一步只按预测起点判断，尚未生成完整密室或检查其群系。

本步骤输出世界种子低 48 位 `low48`、小屋坐标 `x`、`z` 和所用模板 `template`。完整种子剩下的高 16 位在下一步枚举。

### B2 补齐世界种子并检查噪声数值（GPU）

每个低 48 位—坐标组合尝试 **65,536 种高 16 位**，得到完整世界种子。噪声函数根据种子与坐标返回数值，原版用这些数值决定群系、地形、洞穴和地下液体。这里先检查其中一部分数值，避免为每个种子生成全部方块。

下表保留程序中的步骤名，方便与输出对照。`erosion`、`temperature`、`continentalness`、`ridge` 分别是侵蚀、温度、大陆性和山脊相关噪声；`floodedness` 用于含水层液体分布；`entrance`、`cheese` 用于洞口和大洞穴计算；`spaghetti` 是程序组合多项噪声算出的细长洞穴判断值。

| 步骤 | 保留条件与处理 |
|---|---|
| 快速侵蚀检查 | 先计算未加坐标偏移的侵蚀噪声前 4 项之和，要求 ≥ 0.50。只计算部分噪声，成本较低 |
| `erosion` | 按原版坐标偏移计算完整侵蚀噪声，要求 ≥ 0.55 |
| `temperature` | 要求 `−0.45 ≤ temperature ≤ 0.20`，先保留这段气候范围，再由 CPU 查询实际群系 |
| `continentalness` | 要求 `continentalness ≥ −0.11` |
| `ridge` | 要求 `abs(ridge) ≤ 0.42` 或 `ridge ≥ 0.91` |
| `surface56` | 按原版气候参数和预设曲线计算近似地表值，要求 ≥ 56；此时尚未逐列生成实际地形 |
| `dry_60` → `dry_0` → `dry_-53` → `dry_30` → `dry_-30` | 依次在这些高度计算 `floodedness`，每次都要求 ≤ 0.41 |
| `opening_60` → `opening_50` | 依次检查两个高度，每次都要求 `entrance < −0.35` 或 `spaghetti < 0.020001` |
| `cave_0` → `cave_-53` → `cave_-30` → `cave_30` → `cave_-10` → `cave_-40` → `cave_10` → `cave_40` → `cave_20` | 依次检查九个高度，每次都要求 `entrance + bias(y) < 0`，或 `cheese < −0.27`，或 `spaghetti < 0.000001` |

`bias(y) = 0.37 + 0.3 × (1 − clamp((y + 10) / 40, 0, 1))`，其中 `clamp` 表示把结果限制在 0～1。每个高度都必须通过检查，同一高度列出的“或”条件满足一个即可。

气候噪声使用 `(x+8,z+8)` 附近按原版规则偏移的坐标，地下液体与洞穴计算使用 `(x+3,z+3)` 附近的坐标。表中高度用于噪声采样，内部还会缩放坐标。

快速侵蚀检查之后共有 **21 次检查**：4 次气候、1 次地表、5 次地下液体、2 次洞口、9 次洞穴。通过全部检查的种子进入 CPU 阶段。阈值见[版本参数](../config/versions/profiles.json)和[搜索参数](../config/search/screening.json)，构建时写入 `profile.h`；对应实现见 [`noise_cascade26.cu`](../src/ultra_low_hut/search/gpu/noise_cascade26.cu) 和 [`cascade.py`](../src/ultra_low_hut/search/gpu/cascade.py)。

大型生物群系使用原版对应的 `_large` 气候噪声参数。单一生物群系世界的所有位置都采用指定群系，因此跳过温度筛选和 CPU 群系查询，其余地形检查照常执行。指定群系不允许生成小屋时，搜索直接返回空结果。

### B3 计算实际地形并检查能否挖低（CPU）

这一阶段使用 C++ 地形库计算候选位置的方块，比 GPU 阶段只检查噪声数值更细。地形库是对原版生成算法的参考实现；此时尚未放置矿井和其他结构、地物。

程序根据矿井形状，逐列记录它可能挖空哪些位置；先假定这些位置都挖空成功，再估计小屋下方 63 列的平均高度。配置名 `room_budget` 指允许的平均高度上限，当前为 −57：例如估计平均高度为 −55，仍高于 −57，就排除该种子。

| 步骤 | 具体检查 | 执行位置 |
|---|---|---|
| 初始高度估计 | 先假定各列原始高度为 −54，按矿井可挖空的位置计算下降后的高度；63 列高度之和大于 `room_budget × 63` 就排除 | CPU / C++ |
| 高处是否为空气 | 房间底为 −62 时，要求 `(x+3,62,z+3)` 是空气 | CPU / C++ |
| 房间附近是否有液体 | 按房间尺寸选取顶面上方九个位置，以及 Y=−55 附近的四个外侧角点；适用的检查位置发现水或岩浆就排除 | CPU / C++ |
| 检查矿井挖不到的方块 | 在各列的 Y=−54、−53、−52、−48 查询方块。若非空气且不在矿井可挖空的位置内，就调高该列的估计高度；总和超过阈值就排除 | CPU / C++ |
| 小屋群系 | 在原版用于判定小屋能否生成的位置与高度查询群系，检查是否允许生成小屋 | CPU / C++ |
| 小屋范围是否全部被水淹没 | 检查 63 列在 Y=62 的含水层状态，全部被水淹没时排除；部分列有水时继续 | CPU / C++ |
| 地形平均高度 | 读取洞穴雕刻完成后、矿井放置前的 63 列高度，计算整数平均值，向零截断；当前要求 `reference_y ≤ −48` | CPU / C++ |

`reference_y` 是最后一项计算的地形平均高度，尚未计入矿井挖空的效果。**−57 的矿井挖掘后估计高度上限、−48 的矿井放置前地形高度上限、默认 −55 的结果记录高度和 −59 的搜索停止高度，分别控制不同步骤**；它们可以独立配置。

### B4 用原版生成代码比较加载顺序（CPU / Java）

候选通过以上检查后，启用验证时调用对应版本的原版代码。每种加载顺序指定中心与八个邻区块的处理先后，执行区块生成中放置结构和地物的阶段（代码名 `FEATURES`，也称“装饰”）。程序记录实际执行顺序和小屋 HPos；不同顺序的查询重置生成所需的随机数与区块数据，避免上一种顺序留下的方块影响下一种。

完成列表中的全部顺序后，保存最低 HPos、得到该高度的全部顺序，以及不同顺序是否改变高度或使小屋无法生成。列表和测量方法见[验证说明](VERIFICATION.md)。关闭原版验证时，按 CPU 参考高度 `native_y` 记录和停止，保存为待验证的候选。

---

<a id="english"></a>

# Search algorithm

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

A mineshaft starting room and its connected corridors remove terrain, allowing a swamp hut to generate lower. The algorithm first **selects mineshaft layouts offline**, then **searches world seeds and coordinates for a fixed layout**. Stage 1 saves the mineshaft shape and its position relative to the hut as a reusable layout template.

The search checks climate and cave noise values before calculating terrain, reducing how many seeds need chunk generation. These thresholds speed up the search but also skip some seeds that could contain low huts. The selected version’s vanilla generation code determines final HPos: the lowest Y coordinate where witches can spawn inside the hut.

## Stage 1: select mineshaft layouts offline

The model uses vanilla Overworld height and sea level, one naturally placed normal mineshaft (the `NORMAL` code type), and its starting room in the hut chunk.

A 48-bit random-number seed determines the mineshaft’s rooms, corridors and other pieces. This layout seed allows the same arrangement to be reconstructed; it differs from the complete 64-bit world seed entered when creating a world.

| Step | Processing | Processor |
|---|---|---|
| A1 Find states that generate a mineshaft | Enumerate placement random-number states, retain those whose first `nextDouble() < 0.004F`, and recover the corresponding layout seeds | GPU |
| A2 Construct layouts and reject insufficient excavation | Follow vanilla piece generation, collision checks and natural vertical placement. Use room and lowest-piece heights to estimate the maximum possible total height reduction; reject values below 315. Require a low mineshaft piece to cross the hut’s north or west edge | GPU |
| A3 Calculate removal beneath each hut column | Record which blocks the pieces can remove within the 7×9 hut footprint, covering 63 columns. Test nine coordinate-precision combinations and retain a layout if at least one has total reduction `g54 >= 315`; save the qualifying combinations | GPU |
| A4 Save templates | Deduplicate layout seeds and save piece counts, room dimensions and height, excavation scores and eligible coordinate ranges | CPU / Python |
| A5 Estimate the frequency of −59 huts and rank layouts | Use the same natural-terrain samples for all layouts. First assume all possible excavation succeeds; run vanilla placement only for samples that could qualify. By default, place each layout with 256 sets of random numbers per terrain, using the same sets when comparing layouts | CPU / Python, C++, Java |

`g54` starts all 63 columns at height −54 and assumes every block the mineshaft could remove is removed. Sum the resulting height reductions to obtain the score. Lowering the average from −54 to −59 requires at least `63 × 5 = 315`. **The cutoff of 315 therefore selects mineshaft layouts that could produce −59 huts.** Qualifying layouts proceed to world-seed search, where vanilla generation confirms the actual height. Water or lava can prevent pieces from being placed; randomized roofs and wooden supports can leave blocks. Later vanilla verification determines the actual height.

Each terrain sample represents a number of search attempts. A5 combines samples using their weights to estimate how many −59 huts a layout would produce per trillion world-seed and position checks, then uses that estimate to rank layouts. See [layout measurement](LAYOUT_SEARCH.md#measure-59-yield) for inputs and weight fields.

### Nine coordinate-precision combinations and their ranges

Vanilla uses absolute coordinates stored as single-precision floating-point numbers when calculating which roof blocks a mineshaft room removes. These numbers have 24 binary digits of precision. At `2²³ = 8,388,608`, adjacent representable values are one block apart; at `2²⁴ = 16,777,216`, they are two blocks apart. Moving the same layout farther from the origin can therefore change which roof blocks it clears.

Here `a` is the hut-start X or Z coordinate. In this model it moves with the mineshaft starting chunk and is aligned to 16 blocks. Each axis has three classes, restricted to the coordinates actually searched:

| Class | Range of axis coordinate `a` | Spacing between floating-point coordinates | Measurement representative |
|---|---|---|---:|
| 0: `sub-block` | −8,388,608 ≤ a < 8,388,608 | Less than one block | 0 |
| 1: `one-block` | −16,777,216 ≤ a < −8,388,608, or 8,388,608 ≤ a < 16,777,216 | One block | 12,582,912 |
| 2: `two-block` | a < −16,777,216, or a ≥ 16,777,216 | Two blocks | 20,000,000 |

Negative boundaries belong to the class closer to the origin: −8,388,608 is in class 0, and −16,777,216 in class 1. The room extends from its chunk start toward positive X and Z, so a room at a negative boundary lies on the side closer to the origin. Classification cannot simply use the coordinate’s absolute value.

Combining the independent X and Z classes gives nine regions. Cells show the region number used in code and measurement files: `3 * X_class + Z_class`.

| X class ╲ Z class | 0: sub-block | 1: one-block | 2: two-block |
|---|---:|---:|---:|
| 0: sub-block | 0 | 1 | 2 |
| 1: one-block | 3 | 4 | 5 |
| 2: two-block | 6 | 7 | 8 |

For example, region 5 combines both class-1 X ranges with both class-2 Z ranges. Its measurement representative is `(12,582,912, 20,000,000)`.

**These nine classes and their room-roof clearing calculations are shared across all 26 supported releases from 1.19.3 through 26.3.** Yield measurement treats qualifying combinations separately. Stage 2 filters by the actual coordinate class and recalculates clearing at the actual coordinates.

## Stage 2: search for huts with a fixed layout

### B1 Find world seeds and coordinates that produce the layout — GPU

Starting from a chosen layout, solve for world seeds and mineshaft coordinates that can produce it. This is called inversion. Reject positions outside world bounds, outside the layout’s eligible precision ranges, or incompatible with vanilla hut placement. Group possibilities by the low bits of placement random numbers, extend partial seeds to 48 bits, then run the placement calculation forward to verify the layout, hut position and orientation.

From 1.21 onward, also predict nearby trial-chamber starting positions. Skip a candidate when the X distance plus Z distance from a predicted start to the hut center is at most 96 blocks: `|Δx| + |Δz| ≤ 96`. This step has not generated the full chamber or checked its biome.

The output is world-seed low bits `low48`, hut coordinates `x` and `z`, and the selected `template`. The next step enumerates the remaining high 16 bits of the world seed.

### B2 Complete world seeds and check noise values — GPU

For each `(low48, x, z)`, try **65,536 high-16 values** to obtain complete world seeds. Noise functions return numbers from a seed and coordinates; vanilla uses them to determine biomes, terrain, caves and underground fluids. Checking selected values avoids generating all blocks for every seed.

The table retains program step names for comparison with output. `erosion`, `temperature`, `continentalness` and `ridge` are climate and terrain noise values. `floodedness` contributes to aquifer fluid placement; `entrance` and `cheese` contribute to cave entrances and large caves. `spaghetti` combines several noise values to test for narrow caves.

| Step | Required condition or processing |
|---|---|
| Fast erosion check | Sum the first four erosion components without the vanilla coordinate shift and require ≥ 0.50; calculating only part of the noise is cheaper |
| `erosion` | Evaluate the complete erosion noise at vanilla-shifted coordinates and require ≥ 0.55 |
| `temperature` | Require `−0.45 ≤ temperature ≤ 0.20`, before a later CPU query checks the actual biome |
| `continentalness` | Require `continentalness ≥ −0.11` |
| `ridge` | Require `abs(ridge) <= 0.42` or `ridge >= 0.91` |
| `surface56` | Use vanilla climate inputs and preset curves to estimate a surface value; require ≥ 56 before generating actual terrain columns |
| `dry_60` → `dry_0` → `dry_-53` → `dry_30` → `dry_-30` | Check `floodedness` at these heights in order, requiring ≤ 0.41 at every height |
| `opening_60` → `opening_50` | Check both heights in order, requiring `entrance < −0.35` or `spaghetti < 0.020001` at each |
| `cave_0` → `cave_-53` → `cave_-30` → `cave_30` → `cave_-10` → `cave_-40` → `cave_10` → `cave_40` → `cave_20` | Check all nine heights in order, requiring `entrance + bias(y) < 0`, `cheese < −0.27`, or `spaghetti < 0.000001` at each |

`bias(y) = 0.37 + 0.3 * (1 - clamp((y + 10) / 40, 0, 1))`, where `clamp` limits a result to 0–1. Every height must pass, while any one alternative at a given height is sufficient.

Climate sampling uses vanilla-shifted coordinates near `(x+8,z+8)`; underground-fluid and cave calculations use coordinates near `(x+3,z+3)`. Heights in the table are noise-sampling inputs with further internal coordinate scaling.

There are **21 checks** after fast erosion: 4 climate, 1 surface, 5 underground-fluid, 2 entrance and 9 cave checks. Seeds passing them all continue to the CPU. Thresholds are read from [version settings](../config/versions/profiles.json) and [search settings](../config/search/screening.json), then written to `profile.h` during the build. See [`noise_cascade26.cu`](../src/ultra_low_hut/search/gpu/noise_cascade26.cu) and [`cascade.py`](../src/ultra_low_hut/search/gpu/cascade.py).

Large-biome worlds use the corresponding vanilla `_large` climate-noise parameters. Single-biome worlds use the specified biome everywhere, so they skip temperature filtering and CPU biome lookup while retaining the terrain checks. A selected biome that cannot generate huts returns an empty search result.

### B3 Calculate terrain blocks and check excavation — CPU

The C++ terrain library calculates blocks at candidate positions, going beyond the GPU’s noise-value tests. It is a reference implementation of vanilla generation; mineshafts and other structures or features have not yet been placed.

Using the mineshaft’s shape, record which blocks each piece could remove. Assume those removals succeed, then estimate the average height of the hut’s 63 columns. The `room_budget` setting is an average-height ceiling, currently −57: an estimated average of −55 is higher than −57 and rejects the seed.

| Step | Check | Processor |
|---|---|---|
| Initial height estimate | Start each column at −54 and remove positions covered by the mineshaft shape; reject when the sum of 63 heights exceeds `room_budget * 63` | CPU / C++ |
| High air check | If the room floor is −62, require air at `(x+3,62,z+3)` | CPU / C++ |
| Nearby fluid checks | Depending on room dimensions, test nine positions above its roof and four outer corners near Y=−55; reject water or lava at applicable test positions | CPU / C++ |
| Blocks beyond the mineshaft’s reach | Query each column at Y=−54, −53, −52 and −48. A non-air block outside the possible excavation raises that column’s estimated height; reject when the sum exceeds the threshold | CPU / C++ |
| Hut biome | Query the biome at the position and height used by vanilla to decide whether huts may generate | CPU / C++ |
| Flooding | Check aquifer states for all 63 columns at Y=62; reject only if all are flooded | CPU / C++ |
| Terrain average height | Read the 63 post-carving column heights before mineshaft placement, average using integer division truncated toward zero, and require `reference_y <= -48` | CPU / C++ |

`reference_y` is the final row’s terrain average before mineshaft excavation. **The −57 ceiling on estimated height after excavation, −48 ceiling on terrain height before placement, default −55 recording height and −59 search-stop height control different steps** and are configured separately.

### B4 Compare loading orders using vanilla generation — CPU / Java

After the preceding checks, enabled verification calls the chosen version’s vanilla code. Each loading order specifies which of the center and eight neighboring chunks is processed first. They reach the generation stage that places structures and features (`FEATURES`, also called decoration). Record the actual order and hut HPos; reset generation random numbers and chunk data between queries so one order’s blocks do not affect another.

After every configured order completes, save the minimum HPos, all orders attaining it, and whether changing order changes height or prevents the hut from generating. See [verification](VERIFICATION.md#english) for the list and measurement method. With vanilla verification disabled, recording and stopping use CPU reference height `native_y`, and saved results remain candidates awaiting verification.
