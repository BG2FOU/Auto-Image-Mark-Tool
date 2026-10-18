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

## I4a：联合读取与内容绑定的检查复用

GUI 窗口维护最多 256 条已通过的 JPEG 检查摘要，不缓存整批像素；坐标与水印共享一次预检日期/GPS 请求。每次仍重建计划、检查目标与冲突，配置/照片/资源变化时重检。源内容 SHA256 和文件身份在元数据读取前与完整检查后核对，命中时也重读摘要；执行前继续绑定已验证源状态。取消/失败清空窗口缓存，关闭释放。NEF 不使用此缓存。

新增回归覆盖缓存命中、照片字段/StepSpec/源内容/签名变化、恢复源或素材 mtime、目标被占、坏输入、元数据读取期间替换，以及检查后执行前同大小同 mtime 替换。GUI 的检查后开始只完整解码一次，最终处理保护仍执行。

I0 冻结源与候选用同一工具、同一 5038×3363 合成图片，每轮一个新进程，每种路径交替先后配对 5 轮：

| 路径（1 张，数字关闭） | I0 总耗时中位数 | I4a 总耗时中位数 | 结论 |
| --- | --- | --- | --- |
| 直接开始 | 2.943 s | 2.999 s | 额外内容摘要约增加 0.057 s（1.9%）；差值小于该次基线范围宽度 0.085 s，保留观察 |
| 手动检查后开始 | 3.652 s | 3.266 s | 总等待减少约 10.6%；第二次检查不再解码，首次摘要成本已计入 |

41 项相关 GUI/集成/工作流/资源回归和严格 mypy、Ruff/格式通过。这不是 Windows/真实照片承诺。直接开始成本、缓存首轮成本和重复检查收益单列，不把两条路径混为一个提速百分比。原始数据在 `build/performance/implementation/i4a-paired.json`。成片源状态绑定的最终加强由失败注入回归确认，最终累计测量继续覆盖完整实现。
