<a id="chinese"></a>

# 验证小屋

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

CPU 精筛用参考实现计算高度，可能与原版实际生成结果不同；同一种子、位置的小屋高度还可能受邻近区块的装饰顺序影响。这里的“装饰”指在已有地形上放置结构、矿物、植物等内容的生成步骤。

验证使用原版生成代码测量小屋的最低可刷怪高度 HPos，比较配置列表中的顺序，并返回最低 HPos。

## 搜索中的验证

`scripts/search.py` 与 `scripts/campaign.py` 均接受以下参数。已有结果的搜索目录恢复时沿用保存的验证模式。

| 参数 | 处理方式 | 保存候选、达到目标后停止时使用的高度 |
|---|---|---|
| `--verification off` | 将 CPU 精筛候选保存到 `shortlist.jsonl` | 参考高度 `native_y` |
| `--verification on`（默认） | 使用原版生成检查配置的 3×3 区块装饰顺序 | 实测最低 HPos |

## 生成服务

从仓库根目录执行；依赖安装见 [README](../README.md)。1.19.3–1.21.11 使用 Java 21，26.x 使用 Java 25；以下 `java` 应指向相应版本的 Java 可执行程序。支持版本见[版本说明](VERSIONS.md)。服务使用 CPU。

```bash
python3 scripts/verification.py --version 1.21 --output runs/query --java java --workers 2 --generation-mode features --accept-eula
```

服务启动后持续运行，反复处理请求。启动命令会下载缺失的官方服务端及依赖，并编译调用该版本生成代码所需的适配程序；`--accept-eula` 表示接受 Minecraft EULA。已有 JAR（Java 程序包）按文件是否存在直接复用，不重复下载或核对文件内容；下载文件及编译结果保存在 `runs/versions/` 和 `runs/query-service-build/`。仅准备文件时运行：

```bash
python3 scripts/verification/artifacts.py --versions 1.21 --java java --artifacts-only
```

默认按[版本表](VERSIONS.md)准备：同一区间内，小屋相关生成行为相同，只选其中一个版本下载和运行，称为代表版。指定准确发行版时加 `--exact`，例如 `--versions 1.21.1 --exact`。

将以下 JSON 保存为 `runs/request.json`，在服务启动后提交：

```json
{"seed":"1","x":0,"z":0,"world_type":"normal","loading_orders":true,"verification_mode":"on"}
```

```bash
python3 scripts/verification/request.py --service runs/query --request runs/request.json
```

`seed` 为世界种子，`x`、`z` 为查询位置的方块坐标。请求工具等待服务就绪并输出 JSON 响应；`--timeout` 控制等待秒数。`loading_orders:true` 测量配置列表中的全部顺序。单独查询一个顺序时，传入 `chunk_order`（以小屋区块为 `(0,0)` 的九个区块坐标，按执行顺序排列）及 `approach`（该顺序的名称）。

### 请求的世界类型

每个请求独立指定 `world_type`，同一服务可处理不同世界类型：

| `world_type` | 世界配置 |
|---|---|
| `normal`（默认） | 默认主世界 |
| `large_biomes` | 原版大型生物群系主世界 |
| `single_biome` | 默认主世界地形，所有位置使用同一种生物群系 |

`biome` 仅用于 `single_biome`，默认 `minecraft:swamp`；可选值为该版本支持的生物群系，`swamp` 等简写会补全命名空间。例如，将上面的请求改为 `"world_type":"single_biome","biome":"minecraft:swamp"`，即可查询单一沼泽群系世界。响应保留实际世界类型和群系。

| 响应字段 | 含义 |
|---|---|
| `min_hpos`、`heights` | 所测顺序的最低 HPos 及包含该值的列表；均无小屋时为 `null`、`[]` |
| `min_hpos_approaches` | 达到最低值的顺序 ID |
| `loading_order_heights` | 每个顺序测得的高度列表 |
| `loading_order_affected` | 所测顺序之间的高度或小屋存在性是否不同 |
| `loading_orders` | 各顺序响应，含请求及实际装饰顺序 |
| `loading_policy` | 由顺序列表内容计算出的编号；用于判断两次测量是否使用同一列表 |
| `world_type`、`biome` | 世界类型；单群系世界另带群系名 |

<a id="current-order-policy"></a>

## 顺序列表

[方向列表](../config/verification/loading-orders.txt)每行包含九个区块各一次，表示实际装饰顺序。`C` 为小屋所在区块，`N` 为 −Z（北），`E` 为 +X（东）；例如 `N NE C E SE S SW W NW`。

```text
NW  N  NE
 W  C   E
SW  S  SE
```

默认列表含 1,872 个完整顺序。每个顺序只保留从开头到 `C` 的部分（包含 `C`），这部分称为前缀；合并相同前缀后剩下 977 个。装饰到 `C` 后即可读取小屋高度，后续区块的装饰无需继续执行。修改列表会改变顺序列表编号。测量计划保存所用顺序及其内容摘要（哈希，用来识别列表是否改动），修改后需重新创建计划。每个前缀返回一个高度，无小屋为 `null`。

<a id="reproduce-order"></a>

## 首次生成与顺序复现

正式列表中，受顺序影响的记录包含 `min_hpos_order`，表示达到文件标称高度的一条已测顺序，只写到中心 `C`。例如 1.21 的种子 `3856881068873601123`、位置 `(-12363984, 19378240)` 在 `y-57.jsonl` 中记录 `S C`：先装饰南侧区块，再装饰小屋区块，即可测得 HPos=−57。

在上述 FEATURES 查询服务中提交下面的请求，可从独立的初始生成状态复现它。服务要求九个区块，因此把未列出的方向补在 `C` 后面：

```json
{"seed":"3856881068873601123","x":-12363984,"z":19378240,"world_type":"normal","approach":"published-minimum","chunk_order":[[0,1],[0,0],[0,-1],[1,-1],[1,0],[1,1],[-1,1],[-1,0],[-1,-1]]}
```

保存为 `runs/request.json`，使用前面的 `request.py` 命令提交，响应的 `heights` 应为 `[-57]`。`C` 后面的区块不会改变已经确定的小屋高度。

首次在游戏中生成时，使用记录对应的版本与正常世界，并让目标区块保持尚未生成；已生成小屋的高度会保存在世界里。方向记录描述装饰先后，游戏还会按视距和生成任务调度加载周围区块，因此需要在实际世界核对 HPos；这里提供的精确复现入口是查询服务。

## 批量测量

测量计划列出要运行的版本、种子、位置和加载顺序，默认从已发布小屋列表提取，并合并相同种子和位置。以下示例测量 1.21；`java` 应为 Java 21。构建并运行批量测量：

```bash
python3 scripts/verification/measure_orders.py plan --version 1.21 --work runs/orders
python3 scripts/verification/artifacts.py --version 1.21 --java java --artifacts-only
python3 scripts/verification/prepare_prefix.py --version 1.21 --output runs/orders/build --java java
python3 scripts/verification/measure_orders.py run --work runs/orders --workers 2 --cpu-per-jvm 1 --heap 6G --build-dir runs/orders/build --skip-post-hut-features
```

`--workers` 是并行运行的 Java 进程数；`--cpu-per-jvm` 是每个 Java 进程可用的 CPU 数；`--heap` 是每个进程分配给 Java 对象的最大内存。这些进程也称为 JVM，即 Java 虚拟机。默认使用当前进程可用的 CPU 集合；用 `--cpus 0-3,8` 选择其中一部分，程序检查该集合能容纳 `workers × cpu-per-jvm`。按可用 CPU 和内存调整这些值，并为 Java 堆之外的内存留出余量。重复执行 `run` 可恢复；生成错误会暂停队列，处理错误后使用 `--retry-failures`。结果保存为 JSONL（每行一条 JSON 记录），包含版本、种子、坐标、全部前缀高度和顺序列表编号；所有任务完成时进度文件记录 `complete:true`。


实测参考：1.21、正常世界、默认列表、启用前缀复用，32 个单核 JVM、每个堆上限 6 GiB；两台机器各测相同的 128 处小屋，完整耗时分别为 112.43 秒、110.15 秒。扣除首批 32 个冷启动样本后，其余 96 个样本的吞吐分别为 1.382、1.419 小屋/秒。这是 CPU 加载顺序测量的单版本吞吐。

计划可重复指定 `--version`，使用 `--orders` 选择其他顺序文件。创建计划时用 `--world-type large_biomes` 或 `--world-type single_biome --biome minecraft:swamp` 选择世界类型；省略时使用正常世界。整份计划使用相同世界配置，恢复时沿用保存的配置。运行时用 `--max-tasks` 限制任务数，`--reference` 逐项比较已有结果，`--reuse-results` 复用版本、种子、坐标、世界类型与群系、顺序列表编号均匹配且高度列表完整的结果。

---

<a id="english"></a>

# Verify huts

[![中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-red)](#chinese) [![English](https://img.shields.io/badge/Language-English-blue)](#english)

CPU screening calculates heights with a reference implementation, which can differ from vanilla generation. Neighboring chunk decoration order can also change a hut's height at the same seed and position. Here, decoration means the generation step that places structures, ores, plants and other content onto existing terrain.

Verification uses vanilla generation code to measure the hut’s lowest spawning height (HPos), compares the configured orders, and returns the minimum HPos.

## Verification during search

Both `scripts/search.py` and `scripts/campaign.py` accept these options. Resuming a populated search directory keeps its saved verification mode.

| Option | Behavior | Height used to save candidates and stop at the target |
|---|---|---|
| `--verification off` | Save CPU-screened candidates to `shortlist.jsonl` | Reference height `native_y` |
| `--verification on` (default) | Check configured 3×3 decoration orders with vanilla generation | Measured minimum HPos |

## Generation service

Run from the repository root; see [README](../README.md#english) for dependencies. Use Java 21 for 1.19.3–1.21.11 and Java 25 for 26.x. Here, `java` must point to the Java executable required by the chosen version. See [version support](VERSIONS.md#english). The service runs on CPUs.

```bash
python3 scripts/verification.py --version 1.21 --output runs/query --java java --workers 2 --generation-mode features --accept-eula
```

The service stays running to handle repeated requests. Startup downloads missing official server files and dependencies, then compiles the adapter program that calls the chosen version’s generation code; `--accept-eula` accepts the Minecraft EULA. Existing JARs (Java program packages) are reused if present, without redownloading or checking their contents. Downloaded files and compiled programs live under `runs/versions/` and `runs/query-service-build/`. To prepare files only:

```bash
python3 scripts/verification/artifacts.py --versions 1.21 --java java --artifacts-only
```

Preparation follows the [version table](VERSIONS.md#english): versions with the same hut-related generation behavior share an interval, and one is selected for downloading and running. This selected version is called the representative. Add `--exact` for an exact release, for example `--versions 1.21.1 --exact`.

Save this JSON as `runs/request.json`, then submit it after starting the service:

```json
{"seed":"1","x":0,"z":0,"world_type":"normal","loading_orders":true,"verification_mode":"on"}
```

```bash
python3 scripts/verification/request.py --service runs/query --request runs/request.json
```

`seed` is the world seed; `x` and `z` are the query position in block coordinates. The request tool waits for readiness and prints the JSON response; `--timeout` sets the wait limit in seconds. `loading_orders:true` measures every configured order. To query one order, provide `chunk_order` (nine chunk coordinates relative to the hut chunk at `(0,0)`, in execution order) and `approach` (a name for that order).

### Request world type

Each request specifies its own `world_type`, so one running service can handle different world types:

| `world_type` | World configuration |
|---|---|
| `normal` (default) | Default Overworld |
| `large_biomes` | Vanilla large-biome Overworld |
| `single_biome` | Default Overworld terrain with the same biome at every position |

`biome` applies only to `single_biome` and defaults to `minecraft:swamp`. It accepts biomes supported by the chosen version; shorthand such as `swamp` expands to `minecraft:swamp`. For example, change the request above to `"world_type":"single_biome","biome":"minecraft:swamp"` to query a single-biome swamp world. Responses retain the actual world type and biome.

| Response field | Meaning |
|---|---|
| `min_hpos`, `heights` | Minimum measured HPos and a list containing it; `null`, `[]` if all orders lack a hut |
| `min_hpos_approaches` | IDs of orders attaining the minimum |
| `loading_order_heights` | Heights measured for each order |
| `loading_order_affected` | Whether measured height or hut existence differs between orders |
| `loading_orders` | Individual responses, including requested and observed decoration orders |
| `loading_policy` | Identifier calculated from the order-list contents, used to check whether measurements used the same list |
| `world_type`, `biome` | World type, plus biome for single-biome worlds |

## Order list

Each line in the [direction list](../config/verification/loading-orders.txt) contains all nine chunks once, in decoration order. `C` is the hut chunk, `N` is −Z (north) and `E` is +X (east); for example, `N NE C E SE S SW W NW`.

```text
NW  N  NE
 W  C   E
SW  S  SE
```

The default list has 1,872 complete orders. Keep only the portion from the beginning through `C`, inclusive, called a prefix. Merging identical prefixes leaves 977. The hut height can be read once `C` has been decorated, so later chunks need not be decorated. Editing the list changes its identifier. Plans save the orders and a hash, a content summary used to detect changes; create a new plan after editing. Each prefix returns one height, or `null` if no hut exists.

<a id="reproduce-order-en"></a>

## First generation and order reproduction

Affected catalog records include `min_hpos_order`, one measured order attaining the height in the filename, ending at the center `C`. For example, the 1.21 record for seed `3856881068873601123` at `(-12363984, 19378240)` in `y-57.jsonl` specifies `S C`: decorating the southern chunk before the hut chunk produces HPos=−57.

Submit this request to the FEATURES query service above to reproduce it from an independent initial generation state. The service expects nine chunks, so append the remaining directions after `C`:

```json
{"seed":"3856881068873601123","x":-12363984,"z":19378240,"world_type":"normal","approach":"published-minimum","chunk_order":[[0,1],[0,0],[0,-1],[1,-1],[1,0],[1,1],[-1,1],[-1,0],[-1,-1]]}
```

Save it as `runs/request.json` and submit it with the `request.py` command above. The response should contain `heights:[-57]`. Chunks after `C` do not change the hut height already determined.

For first generation in the game, use the record’s version and a normal world, with the target chunk still ungenerated. A generated hut’s height is saved in the world. Directions describe decoration order; view distance and generation scheduling also determine neighboring chunk loading, so check HPos in the actual world. The query service provides exact order reproduction.

## Batch measurement

A measurement plan lists the versions, seeds, positions and loading orders to run. By default it reads the published hut catalog and merges entries with the same seed and position. This example measures 1.21, with `java` selecting Java 21. Build and run the batch measurement:

```bash
python3 scripts/verification/measure_orders.py plan --version 1.21 --work runs/orders
python3 scripts/verification/artifacts.py --version 1.21 --java java --artifacts-only
python3 scripts/verification/prepare_prefix.py --version 1.21 --output runs/orders/build --java java
python3 scripts/verification/measure_orders.py run --work runs/orders --workers 2 --cpu-per-jvm 1 --heap 6G --build-dir runs/orders/build --skip-post-hut-features
```

`--workers` sets the number of concurrent Java processes, `--cpu-per-jvm` sets the CPU count available to each, and `--heap` sets each process’s maximum memory for Java objects. These processes are also called JVMs (Java virtual machines). By default the process inherits its available CPU set. Select a subset with `--cpus 0-3,8`; it must accommodate `workers × cpu-per-jvm`. Adjust these values to available CPU and memory, allowing for memory beyond the Java heap. Repeat `run` to resume. Generation errors pause the queue; use `--retry-failures` after resolving them. Results use JSONL (one JSON record per line), recording version, seed, coordinates, all prefix heights and the order-list identifier. Once all tasks finish, the progress file records `complete:true`.


Measured reference: 1.21, normal worlds, default order list, prefix reuse, 32 single-core JVMs with maximum heaps of 6 GiB each. Two machines each measured the same 128 huts in 112.43 and 110.15 seconds. After the first 32 cold-start cases, the remaining 96 cases ran at 1.382 and 1.419 huts/second. These figures describe single-version CPU loading-order measurement.

Repeat `--version` when planning multiple versions, or use `--orders` for a custom order file. Select the world configuration when planning with `--world-type large_biomes` or `--world-type single_biome --biome minecraft:swamp`; omission selects a normal world. All tasks in a plan share that configuration, which is retained when resuming. At runtime, `--max-tasks` limits tasks, `--reference` compares saved results element by element, and `--reuse-results` reuses results with matching version, seed, coordinates, world type, biome and order-list identifier, and a complete height list.
