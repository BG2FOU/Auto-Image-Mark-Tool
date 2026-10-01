# Auto-Image-Mark-Tool 实施计划与编码 Agent 交接说明

> 分析日期：2026-10-01。基线提交：`44fda21`（`chore: mark example`）。
> 本阶段只分析仓库并维护本计划，不编写业务代码、不安装依赖、不构建、不发布应用。用户已明确授权计划完成后进行一次文档提交与推送；本次仅纳入 `docs/plan.md`，不修改或提交字体、签名原文件。后续所有提交遵守第 1.6 节规范。
> 本文区分“已核实事实”“推荐设计”“待确认决策”。后续 Agent 不得把推荐默认值当作用户已经确认的要求。

> 实施状态更新（2026-10-01）：用户已确认 Photoshop 字号为 36 pt、保留 CC BY-SA 4.0、NEF 加水印导出 JPEG；字体、签名及照片仅供本地使用，不提交到 GitHub 或公开构建物。已在 `data/` 放入 Nikon Z 5 的 JPG/NEF 原片及已处理 JPEG 参考，指纹见 `tests/fixtures/manifest.json`。本段覆盖下文 Q1、Q5、Q6、Q8、Q18 的旧待确认状态；Q4 等未确认项仍按各节边界处理。阶段进度见 `docs/acceptance.md`。

## 1. 当前仓库及事实依据

### 1.1 当前结构

初次分析基线只有 6 个受 Git 跟踪的文件。本次文档提交前工作区另有用户提供的 3 个签名/字体资源和本计划 `docs/plan.md`，提交前检查时这 4 个文件均未跟踪；本次只提交计划。尚无应用源码、依赖清单、测试、构建脚本或 GitHub Actions：

```text
.gitattributes
.gitignore
LICENSE
README.md
data/FangZhengShengShiKaiShuJianTi-Da.ttf
data/NAME.png
data/TrajanPro-Bold.otf
data/example/EMU.png
data/example/VIEW.png
docs/plan.md
```

| 现有文件 | 当前内容及实施影响 |
| --- | --- |
| `README.md` | 只有项目标题及一句英文介绍，不能据此推断已有框架或运行入口。 |
| `LICENSE` | Creative Commons Attribution-ShareAlike 4.0 International（CC BY-SA 4.0）全文；不是 MIT 许可证。未经所有者确认，不得替换。 |
| `.gitignore` | Python 模板；已忽略虚拟环境、缓存、`build/`、`dist/`，也忽略 `*.spec` 和 `*.manifest`，会影响拟新增的 PyInstaller 配置。模板不代表仓库已有 Python 实现。 |
| `.gitattributes` | 仅 `* text=auto`；后续明确源码和脚本文本换行、图像二进制属性。 |
| `data/example/EMU.png` | 铁路水印参考，不是可编辑文字源文件，也不是完整照片。 |
| `data/example/VIEW.png` | 风光水印参考，不是可编辑文字源文件，也不是完整照片。 |
| `data/NAME.png` | 用户已提供的独立透明签名源图；本项目默认签名输入，不再需要从示例裁出签名。保持原文件不变。 |
| `data/TrajanPro-Bold.otf` | 已核实为 Trajan Pro / Bold；按用户最新确认，三类模板全部英文、数字及拉丁符号统一使用该字体，航空也不再需要 Regular。 |
| `data/FangZhengShengShiKaiShuJianTi-Da.ttf` | 已核实为方正盛世楷书简体_大，供风光汉字使用；其内部 style 为 Regular，不应再人为加粗。 |
| `docs/plan.md` | 当前交接计划，尚未实施业务代码。 |

初次分析起始工作区干净；素材补充分析时工作区已有上述未跟踪文件，不得删除或覆盖用户素材。在检查的上级目录和当前仓库未发现适用的 `AGENTS.md`。Git `origin` 指向 `https://github.com/BG2FOU/Auto-Image-Mark-Tool.git`，应用仓库链接应为 `https://github.com/BG2FOU/Auto-Image-Mark-Tool`。

本机只核实到 Python 3.11.4 x64；没有在 PATH 中发现 `uv` 或 `exiftool`。未验证 GitHub 仓库设置、Actions 权限、标签保护或发布权限，不得把本地 remote 配置当作这些权限的证据。

### 1.2 示例图只读分析

两图均为 RGBA PNG，6016×4016 像素，分辨率约 299.9994 ppi；大部分画布透明。以下坐标以左上角为原点，包围盒右、下边界不包含在内：

| 指标 | `data/example/EMU.png` | `data/example/VIEW.png` |
| --- | --- | --- |
| 非透明区域包围盒 | `(3089, 3808, 5991, 3989)` | `(3063, 3806, 5991, 3989)` |
| 可见右边距 / 下边距 | 25 px / 27 px | 25 px / 27 px |
| 签名可见区域 | x=5691…5990，宽 300 px；高 181 px | 与铁路示例相同 |
| 主要实心文字颜色及 Alpha | 白色；Alpha=128，约 50% | 中文区域主要同样为白色、Alpha=128，约 50% |
| 可见内容 | `CR400BF-C-5162`、竖分隔符、`2026/01/01`、`©`、图形签名 | `哈尔滨工业大学主楼`、竖分隔符、同一日期和版权签名 |

重要差异与限制：

- **原需求中文为 30%，示例约为 50%；用户已追加确认采用中文不透明度 50%**。后续以最新确认的 50% 实施，保留示例原件。
- **需求底边距 25 px，示例可见 Alpha 边距 27 px；用户已追加确认底部可见边距 25 px**。最终按组合可见边界定位，不照抄示例的 27 px，也不改写示例。
- 示例文字可见高度约百余像素；“字号 36”更像 Photoshop 的 36 pt，而不是 36 px。推荐基准转换 `36 × 300 / 72 = 150 px`，但 PNG 不能证明原始字体单位或字体文件，须用用户字体/PSD 校准。
- `Ⅰ` 是 U+2160（罗马数字一），不是 ASCII `|`（U+007C）。PNG 无法证明原图字符；用户已明确将应用分隔符改为半角 `|`（U+007C），不再使用 `Ⅰ`。
- 透明像素保留了不同 RGB 值；部分查看器显示的黑块不能当成真实底色。水印默认不添加黑色背景、描边或阴影。
- 独立签名及两款字体已提供，见第 1.4、1.5 节，已覆盖最新确认的默认字体需求；PSD、JPG/NEF 原片尚未提供。不能直接从示例裁切一条完整水印作为动态渲染实现，也不能据此宣称 NEF 或 Photoshop 一致性已验收。

### 1.3 用户追加确认与执行约束

- **已确认视觉参数**：中文不透明度为 50%；标准画布上的底部可见边距为 25 px。此前中文 30% 规则已被覆盖，不再作为待确认事项。
- **已提供签名素材**：`data/NAME.png` 用作本项目三类模板的默认签名源，保留更换自定义签名的入口；对外分发许可与是否内置到公开 EXE 单独确认，不再要求用户重复提供源图。
- **已确认默认字体**：所有英文、数字及拉丁符号（包括航空模板）统一使用 `data/TrajanPro-Bold.otf`；风光中文默认使用 `data/FangZhengShengShiKaiShuJianTi-Da.ttf`。不再需要 Trajan Pro Regular，也不再以缺 Regular 阻止航空处理。
- **已确认分隔符**：全部模板使用受支持的半角 `|`（U+007C），不是 `Ⅰ` 或字母 `I`；默认两侧不加空格，版权符号两侧的半角空格规则不变。
- **已确认可定制能力**：字体和签名均可自行替换；字号、签名大小、水印位置均可调整并保存。用户本地首次使用/恢复默认采用本文给定资源和参数；“默认值”不是不可修改的硬编码。默认字号仍为 36，pt/px 的解释保留 Q1 校准；默认签名宽 300 px、右下可见边距 25 px、三类文字及签名不透明度 50%。
- **用量暂停规则**：执行本项目时，可靠数据表明剩余用量 **低于 5%**，必须暂停；暂停后只有可靠数据表明剩余用量 **大于 95%** 才可继续。恰好 5% 不触发“低于”条件，已暂停时恰好 95% 不满足恢复条件。
- 此处“用量”指用户账户/当前执行服务的剩余额度，不是上下文窗口、计划 token 预算或本地 CPU/磁盘占用。若平台同时有多个会阻止执行的额度窗口，按限制最严格的窗口判断；具体数据源由平台显示或用户提供。
- 本次可用工具未提供账户额度查询接口；后续 Agent 不得猜测或谎称已启用自动监控。具备可靠接口时在阶段开始及长任务前检查；没有接口时依赖用户提供状态，未知不等于低于阈值，也不能作为已暂停后的恢复凭据。
- 触发暂停后不启动新步骤/子进程/发布；对正在写文件的任务只完成必要的安全收尾或取消，记录进度、未完成项和临时文件状态，再等待额度恢复证明。安全收尾不能变成继续推进实现的借口。
- 无后台常驻/额度通知能力时，无法保证自动等待并自动唤醒；额度恢复后由用户通知或下一次可靠查询确认，再从记录的阶段继续。不为此修改全局设置或持久记忆。

### 1.4 独立签名 `data/NAME.png` 只读分析

| 指标 | 已核实结果 |
| --- | --- |
| 格式 / 模式 | PNG / RGBA |
| 文件大小 | 41,587 字节 |
| 像素尺寸 / DPI | 759×459 px / 约 72.009 ppi |
| Alpha 范围 | 0…255；存在完全不透明笔画和半透明抗锯齿像素，不是预先整体降为 50% 的签名 |
| 非透明包围盒 | `(0, 0, 759, 459)`，覆盖整个画布范围；四个角像素本身透明，没有可整体裁掉的外圈留白 |
| 可见颜色 | 以白色为主，包含灰阶边缘；必须保留原 RGB 与 Alpha，不将所有非透明像素强制改成纯白 |
| 300 px 宽对应高度 | `459 × 300 / 759 ≈ 181.423 px`，最终约 181 px；与示例签名 300×181 px 的尺度相符，不代表逐像素一致 |
| SHA-256 | `d86e885e86c0977a2d874aacb16671be11f3bde55fdb23139f6e4aadcf330777` |

后续处理契约：从该源图在内存中加载，按目标有效宽度保持比例缩放，保留抗锯齿并只应用一次 0.50 不透明度；不根据 72 ppi 标签放大到 300 ppi，不重存/重采样源文件，不从参考图反向提取签名，不自动归一化灰阶或 Alpha。预览必须支持深色/棋盘底，避免白色签名在白底上看似空白。源图指纹变化时提示重新验收，不静默沿用旧缓存/基线。

开发运行通过资源加载器解析该仓库资源，不依赖进程当前工作目录。公开 EXE 是否默认内置仍需确认：若允许，由 PyInstaller 从 `data/NAME.png` 映射至包内逻辑路径 `aim_tool/resources/signatures/NAME.png`，无需在源码树复制第二份；若不允许，发行包不包含它，首次使用水印时由用户本地选择。无论哪种发行策略，GPS-only 不受签名是否可用影响。

### 1.5 已提供字体的内部信息与覆盖情况

通过字体 name、OS/2 与 cmap 表只读核实，不依赖文件名推断：

| 文件 | 内部字体名称 / 字重 | 文件大小 / SHA-256 |
| --- | --- | --- |
| `data/TrajanPro-Bold.otf` | family `Trajan Pro`；style `Bold`；PostScript `TrajanPro-Bold`；weight=700 | 65,848 字节；`60c3185c2919d8fdae1ccc5c334c548071dd31700121825c803c2903369dbed5` |
| `data/FangZhengShengShiKaiShuJianTi-Da.ttf` | `方正盛世楷书简体_大` / `FZShengShiKaiShuS-EB-GB`；style `Regular`；PostScript `FZSHENGSKS_DAJW--GB1-0`；weight=400 | 5,432,564 字节；`e654df886e997e9847744583fa5a1ad78930bfde72c358500e4ed4518f49bc76` |

- Trajan Pro Bold 包含需求用到的 ASCII 大写字母、数字、连字符、斜线、空格、`|` 及 `©`；**不包含 `Ⅰ`（U+2160）**。用户已选择受支持的 `|`，因此默认模板不再有该缺字阻塞；仍禁止缺字时静默跨字体回退或输出方框。
- 方正字体覆盖风光示例 `哈齐客专松花江特大桥日落` 和 `哈尔滨工业大学主楼` 所有汉字，也包含 `Ⅰ`；但不含 `©`。日期、分隔符、版权符号仍按需求使用 Trajan 角色，不因方正有某字形就跨角色回退。
- 两个文件的 OS/2 `fsType` 实测均为 8；仅记录元数据，不以该标记推断已获得公开仓库或 EXE 再分发授权。
- 用户最新要求三类模板全部英文/数字统一使用现有 Bold，航空和铁路/风光一起验证；不再要求补齐 Regular。
- 用户输入的其他汉字仍要逐字检查 cmap，不能把两条示例覆盖当成覆盖所有中文。已有资源均保持原字节不变，不做字体转换、子集化、伪加粗或改名。
- 开发默认字体路径按上述映射自动解析，并允许用户覆盖；不得要求重复选择已可读取的项目资源。公开发布默认不捆绑字体，只有确认许可及分发方案后才由构建配置精确列入，不扫描整个 `data/`。

### 1.6 Git 提交与推送规范（本次及后续必须遵守）

用户要求遵守其提供的 Husky 风格提交规范：`subject: message 主体`，冒号必须为 ASCII `:`，其后一个半角空格，主体使用简洁准确的描述，不为空。

| subject | 用途 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `docs` | 仅文档变更 |
| `style` | 不影响逻辑的格式/代码风格调整 |
| `refactor` | 非新功能、非 bug 修复的重构 |
| `perf` | 性能优化 |
| `test` | 添加或修改测试 |
| `chore` | 辅助工具或其他杂项 |
| `build` | 构建系统或依赖变更 |
| `ci` | 持续集成配置变更 |
| `revert` | 回滚提交 |

- 校验首行符合 `^(feat|fix|docs|style|refactor|perf|test|chore|build|ci|revert): [^\s].*$`，拒绝全角冒号、空主体或不在清单内的前缀；示例 `docs: 完善照片水印工具实施计划`。
- 本次计划完成后，检查文档、仅暂存 `docs/plan.md`，用上述 `docs:` 消息提交，正常推送当前 `main` 到 `origin/main`；不把未跟踪字体/签名顺手纳入，不发布标签或 Release。
- 每次提交前核对 `git status --short`、`git diff --cached --name-status` 和 `git diff --cached --check`，只提交本任务已确认范围。不得用 `git add .` 混入用户文件。
- 每次推送前检查待推送提交的首行格式和内容范围；首次采用本规范不要求重写此前历史。若远端先行更新或发生非快进拒绝，先检查差异，不强推、不自动重写用户提交。
- 推送后核实远端分支 SHA 与本地已提交 SHA 一致，分别报告“提交完成”和“推送完成”；本地提交成功不能代替远端验证。
- 当前仓库未发现 Husky 配置或 Node 工程；“遵守消息规范”不等于“已安装 hook”。本阶段只按规则校验，不为此引入 Node/Husky、修改 hooks 或绕过已有 hook。后续若需要自动强制校验，应另行规划 commit-msg hook/CI 检查，并保持同一规则。
- 后续所有提交/推送均遵守该格式约束；该约束不授予无限制提交、推送或发布权限，本次授权仅为计划完成后的这一次文档提交与推送。

## 2. 目标、范围及推荐技术路线

### 2.1 首版目标

制作本地离线 Windows 图形应用，以可组合的工作流卡片处理照片：

`导入照片 → 读取元数据/填写表格 → [位置写入] → [RAW 显影（需要时）] → [版权水印] → 导出及结果报告`

方括号步骤可配置或按输入类型启用；GPS-only 不应依赖字体、签名或 RAW 显影库是否可用。首版提供位置-only、水印-only、位置+水印三个预设。位置与水印都启用时，逻辑顺序必须是位置在前、水印在后；禁止非法拖动顺序。

首版不做任意节点图编辑器、不执行用户脚本、不安装远程插件，不内置联网地图/地理编码、不自动上传照片。扩展通过受代码审查的内置组件注册完成。

### 2.2 推荐技术选型

| 层次 | 推荐方案 | 理由与边界 |
| --- | --- | --- |
| 运行时 | Python 3.12 x64，Windows 10/11 x64 为候选支持范围 | 明确建立新项目，而非改造不存在的代码。S1 实测锁定可共存版本；本机现有 3.11 不等于已具备 3.12。最低 Windows 版本须随 Qt/依赖支持情况确认。 |
| GUI | PySide6 / Qt Widgets | 适合表格、停靠工具栏、拖放、工作流卡片及后台进度。GUI 和处理引擎分离。 |
| GPS/元数据 | 独立 ExifTool 子进程 | JPG/NEF 采用统一的元数据适配层，不让 Pillow 重写 NEF。GPS 必须同时处理坐标与方向字段，见 [ExifTool GPS 文档](https://github.com/exiftool/exiftool/blob/master/html/TagNames/GPS.html)。 |
| 栅格及字体 | Pillow + FreeType，`fontTools` 检查字体名称/字形 | 精确测量字符 advance、可见边界、Alpha 和签名尺寸；预览和导出共用同一渲染器。Pillow 字号使用像素，且 advance 与包围盒并非一回事，见 [ImageFont 文档](https://pillow.readthedocs.io/en/stable/reference/ImageFont.html)。 |
| NEF 显影 | rawpy / LibRaw，仅在 RAW 加水印时调用 | 完整 RAW 显影，不把嵌入式小预览当原片。rawpy 提供 RAW 数据和 postprocess，见 [RawPy 文档](https://letmaik.github.io/rawpy/api/rawpy.RawPy.html)。 |
| 表格 | 标准库 `csv` + `openpyxl` | 支持 CSV、TSV、剪贴板 TSV、XLSX，无需引入 pandas。旧 XLS 首版不支持并明确提示。 |
| 本地配置 | `platformdirs` + 带版本 JSON | 保存地点、模板、用户字体/签名路径；不写到 EXE 目录或 GitHub。 |
| 质量检查 | pytest、pytest-qt、pytest-cov、Ruff、mypy | 业务单测、真实元数据集成测试、GUI 测试分层。 |
| 打包 | PyInstaller，先 onedir，再 onefile EXE | Windows 构建 Windows 产物；先验证目录包利于排查 DLL/资源遗漏，再验证单文件，符合 [PyInstaller 部署说明](https://pyinstaller.org/en/stable/operating-mode.html)；另参考 [Qt for Python 打包文档](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html)。 |
| 发布 | GitHub Actions + GitHub CLI | `vX.Y.Z` 标签触发检查、构建、冒烟及 Release；普通分支不发布。 |

此方案是推荐，不宣称依赖已安装或原型已通过。S1 必须锁定 Python 包、构建工具及 ExifTool 版本/校验值，不使用不可复现的“latest”下载。

## 3. 数据与工作流设计契约

### 3.1 界面分区

- 左侧“工作流”：组件卡片、启用开关、参数入口、输入输出类型、校验错误；提供预设保存/载入。
- 地点停靠工具栏：搜索、新增、编辑、删除、导入/导出，字段为名称、纬度、经度、坐标系。选择地点后应用到勾选照片；一个照片只能有一个最终拍摄点，多选地点时必须显式逐行分配，不能平均或随机选择。
- 中部照片表格：勾选、缩略图、输入路径、类别、拍摄对象/编号、拍摄日期及来源、地点、纬度、经度、输出路径、状态、错误。
- 右侧预览：适应窗口、100% 局部、明/暗/棋盘背景、当前图/批量参数；设置改变仅更新预览，点击“开始”才写文件。
- 底部：输出目录、输出冲突提示、进度、取消、结果摘要、失败项重试、报告导出。
- 设置/关于：字体映射、签名图、模板、ExifTool 健康检查、版本、仓库链接、`©BG2FOU`、许可证和第三方声明。

### 3.2 领域模型

模型禁止依赖 GUI 对象；用类型化 dataclass/枚举及明确校验错误，不传递随意字典：

- `PhotoItem`：稳定 ID、规范化源路径、导入根目录、元数据快照、行级编辑、最终日期/坐标、工作流状态。
- `LocationPreset`：UUID、名称、纬度、经度、`WGS84`、schema 版本；名称不作为唯一主键。
- `WatermarkTemplate`：类别、精确分隔字符、字体角色、字号单位、基准尺寸、颜色、分段 Alpha、签名、缩放/位置/溢出策略。
- `WorkflowSpec` / `StepSpec`：schema 版本、组件 ID/版本、启用状态、参数；未知组件或过新配置报错，不执行任意 Python。
- `Artifact`：源文件、临时副本、栅格图、权威元数据、目标路径；明确哪个产物携带刚写入的 GPS。
- `BatchJob` / `ItemResult`：配置快照、计划输出、取消信号、当前步骤、成功/失败/取消状态、可读错误和警告。

组件契约至少包含 `id`、参数 schema、输入/输出类型、`validate`、`execute`、进度/取消接口。引擎在开始前完成整批计划与路径冲突检查；新组件只需实现接口、注册、增加参数界面和测试，不能往主窗口塞业务分支。

首版默认串行处理全尺寸图片、低并发读取元数据/缩略图。GUI 线程只处理界面；后台 worker 通过信号回传状态。不要同时常驻多张 6016×4016 RGBA 原图（单张像素缓冲约 92 MiB，显影/合成还会增加内存）。

### 3.3 坐标规则

- 输入十进制度：纬度 `[-90, 90]`、经度 `[-180, 180]`，接受负数和零；拒绝 NaN、Infinity、缺一项、误把逗号小数当两个坐标。不静默交换经纬度。
- EXIF 写 WGS84；地点编辑器明确标注坐标系。GCJ-02/BD-09 不能直接标成 WGS84；首版不自动转换，需由用户提供正确坐标。
- 优先级：明确的行级手动覆盖 > 为勾选行应用的地点 > 原 EXIF。只有被位置步骤明确选中的行才写入；无目标坐标且无原 GPS 的行显示“未配置”，由用户补齐或明确排除。
- 内部保存有符号坐标，ExifTool 显式写 `GPSLatitude`、`GPSLatitudeRef`、`GPSLongitude`、`GPSLongitudeRef`；零值采用固定 N/E 约定。写后读回有符号十进制度，误差目标 ≤ `1e-6` 度。
- 不伪造高度或 GPS 时间。若更换拍摄点而原片有旧高度/定位精度/时间等附属 GPS 字段，预检提示；默认清除不再可信的附属值并记录报告，或由用户明确保留，不能悄悄造成自相矛盾的 GPS 数据。
- 地点名称默认只保存为应用预设和作业配置；写 XMP/IPTC 名称属于待确认扩展，不把名称塞入非标准 EXIF 字段。

### 3.4 输出及原片保护

**默认永不原地修改照片。** 输出目录必须与源目录区分；对解析后的绝对路径、大小写、目录连接/符号链接做保护，不靠字符串前缀判断。

| 输入 / 工作流 | 推荐输出 | 关键约束 |
| --- | --- | --- |
| `DSC_1145.jpg` / 仅位置 | `<输出目录>/DSC_1145.jpg` | 文件名及扩展名大小写不变；只改元数据，不重新编码 JPEG 像素。 |
| `DSC_1145.NEF` / 仅位置 | `<输出目录>/DSC_1145.NEF` | 文件名和 RAW 格式不变；仅改副本元数据，RAW 像素及关键 MakerNotes 完整性要验证。 |
| `DSC_1145.jpg` / 水印或位置+水印 | `<输出目录>/DSC_1145_marked.jpg` | 水印导致 JPEG 重编码；GPS/拍摄日期/相机信息按策略保留。 |
| `DSC_1145.NEF` / 水印或位置+水印 | `<输出目录>/DSC_1145_marked.jpg` | 推荐导出显影 JPEG，不能生成伪 NEF。是否另保留已定位 NEF，见待确认事项。 |

- 多根目录同名文件：推荐保留导入根目录别名及相对目录；目标仍同名则预检阻止，要求选择分目录，不能悄悄加数字破坏命名规则。
- JPG+NEF 同名且均导出 JPEG 时同样检查冲突；由用户选处理对象或单独输出根目录。
- 已有目标文件默认跳过并报告冲突，不覆盖；若以后支持覆盖必须显式确认并建立备份。本期不实现源文件覆盖模式。
- 已带 `_marked` 的输入默认警告并排除，避免重复加水印；明确允许时如何再命名需确认，不默默产生 `_marked_marked`。
- 每张图片在目标卷专属临时目录生成，写入、读回校验成功后以不覆盖既有文件的提交方式移到目标。避免 `os.replace` 无条件覆盖在预检后新出现的文件。
- 元数据步骤作用于临时副本；ExifTool 的备份/覆盖参数只允许用于该副本，不允许用于源文件。清理仅针对本作业记录的临时文件。
- 某一步失败，当前图片后续步骤停止且不提交半成品；其他图片可继续。取消保留已完成结果、清理未完成临时文件；源文件 SHA-256 应始终不变。
- 引擎维持作业期间的源文件大小/时间戳或指纹，发现外部改动则停止该项。报告说明每个源文件、步骤、目标、警告和失败原因，不默认公开 GPS。

### 3.5 元数据、方向和颜色

- JPG GPS-only 全程使用 ExifTool；测试比较 JPEG 图像数据/解码像素一致，而不是要求整文件哈希一致。
- NEF GPS-only 要比较写前后的 RAW mosaic（如 rawpy 可读取）、尺寸、关键相机/MakerNotes、预览可读性，并用独立 Nikon 查看器或用户惯用软件抽验。某机型无法通过则阻止该格式写入，不以“ExifTool 支持 NEF”替代实测。
- 水印流程先规范化 EXIF Orientation，再测量最终宽高与布局；导出 Orientation=1，避免 EXIF 再转一次。RAW 显影器的旋转和应用旋转只能执行一次。
- 元数据使用明确白名单保留拍摄时间、必要相机/镜头/曝光、GPS、原有版权等；更新尺寸、Orientation、色彩信息，清理过时缩略图。不要在成品上无差别 `-all:all` 覆盖新方向、尺寸、ICC 或 GPS。
- 位置+水印时，最终元数据从“已定位副本/已更新元数据对象”传递，不得最后从原片重拷 GPS 将新坐标覆盖掉。
- 推荐水印输出统一转换 sRGB 并写入匹配 ICC；CMYK/Adobe RGB/带 ICC JPEG 必须走颜色转换，不能只贴一个 sRGB 标签。无 ICC 的假设应警告并记录。GPS-only 不做色彩转换。
- JPEG 推荐质量 95、4:4:4（可配置，待确认），保留原分辨率；不因为模板基准 300 ppi 而强制重采样。原 DPI 存在则保留，无 DPI 不凭空改照片像素。
- NEF 首版建议相机白平衡、固定曝光/亮度策略、sRGB 8-bit JPEG；和 Nikon/Adobe 的显影效果不保证相同，须用户确认样片。其他 RAW 仅在新增能力声明及真实测试后支持。

## 4. 水印精确规则

### 4.1 内容与字体

统一内容结构：`{内容}|{yyyy/mm/dd} © {签名图}`，分隔符固定使用已确认的半角 `|`。日期与 `©` 之间一个 ASCII 空格；`©` 与签名之间按当前拉丁字体一个 ASCII 空格的 advance 布局。默认分隔符两侧不自动补空格。

| 类别 | 内容校验 | 内容字体 | 日期、分隔符、© 字体 |
| --- | --- | --- | --- |
| 航空 | `[A-Z0-9-]+`，如 `B-1356`、`N766CK` | 已提供的 Trajan Pro Bold | 同左 |
| 铁路 | `[A-Z0-9-]+`，如 `CR400BF-C-5162`、`HXD3D-1886` | Trajan Pro Bold，已提供 `data/TrajanPro-Bold.otf` | 同左 |
| 风光 | 中文为主，如 `哈齐客专松花江特大桥日落` | 方正盛世楷书简体_大，已提供 `data/FangZhengShengShiKaiShuJianTi-Da.ttf` | 已提供的 Trajan Pro Bold |

表格编号按字符串处理，保留前导零；不得把机车号中的 `-` 当数学符号。小写/全角字符可提供“预览规范化”动作，但不能静默改用户原值。风光混排汉字/ASCII 是否允许见待确认事项；渲染器仍按字符角色分段，以免数字错误使用中文字体。

开发版本先解析第 1.5 节已有项目字体，拉丁角色统一默认为 Trajan Pro Bold；用户可覆盖为本机 TTF/OTF/TTC（TTC 需选择 face），记录资源 ID/文件路径、face、名称、文件哈希。用户明确选用其他字体属于受支持的定制，不被固定默认字体名称检查拒绝；仍需检查所选字形和可读性。不能根据屏幕上相似外观认定字体相同，不能用程序描边模拟 Bold，也不能静默回退系统字体。缺字、缺字体按类别和行预检，只阻止受影响的水印任务，GPS-only 仍可用；公开发行是否内置字体按 Q5，未内置时提供字体选择入口。

所有正式模板与测试期望统一使用 `|`（U+007C）；`Ⅰ` 仅作为缺字/旧配置校验用例，不再是默认渲染参数。配置迁移如遇旧分隔符，提示更新到已确认规则，不静默渲染替代字形。

### 4.2 Alpha、签名、布局及缩放

- 推荐默认白色，与示例一致；颜色可配置。以 Photoshop **不透明度** 表示：英文/数字/符号 0.50，中文 0.50，签名 0.50；其中中文 50% 为用户追加确认，覆盖原始 30% 要求。
- 每段使用独立 Alpha 蒙版；不能最后再给整个组合乘 0.5。默认签名使用已提供的 `data/NAME.png`：保留原 RGB、Alpha/抗锯齿，缩放后仅乘一次 0.50，不再预先降低透明度。示例中的签名已经约 50%，禁止裁出后再次衰减；更换的自定义签名是否已半透明应提示用户，不能自动把原有 Alpha 拉满。
- 签名按有效非透明包围盒裁掉透明留白，宽度基准 300 px，高度按原宽高比，不拉伸。当前 `data/NAME.png` 的有效边界就是完整 759×459 画布，基准输出约 300×181 px；其他签名仍需独立测量，不能硬编码所有签名高度为 181 px。缩放使用 Alpha 感知的高质量重采样，避免透明 RGB 引入色边；可见边界按实际渲染结果校验。
- 基准画布 6016×4016 / 300 ppi；推荐基准字号 36 pt = 150 px，不是直接传 Pillow `size=36`。单位可以配置，但出厂模板必须有明确单位。
- 基准右/下边距均为 25 px，定位对象是“文字+签名整体的非透明边界”；**底部可见边距 25 px 已由用户确认**。签名作为最右组件，整个组合整体右对齐；混排文字共享基线，签名推荐可见底部对齐，组内垂直细调待样片校准，不得改变整体底边距。
- 同宽高比缩放 `s = W / 6016 = H / 4016`。不同宽高比推荐适配基准方向：横图 `s=min(W/6016,H/4016)`，竖图 `s=min(W/4016,H/6016)`；所有字号、签名宽、间距和边距统一乘 s。这是待确认默认，不能只缩文字、不缩签名。
- 定位前测量字形实际边界及 advance；半角空格不是固定像素，不能把示例肉眼间距直接硬编码。内部保留浮点精度，最终统一取整，边距/宽度允许 ±1 px 栅格误差。
- **必须支持用户自定义**：替换拉丁/中文角色字体、替换签名图、调整字号、签名宽度（锁定比例）及水印位置（四角锚点、横纵数值偏移和预览拖动）；颜色、各段不透明度也提供参数。默认右下角，右/下可见边距 25 px；用户主动改位置后按其设置输出，不能在导出时又强制回到 25 px。
- 本地“恢复默认”恢复本文给定字体、签名、字号36、签名宽300及右下25等参数；“保存为我的默认”保存用户修改，两者入口明确区分。记录字号单位及基准画布尺寸，界面显示原图像素换算；预览和成品共用同一配置快照。换字体/签名立即重算布局，越界或缺字先提示；不依赖显示器 DPI/Qt 缩放。
- 内容过长默认预检报错，不截断、不自动换行。可提供用户明确勾选的“整组等比例缩小以适应”，签名/边距如何随二次缩放需在模板中记录；首版可先只实现报错。
- 预览生成最终坐标系的水印层再缩放展示；最终导出必须重新按原分辨率渲染，不放大低分辨率预览。

## 5. 表格、日期及本地持久化

### 5.1 导入表格约定

提供 `data/templates/watermark.csv`，推荐字段：`file_name,category,subject,capture_date,location_name,latitude,longitude`；在 UI 中支持中文表头映射（文件名/类别/内容/拍摄日期/地点/纬度/经度）。位置-only 不要求类别/内容字段。

- CSV：UTF-8/UTF-8 BOM 默认；GB18030 仅在用户选择后解析，不能用错误编码猜测覆盖内容。
- TSV / 剪贴板：按真正制表符分列、按记录分行，支持引号、空单元格和 CRLF；不按任意空格拆列。提供导入预览、列映射、逐行错误定位，再由用户确认应用。
- XLSX：读取首个或用户选择的工作表，处理真实日期单元格及 1900/1904 日期系统；拒绝执行宏、公式或外部链接。公式单元格要求用户粘贴值，不能把公式当日期运行。
- 文件匹配：默认精确相对路径；若只给文件名，必须在当前批次唯一。重复行、同名多图、未匹配项单独列错，绝不按排序位置猜测匹配。
- 无文件名的粘贴表格可支持“按已选择照片当前可见顺序”，但必须显示顺序/数量预览并由用户显式确认；筛选/排序变化后重新匹配。
- 多行编辑仅影响指定字段，空单元格默认“不覆盖”；“清空字段”使用显式操作。单张手输和批量导入都通过同一校验器。
- 不支持的类别、缺失内容、非法编号、部分经纬度、重复地点名均在开跑前解决或显式排除。

### 5.2 日期解析

默认优先级：行级手动日期 > 导入表格日期 > EXIF `DateTimeOriginal` > 用户明确同意的 `CreateDate` 回退。不默认使用文件创建/修改时间，更不能缺失时套用今天。

解析 ISO 日期/时间、`yyyy/mm/dd`、EXIF `yyyy:mm:dd HH:MM:SS`、XLSX datetime/date；先验证真实日历日期，再只输出日粒度 `yyyy/mm/dd`。带秒和小数秒只影响解析，不出现在水印中；带时区时默认保留拍摄地/原字段的日历日，不转换 UTC 后改变日期。`01/02/2026` 等有歧义格式要求选择规则，不盲目取前 10 个字符。

每行显示最终日期来源及原值。EXIF 缺失、无效日期或相互矛盾的日期显示警告；不猜日期。日期只用于水印，不自动改写原有拍摄时间 EXIF。

### 5.3 持久化与隐私

配置保存到 `platformdirs` 得到的用户应用数据目录，建议 Windows 为 `%LOCALAPPDATA%/Auto-Image-Mark-Tool/`，包含 `settings.json`、`locations.json`、`workflows.json`。这些是运行时路径，不是仓库文件。

JSON 带 `schema_version`，以临时文件+原子替换保存配置并保留最近有效备份；损坏时给恢复入口。照片行级输入默认只存在本次作业，显式保存项目才写入 JSON。地点、用户额外导入的私人签名和商用字体不得自动收集进源码、CI 缓存、Release 或遥测。用户明确提供在项目中的 `data/NAME.png` 是已知项目素材，并非禁止本地使用的私人配置；其公开分发仍按第 1.4 节和 Q18 确认。配置区分资源 ID 与外部文件路径，避免把开发机绝对路径写成默认模板。作业报告默认保存在输出目录，导出包含 GPS 的报告必须提示隐私。

## 6. 文件级实施清单

除特别标注的条件项外，下列都是**未来实施**。本次仅维护 `docs/plan.md`，只读检查用户新增的签名与两款字体。包名统一 `aim_tool`，使用 `src` 布局，禁止实施时另起一套目录后不更新计划。

### 6.1 根目录、文档及资源

| 操作 | 仓库相对路径 | 具体内容 |
| --- | --- | --- |
| 修改 | `README.md` | 中文功能说明、支持矩阵、安装/运行/构建/测试入口、原片保护和 NEF 导出说明、字体准备、仓库链接及 `©BG2FOU`。 |
| 修改 | `.gitignore` | 增加 `tools/`、本地照片/字体测试输入、报告等精确规则；为 `packaging/AutoImageMarkTool.spec` 添加白名单；保留锁文件跟踪。不要忽略所有 PNG/NEF 而掩盖合法测试素材。 |
| 修改 | `.gitattributes` | 为 `.py/.toml/.md/.yml/.json/.lock` 规范文本换行，为 `.ps1` 明确换行，为 PNG/JPG/NEF/字体标记 binary。 |
| 新增 | `pyproject.toml` | 包元数据、Python 约束、运行/开发依赖、`aim-tool` 入口、版本读取、pytest 标记、Ruff/mypy/coverage 配置及包数据。 |
| 新增 | `requirements-dev.lock` | 从 pyproject 的运行+dev 依赖生成的带哈希锁文件，包含测试/打包工具版本，锁定 Windows/Python 验证组合；CI 不重新解析最新依赖。 |
| 保留；条件修改 | `LICENSE` | 默认不动。若所有者批准软件许可证变更，记录代码与示例资源许可边界后再修改；不能擅自继承字体许可。 |
| 新增 | `THIRD_PARTY_NOTICES.md` | 列出 Qt/PySide6、Pillow、rawpy/LibRaw、ExifTool 及实际打包组件、许可证、来源、版本和发行说明；分发所需完整许可证随构建包附带。 |
| 新增；本阶段 | `docs/plan.md` | 本交接计划；实现阶段仅根据明确决策/验证结果更新状态，不把待办写成已完成。 |
| 新增 | `docs/architecture.md` | 工作流契约、数据流、坐标/日期/元数据/原片保护规则，新增组件示例说明与配置迁移规则。 |
| 新增 | `docs/user-guide.md` | 地点维护、批量勾选、逐图编辑、表格粘贴、字体/签名设置、预览、错误处理、GPS 隐私说明。 |
| 新增 | `docs/build-release.md` | 固定工具链、依赖锁更新、本地打包、标签发布、签名/校验、回滚及重试边界。 |
| 新增 | `docs/acceptance.md` | 本计划测试矩阵、样片机型和哈希、视觉确认、Windows 手工验收记录；不得提交私人路径/GPS。 |
| 新增 | `data/templates/watermark.csv` | UTF-8 BOM 示例表头，航空/铁路/风光各一行虚构数据及带秒日期，文件名匹配示意。 |
| 保留不改 | `data/example/EMU.png`、`data/example/VIEW.png` | 只读参考；不能拿来覆盖输出或用生成图替换。 |
| 用户已新增；保留不改 | `data/NAME.png` | 默认签名唯一源文件；按第 1.4 节指纹登记，禁止覆盖、就地裁剪或提前乘 Alpha。是否跟踪/公开分发按用户发布决定，本阶段不暂存或提交。 |
| 用户已新增；保留不改 | `data/TrajanPro-Bold.otf` | 三类模板统一的默认英文/数字/拉丁符号字体源；登记第 1.5 节名称/指纹/字形覆盖，不自动提交或公开分发。 |
| 用户已新增；保留不改 | `data/FangZhengShengShiKaiShuJianTi-Da.ttf` | 风光中文字体源；登记第 1.5 节名称/指纹/字形覆盖，直接使用原字体，不额外加粗、不自动提交或公开分发。 |
| 新增 | `src/aim_tool/resources/default_templates.json` | 三类模板及 schema；拉丁角色均映射到已有 Bold，分隔符 U+007C，中文方正、NAME 签名，明确单位、Alpha、边距及缩放规则；保存可恢复的项目默认，不写开发机绝对路径，不以常量阻止用户定制。 |
| 新增 | `src/aim_tool/resources/README.md` | 登记已有签名与两款字体的来源/指纹、字体角色、半角分隔符、加载/替换方式、缩放/Alpha 契约和分发决策；不捆绑未授权的字体或其他个人签名。 |

### 6.2 应用与领域逻辑

| 操作 | 仓库相对路径 | 具体内容 |
| --- | --- | --- |
| 新增 | `src/aim_tool/__init__.py` | 单一版本源 `__version__`，不导入 GUI/重量库；pyproject 和打包脚本读取它。 |
| 新增 | `src/aim_tool/__main__.py` | 模块启动入口；解析诊断/自测参数，正常启动 GUI。 |
| 新增 | `src/aim_tool/app.py` | QApplication 初始化、应用标识、全局错误报告、资源/依赖注入；无业务写图逻辑。 |
| 新增 | `src/aim_tool/domain/__init__.py` | 领域包入口，仅显式导出必要类型。 |
| 新增 | `src/aim_tool/domain/models.py` | 第 3.2 节模型、枚举、不可变配置快照和结果结构。 |
| 新增 | `src/aim_tool/domain/validation.py` | 编号/坐标/内容/输出条件校验及字段级错误；统一供 UI、导入和引擎使用。 |
| 新增 | `src/aim_tool/domain/dates.py` | 日期格式白名单、EXIF 日期、日期来源优先级和歧义错误；无文件修改。 |
| 新增 | `src/aim_tool/workflow/__init__.py` | 工作流包入口。 |
| 新增 | `src/aim_tool/workflow/contracts.py` | Step 协议、输入/输出能力、上下文、取消、进度及类型校验约定。 |
| 新增 | `src/aim_tool/workflow/registry.py` | 内置组件注册表和预设工厂；禁止从配置动态导入任意模块。 |
| 新增 | `src/aim_tool/workflow/engine.py` | 整批预检、顺序执行、步骤间产物传递、行级失败隔离、取消/重试及事务提交。 |
| 新增 | `src/aim_tool/workflow/steps.py` | `LocationStep`、`RawDevelopStep`、`WatermarkStep`、`ExportStep`；只编排服务，不重复实现底层处理。 |
| 新增 | `src/aim_tool/services/__init__.py` | 服务包入口。 |
| 新增 | `src/aim_tool/services/exiftool.py` | 可执行文件定位、版本检查、参数数组、JSON 输出、超时/退出码/告警、GPS 写入和读回；Windows 隐藏子进程窗口，禁用 shell 拼接。 |
| 新增 | `src/aim_tool/services/metadata.py` | 元数据标准化、GPS 合并、保留白名单、方向/尺寸/ICC 冲突处理，保证最终 GPS 来自正确产物。 |
| 新增 | `src/aim_tool/services/images.py` | JPG 解码、EXIF 方向归一化、ICC 变换、JPEG 编码、缩略图与大小限制。 |
| 新增 | `src/aim_tool/services/raw.py` | rawpy 能力探测、NEF 显影、白平衡/曝光/方向策略，延迟导入及不支持机型错误。 |
| 新增 | `src/aim_tool/services/fonts.py` | 解析统一 Bold/方正默认映射和用户字体/TTC face，检查逐字符覆盖、文件指纹、缓存；区分默认字体指纹核验和合法自定义替换，不再要求 Regular，不静默替代字体或跨角色补字。 |
| 新增 | `src/aim_tool/services/resources.py` | 统一解析模板/签名/字体资源 ID、源码运行路径、冻结程序资源路径与用户文件覆盖；验证可读性/指纹及签名 Alpha，不依赖 cwd；缺失或未内置时返回针对该资源的选择文件提示。 |
| 新增 | `src/aim_tool/services/watermark.py` | 字体角色分段、Alpha 蒙版、文字 advance/包围盒、签名合成、缩放定位和溢出校验；接入 `data/NAME.png` 默认资源，保持原 RGB/Alpha、按宽高比缩放、只乘一次不透明度；纯渲染接口供预览/导出复用。 |
| 新增 | `src/aim_tool/services/table_import.py` | CSV/TSV/XLSX/剪贴板解析、表头映射、日期单元格、公式拒绝、文件匹配预览及错误。 |
| 新增 | `src/aim_tool/services/storage.py` | 配置目录、schema 迁移、地点 CRUD、工作流预设、备份恢复和原子保存。 |
| 新增 | `src/aim_tool/services/output.py` | 命名、同名冲突、路径安全、目标卷临时文件、不覆盖提交、失败清理与作业报告。 |

### 6.3 图形界面

| 操作 | 仓库相对路径 | 具体内容 |
| --- | --- | --- |
| 新增 | `src/aim_tool/ui/__init__.py` | UI 包入口。 |
| 新增 | `src/aim_tool/ui/main_window.py` | 分区布局、菜单、文件拖放、导入/执行命令和关于入口；调用 controller/worker，不直接写图。 |
| 新增 | `src/aim_tool/ui/photo_table.py` | QAbstractTableModel、勾选、行级编辑、批量应用、校验提示、排序后的稳定 ID 映射。 |
| 新增 | `src/aim_tool/ui/location_panel.py` | 地点工具栏、CRUD、搜索、选择应用、WGS84 标签、重复名称处理。 |
| 新增 | `src/aim_tool/ui/workflow_panel.py` | 卡片、启用/禁用、合法排序、参数页、预设存取及输入输出能力提示。 |
| 新增 | `src/aim_tool/ui/import_dialog.py` | 表格文件/粘贴入口、分隔符/编码/工作表/列映射、匹配预览及确认。 |
| 新增 | `src/aim_tool/ui/preview_panel.py` | 异步预览、缩放/局部、拖动水印锚点、参数回写；丢弃过期预览结果。 |
| 新增 | `src/aim_tool/ui/settings_dialog.py` | 字体/签名选择与健康检查、NAME 预览/自定义替换、字号/签名宽度/位置数值输入、深色或棋盘背景、恢复项目默认与保存个人默认、颜色/Alpha、JPEG/RAW 设置；资源未随包提供时引导本地选择。 |
| 新增 | `src/aim_tool/ui/workers.py` | 后台作业与 GUI 信号桥、进度、取消和关闭窗口时安全收尾。 |
| 新增 | `src/aim_tool/ui/about_dialog.py` | 项目名称、版本、仓库链接、`©BG2FOU`、LICENSE 和第三方声明；不假设字体可再分发。 |

### 6.4 构建、发布及测试

| 操作 | 仓库相对路径 | 具体内容 |
| --- | --- | --- |
| 新增 | `scripts/fetch_tools.py` | 按清单下载官方 ExifTool Windows 分发包、校验哈希、安全解压到被忽略的 `tools/exiftool/`，支持已有缓存和离线指定路径；保留所需支持文件。 |
| 新增 | `packaging/toolchain.json` | Python/打包引导工具/ExifTool 的准确版本、官方 URL、SHA-256、预期目录和许可来源；不得保留占位哈希通过验收。 |
| 新增 | `packaging/AutoImageMarkTool.spec` | PyInstaller 配置，收集模板、许可证、Qt 插件、rawpy DLL、ExifTool 完整运行时；允许公开内置签名时，显式将 `data/NAME.png` 映射到 `aim_tool/resources/signatures/NAME.png`，不扫描打包整个 `data/`；由构建脚本选择 onedir/onefile，不包含用户照片/字体。 |
| 新增 | `packaging/entrypoint.py` | 冻结应用启动 shim，调用 `aim_tool.__main__` 的入口，避免相对导入问题。 |
| 新增 | `scripts/build.ps1` | 检查版本和工具链，生成 Windows 版本信息，调用同一 spec，产物仅写 build/dist；检测外部命令退出码并失败即停止。 |
| 新增 | `scripts/smoke_exe.py` | 带超时启动冻结程序自测，检查退出码和 JSON 结果、无残留进程；测试 Qt 初始化、资源、ExifTool、合成 JPEG GPS+水印输出。 |
| 新增 | `scripts/check_release.py` | 核验标签与单一版本源一致、工具链/许可证/测试证据完整、产物/校验值存在；禁止版本错配发布。 |
| 新增 | `.github/workflows/ci.yml` | PR/push 跑锁定安装、静态检查、单测/集成/GUI 测试，Windows onedir 构建和冒烟；最小读权限。 |
| 新增 | `.github/workflows/release.yml` | `v*` 标签及显式手工恢复触发，复用同一检查/构建命令；onefile 冒烟、校验清单、Release 草稿上传后发布，发布 job 才给 contents:write。 |
| 新增 | `tests/conftest.py` | 临时输入/输出、合成图片/EXIF、可分发测试字体与假签名、Qt fixture；真实工具/样片缺失时的分层处理。 |
| 新增 | `tests/unit/test_validation_dates.py` | 经纬度边界、类别/编号、日期格式/优先级/时区/闰年及空值。 |
| 新增 | `tests/unit/test_table_import.py` | TSV/CSV/XLSX、中文/BOM/引用、日期 epoch、公式、重复/错配及前导零。 |
| 新增 | `tests/unit/test_workflow.py` | 能力/顺序校验、三种预设、测试用新组件注册、取消、失败隔离、产物及 GPS 传递。 |
| 新增 | `tests/unit/test_storage_output.py` | 配置迁移/损坏/备份、输出命名/路径冲突/目录连接保护/并发目标出现、清理边界。 |
| 新增 | `tests/unit/test_watermark.py` | 三模板、码点、pt/px、分段 Alpha、默认签名 759:459 比例及约 300×181 输出、只施加一次 0.50、源图不变、可见边界、缩放/竖图/溢出、字体缺失；保留合成签名以测试其他比例/Alpha。 |
| 新增 | `tests/unit/test_resources.py` | 开发/冻结/自定义签名与字体解析优先级，切换 cwd 后仍可加载；NAME 指纹、完整有效边界、72 ppi 不影响输出尺寸、缺失/损坏/全透明签名提示。 |
| 新增 | `tests/unit/test_fonts.py` | 已有两款字体内部名称/字重/指纹、三模板统一 Bold、示例汉字覆盖、U+007C 与 © 的正确字体角色、U+2160 缺字负例、合法自定义字体替换后重新校验；不能要求 Regular 才放行航空。真实项目字体测试与可分发测试字体用例分开。 |
| 新增 | `tests/integration/test_exiftool.py` | 真实 ExifTool JPG/NEF 坐标写回、原片哈希、图像数据、MakerNotes、中文/特殊路径和损坏输入。 |
| 新增 | `tests/integration/test_pipeline.py` | JPG/NEF 三类流程、方向/ICC/日期/GPS 保留、最终命名、部分失败和取消。 |
| 新增 | `tests/gui/test_main_window.py` | pytest-qt 验证地点到勾选行、逐张编辑、导入预览、启停卡片、后台响应/取消、关于和缺依赖提示。 |
| 新增 | `tests/visual/test_reference_layout.py` | 原示例指标只读回归、受控字体下渲染指标、确认后视觉基线比较；中文 50% 为已确认要求，原示例 27 px 底边距不得覆盖已确认的 25 px。 |
| 新增 | `tests/fixtures/README.md` | 样片来源/授权、机型、下载/本地放置方法、哈希及 CI 可用性；禁止未经允许公开原片。 |
| 新增 | `tests/fixtures/manifest.json` | 真实 JPG/NEF/ICC/方向/字体样片的路径、SHA-256、用途与许可；登记已有签名及两款字体（路径基准统一为仓库根目录）和第 1.4/1.5 节指纹，不复制到 fixtures；其他样片引用公开可分发资源或私有本地位置，不提交占位假数据。 |

测试授权素材存放于 `tests/fixtures/public/`，私人素材放被忽略的 `tests/fixtures/private/`；具体文件名只有取得实际素材后才能准确列出，必须先更新 manifest，不编造已存在的 NEF。视觉基线在确认后以 `tests/fixtures/public/expected_railway.png` 和 `tests/fixtures/public/expected_landscape.png` 保存；若包含不可公开素材则同名保存在 private 目录，不进 Git。

**删除文件：无。** 本计划不要求删除现有文件。构建产物、缓存和作业临时文件不是源文件删除任务；清理脚本必须先验证路径位于指定 build/dist 或本作业目录。

## 7. 实施步骤、依赖、前置与验收

依赖主线：`S0 → S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8 → S9 → S10`。其中 S4/S5 的纯模块设计可独立于对方推进，但最终必须在 S6 收敛；本计划不授权自动开启子 Agent。

| 步骤 | 前置条件 | 实施内容与关联文件 | 验收条件 |
| --- | --- | --- | --- |
| S0 决策与素材 | 用户批准进入实现；工作树与本文基线重新核对 | 对第 10 节建立决策表；登记已有签名/两款字体和统一 Bold、半角分隔符、自定义能力等已确认要求；补齐 JPG/NEF，确认字号单位与分发策略，更新 `docs/acceptance.md`、fixture manifest；若源码许可证未决保留原 LICENSE | 字号单位/NEF 输出等未决项有明确答复或显式标记阻塞；已有素材指纹符合记录；不再索取 Regular 或重复询问分隔符；公开分发未决不阻止本地渲染验证，但阻止擅自打包公开发布。 |
| S1 工程与工具链 | S0；可用 Python 3.12 x64；允许安装依赖后才安装 | 新建 pyproject、锁文件、包入口、toolchain、fetch_tools；修改 Git 配置；建立最小 CI 与测试骨架，版本选型实际验证 | 锁定环境安装成功，`pip check`/Ruff/mypy/最小 pytest 通过；空 GUI 可启动；实际 ExifTool `-ver` 正确；忽略规则不会漏掉 spec/lock。 |
| S2 模型与引擎 | S1 | domain、workflow contracts/registry/engine、output/storage 基础；先用假步骤测试，不改真实照片 | 三种预设规划正确；非法顺序/路径冲突开跑前阻止；测试组件可注册而不改主窗口；取消/逐项失败状态正确；配置重启可恢复。 |
| S3 GPS 最窄闭环 | S2；真实 ExifTool；授权 JPG/NEF | exiftool/metadata/LocationStep；先一张 JPG，再 NEF，完整执行“读→副本写 GPS→读回→提交” | 原片哈希不变；同名输出；四个坐标字段及误差正确；JPG 图像未重编码；NEF 数据/MakerNotes/查看器检查通过。NEF 失败时不得放行该机型。 |
| S4 导入与日期 | S2 | dates、validation、table_import、模板 CSV；用当前批次 ID 做文件匹配 | 秒截取到日；EXIF 日期回退正确；重复/未知/歧义日期明确报错；粘贴预览后才应用；手动和批量输入结果一致。 |
| S5 水印渲染闭环 | S2；已有签名/Bold/方正完整；S0 中字号单位已确认，分隔符沿用已确认 U+007C | fonts、resources、watermark、default_templates、images 颜色/方向处理；使用已提供字体完成三类模板；以 NAME 源图生成内存蒙版及单张 JPG，参数支持用户调整 | 项目默认字号/签名 300×约181/边距/Alpha 指标通过；不修改素材，不因 72 ppi 变更尺寸，不双重衰减；替换字体/签名、修改大小和位置均正确重算；三类样片人工认可；无需 Regular。 |
| S6 RAW 与流水线集成 | S3、S4、S5；已确认 NEF 显影及导出格式 | raw、images、metadata、全部内置步骤及输出事务；位置+水印端到端 | JPG 输出 `_marked` 且保留新 GPS；NEF 成功显影为约定格式；方向/ICC 一致；位置-only 不触发显影或水印；中途失败不产生伪成功文件。 |
| S7 GUI 完整交互 | S6；服务接口稳定 | 全部 ui 文件及 app；连接模型、worker、导入对话框和用户配置 | 能拖入照片、维护地点、勾选应用/手填、粘贴表格、替换字体/签名、调字号/签名宽/位置、保存个人默认及恢复项目默认、真实预览、运行/取消/重试；窗口可操作；关于链接和 `©BG2FOU` 正确。 |
| S8 集成回归与文档 | S7；完整授权样片和确认后的视觉规则 | 补齐 unit/integration/gui/visual 测试、README、用户手册、architecture、acceptance | 第 9 节矩阵全部通过或明确阻塞；核心非 UI 逻辑覆盖率建议 ≥85%；真实工具测试不能被 mock 替代；未测格式不写“支持”。 |
| S9 Windows 打包 | S8；第三方分发许可和完整工具链已核对；Q18 签名内置策略已确定 | spec、entrypoint、build.ps1、smoke_exe.py、THIRD_PARTY_NOTICES、build-release，校验默认签名资源是否按已批准策略收集 | onedir 后 onefile 冒烟通过；无 Python/ExifTool/源码目录的干净 Windows 可离线运行；程序路径中文/空格可用；允许内置时 NAME 开箱可用，否则引导本地选择；用户字体仍由用户提供。 |
| S10 自动发布 | S9；所有者确认发布策略和 GitHub 权限 | 完成 ci/release、check_release；设置 tag/version 校验、权限和并发 | 用明确批准的测试版本验证标签→检查→EXE→校验值→Release 全链；下载产物再运行；未授权前仅验证 workflow/本地构建，不创建标签、推送或发布。 |

每步结束更新实际修改清单、命令/结果和未完成项；若有用户已有改动，保留且不混入本任务。未达到前一步验收就先修复该窄链路，不通过扩大格式范围掩盖问题。

## 8. 预定测试、静态检查、构建和发布命令

以下命令是后续实现阶段应提供并运行的接口，**当前仓库尚不能运行，本阶段未执行**。以仓库根目录为工作目录、PowerShell 为 shell。新脚本必须实现这里列出的参数，不得仅文档写有而脚本缺失。

### 8.1 环境与依赖

首次 S1 创建环境及生成锁（工具版本确定后写入 `packaging/toolchain.json`，不得将占位字符串提交）：

```powershell
py -3.12 -m venv .venv
$tc = Get-Content packaging/toolchain.json -Raw | ConvertFrom-Json
.\.venv\Scripts\python.exe -m pip install "pip==$($tc.pip)" "pip-tools==$($tc.pip_tools)"
.\.venv\Scripts\pip-compile.exe --extra dev --generate-hashes --output-file requirements-dev.lock pyproject.toml
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe scripts/fetch_tools.py --manifest packaging/toolchain.json
.\tools\exiftool\exiftool.exe -ver
.\.venv\Scripts\python.exe -m pip check
```

pyproject 的 dev 依赖须包含所选构建后端，保证 `--no-build-isolation` 可用。日常/CI 安装跳过 pip-compile，直接按已提交锁文件安装；pip-tools 仅用于显式升级锁。安装器及 pip-tools 也按 toolchain 固定版本，S1 核实锁文件哈希兼容对应 Windows/Python 组合。

### 8.2 静态与自动化检查

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests scripts packaging
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts packaging
.\.venv\Scripts\python.exe -m mypy src/aim_tool
.\.venv\Scripts\python.exe -m pytest tests/unit -q
$env:AIM_EXIFTOOL = (Resolve-Path tools/exiftool/exiftool.exe).Path
.\.venv\Scripts\python.exe -m pytest tests/integration -m "not raw" -q
$env:AIM_TEST_ASSETS = (Resolve-Path tests/fixtures/private).Path
.\.venv\Scripts\python.exe -m pytest tests/integration -m raw --require-real-assets -q
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m pytest tests/gui -q
.\.venv\Scripts\python.exe -m pytest tests/visual --require-visual-assets -q
.\.venv\Scripts\python.exe -m pytest tests/unit tests/integration tests/gui --cov=aim_tool.domain --cov=aim_tool.services --cov=aim_tool.workflow --cov-report=term-missing --cov-fail-under=85
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
git diff --check
```

`--require-real-assets`、`--require-visual-assets` 由 `tests/conftest.py` 实现；普通开发可显示明确 skip，但正式 RAW/视觉验收缺素材必须失败，不许全跳过仍算通过。若使用可公开样片，将 `AIM_TEST_ASSETS` 指向 `tests/fixtures/public`。fixture 通过 manifest 查找字体/原片，私有素材不存在时先获取，不创建空目录假装满足。

CI 不获得商用字体时：通用字形/布局测试用合法可分发测试字体，原示例指标测试独立执行；商业字体视觉匹配是独立人工门禁。不要把 CI 绿灯描述成 Photoshop 一致性证明。

### 8.3 GUI 与本地打包

```powershell
.\.venv\Scripts\python.exe -m aim_tool
powershell -NoProfile -File scripts/build.ps1 -Mode onedir
.\.venv\Scripts\python.exe scripts/smoke_exe.py --exe dist/AutoImageMarkTool/AutoImageMarkTool.exe
powershell -NoProfile -File scripts/build.ps1 -Mode onefile
.\.venv\Scripts\python.exe scripts/smoke_exe.py --exe dist/AutoImageMarkTool.exe
Get-FileHash dist/AutoImageMarkTool.exe -Algorithm SHA256
```

`build.ps1` 读取固定清单，不在内部默默升级依赖；外部命令任一失败返回非零。冻结程序提供 `--self-test --report <path>` 给 smoke 脚本调用，自测使用临时合成 JPEG、合法测试字体/签名，不依赖生产商用字体、不写原片、不联网。冻结自测不能代替真实 NEF/商用字体/交互验收。

### 8.4 版本和自动 Release

- 单一版本源为 `src/aim_tool/__init__.py`；pyproject 动态读取；EXE 文件版本、About 与标签必须一致。
- `ci.yml`：PR 和主分支 push 执行检查，不使用发布权限。
- `release.yml`：`push.tags: ['v*']`，只接受校验通过的版本；`workflow_dispatch` 提供既有 tag 作为恢复入口。不要同时用 tag push 和 release published 两个触发器互相重复创建发布。
- Windows runner、Python、Actions 版本固定；Actions 固定到审查过的 commit SHA，更新时单独验证。构建 job 仅 `contents: read`；上传/发布 job 才 `contents: write`，只使用仓库内置 token。
- 顺序：校验 tag 对应提交 → 锁定安装 → 静态/测试 → onedir/onefile 构建和冒烟 → 生成版本 EXE、SHA256SUMS、第三方声明 → 创建 Release 草稿 → 上传并核验全部资产 → 发布草稿。
- 使用 GitHub CLI 的 `--verify-tag` 避免自动创建错误标签，参见 [gh release create](https://cli.github.com/manual/gh_release_create)；触发与过滤规则参见 [GitHub Actions 文档](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)。
- Release 资产建议 `AutoImageMarkTool-vX.Y.Z-windows-x64.exe`、`SHA256SUMS.txt`、`THIRD_PARTY_NOTICES.md` 和所需许可附件。是否同时提供 onedir ZIP 见待确认；首要满足 Windows EXE。
- 同一标签并发互斥；已发布版本不可静默重建替换，修复需新版本。恢复仅处理未发布草稿或经过显式批准的补传，不重复发布。
- 标签发布前，确认 raw/视觉手工验收记录对应当前版本、样片与字体指纹。若 CI 无法拿到这些素材，不能声称 CI 已自动验证它们，正式版本必须有独立验收记录。

版本检查预定命令（只检查，不发布）：

```powershell
.\.venv\Scripts\python.exe scripts/check_release.py --tag v0.1.0 --dist dist
```

其中 `v0.1.0` 仅为示例，实际使用对应版本。本阶段只执行第 1.6 节明确授权的文档提交/普通分支推送，不运行 `git tag` 或 `gh release create/edit`。后续实施、提交/推送及应用发布范围仍分别确认；所有提交消息和待推送的新提交必须符合第 1.6 节。

## 9. 测试和最终验收矩阵

### 9.1 自动化必须覆盖

1. **GPS**：东/西/南/北、0/0、边界 ±90/±180、多位小数、无/有原 GPS、旧高度字段、坏 EXIF、负坐标方向；写后读回误差 ≤1e-6 度。
2. **原片与命名**：输入 SHA-256 不变；GPS-only 同名同格式；水印 `_marked`；大小写扩展名、多点文件名、中文/空格/前导连字符路径、大小写冲突、同名 JPG/NEF、已有目标、重复执行。
3. **图像兼容**：JPEG baseline/progressive、EXIF Orientation 1–8、无/有 ICC、Adobe RGB/CMYK、横图/竖图/方图/全景、小图和大图；超限图像给明确错误而非无限内存申请。
4. **NEF**：至少用户实际机型和实际压缩模式样片；仅 GPS 不显影；显影水印使用真实完整 RAW；原始像素、关键 MakerNotes、预览及最终 JPEG 可读。只测试过一个机型就只声明该验证范围。
5. **水印**：三类模板英文/数字/拉丁符号均默认使用提供的 Bold、风光中文使用方正；分隔符 U+007C；内容/日期/空格精确；中文及其他实心文字区域 Alpha 均约 128/255（50% 不透明度，保留抗锯齿容差），签名不被重复衰减。
   默认签名单独覆盖 `data/NAME.png` 的 SHA-256、759×459、Alpha 0…255 与完整可见包围盒；缩放后实心笔画最大 Alpha 应约 128，而非 64，边缘保留部分透明度及原灰阶。加载、预览、批处理后源图哈希不变；资源解析不依赖 cwd，冻结产物不依赖仓库仍在磁盘上。
6. **尺度与定制**：项目默认下 6016×4016 时签名有效宽 300±1 px，右/下可见边距 25±1 px；3008×2008 时统一半缩放；分辨率标签 72/300 ppi 但像素相同，布局相同；竖图/其他比例按确认规则。分别替换字体/签名、调整字号/签名宽/位置，确认预览和成品一致、设置重启保留；恢复默认回到项目值，用户自定义边距不被 25 px 默认强制覆盖。
7. **日期/表格**：有秒/时区、闰日、EXIF 特殊格式、XLSX 两种 epoch、公式/宏拒绝、粘贴空格/制表符差异、列映射、空值、重复文件、缺失日期、不改变原时间 EXIF。
8. **工作流**：三预设、新测试组件、非法顺序、单步禁用、缺字体仍可 GPS-only、元数据不回退、错误照片不拖垮全批、取消后可重试。
9. **IO 失败**：无权限、空间不足、文件被占用、ExifTool 超时/异常退出、输入被外部修改、目标竞争创建；均不覆盖源文件、不留下伪成功输出。
10. **配置与 GUI**：保存重启、损坏恢复、版本升级、排序/筛选后批量应用仍命中正确照片、异步预览不串图、取消和窗口关闭后不留进程。

自动图像差异测试使用确认后的独立基线，不要求跨 Pillow/FreeType/Photoshop 逐像素完全相同；几何/Alpha/内容是硬指标，字体外观由原尺寸局部和人工签字确认。升级字体或渲染器必须重跑视觉验收。

### 9.2 手工验收清单

- 在干净 Windows x64 标准用户账户下，无 Python/ExifTool 安装，双击 EXE；不要求管理员权限，不出现意外控制台窗口，不依赖联网。
- 首次配置真实字体，开发版本默认显示 `data/NAME.png`；已批准内置的 EXE 同样默认可用，否则按分发策略本地选择该图。在深色/棋盘底确认笔画完整，测试更换签名及恢复默认；添加两个地点，退出重开仍存在，勾选多图应用一处，单图改为另一组经纬度，最终 GPS 分别正确。
- 同批包含 JPG、NEF；仅位置导出检查原名，查看器能打开；原片文件字节哈希不变。
- 分别导入 CSV/XLSX、从 Excel 粘贴 TSV，核对文件匹配、日期只显示到日，以及错误行提示。
- 三类别各导出至少一张，在原尺寸和深浅底图下对照示例；核对文字字重、颜色、分隔符、空格、签名宽、透明度、右/下边距。
- 开发版自动识别已有 Bold/方正并显示内部名称，三类模板默认拉丁字体均为 Bold、分隔符均为半角 `|`；无需 Regular。更换字体/签名、改变字号/签名宽和位置，比较预览与导出、重启后恢复个人设置，再验证恢复项目默认。已有字体和签名测试前后哈希相同。
- 位置+水印导出后由独立工具读取 GPS、拍摄时间、Orientation 和 ICC；确保 EXIF 没被 JPEG 编码丢弃或被原片旧值覆盖。
- 批量至少 100 张实际尺寸照片，记录机器、总耗时、峰值内存、GUI 响应；目标是内存随并发受控而不是随照片数量线性增长，取消能在当前不可中断操作结束/超时后停止下一项。
- 测试已有输出、目录不可写、取消、损坏图片；成功/失败报告与磁盘结果一致。
- 检查 About 中版本、`©BG2FOU` 和正确仓库链接；字体与照片没有混进发布包。
- 实际批准发布后，从 GitHub Release 下载 EXE、验证 SHA-256，再在干净机器运行；“本地能运行”“CI 通过”“已发布”“下载验收通过”分别记录。

## 10. 风险、兼容性及待确认事项

### 10.1 高优先级待确认（影响实现或验收）

| 编号 | 需要确认的问题 | 推荐处理 / 未确认时边界 |
| --- | --- | --- |
| Q1 | Photoshop 的 36 是 pt 还是 px？是否可提供 PSD/字体参数截图？ | 推荐 36 pt=150 px；先参数化，未确认不能宣称视觉还原。 |
| Q4 | 签名与文字在组合内部是底部、基线还是视觉中心对齐？ | 推荐签名可见底部对齐文字可见底部；仅组内对齐待确认，整体底部可见边距 25 px 已确认。 |
| Q5 | 已提供字体是否获准公开仓库/EXE 分发？ | 三类模板统一使用现有 Bold 已确认，不再需要 Regular；本地默认使用已有字体且支持替换。未确认再分发许可前不自动提交/捆绑字体；本次文档推送不包含字体文件。签名公开内置策略单列 Q18。 |
| Q6 | NEF 添加水印是否接受导出 JPEG？是否需要 TIFF、另存 GPS NEF 副本或只处理伴随 JPG？ | 推荐 NEF→JPEG；只做 GPS 保持 NEF 同名。确认前不实现伪 RAW 水印输出。 |
| Q7 | “jpg、nef 等格式”还包括哪些格式/机型/压缩模式？ | 首版保证经验证的 JPEG/NEF；TIFF/PNG/HEIC/其他 RAW 后续能力组件，不承诺全部。 |
| Q8 | 程序软件许可证是否保留现有 CC BY-SA 4.0，或经所有者批准改用软件许可证并单独声明示例素材？ | 未批准不改 `LICENSE`。CC 官方不推荐用 CC 许可证发布软件，见 [CC FAQ](https://creativecommons.org/faq/)。发布前核对实际第三方分发要求，不把此计划当法律结论。 |

### 10.2 可先按推荐值设计、验收前确认

原 Q2（分隔符）已解决：半角 `|`（U+007C）；原 Q3（中文不透明度）已解决：50%；Q5 中航空字重已解决：与其他英文/数字统一使用现有 Bold。字体/签名替换及字号、签名大小、位置调整是已确认能力，不再待确认；见第 1.3 节。保留其余问题编号便于追踪。

| 编号 | 问题 | 推荐默认 |
| --- | --- | --- |
| Q9 | 水印-only 是否需要，位置+水印是否保留中间文件？ | 提供水印-only；组合流程只提交最终文件，中间 GPS 副本默认清理，可扩展显式保留。 |
| Q10 | 竖图、方图、全景按哪个默认比例缩放？ | 推荐第 4 节方向适配 min 比例；水印位置可调整已确认，提供四角+数值偏移+预览拖动，不再将位置定制作为未决功能。 |
| Q11 | 白色是否固定？风光内容是否允许中文标点/数字/英文？编号是否自动转大写？ | 白色可改；混排按字符角色；规范化先预览，不静默改值。 |
| Q12 | 表格实际列名/样表、默认类别、日期冲突优先级？ | 提供映射；逐行类别优先，无类别时用户选择批次模板；日期按第 5 节。 |
| Q13 | 地点名称是否也写入 IPTC/XMP？坐标来源是否为 WGS84？需要海拔/度分秒输入吗？ | 首版 WGS84 十进制度，经纬度必填，不默认写名称或海拔。 |
| Q14 | 同名输入和已有 `_marked` 如何处理？允许原地写 EXIF 吗？ | 分目录、冲突阻止/跳过、已标记默认排除；首版不覆盖原片。 |
| Q15 | JPEG 质量、色彩空间、NEF 显影色调/亮度及 DPI？ | 质量95/4:4:4、sRGB、相机白平衡，保留像素和已有 DPI；样片确认后冻结。 |
| Q16 | “exe”要求单文件便携 EXE、安装器，还是可接受含 EXE 的目录 ZIP？最低 Windows、ARM64？ | 首版 x64 单文件 EXE，onedir 用作验证；不含安装器/ARM64，最低系统按锁定依赖实测。 |
| Q17 | 发版由推送版本标签还是手工 Release 驱动？是否自动公开、需不需要代码签名？ | `vX.Y.Z` 标签自动构建，草稿组装完后发布；签名若无证书明确标未签名，不伪造可信发布者。 |
| Q18 | `data/NAME.png` 是否允许作为默认签名随公开仓库和 EXE 分发？需怎样的素材署名/许可说明？ | 本地已按用户提供的项目素材使用，无需重新提供；推荐经确认后随 EXE 内置且可替换。未确认前不自动提交/发布该素材、不把仓库代码许可证推定为签名的再分发许可；此项不阻塞本地渲染开发。 |

### 10.3 主要技术与分发风险

- **RAW 写入风险**：NEF 变体、MakerNotes、偏移和厂商工具兼容性需要真实样片验证；永远先副本，失败不提交。
- **RAW 显影差异**：LibRaw 与相机 JPEG/Adobe/Nikon 色彩不同；嵌入预览不能替代完整显影，也不承诺无损水印。
- **字体与签名授权**：开源仓库不意味着第三方字体可以公开分发；签名、Bold 和方正已覆盖用户确认的本地默认素材需求，公开内置策略分别按 Q18/Q5 确认。CI 公共日志/产物不得意外带入未批准分发资源；原 Regular/分隔符缺字阻塞已通过最新需求解决，不得继续作为阻塞项。
- **许可证/打包**：核对 Qt/PySide6 和实际第三方组件的声明与分发要求，见 [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html)。单文件打包不是免除许可证义务的方式。
- **Windows 运行时**：Qt 插件、rawpy/LibRaw DLL、ExifTool 支持目录、临时解包路径、中文路径都可能只在冻结产物失败，必须离线干净机验收。
- **未签名 EXE**：可能触发 SmartScreen/杀毒提示；公布校验值和来源，签名是单独发布能力，不能通过关闭安全软件规避验收。
- **资源/并发**：超大图片、RAW 解码和缓存占内存；限制在途全尺寸图片、缩略图缓存容量和输入尺寸，超时/取消要清理子进程。
- **日期/坐标数据质量**：来源时区、Excel 自动转换、GCJ-02/WGS84 混淆会产生“程序成功但内容错误”；要显示来源和预检结果，而非只判断保存成功。
- **发布可复现性**：固定依赖/工具版本和哈希，不承诺不同时间构建出的 EXE 必然逐字节相同；记录构建来源提交和工具链，确保可追溯。

## 11. 交接给编码 Agent 的执行准则

1. 先读本计划、最新 `git status` 和适用 `AGENTS.md`，保留用户已有改动；确认用户已授权实现，不把此计划文档视为已经授予发布权限。执行期间遵守第 1.3 节用量门禁：低于 5% 暂停，超过 95% 才恢复；额度未知时说明限制，不伪造监控结果。
2. 按 S0 收集决策；未确认内容只做参数化/可替换边界，不能替用户下结论或伪造素材。
3. 按 S1→S10 逐步实现，优先完成 JPG GPS-only 的窄闭环，再扩展 NEF、日期、水印、GUI、打包。不得一开始就搭复杂插件市场或节点图。
4. 严格遵守第 6 节路径；新增文件如需偏离，应说明原因并更新清单，不能遗漏测试/脚本/锁文件。
5. 每一阶段运行对应第 8 节命令，记录“通过/失败/未运行/缺素材”；skip 不等于功能验收。
6. 保持 `data/NAME.png`、`data/TrajanPro-Bold.otf`、`data/FangZhengShengShiKaiShuJianTi-Da.ttf`、两张示例和原照片不变；签名只在内存中缩放/合成，真实照片只在授权样片副本上测试。
7. 最后交付实现代码、锁文件、用户手册、测试记录和本地 EXE；有明确远程授权再进行标签/推送/Release，并分开报告各阶段状态。
8. 本次与后续所有提交消息、待推送的新提交都按第 1.6 节规范检查；纯计划文档使用 `docs:`。不能把遵守格式描述为已安装 Husky，也不能将提交规范当作自动发布授权。

本计划完成不表示上述功能、依赖兼容性、测试、构建或 Release 已完成。
