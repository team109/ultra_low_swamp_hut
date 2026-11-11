<a id="chinese"></a>

# 筛选矿井布局

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

本项目先找出适合挖低小屋的矿井形状，再寻找能生成这些矿井的世界种子和坐标。“布局”指矿井起始房间、通道、交叉口和楼梯的形状与位置；“模板”是保存布局种子、小屋占地范围和搜索所需信息的文件。可直接使用[随附模板](../data/mineshafts/templates.json)，或自行枚举、测量并选择模板。这里使用原版主世界高度和海平面，只考虑一座自然生成的普通（`NORMAL`）矿井，且起始房间与小屋位于同一区块；版本适用范围见[版本说明](VERSIONS.md)。

## 枚举布局

完成 [README](../README.md) 中的依赖准备后执行：

```bash
python3 scripts/layouts/enumerate.py --devices 0 --arch sm_80 --output runs/layouts/templates.jsonl
```

按实际 GPU 架构设置 `--arch`，多卡通过 `--devices` 指定逗号分隔的设备编号。程序按原版规则生成矿井各部件，再计算它们能挖掉小屋 7×9 范围内多少阻挡方块。计算时先假设 63 列地形的高度都为 Y=−54，并假设矿井每处挖掘都能成功；各列下降格数之和达到 315 才保留，因为平均从 −54 降到 −59 需要 `63 × 5 = 315`。这个门槛筛出有可能生成 −59 小屋的矿井布局，结果保存为模板文件，供后续搜索实际种子并验证高度。进度与断点保存在 `runs/layouts/enumeration/`；使用相同参数重跑可继续枚举。

## 测量 −59 产率

完成 [README](../README.md) 中的 CPU 库构建与 1.21 原版验证器准备后，先从随附的地形种子列表生成快照与配套配置，再测量产率。Java 需使用 21 或更新版本：

```bash
python3 scripts/layouts/prepare_panel.py --output runs/terrain --java java
python3 scripts/layouts/measure_yields.py --layouts data/mineshafts/templates.json --terrain-panel runs/terrain/panel.json --output runs/layout-yields --workers 4 --java java
```

`prepare_panel.py` 读取 [yield-panel.json](../data/mineshafts/yield-panel.json) 中的 411 份地形种子、坐标与权重，以及 [yield-measurement.json](../data/mineshafts/yield-measurement.json) 中的采样配置；构建 1.21 原版服务，在洞穴雕刻完成、地物装饰开始前保存方块。输出为 `runs/terrain/panel.json`、`configuration.json` 和 `snapshots/*.bin`，可用相同命令继续生成缺失的快照；已有输出目录只接受相同的地形列表和配置。默认单个 Java 进程，堆内存上限 2 GiB。需要换地形样本时，通过 `--panel`、`--configuration` 指定同格式的列表和配置。

随附面板来自 2,199,023,255,552 次完整种子—位置尝试，并结合固定数量的条件样本及其权重。发布测量覆盖 101 个布局、348 个坐标精度组合，每份符合条件的地形放置 256 次，共实际放置 674,304 次。[yield-results.jsonl](../data/mineshafts/yield-results.jsonl) 保存各组合的地形数、放置数和成功次数，与 `regions/` 中的产率逐项对应。

测量把同一批真实地形依次交给各个矿井布局，比较它们把小屋降到 HPos≤−59（最低可刷怪高度不高于 −59）的机会。调用原版放置代码前，先进行两项检查：

1. 调用搜索器的房间筛选：检查房间周围指定位置的水和岩浆，以及小屋 63 列中剩余方块所允许的最低高度；发现流体、指定位置有阻挡，或估计平均高度高于配置的 `gate_budget` 时跳过。
2. 假设矿井能挖空其全部可挖范围，从已保存的地形方块中直接删掉这些方块；如果剩余方块决定的平均高度仍高于 −59，就算每次挖掘都成功也达不到目标，因此跳过原版放置。

通过检查后，默认在每份地形上运行 256 次原版矿井放置，用不同随机数决定顶板挖掘、木支撑等细节；`--draws` 可修改次数。比较不同布局及不同坐标时，同一份地形使用相同的随机数起点，减少随机选择带来的比较误差。

`results.jsonl` 按产率、挖掘量降序排列，主要字段为：

| 字段 | 含义 |
|---|---|
| `layout_seed` | 决定矿井部件形状的 48 位随机数种子 |
| `excavation` | 小屋 7×9 范围在 Y=−54 平地上的理想高度下降总量 |
| `expected59_per_trillion_trials` | 固定布局后，每万亿次完整种子—位置筛选预期产生的 HPos≤−59 小屋数 |

原版计算矿井房间顶部时使用单精度浮点数，远离原点后会发生舍入，改变同一布局能挖掉的方块。X、Z 各按能表示小于一格、一格或两格的坐标间隔分成三类，组合得到九类坐标条件；程序分别测量符合筛选条件的组合，称为“坐标精度区域”。类别的具体坐标范围、九种组合和版本适用范围见[坐标精度说明](ALGORITHM.md#九种坐标精度组合及范围)。`details/` 保存每份地形上成功生成 −59 小屋的次数，`summary.json` 保存地形数量、尝试次数和耗时。已收录布局的测量数据见[数据说明](../data/mineshafts/README.md)。

### 地形样本格式

`panel.json` 列出用于比较布局的地形。每项包含 `id`、十进制字符串形式的完整世界种子 `seed`、方块坐标 `x`、`z`、矿井放置前小屋 63 列的平均高度 `raw_y`，以及保存地形方块的文件路径 `snapshot_file`（相对于 `panel.json` 所在目录）。

“样本权重”表示一份地形在全部种子—位置尝试中占的比例，用于把每份地形的放置成功率换算为总产率。程序优先使用该项的 `trial_weight`；没有时使用 `1 / balance_exposure`；两者都没有时使用 `1 / seed_position_trials`。例如从一百万次尝试中各保留一次符合条件的地形，每份的权重就是百万分之一。将每份地形的权重乘以该地形上“成功次数 / 放置次数”，求和后再乘以一万亿，即得到 `expected59_per_trillion_trials`。

同目录的 `configuration.json` 示例：

```json
{"seed_position_trials":65536000,"raw_height_max":-46,"gate_budget":-57,"reference_max_y":-48}
```

| 字段 | 含义 |
|---|---|
| `seed_position_trials` | 收集地形时检查过的完整世界种子—位置组合数 |
| `raw_height_max` | 收集地形时允许的最高 `raw_y`；示例中仅收集平均高度不高于 −46 的地形 |
| `gate_budget` | 第一项房间筛选允许的估计平均高度上限；示例为 −57 |
| `reference_max_y` | 计入最终产率的地形平均高度上限；示例中仅计入 `raw_y≤−48` 的结果，与搜索器的地形高度筛选保持一致 |

这些值应与实际采样和搜索配置一致。程序会根据布局最多能挖低多少，计算仍可能达到 −59 的地形最高可以多高；如果 `raw_height_max` 低于这个高度，说明所收集地形不完整，程序报错。

“快照”即保存下来的地形方块数据，内容为原版洞穴生成完成、矿井放置前的 16×16×384 方块，Y 范围 −64～319，按 Z、X、Y 排列，每格一个字节：`0` 空气、`1` 深板岩、`2` 水、`3` 熔岩、`4` 基岩。

## 使用布局搜索小屋

```bash
python3 scripts/layouts/select.py --seed 270840896143627 --output runs/layout.json
```

从自己枚举的模板中选择时，加入 `--catalog runs/layouts/templates.jsonl`。把输出文件传给 [README](../README.md) 搜索命令的 `--layout-template`。

一次提交多个模板进行搜索（`--layout-pool` 接受模板列表文件）：

```bash
python3 scripts/campaign.py --root runs/pool-search --version 1.21 --layout-pool data/mineshafts/templates.json --devices 0 --stop-when-pool-exhausted --java java --accept-eula
```

布局按输入顺序逐个搜索，找到目标高度后停止；进度和汇总结果保存在 `--root`。恢复时使用相同目录并加入 `--resume`。

---

<a id="english"></a>

# Screen mineshaft layouts

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

The project first finds mineshaft shapes that can lower huts, then searches for world seeds and coordinates that generate those shapes. A layout describes the starting room, corridors, crossings and stairs. A template is a file recording its layout seed, hut footprint and other inputs needed by the searcher. Use the [supplied templates](../data/mineshafts/templates.json), or enumerate, measure and select your own. The model uses vanilla Overworld height and sea level, one naturally placed normal (`NORMAL`) mineshaft, and its starting room in the hut chunk. See [versions](VERSIONS.md#english) for compatibility.

## Enumerate layouts

After fetching the dependencies in the [README](../README.md#english), run:

```bash
python3 scripts/layouts/enumerate.py --devices 0 --arch sm_80 --output runs/layouts/templates.jsonl
```

Set `--arch` for your GPU architecture and supply comma-separated GPU IDs through `--devices` for multiple GPUs. The program constructs mineshaft pieces using vanilla rules and calculates how far they could lower all 63 columns in the 7×9 hut footprint. This calculation starts every column at Y=−54 and assumes all clearing succeeds. A layout must lower the summed heights by at least 315, because lowering the average from −54 to −59 requires `63 × 5 = 315`. This cutoff selects layouts that could produce −59 huts. They are saved as templates for world-seed search and height verification. Checkpoints and progress are written to `runs/layouts/enumeration/`; rerunning with the same parameters resumes enumeration.

## Measure −59 yield

Follow the [README](../README.md#english) to build the CPU library and prepare the 1.21 vanilla verifier. Rebuild the terrain snapshots and configuration from the supplied seed list, then measure yields. Use Java 21 or newer:

```bash
python3 scripts/layouts/prepare_panel.py --output runs/terrain --java java
python3 scripts/layouts/measure_yields.py --layouts data/mineshafts/templates.json --terrain-panel runs/terrain/panel.json --output runs/layout-yields --workers 4 --java java
```

`prepare_panel.py` reads the 411 terrain seeds, coordinates and weights in [yield-panel.json](../data/mineshafts/yield-panel.json) and the sampling configuration in [yield-measurement.json](../data/mineshafts/yield-measurement.json). It builds the vanilla 1.21 service and captures blocks after cave carving and before feature decoration. Outputs are `runs/terrain/panel.json`, `configuration.json` and `snapshots/*.bin`. Rerun the command to capture missing snapshots. An existing output directory requires the same terrain list and configuration. It uses one Java process with a 2 GiB heap limit. Supply other panels and configurations of the same format with `--panel` and `--configuration`.

The supplied panel combines 2,199,023,255,552 complete seed-position trials with fixed-count conditional samples and their weights. The published measurement covers 101 layouts and 348 coordinate-precision combinations, using 256 placements per eligible terrain and 674,304 actual placements in total. [yield-results.jsonl](../data/mineshafts/yield-results.jsonl) records terrain counts, placements and successes for each combination, matching the yields under `regions/`.

The measurement places each layout into the same set of real terrains and compares its chance of producing HPos≤−59, meaning a lowest spawning height no higher than −59. Two checks run before vanilla placement:

1. Run the searcher's room filter. It checks water and lava at selected positions around the room and estimates the lowest possible average across the hut's 63 columns from the remaining blocks. Fluids, an obstruction at a required empty position, or an estimate above `gate_budget` cause that terrain to be skipped.
2. Remove every block the mineshaft could clear from the saved terrain, assuming all clearing succeeds. If the average height determined by the remaining blocks still exceeds −59, this layout cannot reach the target even under that assumption, so vanilla placement is skipped.

Each remaining terrain receives 256 vanilla mineshaft placements by default, varying random choices such as roof clearing and wooden supports; change the count using `--draws`. For a given terrain, different layouts and coordinates use the same initial random states to reduce differences caused by random choices.

`results.jsonl` sorts by descending yield, then excavation. Its main fields are:

| Field | Meaning |
|---|---|
| `layout_seed` | The 48-bit random seed determining the mineshaft shape |
| `excavation` | Summed column-height reduction within the 7×9 hut footprint, starting from flat Y=−54 terrain and assuming all clearing succeeds |
| `expected59_per_trillion_trials` | Expected HPos≤−59 huts per trillion complete world-seed and position trials with this layout fixed |

Vanilla calculates the room roof with single-precision floating-point numbers. Rounding far from the origin changes which blocks the same layout clears. Each axis has three classes where representable coordinate values are spaced less than one block, one block or two blocks apart. Their nine X/Z combinations are called coordinate-precision regions; eligible combinations are measured separately. See [coordinate precision](ALGORITHM.md#nine-coordinate-precision-combinations-and-their-ranges) for exact ranges, all nine combinations and version compatibility. `details/` records successful −59 placements on each terrain, and `summary.json` records terrain counts, trial counts and duration. See the [data guide](../data/mineshafts/README.md#english) for published measurements.

### Terrain panel format

`panel.json` lists the terrains used to compare layouts. Each entry contains `id`, decimal-string world `seed`, block coordinates `x`/`z`, the average height of the hut's 63 columns before mineshaft placement as `raw_y`, and a terrain-block file in `snapshot_file`, relative to the directory containing `panel.json`.

A sample's weight represents its share of all seed-position trials. The program uses `trial_weight` if present, otherwise `1 / balance_exposure`, otherwise `1 / seed_position_trials`. For example, each terrain retained once from one million trials has a weight of one millionth. Multiply each terrain's placement success fraction by its weight, sum the contributions, then multiply by one trillion to obtain `expected59_per_trillion_trials`.

Place `configuration.json` beside `panel.json`:

```json
{"seed_position_trials":65536000,"raw_height_max":-46,"gate_budget":-57,"reference_max_y":-48}
```

| Field | Meaning |
|---|---|
| `seed_position_trials` | Number of complete world-seed and position combinations checked while collecting terrain |
| `raw_height_max` | Highest `raw_y` admitted during collection; −46 in this example |
| `gate_budget` | Highest estimated average allowed by the first room check; −57 here |
| `reference_max_y` | Highest terrain average included in the final yield; only `raw_y≤−48` contributes here, matching the searcher's terrain-height filter |

Use values matching the actual collection and search settings. The program calculates the highest initial terrain that could still reach −59 given the layout's maximum possible clearing. If `raw_height_max` is lower than that value, the collected terrain is incomplete and the program raises an error.

A snapshot is a saved copy of terrain blocks. It contains vanilla blocks after cave generation and before mineshaft placement in a 16×16×384 volume, Y=−64 through 319, ordered by Z, X and Y. Each cell is one byte: `0` air, `1` deepslate, `2` water, `3` lava, `4` bedrock.

## Search from a layout

```bash
python3 scripts/layouts/select.py --seed 270840896143627 --output runs/layout.json
```

Select a template using the command. Add `--catalog runs/layouts/templates.jsonl` to select from your own enumeration. Pass the output to `--layout-template` in the [README](../README.md#english) search command.

The following command supplies multiple templates in one list through `--layout-pool`. It searches them in input order, stops at the target height, and saves progress and results beneath `--root`. Resume with the same directory and `--resume`.

```bash
python3 scripts/campaign.py --root runs/pool-search --version 1.21 --layout-pool data/mineshafts/templates.json --devices 0 --stop-when-pool-exhausted --java java --accept-eula
```
