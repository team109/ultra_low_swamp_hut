<a id="chinese"></a>

# 数据目录

中文 | [English](#english)

| 目录 | 内容 |
|---|---|
| [huts/](huts/README.md) | 历史发现并经原版生成验证的小屋，按适用版本分目录、按 HPos 分文件，记录世界种子和 X、Z 坐标 |
| [mineshafts/](mineshafts/README.md) | 101 个矿井布局的种子、挖掘量、自然 −59 产率、完整搜索模板，以及测量所用的参考坐标 |
| search/ | 搜索默认配置，包括布局选择、坐标范围、批大小和筛选参数 |
| versions/ | 游戏版本到筛选配置的映射、种子互通区间及复核源码的提交号 |
| noises/ | GPU 地形计算使用的噪声参数，包括倍频程、振幅和种子派生信息 |

小屋数据中的 `seed` 是完整世界种子；矿井数据中的 `layout_seed` 是决定结构布局的 48 位随机数种子。两种种子均以十进制字符串保存。

---

<a id="english"></a>

[中文](#chinese) | English

# Data directory

| Directory | Contents |
|---|---|
| [huts/](huts/README.md) | Historical huts verified with vanilla generation, grouped by applicable version and HPos, with world seeds and X/Z coordinates |
| [mineshafts/](mineshafts/README.md) | Seeds, excavation, natural −59 yield and complete search templates for 101 mineshaft layouts, plus measurement reference positions |
| search/ | Default search settings, including layout selection, coordinate domains, batch sizes and screening parameters |
| versions/ | Game-version screening configurations, seed-compatibility intervals and reviewed source commit IDs |
| noises/ | Noise parameters for GPU terrain computation, including octaves, amplitudes and seed derivation |

A hut's `seed` is a full world seed. A mineshaft's `layout_seed` is the 48-bit RNG seed determining its structure layout. Both are stored as decimal strings.
