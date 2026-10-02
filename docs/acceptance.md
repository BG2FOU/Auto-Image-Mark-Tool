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
| 字体、签名、字号、签名宽度和位置定制 | 渲染参数已实现，GUI 设置待做 | 本地预览可替换素材、调整字号、签名宽度、颜色、透明度、四角锚点与偏移；个人默认的保存/恢复尚未接入。 |
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
| S7–S8 | 未开始完整阶段 | 坐标 GUI 已按用户优先顺序交付；水印 GUI 和完整应用验收待做。 |
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
