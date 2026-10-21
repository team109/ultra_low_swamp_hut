<a id="chinese"></a>

# 搜索算法

中文 | [English](#english)

矿井起始房间与相连通道挖空地形后，沼泽小屋可能生成在更低的位置。搜索分为布局筛选与世界种子筛选。

## 布局筛选

GPU 枚举通过矿井放置判定的随机数状态，构造矿井部件树并计算自然放置高度。对小屋 7×9 范围逐列累加理想高度下降量，保留有机会达到 HPos≤−59 的布局。

房间顶部的挖掘形状受世界坐标浮点精度影响，因此分别计算九种 X、Z 精度组合。布局的自然产率使用同一组加权自然地形和每份地形固定 256 组装饰随机序列测量，原版部件放置保留流体否决、随机顶板与支撑方块。结果按产率、挖掘量降序排列。

## 小屋搜索

1. **反解低 48 位。** 固定矿井布局，寻找起始房间与小屋位于同一区块的种子与坐标。先检查小屋放置随机数的低位，再补齐种子并正向确认；1.21 起同时排除附近的试炼密室起点。
2. **GPU 批量筛选。** 枚举高 16 位，依次检查侵蚀、温度、地表和洞穴噪声。逐步压紧候选，并复用噪声状态与显存。
3. **CPU 地形精筛。** 在实际坐标计算挖掘范围，检查房间边界流体和小屋高度预算。每个布局自动生成并缓存探测计划，地形插值节点按需计算；GPU 同时处理下一批。
4. **原版验证。** 常驻查询服务生成小屋附近的原版区块，返回 HPos，并立即写入符合记录阈值的结果。

多卡按反解域分工，每张卡有独立流水线。搜索进度按已完成批次保存，恢复时跳过已处理的位置。

---

<a id="english"></a>

[中文](#chinese) | English

# Search algorithm

A mineshaft starting room and its connected corridors can excavate terrain so a swamp hut generates lower. The search has two stages: layout screening and world-seed screening.

## Layout screening

GPUs enumerate RNG states passing mineshaft placement, construct their piece trees and calculate natural placement height. The ideal height reduction is summed across the 7×9 hut footprint; layouts capable of HPos≤−59 are retained.

World-coordinate float precision affects room clearing, so nine X/Z precision combinations are evaluated separately. Natural yield uses the same weighted terrain panel and a fixed 256 decoration streams per terrain. Vanilla placement retains liquid vetoes, random roofs and supports. Results sort by descending yield, then excavation.

## Hut search

1. **Invert the lower 48 bits.** Fix a layout and find seeds and coordinates placing its starting room and the hut in the same chunk. Prune hut-placement RNG bits before completing the inverse and checking forward. From 1.21 onward, also exclude nearby trial-chamber starts.
2. **Screen GPU batches.** Enumerate the upper 16 bits and check erosion, temperature, surface and cave noise. Compact survivors progressively and reuse noise state and device memory.
3. **Refine terrain on the CPU.** Compute clearing at actual coordinates and check boundary liquids and the footprint height budget. Probe plans compile and cache automatically per layout; terrain interpolation nodes are computed on demand while the GPU processes the next batch.
4. **Verify with vanilla generation.** A persistent query service generates nearby vanilla chunks, returns HPos and immediately records qualifying results.

GPUs divide the inverse domain into independent pipelines. Completed batches are checkpointed and skipped when resuming.
