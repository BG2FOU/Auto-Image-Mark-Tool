# Auto-Image-Mark-Tool

本地 JPG/JPEG 坐标与版权水印批处理工具。使用 PySide6 图形页面，先预检、再写入输出副本，不覆盖原片或已有成品。许可证保留 **CC BY-SA 4.0**，`©BG2FOU`。

## 当前源码功能

| 流程 | 输入 | 输出 |
| --- | --- | --- |
| 坐标 | JPG / JPEG | 原文件名及扩展名，图像像素不重编码 |
| 水印 | JPG / JPEG | `_marked.jpg`，保留像素尺寸和拍摄信息 |
| 坐标＋水印 | JPG / JPEG | `_marked.jpg`，保留本次写入的新 GPS |

- 坐标列表支持维护、搜索、导入/导出和备份恢复；Windows 便携 EXE 的 `locations.json` 与 EXE 同目录。
- 航空、铁路、风光三类水印；字号使用 pt，文字、签名、间距和边距按实际画幅一起缩放，与照片 DPI 无关。
- 逐行编辑、勾选批量应用、CSV/TSV/XLSX 与剪贴板导入预览。
- 后台预检、异步预览、原像素水印局部、拖动位置、取消、失败项重试和结果报告。
- 字体和透明签名在本机选择，支持保存个人默认及恢复项目默认。

**NEF 坐标、显影和水印列入后续版本，当前页面只导入 JPG/JPEG。** 字体、签名、照片及真实坐标只留在本地，不提交或捆绑到公开构建物。

## 运行与测试

使用 Python **3.12.3 x64** 和已锁定依赖；按 [构建说明](docs/gps-gui-preview.md) 准备 ExifTool **13.59**。

```bash
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m aim_tool
```

`python -m aim_tool --gps-only` 保留独立坐标预览页面。主页面操作见 [用户手册](docs/user-guide.md)。公开 GPS 预发布 `v0.2.0-rc.2` 不含新水印页面；完整 JPG 构建与发布进度见 [验收记录](docs/acceptance.md)。

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests/unit tests/integration tests/gui -m 'not raw' -q
python -m ruff check src tests scripts packaging
python -m ruff format --check src tests scripts packaging
python -m mypy src/aim_tool
```

上述 `QT_QPA_PLATFORM` 为 Linux 无显示器检查用；Windows 使用 `set QT_QPA_PLATFORM=offscreen` 或对应 PowerShell 环境变量语法。真实字体/样片保持私有，普通测试在缺失时跳过；本地验收加 `--require-real-assets`，不得把跳过记作通过。

项目：[BG2FOU/Auto-Image-Mark-Tool](https://github.com/BG2FOU/Auto-Image-Mark-Tool)。
