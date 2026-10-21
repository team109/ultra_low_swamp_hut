<a id="chinese"></a>

# 验证小屋

中文 | [English](#english)

## 同时验证多个版本

以 1.21 筛选，同时在 1.21 和 26.3 验证：

```bash
python3 tools/prepare_version_verifier.py --version 1.21 --java java21
python3 tools/prepare_version_verifier.py --version 26.3 --java java25
python3 tools/search_huts.py --version 1.21 --layout-template runs/layout.json --root runs/dual-version --devices 0 --java java25 --verify-version 1.21 --verify-version 26.3 --accept-eula
```

这里 `java21`、`java25` 分别表示对应的 Java 可执行文件。搜索保留至少一个版本验证通过的结果；同一高度的适用版本合并到 `versions`，不同高度分别记录。

## 在游戏中复核

将 `SEED`、`X`、`Z` 设为结果中的值：

```bash
python3 tools/verify_vanilla.py --version 1.21 --seed "$SEED" --x "$X" --z "$Z" --approach center --output runs/recheck --java java21 --accept-eula
```

命令创建新世界，生成小屋附近区块并读取结构高度；世界保留在输出目录，可在游戏中打开。使用 `--approach east` 或 `west`，配合新的输出目录，可比较区块加载顺序的影响。

## 单独查询

```bash
python3 tools/start_terrain_service.py --version 1.21 --output runs/query --java java21 --accept-eula
python3 tools/terrain_request.py --service runs/query --request request.json
```

`request.json` 支持批量种子与方块坐标：

```json
{"requests":[{"seed":"0","x":0,"z":0},{"seed":"1","x":512,"z":512}]}
```

响应的 `heights` 是请求区块内小屋的 HPos 列表，`hut_pieces` 给出包围盒。可选字段 `approach` 接受 `center`、`east`、`west`。服务复用 JVM，每次请求默认生成新的内存世界上下文。

服务就绪标记为 `ready.json`，日志为 `server.log`，进程号在 `process.json` 中。向该进程发送 `SIGTERM` 可停止服务。

---

<a id="english"></a>

[中文](#chinese) | English

# Verify huts

## Verify multiple versions

The commands above screen for 1.21 and verify in both 1.21 and 26.3. `java21` and `java25` denote the corresponding Java executables. Results passing at least one version are retained. Equal heights combine their `versions`; different heights are recorded separately.

## Recheck in the game

Set `SEED`, `X` and `Z` to a recorded result and run the recheck command above. It creates a fresh world, generates nearby chunks and reads structure height. The world remains in the output directory for opening in the game. Repeat with `--approach east` or `west` and new output directories to compare chunk loading orders.

## Standalone queries

Start the service and submit `request.json` using the commands above. A request supports batches of decimal-string seeds and block coordinates. Responses contain hut HPos values in `heights` and bounding boxes in `hut_pieces`. Optional `approach` accepts `center`, `east` or `west`. The JVM is reused; each request defaults to a fresh in-memory world context.

Readiness is recorded in `ready.json`, logs in `server.log`, and the PID in `process.json`. Send `SIGTERM` to that PID to stop the service.
