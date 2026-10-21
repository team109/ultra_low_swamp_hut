<a id="chinese"></a>

# 源码打包

中文 | [English](#english)

```bash
python3 tools/package_source.py --output dist/ultra-low-hut-source.tar.gz
```

打包当前工作区的源码、文档、101 个矿井布局和小屋数据，并生成 `SHA256SUMS`。依赖、编译产物和运行日志保留在各自目录。检查报告位于 `runs/release-audit.json`。

---

<a id="english"></a>

[中文](#chinese) | English

# Package the source

The command above packages the current source, documentation, 101 mineshaft layouts and hut data, and writes `SHA256SUMS`. Dependencies, build artifacts and runtime logs stay in their own directories. The audit report is written to `runs/release-audit.json`.
