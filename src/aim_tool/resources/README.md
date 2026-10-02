# 水印项目默认资源

`default_templates.json` 保存三类模板可恢复的公开参数和逻辑资源 ID。它不包含字体、签名或用户照片，也不写开发机绝对路径。所有拉丁文字、数字、半角分隔符 `|` 和 `©` 使用 `latin_bold`；风光汉字使用 `chinese`。

本地开发版本将 ID 映射到仓库根目录下的三份用户文件；公开构建不捆绑它们。用户替换字体或签名时使用所选本地路径和 face，并重新校验字形、尺寸及指纹。项目默认资源的已登记指纹：

| 资源 ID | 本地文件 | SHA-256 |
| --- | --- | --- |
| `project:trajan-pro-bold` | `data/TrajanPro-Bold.otf` | `60c3185c2919d8fdae1ccc5c334c548071dd31700121825c803c2903369dbed5` |
| `project:fangzheng-shengshi-kaishu` | `data/FangZhengShengShiKaiShuJianTi-Da.ttf` | `e654df886e997e9847744583fa5a1ad78930bfde72c358500e4ed4518f49bc76` |
| `project:name-signature` | `data/NAME.png` | `d86e885e86c0977a2d874aacb16671be11f3bde55fdb23139f6e4aadcf330777` |

默认 Photoshop 字号为 36 pt，在 300 ppi 基准下是 150 px。签名有效宽 300 px、保持原 759:459 比例，原 RGB 和 Alpha 保留并仅乘一次 0.50；组合可见右/下边距为 25 px。签名组内垂直位置目前默认可见底部对齐，可由 `signature_offset_y` 调整，最终视觉对齐尚待确认。
