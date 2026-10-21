<a id="chinese"></a>

# 筛选矿井布局

中文 | [English](#english)

在单座普通矿井的起始房间与小屋同区块的搜索模型下，完整枚举得到全部 101 个可能产生 −59 小屋的布局。[结果](../data/mineshafts/1.21/layouts.jsonl)按 −59 产率、挖掘量降序排列。[完整模板](../data/mineshafts/1.21/templates.json)可直接用于测量和小屋搜索。

## 枚举布局

完成 [README](../README.md) 中的依赖准备后执行：

```bash
python3 tools/enumerate_layouts.py --devices 0 --arch sm_80 --output runs/layouts/templates.jsonl
```

多卡使用 `--devices 0,1,2,3,4,5,6,7`。程序展开矿井部件，保留小屋范围理想挖掘量达到 315 的布局，输出完整模板。进度与断点保存在 `runs/layouts/enumeration/`；使用相同参数重跑可继续枚举。

## 测量 −59 产率

完成 CPU 库构建并准备 1.21 的验证器后，使用共享自然地形样本：

```bash
python3 tools/measure_layout_yields.py --layouts data/mineshafts/1.21/templates.json --terrain-panel runs/terrain/panel.json --output runs/layout-yields --workers 4 --java java
```

每份地形固定执行 256 组装饰随机序列，可通过 `--draws` 修改。结果 `results.jsonl` 按产率、挖掘量降序排列，开头三个字段为：

| 字段 | 含义 |
|---|---|
| `layout_seed` | 矿井布局的 48 位随机数种子 |
| `excavation` | 小屋 7×9 范围在 Y=−54 平地上的理想高度下降总量 |
| `expected59_per_trillion_trials` | 固定布局后，每万亿次完整种子—位置筛选预期产生的 HPos≤−59 小屋数 |

不同坐标精度区域分别输出。`details/` 保存逐份地形的放置结果，`summary.json` 保存样本预算与耗时。已收录布局的测量数据见[数据说明](../data/mineshafts/README.md)。

### 地形样本格式

`panel.json` 为数组，每项包含 `id`、完整世界种子 `seed`、方块坐标 `x`、`z`、原始地形平均高度 `raw_y`、相对快照路径 `snapshot_file`。加权样本可指定 `trial_weight`；等权样本每项权重为 `1 / seed_position_trials`。

同目录的 `configuration.json` 包含：

```json
{"seed_position_trials":2199023255552,"raw_height_max":-46,"gate_budget":-57,"reference_max_y":-48}
```

这四项分别表示采样的完整筛选次数、样本覆盖的原始高度上限、布局地形筛选预算、搜索器的原始高度门槛。

快照为原版洞穴雕刻完成后的 16×16×384 方块，Y 范围 −64～319，按 Z、X、Y 排列，每格一个字节：`0` 空气、`1` 深板岩、`2` 水、`3` 熔岩、`4` 基岩。

## 使用布局搜索小屋

```bash
python3 tools/select_layout.py --seed 270840896143627 --output runs/layout.json
```

从自己枚举的模板中选择时，加入 `--catalog runs/layouts/templates.jsonl`。把输出文件传给 [README](../README.md) 搜索命令的 `--layout-template`。

批量搜索布局池：

```bash
python3 tools/search_layout_pool.py --root runs/pool-search --version 1.21 --layout-pool data/mineshafts/1.21/templates.json --devices 0 --stop-when-pool-exhausted --java java --accept-eula
```

布局按输入顺序逐个搜索，找到目标高度后停止；进度和汇总结果保存在 `--root`。恢复时使用相同目录并加入 `--resume`。

---

<a id="english"></a>

[中文](#chinese) | English

# Screen mineshaft layouts

Exhaustive enumeration found all 101 layouts capable of producing −59 huts in the single-normal-mineshaft, same-starting-chunk search model. The [results](../data/mineshafts/1.21/layouts.jsonl) sort by descending −59 yield, then excavation. [Complete templates](../data/mineshafts/1.21/templates.json) can be measured or searched directly.

## Enumerate layouts

After fetching the dependencies in the [README](../README.md), run the enumeration command above. Use `--devices 0,1,2,3,4,5,6,7` for eight GPUs. The program constructs mineshaft pieces and retains templates with ideal excavation of at least 315 over the hut footprint. Checkpoints and progress are written to `runs/layouts/enumeration/`; rerunning with the same parameters resumes enumeration.

## Measure −59 yield

Build the CPU library and prepare the 1.21 verifier, then run the measurement command above with a shared natural-terrain panel. Each terrain receives a fixed 256 decoration streams; change this using `--draws`.

`results.jsonl` sorts by descending yield, then excavation. Its first three fields are `layout_seed` (48-bit layout RNG seed), `excavation` (ideal summed height reduction on flat Y=−54 terrain) and `expected59_per_trillion_trials` (expected HPos≤−59 huts per trillion complete seed-position trials with the layout fixed). Coordinate-precision regions are reported separately. `details/` contains per-terrain outcomes; `summary.json` contains the budget and duration. See the [data guide](../data/mineshafts/README.md) for published measurements.

### Terrain panel format

Each `panel.json` entry contains `id`, decimal-string world `seed`, block coordinates `x`/`z`, raw average height `raw_y` and relative `snapshot_file`. Weighted entries specify `trial_weight`; otherwise each entry weighs `1 / seed_position_trials`.

The accompanying `configuration.json` example above supplies the full sampling trial count, panel height coverage, layout terrain-gate budget and raw-height screening cutoff, respectively.

Snapshots contain vanilla post-carving blocks in a 16×16×384 volume, Y=−64 through 319, ordered by Z, X and Y. Each cell is one byte: `0` air, `1` deepslate, `2` water, `3` lava, `4` bedrock.

## Search from a layout

Select a template using the command above. Add `--catalog runs/layouts/templates.jsonl` to select from your own enumeration. Pass the output to `--layout-template` in the [README](../README.md) search command.

The layout-pool command above searches templates sequentially in input order, stops at the target height, and aggregates progress and results beneath `--root`. Resume with the same directory and `--resume`.
