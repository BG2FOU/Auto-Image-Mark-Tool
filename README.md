# Auto-Image-Mark-Tool

本地照片坐标与 JPG/JPEG 版权水印批处理工具。使用 PySide6 图形页面，先预检、再写入输出副本，不覆盖原片或已有成品。许可证保留 **CC BY-NC-SA 4.0**，`©BG2FOU`。

## 下载

JPG 水印与 NEF 坐标图形正式版 [v0.5.1](https://github.com/BG2FOU/Auto-Image-Mark-Tool/releases/tag/v0.5.1)：

- [Windows x64 单文件 EXE](https://github.com/BG2FOU/Auto-Image-Mark-Tool/releases/download/v0.5.1/AutoImageMarkTool-v0.5.1-windows-x64.exe)
- [Windows x64 目录 ZIP](https://github.com/BG2FOU/Auto-Image-Mark-Tool/releases/download/v0.5.1/AutoImageMarkTool-v0.5.1-windows-x64.zip)
- [Ubuntu 24.04 / Linux amd64 DEB](https://github.com/BG2FOU/Auto-Image-Mark-Tool/releases/download/v0.5.1/auto-image-mark-tool_0.5.1_amd64.deb)

Windows 双击 EXE，或解压 ZIP 后运行其中的 EXE；Linux 用 `sudo apt install ./auto-image-mark-tool_0.5.1_amd64.deb` 安装，再启动 `auto-image-mark-tool`。使用 Release 附带的 SHA256SUMS.txt 校验下载；完整许可与构建来源随附件提供。无需另装 Python 或 ExifTool，水印字体和签名由用户在本地选择。

默认使用快速检查，也可选择完整检查；快速检查将完整图像/NEF 校验放到逐张实际处理，减少批次开始前的等待，坏图可能在处理到该张时才报告。用户已于 2026-10-28 确认候选 EXE 测试通过。EXE 未做 Windows 代码签名；正式构建和公开下载的独立核验结果见 [验收记录](docs/acceptance.md)。

## 当前功能

| 流程 | 输入 | 输出 |
| --- | --- | --- |
| 坐标 | JPG / JPEG / Nikon NEF | 原文件名及扩展名，副本写入，不重编码或显影 |
| 水印 | JPG / JPEG | `_marked.jpg`，保留像素尺寸和拍摄信息 |
| 坐标＋水印 | JPG / JPEG | `_marked.jpg`，保留本次写入的新 GPS |

- 启动后默认仅启用“写入坐标”；NEF 卫星数缺省 00，GPS 日期/时间来自 EXIF 拍摄时间。
- 海拔写入默认 0，坐标列表支持维护高度；小工具支持离线批量 GCJ-02 ↔ WGS84 与转换结果追加列表。
- 坐标列表支持维护、搜索、导入/导出和备份恢复；Windows 便携 EXE 的 `locations.json` 与 EXE 同目录。
- 航空、铁路、风光三类水印；字号使用 pt，文字、签名、间距和边距按实际画幅一起缩放，与照片 DPI 无关。
- 逐行编辑、勾选批量应用、CSV/TSV/XLSX 与剪贴板导入预览。
- 照片默认按拍摄时间从早到晚排序，缺失或无效时间排末尾；支持全选/全不选与 Ctrl/Shift 多行选中后统一勾选/取消勾选。全选覆盖搜索隐藏的照片。
- 后台预检、异步预览、原像素水印局部、拖动位置、取消、失败项重试和结果报告。
- 字体和透明签名在本机选择，支持保存个人默认及恢复项目默认。
- “附加频域水印”：水印栏可选 DCT/FFT 与低、中、高档，默认 DCT 中档，可单独关闭；保存后的 JPG 完整提取核验通过才提交成片。正式版本已包含，详见 [频域水印说明](docs/user-guide.md)。

**NEF 坐标写入取消固定相机型号、位深和尺寸白名单，按每张 Nikon NEF 的容器、RAW/预览哈希、元数据与 GPS 读回结果检查，输出同名 NEF 副本。显影及水印暂缓。** 支持范围和未实测边界见 [NEF 兼容说明](docs/nef-gps-compatibility.md)。 字体、签名、照片及真实坐标只留在本地，不提交或捆绑到公开构建物。

## 运行与测试

使用 Python **3.12.3 x64** 和已锁定依赖；按 [完整 JPG 构建说明](docs/build-release.md) 准备 ExifTool **13.59**。

```bash
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m aim_tool
```

`python -m aim_tool --gps-only` 保留独立坐标预览页面。主页面操作见 [用户手册](docs/user-guide.md)。旧 GPS 预发布 `v0.2.0-rc.2` 与 JPG 版 `v0.3.0-rc.1` 保留；新版请使用上面的 `v0.5.1`。旧 `--gps-only` 预览仍保留原验收门禁，NEF 请使用主页面的“坐标”流程。

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests/unit tests/integration tests/gui -m 'not raw' -q
python -m ruff check src tests scripts packaging
python -m ruff format --check src tests scripts packaging
python -m mypy src/aim_tool
```

上述 `QT_QPA_PLATFORM` 为 Linux 无显示器检查用；Windows 使用 `set QT_QPA_PLATFORM=offscreen` 或对应 PowerShell 环境变量语法。真实字体/样片保持私有，普通测试在缺失时跳过；本地验收加 `--require-real-assets`，不得把跳过记作通过。

项目：[BG2FOU/Auto-Image-Mark-Tool](https://github.com/BG2FOU/Auto-Image-Mark-Tool)。
