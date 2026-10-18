# 检查与处理提速实施记录

2026-10-18 用户授权逐节点实施、提交推送，最终先提供 Windows EXE 测试。工作分支 `codex/performance-check-processing`；main 和正式发布维持原状。统一任务定义见 [计划第 19 节](plan.md#19-性能调研成果改进计划2026-10-15)。

## I0：可复现基准

新增 `scripts/benchmark_metrics.py`，扩展 `scripts/benchmark_pipeline.py`：

- `--digital off|dct|fft`、`--level low|medium|high`、`--flow`；合成签名包含可恢复笔画，全部模式共用同一素材。
- `--entry pipeline|gui-start|gui-check-start`；后两项实际驱动 Qt 主窗口与后台 worker，分别测直接开始和先检查再开始。导入/初始预览不计入点击后的耗时；运行环境配置与素材全部临时隔离。
- pipeline 关闭预检会话后重新开启，匹配 GUI worker 的会话边界；每张处理延迟、吞吐、总耗时和分阶段包含耗时。
- 每 25 ms 同时采样本进程及子进程 RSS/working set；Windows 另记录 private bytes。共享页可能重复计数；采样可能漏掉短于采样间隔的瞬时峰值；不把采样峰值等同于系统物理占用或旧主进程 HWM。
- Linux `/proc` 与 Windows 原生 API，无新增运行依赖；不支持或无法采样时报告错误，不伪造零占用。GUI 的单张 p50/p95 暂不可用，pipeline 小样本经验 p95 不作大批次尾延迟承诺。

最小检查：Ruff/格式通过；1920×1280、1 张的 pipeline 与 gui-check-start 均成功，独立请求统计及进程树采样产生结果。正式对比使用冻结的 I0 源快照、相同参数至少 5 轮；原始 JSON、快照及私人样片保持本地忽略目录。

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/benchmark_pipeline.py \
  --flow location_and_watermark --count 1 --rounds 5 --digital dct \
  --report build/performance/implementation/i0-dct.json
QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/benchmark_pipeline.py \
  --flow location_and_watermark --count 1 --rounds 5 --entry gui-check-start \
  --report build/performance/implementation/i0-check-start.json
```

完整尺寸/大批次/真实 JPEG/NEF、取消、原生 Windows 和冻结包验收在后续节点继续补齐，当前未把这些标记通过。正式发布须等待本次最终 EXE 的用户反馈。
