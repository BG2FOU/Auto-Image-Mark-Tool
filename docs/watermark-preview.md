# S5 本地水印预览

这是 JPEG 单张渲染预览，用于检查三类模板和可配置布局。原片、字体和签名只在本地读取；输出应放在 Git 忽略的 `demo-output/`，不提交到 GitHub。NEF 显影和完整 EXIF/GPS 传递属于后续流水线阶段。

从仓库根目录运行：

```bash
.venv/bin/python scripts/preview_watermark.py data/DSC_0168.jpg \
  --category aviation --content LX-VCF --date 2026-09-13 \
  --output demo-output/s5-review-2026-10-02/aviation.jpg
```

日期应由用户或已核对的拍摄日期提供；本例的 `2026-09-13` 来自样片 EXIF。`--category` 可选 `aviation`、`railway`、`landscape`，分隔符固定为半角 `|`。默认配置为 36 pt、300 ppi 基准、签名宽 300 px、整体右下可见边距 25 px，三段透明度均为 0.5。

可使用 `--latin-font`、`--chinese-font`、`--signature` 和对应的 `--latin-face`、`--chinese-face` 选择本地资源；`--font-size-pt`、`--signature-width`、`--margin-x`、`--margin-y`、`--anchor`、`--offset-x`、`--offset-y`、`--signature-offset-y`、`--color '#RRGGBB'`、`--latin-opacity`、`--chinese-opacity`、`--signature-opacity` 调整外观。四角锚点分别为 `top_left`、`top_right`、`bottom_left`、`bottom_right`。找不到字体、缺字、签名全透明或布局越界会报错，不自动替换资源或缩小文字。

输出始终是新 JPEG，已有目标拒绝覆盖；源片哈希在保存前后校验。预览按 EXIF Orientation 旋转一次，有嵌入 ICC 时转换到 sRGB 并写入匹配 ICC；无 ICC 的 RGB 会提示 sRGB 假设，无 ICC 的 CMYK 拒绝。保留原 DPI，导出 Orientation=1。当前预览**不保留全部拍摄 EXIF/GPS**，不能作为正式成片使用。

本地已重新生成航空、铁路和风光三类 6016×4016 预览，路径为 `demo-output/s5-review-2026-10-02/`。公开 Python wheel 只包含默认模板 JSON，不包含字体、签名或照片。按相同文字与日期对比，提供的参考成片水印视觉位置比新预览更高、更靠左；已确认的 36 pt、签名 300 px 与底部可见边距 25 px 继续作为实现值。签名组内垂直位置可用 `--signature-offset-y` 微调；默认可见底部对齐及三类预览已于 2026-10-02 获用户确认。
