# 本地 GPS 批量原型

本阶段先实现坐标写入及 PyInstaller 原型包。它是命令行程序，仅处理 JPG/JPEG；没有水印界面，也不代表 `docs/plan.md` 的正式 S9 发布验收。NEF 批量输出仍需独立 Nikon 查看器抽验后放行。

CSV 使用 UTF-8，首行必须包含 `file_name,latitude,longitude`。`file_name` 是相对输入目录的准确路径，坐标是 WGS84 有符号十进制度。负纬度为南、负经度为西。示例：

```csv
file_name,latitude,longitude
中文目录/DSC_0001.jpg,24.478123,118.085456
DSC_0002.jpeg,-24.123456,-118.987654
```

Linux 开发版预检与执行：

```sh
.venv/bin/python scripts/batch_gps.py --csv rows.csv --input-root /path/to/input --output-root /path/to/output
.venv/bin/python scripts/batch_gps.py --csv rows.csv --input-root /path/to/input --output-root /path/to/output --execute --report /path/to/output/report.json
```

Windows 构建需在 Windows x64、已按 `docs/plan.md` 锁定安装 `.venv`、已运行 `scripts/fetch_tools.py` 后执行：

```powershell
.\scripts\build_gps.ps1
```

脚本先生成目录包，再生成单文件 EXE，并对各自运行两张合成 JPEG 的写回冒烟测试。目录包位于 `dist/AutoImageMarkGps/`，单文件位于 `dist/gps-onefile/AutoImageMarkGps.exe`。在 Linux 上运行相同 spec 生成的是 Linux ELF，不是 Windows EXE。

运行 Windows 原型：

```powershell
.\dist\gps-onefile\AutoImageMarkGps.exe --csv rows.csv --input-root C:\Photos\input --output-root C:\Photos\output
.\dist\gps-onefile\AutoImageMarkGps.exe --csv rows.csv --input-root C:\Photos\input --output-root C:\Photos\output --execute
```

默认只预检。`--execute` 才写入独立输出目录，保持相对路径与同名格式；已有目标和重复行会在整批开跑前拒绝。旧 GPS 高度、时间等附属字段会触发预检失败；确认替换拍摄点后可加 `--clear-auxiliary-gps` 清除旧附属信息。原片始终不写入，输出报告默认不含坐标，但文件名和路径仍可能敏感，应只留本地。用户照片、字体、签名均不进入构建包或 GitHub。

## GPS 预览版安装包

`v0.1.0-gps.1` 是命令行预览版，仅处理 JPG/JPEG 坐标写入；它不是计划中的完整 GUI/S9/S10 正式版本。Windows x64 下载 `AutoImageMarkGps-v0.1.0-gps.1-windows-x64.exe`，Linux Ubuntu 24.04 amd64 下载 `auto-image-mark-gps_0.1.0~gps.1_amd64.deb`。两者都离线运行并附带 ExifTool 13.59，不包含照片、签名或字体。EXE 未签名。

Linux 安装后命令为 `auto-image-mark-gps`，参数与上述 Windows 命令相同。DEB 构建命令为 `.venv/bin/python scripts/build_gps_deb.py`；脚本会先构建 PyInstaller 目录包并用两张合成 JPEG 冒烟，再生成 DEB。公开版本的 Windows EXE 必须由 `.github/workflows/gps-preview-build.yml` 在原生 Windows runner 上构建并通过相同冒烟，不能以 Wine 单文件失败的本地产物替代。

下载后先对照 Release 附带的 `SHA256SUMS.txt` 核验，再在自己的本地目录预检。首次执行不要加 `--execute`；确认清单与输出目录后再加该参数。NEF 坐标写入和任何格式的水印均未进入此预览版。
