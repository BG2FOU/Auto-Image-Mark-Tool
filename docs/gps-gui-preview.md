# GPS 图形预览版（0.2.0rc1）

本版本先提供坐标写入图形页面。水印按钮是后续模块的入口，占位期间不可点击。当前页面只放行 JPG/JPEG 的坐标写入；NEF 虽可导入，但在独立 Nikon 查看器确认副本前，批次预检会明确阻止它。

## 使用

1. 点击“添加照片”或“添加文件夹”。勾选要处理的 JPG/JPEG。
2. 在表格中逐行填写 WGS84 十进制度的纬度、经度；也可在下方填写一组坐标，点击“应用到勾选照片”。负数与零均可用。
3. 选择与原片目录不同的输出目录，点击“检查批次”。检查不写文件；路径冲突、无效坐标或不允许的 NEF 会阻止整批运行。
4. 点击“开始写入副本”。状态列、进度条和底部日志显示每张照片的结果。输出保持输入文件名和扩展名；原片不会改写。点击“取消”会在当前文件步骤结束后停止后续照片。

JPG/JPEG 写入只改变元数据，不重新编码照片像素。坐标使用 WGS84；页面不提供 GCJ-02 或 BD-09 转换。输出目录已有同名文件时预检会报冲突，不覆盖它。

## 本地构建与验证

Linux：`python scripts/build_gps_gui_deb.py`，生成 `dist/auto-image-mark-gps-gui_0.2.0~rc1_amd64.deb`。安装后从应用菜单启动，或运行 `auto-image-mark-gps-gui`。DEB 声明 Qt 运行所需系统库。Windows：在已安装固定依赖并运行 `scripts/fetch_tools.py` 的 Windows x64 环境执行 `scripts/build_gps_gui.ps1`；先生成 onedir 并自测，再生成 onefile EXE 并自测。GitHub Actions 的 `GPS GUI preview native Windows build` 手动工作流使用相同步骤。

冻结程序可用 `--self-test --report <JSON 路径>` 离线检查窗口启动、ExifTool、合成 JPEG 的 GPS 回读、原片字节和像素。此自测不代替 Nikon NEF 查看器确认，也不代替 Windows 实际点击操作。公开构建不包含用户照片、商业字体或签名素材；许可证与组件信息见包内声明。项目原有 CC BY-SA 4.0 许可证保留。
