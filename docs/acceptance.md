# 验收记录：GPS-only JPG 原型

本记录对应首次 GPS-only 原型提交。完整阶段计划见 `docs/plan.md`。此原型只处理 JPG/JPEG 批量坐标写入；NEF 写入仍需独立 Nikon 查看器验收，水印与完整 GUI 不在本次提交范围。

## 已验证

- 原片、字体、签名均保持本地；`data/` 中六份已登记素材的 SHA-256 见 `tests/fixtures/manifest.json`，原文件不纳入 Git 或构建包。
- Linux Python 3.12 锁定依赖安装、`pip check`、Ruff、mypy、单元与 GUI 启动测试通过。
- ExifTool 13.59 已按固定版本与校验值取得；Linux 原生命令和 Windows 包在 Wine 中返回正确版本。原生 Windows 验证仍待完成。
- 合成与 Nikon Z 5 JPG 的 GPS 写入在副本上完成，四个 GPS 字段读回误差不超过 `1e-6` 度；原片 SHA-256 与 JPEG 解码像素保持不变。两图 CSV 批量、中文路径、重复行、已有目标和旧附属 GPS 预检通过。
- PyInstaller Windows 目录版 PE64 EXE 已在 Wine 中完成两图坐标写入与独立读回；单文件 EXE 已构建，但 Wine 报父进程安全校验错误，尚未在原生 Windows 验收。
- 本次提交不包含 NEF 批量输出、水印模块、私有照片、字体或签名；Windows 单文件与正式发布仍需额外门禁。

## 计划偏差

用户要求先集中实现坐标写入、先用 PyInstaller 编译 EXE，再做水印。因此 GPS-only EXE 原型早于计划的正式 S9 阶段；它不代表 S3、S9 或 S10 正式验收完成。许可证保留现有 CC BY-SA 4.0。用户随后授权先提交 JPG-only 坐标原型，并要求后续第一步 GPS EXIF 支持 JPG 和 NEF、第二步图像水印处理暂只支持 JPG。
