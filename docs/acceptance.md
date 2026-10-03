# 验收记录

本文件记录 `docs/plan.md` 的实际进度。未列为通过的项目不能据此声称已验收。

## S0：决策与素材（已完成登记）

2026-10-01 开始实施前核对 `origin/main` 的 `ef13d52`：当时仓库只有计划、说明、许可、Git 配置和两张参考 PNG；没有应用源码、依赖锁、测试或构建入口。用户提供的三份本地素材均未受 Git 跟踪，未修改或暂存。适用路径上未发现 `AGENTS.md`。

| 项目 | 状态 | 证据或后续要求 |
| --- | --- | --- |
| 默认签名 `data/NAME.png` | 指纹通过 | SHA-256 `d86e885e86c0977a2d874aacb16671be11f3bde55fdb23139f6e4aadcf330777`；保持原文件不变。 |
| 拉丁字体 `data/TrajanPro-Bold.otf` | 指纹通过 | SHA-256 `60c3185c2919d8fdae1ccc5c334c548071dd31700121825c803c2903369dbed5`；三类模板统一用 Bold。 |
| 中文字体 `data/FangZhengShengShiKaiShuJianTi-Da.ttf` | 指纹通过 | SHA-256 `e654df886e997e9847744583fa5a1ad78930bfde72c358500e4ed4518f49bc76`。 |
| 默认分隔符 | 已实现并测试 | 半角 `|`（U+007C），默认两侧无空格；三类模板渲染测试通过。 |
| 默认中文不透明度及可见底边距 | 已实现并测试 | 中文、拉丁文字与签名分别应用一次 50% 不透明度；基准画布组合可见右/下边距 25 px。 |
| 字体、签名、字号、签名宽度和位置定制 | JPG 渲染与 GUI 设置已实现 | 本地预览可替换素材、调整字号、签名宽度、颜色、透明度、四角锚点与偏移；个人默认的保存/恢复、异步预览与拖动已接入。 |
| JPG/NEF 真实样片及机型 | JPG 定向检查通过，NEF 待查看器验收 | Nikon Z 5 三份照片只留本地，哈希见 manifest；JPG GPS 与水印预览已核对原片哈希。NEF 坐标诊断未取得独立 Nikon 查看器认可，正式批量仍阻止。 |
| Photoshop 字号单位与 NEF 水印输出 | 已确认 | 36 pt；在 300 ppi 基准画布换算为 150 px。NEF 加水印显影后导出 JPEG。 |
| 组内对齐 | 已确认当前三类预览 | 用户于 2026-10-02 确认三类预览，默认可见底部对齐与 36 pt、300 px 签名、25 px 可见边距获认可；参数仍可调整。 |
| 素材与许可证 | 已确认 | 保留现有 CC BY-SA 4.0 `LICENSE`；照片、签名、字体只留本地，不提交到 GitHub，也不纳入公开构建物。 |

### 第 10 节决策表

| 编号 | 当前状态 | 处理边界 |
| --- | --- | --- |
| Q1 | 已确认 | Photoshop 36 pt；300 ppi 基准下为 150 px。 |
| Q4 | 已确认当前默认 | 2026-10-02 用户确认三类本地预览的字号、签名组内对齐和可见边距。 |
| Q5 | 已确认 | 字体只留本地，不提交或捆绑公开 EXE。 |
| Q6 | 已确认 | NEF 加水印显影并导出 JPEG；仅位置处理仍保持 NEF。 |
| Q7 | 部分已知 | 本地样片为 Nikon Z 5；不承诺 JPEG/NEF 以外的格式或未经验证的机型。 |
| Q8 | 已确认 | 保留现有 CC BY-SA 4.0 `LICENSE`。 |
| Q9 | 待确认 | 水印-only 与中间文件策略按计划推荐设计，实施前核对。 |
| Q10 | 待确认 | 竖图/其他比例按计划推荐设计，视觉验收前确认。 |
| Q11 | 待确认 | 颜色与风光混排、大小写规则按计划边界处理。 |
| Q12 | 待确认 | 等待真实表格列名与日期冲突规则。 |
| Q13 | 待确认 | 默认 WGS84 十进制度，不擅写地点名或海拔。 |
| Q14 | 默认保护已实现 | GPS 与水印预览都写副本，拒绝覆盖源片或已有目标；是否提供显式覆盖选项仍待确认。 |
| Q15 | 待确认 | JPEG/RAW 颜色与质量参数需真实样片验收。 |
| Q16 | GPS 预览版已验证 | 原生 Windows CI 的 GPS GUI onedir/onefile 构建与冻结自检通过；完整水印应用的 Windows 支持范围仍待验证。 |
| Q17 | GPS 预览发布已获授权 | 用户已明确要求提交和发布 GPS GUI；`v0.2.0-rc.2` 已发布。完整水印应用的发布策略仍待后续阶段核对。 |
| Q18 | 已确认 | `NAME.png` 只留本地，不提交或捆绑公开 EXE；本地开发版本可直接加载。 |

## 阶段验证

| 阶段 | 结果 | 未完成项 |
| --- | --- | --- |
| S0 | 已完成登记 | 三份项目素材及 Nikon Z 5 样片指纹已核对；Q4 和其余推荐默认仍待视觉或功能验收时确认。 |
| S1 | 当前 GPS GUI 范围通过 | 固定依赖在 Windows CI 安装，ExifTool 13.59 版本检查、Qt GUI 测试与静态检查通过。 |
| S2 | 模型与引擎定向测试通过 | 三种预设、组件注册、全批预检、取消、逐项失败及配置恢复已有自动化测试。 |
| S3 | JPG 坐标闭环通过；NEF 阻止 | 真实 ExifTool 13.59 的 JPG 副本写入、读回及原片保护通过；Windows 原生冻结自检通过。NEF 仍需独立 Nikon 查看器抽验。 |
| S4 | 日期与表格后端完成 | 日期来源、CSV/TSV/XLSX 预览与应用已有测试；完整 GUI 导入交互仍属后续阶段。 |
| S5 | 单图 JPEG 渲染与预览已提交，三类默认视觉已确认 | 三类模板、36 pt/300 ppi、签名 300×约181、Alpha、边距、方向/ICC、替换素材与位置参数已有定向测试；完整 EXIF/GPS 传递和批量工作流仍属 S6。 |
| S6 | JPG/JPEG 后端集成通过；NEF 图像处理暂缓 | 正式水印与位置+水印保留当前 GPS 和元数据白名单，方向/ICC/事务/取消测试通过；NEF 按用户 JPG-only 指示继续阻止。 |
| S7 | JPG 页面与交互已接入 | 三预设、稳定 ID 表格、坐标列表、导入预览、素材设置、异步预览/拖动、后台运行/取消/重试及报告已实现；本期不做 NEF。 |
| S8 | JPG 集成回归进行中 | Linux JPG 范围回归通过；原生 Windows 检查、批量压力记录和冻结发布门禁继续补齐。 |
| S9 | GPS GUI 预览包通过；完整水印包未开始 | 原生 Windows runner 的 GPS GUI onedir/onefile 与 Linux DEB 冻结自检通过；水印未纳入公开包，私人素材未捆绑。 |
| S10 | GPS GUI 预发布链通过；完整发布未开始 | `v0.2.0-rc.2` 标签、EXE/DEB、SHA256、下载回读校验通过；完整水印应用的发布门禁仍待 S6–S9。 |

以下按日期记录当时的验证快照；上面的阶段表是当前状态。

### S1 命令和结果（2026-10-01）

| 检查 | 结果 | 证据与限制 |
| --- | --- | --- |
| Python 3.12 x64 隔离环境 | 通过，Linux 替代启动 | 本机缺少 `ensurepip`，普通 `venv` 失败；改用 `venv --without-pip`，再通过系统 pip 的 `--python .venv` 安装固定的 pip 24.0 / pip-tools 7.6.1。未改系统包。 |
| 依赖锁 | 通过，仍待 Windows 安装 | `requirements-dev.lock` 由 `pip-compile --extra dev --generate-hashes --reuse-hashes` 生成；35 个包的 630 个哈希取自 PyPI 官方发布元数据。Linux `pip install --require-hashes`、本地包 `--no-deps --no-build-isolation -e .` 和 `pip check` 通过；Windows x64/Python 3.12 的 35 个 wheel 均下载且通过锁文件哈希验证，但尚未在 Windows 执行安装。 |
| 静态检查 | 通过 | Ruff check、Ruff format --check、mypy 均通过；`git diff --check` 通过。 |
| 测试与空 GUI | Linux 通过 | `QT_QPA_PLATFORM=offscreen` 下 5 个 unit 和 1 个 GUI 测试通过；模块 `--version` 输出 0.1.0。首次未设置 offscreen 的组合测试在无显示器的 Linux 主机上由 Qt 中止，设置后通过。Windows GUI 尚未测试。 |
| ExifTool 固定包 | Linux 与 Wine 运行通过，原生 Windows 待验收 | 后续从 SourceForge 获取官方 Windows ZIP，SHA-256 `44b512b25af500724ba579d0a53c8fc5851628b692dd5e5d94ae4a15c2cba9ec` 与官方清单一致，支持目录完整提取；Wine 下 `exiftool.exe -ver` 返回 `13.59`。Linux 13.59 源包已按固定哈希验证并执行。 |
| CI | 本地文件，未运行 | `ci.yml` 固定官方 Actions 提交，使用只读权限和 Windows runner；按用户要求没有提交或推送，无法通过 GitHub Actions 验证。 |

S1 使用官方 `PySide6-Essentials` 提供 Qt Widgets，未引入暂不需要的 Addons；PyInstaller 的 Windows 条件依赖 `pefile`、`pywin32-ctypes` 显式列入锁。当前主机为 Linux，没有 PowerShell 或 Windows 运行环境。所有用户照片、签名和字体保持本地，未暂存、未打包或公开。Windows 锁定安装、空 GUI 和 ExifTool 版本验证仍须补齐；用户同意继续后，S2 先做 Linux 侧假步骤验证，正式阶段门禁仍待 S1。

## Linux 本地 demo（2026-10-01，用户追加优先要求）

用户要求先在 Linux 做初步 demo。因此增加独立单张 JPG/NEF 水印预览，不接入正式工作流，也不把 S1 Windows/ExifTool 门禁或 S2–S7 记作通过。这是相对计划阶段顺序的明确偏差，仅用于本地视觉审查；未实现 GPS、完整 EXIF 保留、正式批量处理或 Windows 构建；另有独立 Linux Qt 预览窗口，不等于 S7 GUI 验收。

使用本地 Nikon Z 5 JPG/NEF、已登记字体和签名，以 36 pt、300 px 签名、25 px 可见右下边距、各段 50% 不透明度生成两个 JPEG 到被忽略的 `demo-output/`。原片哈希与 manifest 核对，输出像素尺寸、文件格式和无覆盖行为已检查；NEF 使用 rawpy 相机白平衡和默认自动亮度。对本地 JPG/NEF 产物验证了 JPEG 格式和 6016×4016 有效画幅；另用合成 JPG 验证中文模板和参数调整；独立 Qt 窗口在 Linux offscreen 下完成启动、后台导出和缩略预览冒烟。重复目标与源目录输出均按预期拒绝，未创建伪成功文件。Ruff check/format、mypy `src scripts`、现有 pytest unit/gui（6 passed）、`pip check`、`git diff --check` 全部通过。视觉结果尚待用户确认，NEF 色调与相机 JPG 有差异；元数据策略尚未实现，产物不能作为正式交付图像。参见 `docs/linux-demo.md`。

## S2：Linux 侧模型与引擎验证（2026-10-01）

在用户同意继续后，按 S2 范围新增 GUI 无关领域模型、组件协议与显式注册表、三种预设、全批输出路径预检、串行引擎和本地配置基础。步骤执行测试全部使用临时合成文件及假组件，不读取或修改真实照片；现有主窗口公共接口保持不变。注册表拒绝未知/重复组件及版本不符，参数按组件 schema 在开跑前检查；JPG/NEF 的 RAW 步骤适用性和输出命名分别规划。已有目标、大小写折叠后的目标冲突、源目录别名及已标记输入会被预检阻止；提交辅助函数使用不覆盖目标的同卷硬链接。

定向 S2 测试 15 项通过：三预设、非法顺序、未知/自定义组件、参数、全批预检、失败隔离、取消保留已完成项、源文件外部变化、配置重启/备份恢复及输出保护。Ruff check/format、mypy `src scripts`、全部 unit/gui 测试（21 passed）、`pip check` 和 `git diff --check` 均通过。配置仅写本地用户配置目录或测试临时路径，未提交任何用户素材。

**计划偏差与门禁：** S1 的 Windows 锁定安装、真实 ExifTool `-ver` 和 Windows 空 GUI 仍未完成；本段仅是 Linux 侧 S2 实现和验证，不能将 S1/S2 标记为正式验收，也未进入 S3 的真实 GPS 写入。正式引擎的文件事务和元数据接入仍需按后续阶段验证。

## S3 JPG 坐标闭环及提前的 GPS-only EXE 原型（2026-10-01）

用户追加顺序为“先集中批量实现坐标写入功能，先编译一个 exe，再做水印模块”，指定 PyInstaller，并明确用量暂停规则只看五小时额度。本节是相对计划 `S3→S4→S5→…→S9` 的授权偏差：先完成 JPG 批量 GPS 与 GPS-only 构建原型，不将其认定为正式 S3 或 S9 验收。未提交 GitHub。

ExifTool 13.59 适配层在同卷临时副本上清除旧 GPS 字段，显式写入纬度、纬度方向、经度、经度方向，随后独立读回；使用 UTF-8 参数流处理 Windows 中文路径。CSV 入口默认整批预检，`--execute` 才创建目标；重复行、已有目标、无效坐标和 NEF 行在预检时拒绝。旧高度等附属 GPS 字段须显式确认清理。源片写前写后比较 SHA-256，JPG 像素不重编码。CSV 与本地使用方法见 `docs/gps-prototype.md`。

| 检查 | 结果 | 限制 |
| --- | --- | --- |
| 真实 ExifTool JPG 集成 | 通过 | 合成 JPG、用户 Nikon Z 5 JPG、旧附属 GPS、负坐标/零值及两图 CSV 批量测试；原片哈希和 JPEG 解码像素保持一致。 |
| NEF 诊断副本 | 局部通过，批量禁用 | 用户 Nikon Z 5 NEF 的 RAW mosaic、尺寸、关键相机字段及嵌入预览解码像素一致；嵌入预览 JPEG 字节发生变化，尚无独立 Nikon 查看器抽验。位置步骤默认阻止 NEF。 |
| Linux 冻结原型 | 通过 | PyInstaller 6.22.3 onedir 生成 ELF，捆绑 Linux ExifTool 13.59；两张合成 JPG 的预检、写入、读回、源片哈希与像素检查通过。该 ELF 不是 Windows EXE。 |
| Windows 目录版 EXE | Wine 下通过，原生 Windows 待测 | 官方 Windows Python 3.12.3 x64 与锁定的 PyInstaller 6.22.3 及其轮子在隔离 Wine 容器构建 PE32+ x86-64；中文路径及两张合成 JPG 执行成功，独立 ExifTool 读回误差 ≤1e-6 度，源片无 GPS，像素一致。 |
| Windows 单文件 EXE | 已构建，运行未通过 | `dist/gps-win-onefile/AutoImageMarkGps.exe`，19,772,312 字节，SHA-256 `316281c7a7c4eab2155b24bacbbc201778f57d7e0c93e6fd581da4b000b888e0`。Wine 启动时报 `Security validation failure: failed to obtain executable path for originating onefile parent process!`，因此不能声称单文件可运行；须在原生 Windows 完成冒烟。 |
| 资源审计 | 通过 | PyInstaller 归档含 `LICENSE`、ExifTool 可执行文件和其许可文件；未发现私有照片、字体或签名。`build/`、`dist/`、`tools/`、`demo-output/` 保持忽略且只在本地。 |
| 回归与静态检查 | 通过 | 全部 unit/integration/gui 27 passed；Ruff check/format、mypy、`pip check`、`git diff --check` 通过。 |

正式 S1 仍需原生 Windows 锁定安装、空 GUI 与 ExifTool 验证；正式 S3 仍需 NEF 独立查看器验收。此次 EXE 仅含 GPS 命令行功能，正式 S9 的 GUI、水印、许可清单、干净 Windows 环境验证和发布检查均未完成。水印模块尚未接入正式工作流。

## S5 单图水印模块初步实现（2026-10-01）

在 GPS-only EXE 原型构建后，新增独立透明层渲染与 JPEG 准备服务。调用方显式传入本机字体、签名路径，未把它们复制进源码或 EXE。默认模板按 36 pt、300 ppi 基准换算；三类内容使用半角 `|`，签名等比缩放并按源 Alpha 乘一次可配置不透明度。字号、签名宽、边距、颜色、拉丁/中文/签名不透明度、四角锚点和偏移可覆盖。源 JPEG 先执行一次 EXIF 方向变换；有 ICC 时转换成 sRGB 并携带匹配配置，无 ICC 的 RGB 给出假设警告，无 ICC 的 CMYK 拒绝。

本地三类模板透明层、边距、Alpha、参数重排及单图合成 6 项测试通过；JPEG 方向、sRGB ICC 和无 ICC CMYK 3 项测试通过。全量 unit/integration/gui 回归 36 项通过。使用已登记的 Nikon Z 5 JPG 在忽略目录生成 `demo-output/s5-watermark-jpg-preview.jpg`（6016×4016），源片 SHA-256 保持不变。该 JPEG 仅供本地视觉检查，尚未传递原片的完整拍摄元数据；组内对齐 Q4、三类人工视觉认可、批量集成、NEF 显影及最终元数据白名单仍待后续阶段。


## 2026-10-02：GPS 预览发布与 S5 本地 JPEG 渲染

GPS 图形版 `v0.2.0-rc.2` 已从提交 `3eb74b0` 构建并发布；原生 Windows CI、onedir/onefile 冻结自检、Linux DEB 构建及下载回读 SHA256 校验均通过。坐标列表页面可维护、导入/导出、应用到勾选照片并从备份恢复。按用户本次指示，Windows 便携 EXE 的 `locations.json` 放在 EXE 同目录，覆盖了计划第 5 节对用户配置目录的默认建议。此包只支持 JPG/JPEG 坐标写入；NEF 和水印仍不在公开包内。

S5 本地单图 JPEG 水印预览提交为 `bec04b2`。三类模板使用本地 `TrajanPro-Bold.otf`、方正字体及 `NAME.png`；三份资源哈希与 manifest 一致，公开 wheel 只含 `default_templates.json`，没有私人素材。本地真实素材定向测试 16 项、全量 unit/integration/gui 测试 74 项通过；Ruff、mypy、`pip check` 通过。Windows CI `36962898376` 通过 wheel 内容检查及不依赖私人素材的测试；真实素材测试只在本地运行。航空、铁路和风光预览均为 6016×4016 JPEG，位于被忽略的 `demo-output/s5-review-2026-10-02/`，源 JPG 哈希仍为 `f3f5e3e3b22d3361d66129da2c8bc73e657be9d07e9872bcd377e6bf9aba6ab3`。预览只用于视觉审查，不保留完整 EXIF/GPS。

**未完成门禁：**三类模板的视觉认可及签名组内对齐 Q4 已于 2026-10-02 获用户确认；NEF GPS 仍待独立 Nikon 查看器确认；S6 的最终元数据白名单、NEF 显影与 JPG/NEF 工作流集成尚未开始。

2026-10-02 用户明确回复“确认，继续工作”，认可 `s5-review-2026-10-02` 中三类预览。S6 先实现 JPG/JPEG 的正式水印和位置+水印流水线；NEF 图像处理仍按用户此前的 JPG-only 指示暂缓。

## 2026-10-02：S6 JPG/JPEG 后端集成

已新增 `services/metadata.py` 和真实 `WatermarkStep`。组合流程从已定位副本传递 GPS，白名单保留拍摄时间、相机/通用镜头与曝光、GPS、原有版权/作者；导出更新方向、尺寸和颜色信息，不复制 MakerNotes 或旧缩略图。正式流水线输出仍为 `_marked.jpg`，原片哈希不变。水印配置与素材指纹在预检时固定；无 ICC 的假设进入逐图警告，失败或提交前取消清理未提交产物。

元数据/GPS 定向测试 8 项通过，JPG 流水线定向测试 8 项通过（含本地 Nikon Z 5），全量回归 86 项通过；Ruff check/format、mypy、`pip check` 通过。重新构建 Linux GPS-only onedir，并运行窗口、坐标列表、ExifTool/GPS、原片与像素冻结自检通过，验证 GPS 路径不加载水印字体或 RAW 依赖。原生 Windows CI 增加真实 ExifTool 与合成字体流水线检查，私人素材仍仅在本地检查。

本地正式组合输出位于忽略目录 `demo-output/s6-jpg-gps/DSC_0168_marked.jpg`，使用既有 GPS 试验坐标；坐标不记入此公开文档。该图已独立读回相机、拍摄日期、方向、尺寸及 GPS。NEF 图像处理继续暂缓，独立 Nikon 查看器验收也仍未取得；本节不宣称完整 S6、S7 或正式水印发布通过。

## 2026-10-02：当前范围调整

用户要求先试验非标准尺寸 `DSC_0387.jpg`，本期只完善 JPG/JPEG 的坐标、水印、组合流程和图形页面。NEF GPS、显影、水印均移入后续版本，当前 GUI 不导入 NEF；既有接口保留。本期 S6–S10 不再以 NEF 查看器认可为前置。前一轮的原生 Windows CI（`36974383463`，提交 `e5f279d`）已确认成功。

### DSC_0387 非标准画幅试验

真实 JPG 5038×3363（原像素保留），使用航空试验内容 `DSC-0387`（文件标识，并非推断飞机注册号）、原拍摄日 2026-09-26；正式水印-only 输出在忽略目录 `demo-output/dsc0387-adaptive/DSC_0387_marked.jpg`。按 min 比例自适应后字体 126 px、签名有效宽 251 px、可见右/下边距 21 px；拍摄时间、sRGB ICC、300 DPI 和方向字段通过读回，原片 SHA-256 不变，无警告。新增不同画幅、半尺寸、竖幅、方幅、全景及 DPI 不影响布局的合成素材回归；定向缩放和流水线共 19 项通过，Ruff、mypy、diff 检查通过。

### S7：表格和本地设置基础

新增 `ui/photo_table.py` 的 QAbstractTableModel 与稳定 ID 排序编辑、JPG-only 拖放入口，以及 `ui/settings_dialog.py` 的本地素材/face、字号、签名宽、位置、颜色、不透明度、JPEG 参数、保存个人默认与恢复项目默认。`services/storage.py` 保存带 schema 的私有设置 JSON，原子更新并保留有效备份；损坏文件不会被静默覆盖。资源解析不依赖 cwd，公开版引用 EXE 旁可选 data 或用户路径，不捆绑素材。共享像素缩放与日期配置入口供下一步异步预览使用；修正表格日期来源传给水印报告的字段。相关 GUI/存储/缩放/依赖隔离 21 项通过，Ruff 和 mypy 通过；主窗口与异步预览尚待连接。

### S7：异步预览与可取消预检

`ui/workers.py` 新增后台元数据、整批预检和预览任务；`ui/preview_panel.py` 只运行一个预览任务并合并待办，按 generation 丢弃过期结果，不把全尺寸图像留在 GUI 缓存。提供适应画面、100% 水印局部、深浅/棋盘背景，以及把拖动距离换算回原图像素的信号。`build_plan` 新增可选取消事件，保持既有调用有效，在照片/步骤边界停止预检。真实合成 JPEG 预览、过期结果、拖动和原坐标 GUI 回归等 16 项通过；Ruff、mypy 通过。主页面连接与批量交互仍在下一步。

### 按用户指定内容重做 DSC_0387

后续用户明确指定 B-1356、2026/9/26 及拍摄坐标后，重新执行正式位置+水印流水线至 `demo-output/dsc0387-b1356-gps/DSC_0387_marked.jpg`。水印日粒度显示为 2026/09/26；指定 GPS 读回误差小于 1e-6，像素 5038×3363、拍摄时间 2026:09:26 15:33:31 和原片哈希保持不变。真实坐标和图像仅保存在本地，不进入公开记录。

### S7：表格导入交互

新增 `ui/import_dialog.py`，在后台读取 CSV/TSV/XLSX 或粘贴 TSV，提供明确编码、工作表、可选列映射、唯一照片匹配预览；错误或歧义时禁止应用，输入改变后旧预览作废。现有表格服务新增可选 column_mapping，默认行为保持不变。导入 GUI 与服务回归 11 项通过，Ruff、mypy 通过。

### S7：完整 JPG 页面连接与界面优化

默认入口改为三种 JPG 流程的主页面，保留 `--gps-only` 和 `GpsWindow` 公共接口。`ui/main_window.py` 编排服务、模型与后台任务；工作流卡片固定先坐标再水印，可存本地预设；批次预检全异步，运行/取消/关闭时安全收尾。接入勾选行批量输入、逐行编辑、地点列表、导入预览、字体/签名设置、实时预览、原像素局部、位置拖动、失败项重试及结果报告。输出报告不包含专门的坐标字段。关于页面包含版本、©BG2FOU、项目链接及 CC BY-SA 4.0。界面采用浅色卡片和青色主操作，状态列固定靠前；坐标列表分行布局，长路径不挤占主要操作。

用指定非标准画幅样片生成本地页面截图（忽略目录），并核对 5038×3363、126 px 字号、251 px 签名。增加原生服务 GUI 测试：组合 GPS 不回退、无素材/无拍摄日期仍可 GPS-only、坏行整批阻止、预检取消关闭等待及 NEF 不导入。完整 JPG 回归 110 项通过、2 个 RAW 用例主动排除；后续新增用户给出的无补零日期 `2026/9/26` 支持并定向复测。Ruff、mypy 和 pip check 通过。

修复 Windows 中文 CSV 测试缺编码（`4659737`），其单元测试已原生通过；随后发现 GUI 测试先于 ExifTool 安装，已将工具准备提前（`8386ac2`）。pytest 采用 importlib 模式以支持计划中的同名 unit/integration 测试。GPS 构建配置使用独立启动 shim，保持旧包默认只开坐标页面；完整 JPG 构建和发布仍是 S9–S10，不能把源码 GUI 验证当作发布验收。

补充：GUI 与日期定向回归 36 项通过；逐图预检错误现在通过稳定 ID 标红对应状态行，保留原异常类型及错误上下文。原生 Windows CI `36981454550` 已确认通过 UTF-8、工具准备顺序、合成字体预览和真实元数据检查；完整主页面的新提交仍须在其自身 SHA 上再次验证。

### S8：JPG 兼容性与资源边界

补齐 EXIF Orientation 1–8、baseline/progressive、灰度图、损坏及模式不匹配 ICC、大图解码前拒绝，以及超长内容在位图分配前拒绝。预览/水印 JPEG 限制 6000 万像素，签名原图限制 1600 万像素，文字和缩放签名不得超过画布；超限报错而非降低原片尺寸。坐标-only 不解码或重编码。用户手册和架构同步当前完整 JPG GUI、异步预检及取消语义。

全量 JPG unit/integration/gui 126 passed、2 个 RAW 用例按当前范围排除；domain/services/workflow 行覆盖率 90%（1506 行，149 未覆盖），超过计划建议的 85%。Ruff、mypy 和差异检查通过。Linux 另用系统安装的 AdobeRGB1998 与 FOGRA39L_coated ICC 合成 RGB/CMYK JPEG 验证向 RGB/sRGB 转换；这些 ICC 未复制、未提交，不能将此本地检查描述为 Windows CI 覆盖。

完整 JPG 页面提交 `aa5d691` 的原生 Windows CI `36981989418` 已通过：单元 58、GUI 22、元数据/流水线 12 项通过（1 个视觉用例未运行），静态检查及公开模板打包通过。用户补报的预览失败日志对应较早提交 `4659737` 的 CI `36981054178`；其 ExifTool 准备顺序已在 `8386ac2` 修复，新的检查确实执行了该异步预览用例。

### S8：100 副本图形批次与人工外观认可

Linux x86_64、Intel N95（4 核）、7.5 GiB 内存，使用同一张授权 5038×3363 JPG 的 100 个硬链接副本，经完整主页面运行坐标+水印流水线。这是重复场景的批处理压力检查，不是 100 张不同照片的兼容性覆盖。主批次 100 成功、0 失败，含整批预检总耗时 512.824 秒；主批次主进程峰值 RSS 416.3 MiB，包含随后取消轮次的全程峰值 594.7 MiB。100 ms GUI 定时器在主批次的最大调度间隔 178.4 ms；这是事件循环响应记录，不等同于人工操作延迟。ExifTool 子进程内存未计入该主进程 RSS。

第二轮仍从图形页面整批预检后运行，在首张提交后取消：1 成功、99 取消、0 失败，取消信号后约 99 ms 完成状态收尾。磁盘成品数与成功数一致，无临时半成品；原片 SHA-256 不变，关闭后无在途工作线程。全部素材、原片、副本、输出、脚本和原始性能报告仅保留在本地忽略目录。首次检查已通过功能断言但报告未在退出前保存；补录进程一度收到终止信号，最后重新执行并完整记录上述结果，不把终止过程计为应用成功测试。

用户在查看三类本地水印样例后回复“认可，继续工作”，本期字体、签名、组内对齐及尺寸人工外观验收已记录；其认可不代替尚未执行的冻结包检查。新页面本地截图已同步最终卡片样式，公开仓库不提交该截图。

当前原生 Windows 修复提交 `04b8495` 的 CI `36983259250` 通过：单元 73、GUI 22、元数据/流水线 12 项通过（1 个视觉用例按素材边界未运行），Ruff、格式、mypy 和公开模板打包检查均通过。全量 Linux JPG 回归 126 项通过、2 个 RAW 用例排除。完整应用 S9–S10 的冻结构建、许可附件、干净系统检查和新 Release 尚未完成，既有 GPS Release 不包含完整 JPG 水印功能。

2026-10-03：上次文档提交因自动审批检查额度耗尽而未执行。说明恢复门槛后，用户再次明确要求继续工作，并要求及时推送、发布；按此次直接指示恢复执行，保留后续五小时剩余额度低于 5% 的暂停规则。


### S9：冻结自测入口

完整 JPG 版新增 `--self-test-jpg --report`；既有 GPS `--self-test` 保持有效，GPS 包明确排除完整 JPG 自测模块。完整自测在临时目录生成自有方块字形字体、纯色签名、带方向/日期/sRGB 的 JPG 和 XLSX；通过真实主页面执行 GPS+水印并读回，检查设置、地点保存、预览、方向、ICC、原日期、源哈希、报告及线程/临时文件清理。源码环境自测通过，主页面/预览/启动定向 GUI 8 项通过，Ruff 与 mypy 通过。`scripts/smoke_exe.py` 从仓库外的临时 cwd 启动冻结程序，移除 AIM_EXIFTOOL/PYTHONPATH 并要求 bundled ExifTool 和 frozen 标志；冻结产物仍待实际构建验证。


### S9：完整 JPG Linux 冻结包与发布准备

版本提升为 0.3.0rc1（拟发布 v0.3.0-rc.1），两平台复用单一 spec。固定版本上游许可归档经 SHA256 验证；文本许可、Qt 归属元数据、Python 依赖许可和实际 Linux 系统库版权随包收集。公开包只包含公开模板、程序、ExifTool 与许可，不收集 data、私人字体/签名或 RAW 实现。目录 ZIP 同时提供可替换的依赖库。项目 CC BY-SA 4.0 保持不变，EXE 未做代码签名。

Linux 本地完整 onedir 与 DEB（约 72 MB）构建通过；目录程序和 DEB 解包程序均在仓库外临时 cwd 离线自测通过，12 类检查全部成功：GUI、设置、地点、预览、GPS+水印、方向、ICC、原日期、原片哈希、清理、报告、XLSX。包内容未发现照片、字体、签名或 rawpy/LibRaw。Windows 原生完整 onedir/onefile、中文含空格路径和新发布链尚待自身提交 CI 验证；不将此本地结果认定为完成 S9/S10。

新增 assemble_release/stage_jpg_artifact 两个构建辅助脚本以落实计划中的资源审计、版本化资产及校验清单，已同步计划文件清单；这是实现拆分，不扩展产品功能。新增完整 release workflow 保留旧 GPS 发布流程，以未发布草稿恢复、同标签互斥、下载回读校验及禁止覆盖已发布包为门禁。

发布准备本地检查：与公开 CI 相同且不依赖私人素材的 JPG 单元/GUI/元数据/流水线 107 passed、1 个视觉用例排除；Ruff、格式、mypy、git diff 检查通过；固定版本 actionlint 1.7.7 校验新 release workflow 通过。上一次源码自测提交 ae43fdf 的原生 Windows CI 37095300564 已通过。


首次完整构建运行 37095755913 的 Windows 混合 unit/GUI/integration 进程在 Qt 事件处理中 Aborted；相同源提交 5ce2867 的现有分进程 CI 37095744525 已成功。没有足够日志判定该混合进程退出的应用根因，发布工作流改为与现有 CI 相同的三个独立进程，GUI 输出逐用例日志，等待原生重测。离线冻结冒烟同时将 PATH 限制为系统目录并清除外部 Qt 插件路径，以检查不使用安装的 Python/ExifTool/Qt。


第二轮 37095957279：两个平台的分进程 107 项回归通过；Linux 完整 DEB、解包自测、资源审计成功。Windows onedir 实际冻结完成后，冒烟启动器把 Windows 环境复制为普通 dict 后按 SystemRoot 混合大小写取键，导致 KeyError（尚未启动成品）。修正为使用 Windows 原生大小写不敏感的 os.environ 读取系统目录，保持 PATH 隔离；等待同提交原生重测，不把“冻结完成”算作冒烟成功。


第三轮 37096248316：Windows 冻结成品实际启动，自测因设置路径比较失败而停止。Linux 把 TMPDIR 指向目录软链接，可稳定复现相同 Settings cannot be reopened：存储契约把路径 resolve 后保存，而自测期望仍保留目录别名。将自测临时根目录先 resolve，不修改存储 API；新增启动回归从目录别名执行完整源码自测。Windows 临时目录的短路径别名可能触发这一差异，实际修复效果以新原生自测为准。


同一目录别名审查发现冻结归属检查也将已 resolve 的 ExifTool 路径与未 resolve 的 _MEIPASS 比较；一并解析 bundle 后再做包含关系检查，避免 onefile 解包路径别名造成误判。仍要求 ExifTool 确实位于真实冻结目录，不降低归属门禁。


运行 37096722648：Windows ASCII 目录版完整离线自测全部通过，中文含空格安装目录失败，日志显示官方 tiny launcher 把中文目录转成 ?? 后找不到 Perl DLL。固定官方包已包含 perl.exe、exiftool.pl 和完整 lib；适配器在该运行时存在时直接用包内 Perl、相对脚本/库路径及 Unicode cwd，不依赖外部 Perl，不改版本或公开 ExifTool API。照片参数转绝对路径保持原相对路径语义；增加原生 Windows 中文运行时目录 GPS 写回测试。许可收集同时把原包 ExifTool 许可、Strawberry Perl 许可 ZIP 和 CC0 launcher readme 纳入附件，原分发包仍完整捆绑。尚待新原生测试确认。


运行 37097210324：Windows 源码 73 unit、23 GUI、13 metadata/pipeline 全部通过（1 视觉用例排除），包含真实中文目录 Perl GPS；ASCII 冻结自测通过，中文冻结目录的 Perl 报 exiftool.pl Invalid argument，未发布。按 PyInstaller 6.22.3 官方子进程文档，在 Windows 冻结进程创建 Perl 前临时清除 DLL 搜索目录，并从子进程 PATH 去掉冻结库目录；创建后立即恢复父进程 DLL 路径，锁仅覆盖启动，不阻塞整个处理。超时杀死并回收子进程，保持原超时接口。原生中文运行时回归同时模拟冻结 DLL 搜索路径并断言恢复，最终仍须真实冻结自测通过；不预先声称这是唯一根因。


运行 37097707362：原生 Windows 源码回归和 DLL 路径恢复断言均通过；ASCII 目录冻结自测全部通过，中文冻结目录仍报 perl exiftool.pl Invalid argument，DLL 隔离没有消除此问题。Linux 完整包通过。S9 中文目录门禁未满足，S10 标签和新 Release 未创建。新增失败诊断仅比对固定包与冻结包内 Perl/script 哈希，并从外部 Python 在系统 PATH 下执行相同 Perl、读取 DOS 短路径来区分内容与启动路径问题；不删除门禁，不改工具版本，不猜测最终原因。


运行 37098067587：中文冻结目录仍报 Perl Invalid argument，随后诊断脚本输出中文路径时因 Windows 默认 cp1252 编码退出，未得到所需比对结果。Windows 发布构建任务显式设置 PYTHONIOENCODING=utf-8，只改变 Python 标准输入输出编码，不改变 ExifTool 参数、工具版本或中文目录门禁。等待新原生诊断，不认定主故障已修复。五小时额度已可靠恢复至剩余 97%，符合计划恢复条件。


运行 37112362266：UTF-8 诊断输出通过。原包与冻结包的 perl.exe、perl532.dll、exiftool.pl 哈希一致；原 ASCII 目录直接执行返回 13.59，中文目录从外部 Python 直接执行仍报 Invalid argument。GetShortPathNameW 返回原中文路径，不能解决此卷没有 DOS 别名的限制，说明问题不要求冻结父进程即可复现。适配器优先选无损系统代码页路径/现有 DOS 别名；无法表示的支持目录复制到对象所属的临时目录，使用相同 Perl/脚本/库，释放对象或初始化失败时清理。新增真实 Windows 构建卷中文目录 GPS/像素、运行时全部文件哈希及临时清理回归；保留冻结中文路径冒烟，最终以新原生结果验收。临时目录同样不可表示时明确报错，不改全局系统设置。
