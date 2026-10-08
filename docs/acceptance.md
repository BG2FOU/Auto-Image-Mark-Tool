# 验收记录

本文件记录 `docs/plan.md` 的实际进度。未列为通过的项目不能据此声称已验收。

当前交付为 [v0.4.0-rc.1](https://github.com/BG2FOU/Auto-Image-Mark-Tool/releases/tag/v0.4.0-rc.1)：JPG 三流程、已验证 Nikon Z 5 NEF 坐标副本写入、海拔和离线批量坐标转换。发布源 `2a0ef17` 的 CI `37130710745` 与正式发布/公开 Windows 下载流程 `37131275318` 均成功；全部公开附件及实际下载 DEB 已验证。按用户要求，本次测试和发布完成后暂停工作。历史日期记录保留当时结论。

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
| JPG/NEF 真实样片及机型 | JPG 与已验证 NEF 坐标通过 | Nikon Z 5 三份照片只留本地，哈希见 manifest；用户已确认 NEF 试写独立检查通过。NEF 只开放已测试的 14-bit lossless / 6040×4032 编码，显影与水印暂缓。 |
| Photoshop 字号单位与 NEF 水印输出 | 已确认 | 36 pt；在 300 ppi 基准画布换算为 150 px。NEF 加水印显影后导出 JPEG。 |
| 组内对齐 | 已确认当前三类预览 | 用户于 2026-10-02 确认三类预览，默认可见底部对齐与 36 pt、300 px 签名、25 px 可见边距获认可；参数仍可调整。 |
| 素材与许可证 | 最新变更已执行 | 当前项目 CC BY-NC-SA 4.0；历史发布及第三方许可不重写。照片、签名、字体只留本地，不提交到 GitHub，也不纳入公开构建物。 |

### 第 10 节决策表

| 编号 | 当前状态 | 处理边界 |
| --- | --- | --- |
| Q1 | 已确认 | Photoshop 36 pt；300 ppi 基准下为 150 px。 |
| Q4 | 已确认当前默认 | 2026-10-02 用户确认三类本地预览的字号、签名组内对齐和可见边距。 |
| Q5 | 已确认 | 字体只留本地，不提交或捆绑公开 EXE。 |
| Q6 | NEF GPS 已授权并验收；显影/水印暂缓 | 后续坐标阶段只输出同名 NEF 副本，用户已确认试验通过；NEF 加水印显影并导出 JPEG 的规则继续留给后续版本。 |
| Q7 | JPG/JPEG 与已验证 NEF | 新版本 NEF 坐标限 Nikon Z 5、14-bit lossless、RAW 6040×4032；其他格式/机型/编码不承诺。 |
| Q8 | 用户追加变更已执行 | 当前项目使用 CC BY-NC-SA 4.0；官方全文、包元数据、关于和构建声明同步，旧发布及第三方许可保留原状。 |
| Q9 | 推荐默认已实现 | 提供坐标、水印、坐标+水印三预设；组合流程只提交最终结果，临时中间副本清理。未将推荐默认记为用户逐项确认。 |
| Q10 | 自适应已实现并测试 | 按方向适配的 min 比例统一缩放；用户指定的非标准画幅 JPG 已试验，三类本地外观已获认可，自动化覆盖竖图等画幅。 |
| Q11 | 推荐边界已实现 | 颜色可调，风光按字符角色选字体；航空/铁路按大写编号校验，不静默改写输入。 |
| Q12 | 默认规则和映射已实现 | 中文/自定义列映射、导入预览及唯一匹配已接入；日期采用手动 > 表格 > EXIF > 明确允许的 CreateDate。用户特定表格尚无额外承诺。 |
| Q13 | 推荐默认已实现 | WGS84 十进制度；按用户新要求写入海拔，缺省 0，地点名保存在本地列表。其他附属 GPS 的清理仍要求明确选择，不写地名。 |
| Q14 | 本期保护规则已实现 | 正式三种流程均写输出副本；拒绝源目录、已有目标及重复加水印输入，本期没有源片覆盖模式。 |
| Q15 | JPG 默认已实现并验收；RAW 暂缓 | 默认 JPEG 95/4:4:4、sRGB，保留有效画幅与已有 DPI；本地样片已获外观认可，参数可调。RAW 色调不在本期验收范围。 |
| Q16 | 当前 0.4.0rc1 冻结包通过自动化 | Windows x64 onedir/onefile、中文含空格路径、公开 EXE 下载后自测及 Linux DEB 已通过；用户于 2026-10-03 确认人工核验完成；未提供系统版本及逐项记录。 |
| Q17 | 当前版本已授权并发布 | 用户授权逐步提交、推送及发布；`v0.4.0-rc.1` 标签触发完整构建、草稿核验、公开发布和下载验收，历史版本保留。 |
| Q18 | 已确认 | `NAME.png` 只留本地，不提交或捆绑公开 EXE；本地开发版本可直接加载。 |

## 阶段验证

| 阶段 | 结果 | 未完成项 |
| --- | --- | --- |
| S0 | 本期决策与素材已登记 | Q1/Q4/Q5/Q8/Q18 已确认；其他默认规则的实际边界见上表，未伪造逐项确认。 |
| S1 | 完整 JPG 工具链通过 | 锁定安装、ExifTool 13.59、Qt、静态检查已在 Windows/Linux CI 验证。 |
| S2 | 模型与引擎通过 | 三预设、稳定 ID、全批预检、取消、失败隔离及本地配置恢复已测试。 |
| S3 | JPG 与已验证 NEF 坐标闭环通过 | NEF 实际样片、RAW/预览/MakerNotes 和原片保护通过，用户确认独立软件抽验；编码范围见后续阶段记录。 |
| S4 | 日期、表格与 GUI 导入通过 | CSV/TSV/XLSX/剪贴板映射、预览、应用和日期优先级已实现并测试。 |
| S5 | 自适应水印通过，默认外观已确认 | 字体角色、pt、Alpha、缩放、边距和定制已测试；三类本地外观获用户认可。 |
| S6 | JPG 后端集成通过；NEF 显影/水印延后 | JPG 三流程与当前 GPS、元数据白名单、方向/ICC、事务和取消已验证；NEF 仅坐标。 |
| S7 | JPG 页面已验收，NEF 坐标接入通过 | 地点列表、表格编辑/导入、设置、预览、拖动、后台执行/取消/重试及报告已接入；实机人工检查见下节。 |
| S8 | 本期集成回归与 Linux 压力检查通过 | Linux 全量 JPG 回归、90% 核心覆盖率及 100 副本批次已有记录；跨机型/其他系统不作泛化声明。 |
| S9 | 当前 EXE/ZIP/DEB 自动化通过；已有 JPG/NEF 人工确认 | Windows 两种包及中文路径、Linux DEB、许可/私人资源审计通过；人工结论来自用户确认，具体环境/逐项明细未提供；EXE 未签名。 |
| S10 | 当前预发布链通过，随后暂停 | `v0.4.0-rc.1` 标签、EXE/ZIP/DEB、哈希、公开 EXE/DEB 下载后运行已验证。 |

## 桌面人工验收（用户确认完成）

2026-10-03 用户明确反馈“已经人工核验完成”。据此关闭本期 JPG 人工验收收尾项。用户未提供操作系统版本、缩放比例和逐项检查日志，以下保留复查清单，不将整体确认写成特定 Windows 版本或逐项实测数据。当前会话本身仍只有 Linux。

| 检查 | 操作与通过条件 | 结果 |
| --- | --- | --- |
| 环境与启动 | 记录 Windows 版本/内部版本号、标准用户、屏幕分辨率和缩放比例；在可写的中文含空格目录双击公开 EXE，无额外 Python/ExifTool 安装、管理员要求或意外控制台；关于显示 0.3.0rc1、©BG2FOU 与项目链接。 | 用户整体确认；逐项记录未提供 |
| 页面可操作 | 记录实际缩放比例；调整窗口，确认导入、表格编辑、设置、输出目录、开始/取消均可见且可操作。 | 用户整体确认；逐项记录未提供 |
| 地点持久化 | 新增两处测试地点，应用到不同勾选行；退出重开仍保留，EXE 旁 locations.json 存在；排序后再次应用应命中勾选照片。 | 用户整体确认；逐项记录未提供 |
| 坐标流程 | 未选择字体/签名也可导出 JPG 副本；名称不变，查看器可打开，GPS 与输入一致；原片哈希不变。 | 用户整体确认；逐项记录未提供 |
| 表格与日期 | CSV/XLSX/剪贴板各导入一次，先预览再应用；重复/错配行能提示，日期日粒度正确，原 EXIF 拍摄时间保留。 | 用户整体确认；逐项记录未提供 |
| 水印与定制 | 本地选择字体/签名，分别导出航空/铁路/风光；检查非标准画幅与竖图，修改字号/位置、保存个人默认后重启，预览与成品对应；恢复项目默认的入口可用。 | 用户整体确认；逐项记录未提供 |
| 组合元数据 | 位置+水印成品保留新 GPS、拍摄日期、正确方向及 ICC；可由本地已有的独立查看器核查，未能核查的字段单独记待验。 | 用户整体确认；逐项记录未提供 |
| 批量与失败收尾 | 使用本地 JPG 或副本组成批次，记录数量与响应；取消/关闭能收尾，已成功文件保留；已有输出、不可写输出目录和损坏 JPG 有明确反馈，无伪成功成品。 | 用户整体确认；逐项记录未提供 |
| 原片与素材保护 | 对测试前后原片及字体/签名计算哈希，应一致；只报告检查结论，不上传私人照片、坐标列表或素材。 | 用户整体确认；逐项记录未提供 |

后续复查时可记录：Windows 版本、缩放比例、EXE/ZIP 类型、通过项目、失败时的操作与错误文本；本地真实路径可脱敏。不要为填写此表假设未执行项目通过。

若需要先确认本机运行环境，可在下载 EXE 的目录打开 PowerShell，运行已有冻结自测（只生成临时合成资源）：

```powershell
$jpgExe = (Resolve-Path '.\AutoImageMarkTool-v0.3.0-rc.1-windows-x64.exe').Path
$jpgProcess = Start-Process -FilePath $jpgExe -WorkingDirectory $PWD.Path -ArgumentList '--self-test-jpg --report jpg-self-test.json' -Wait -PassThru
$jpgProcess.ExitCode
Get-Content -LiteralPath '.\jpg-self-test.json' -Encoding UTF8
```

退出码应为 0，报告应含 `version: 0.3.0rc1`、`frozen: true`、`ok: true` 及 12 类 checks。此报告仅用于环境诊断，该命令不是本次用户人工核验的证据。

## NEF 坐标后续阶段（2026-10-03）

用户已明确授权 NEF 仅写坐标，输出保持 NEF；显影和水印仍暂缓。JPG 的人工确认不转用于 NEF。

- 已用本地 Nikon Z 5、14-bit、NEFCompression=3（lossless）、RAW 6040×4032 样片在副本试写。原片哈希、rawpy 解码的 RAW mosaic/尺寸与预览像素、关键相机信息、MakerNotes 和 ExifTool 验证结果均一致，GPS 读回正确。
- 本地诊断副本在 `demo-output/nef-gps-review/DSC_0168.NEF`；原片、输出和本地检查 JSON 均不提交、不打包。该副本用于独立软件抽验，不是公开样片。
- 新增 `services/nef_gps.py`，专门完成编码范围检查及压缩 RAW/缩略图/嵌入 JPEG 数据、ExifIFD/MakerNotes 的写后比对，不包含 RAW 显影。这是第 6 节文件清单的增补，避免在仍暂缓的 raw 显影模块中混入坐标功能。
- 图形页面已接入 NEF 导入、坐标批处理、无 JPG 预览提示及水印前置阻止；用户随后明确反馈“NEF试验已检查，通过”，因此主页面开放该编码的坐标流程；底层 `LocationStep` 与旧独立 GPS 预览保留显式验收开关，其他机型/编码仍不放行。
- 冻结自测新增 `nef_scope`：拒绝改名的合成 JPEG 作为 NEF、NEF 不解码预览、水印批次阻止，以及不加载 rawpy。它只验证打包和拒绝路径，不替代真实 NEF 成功写入或独立查看器验收。该阶段源码自测 13 类检查通过；后续海拔/转换新增为 15 类。
- 用户追加海拔：GPS 同时写入高度/方向，列表和行级编辑支持，旧列表缺省 0；冻结自测增加负海拔及列表持久化检查。
- 本地回归（启用 NEF 后、海拔修改前）：140 passed、2 Windows 专属 skipped、1 visual deselected；Ruff/格式/mypy/Actionlint 通过，全部原片/字体/签名指纹不变。
- 独立软件抽验已由用户确认通过（2026-10-03），未提供软件名称/版本，不补写具体环境。新版本 0.4.0rc1 的 EXE/DEB 构建与发布验收正在进行；其他机型、12-bit 或其他压缩编码明确拒绝。

## 历史验证记录

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


中文程序路径门禁同时覆盖目录版和单文件版：onefile 构建后复制单个 EXE 至中文含空格目录，再从仓库外 cwd 执行完整离线自测，避免只用目录版结果推定单文件版通过。待原生运行确认。


S10 下载验收增加只读 Windows job：公开 Release 发布后，重新下载单文件 EXE、SHA256SUMS 和 BUILD_INFO，核对文件哈希、标签及源 SHA，再从中文含空格下载目录执行离线完整冻结自测。该 job 不安装项目依赖或 ExifTool，冒烟仍清除子进程 PYTHONPATH 并限制 PATH；结果独立记录，不将构建前自测称为下载验收。Linux 的公开 DEB 下载、解包与本地离线运行在发布后另行记录。


### S9–S10：完整 JPG 预发布与公开下载验收（2026-10-03）

已发布 [v0.3.0-rc.1](https://github.com/BG2FOU/Auto-Image-Mark-Tool/releases/tag/v0.3.0-rc.1)，公开时间 2026-10-03 17:41:02（UTC+8），为预发布而非草稿。发布源 SHA 为 `946ea9ad9c5c0b9218ff0d4b430bf5bcf2054cf2`，标签保持指向该提交；之后的文档提交不改变已有发布包。

- 发布源自身 [Windows CI 37113235645](https://github.com/BG2FOU/Auto-Image-Mark-Tool/actions/runs/37113235645) 成功。
- 修复预构建 [37112858696](https://github.com/BG2FOU/Auto-Image-Mark-Tool/actions/runs/37112858696) 成功，验证无 DOS 别名的中文目录运行时、复制字节一致和清理。
- 正式标签 [37113456901](https://github.com/BG2FOU/Auto-Image-Mark-Tool/actions/runs/37113456901) 全链成功：版本/提交校验、Windows/Linux 测试与构建、附件组装/审计、草稿下载核验、公开发布、Windows 公开 EXE 下载后运行。
- Windows 原生：73 unit、23 GUI、14 metadata/pipeline passed，1 个依赖私人素材的视觉用例排除；Ruff/格式/mypy 通过。目录版和单文件版均通过普通路径、中文含空格路径的完整冻结自测。Windows 2022 runner 使用系统 PATH 隔离，不能将此记录写成独立 Windows 10 桌面人工验收。
- Linux 原生：73 unit、23 GUI、12 metadata/pipeline passed；2 个 Windows 专项按平台 skip，1 个视觉用例排除。Ubuntu 24.04 / amd64 的目录程序、DEB 和解包程序完整冻结自测通过。
- Windows 公开下载：只读 job 下载发布 EXE、清单和 BUILD_INFO，文件哈希、版本标签、源 SHA 匹配；下载程序在中文含空格路径、仓库外 cwd、系统 PATH 下完成 12 类检查，未安装项目依赖或外部 ExifTool。
- Linux 公开下载：本地 Ubuntu 24.04.5 / glibc 2.39 下载全部 7 个附件，`check_release.py --tag v0.3.0-rc.1 --dist build/published-v0.3.0-rc.1` 成功；实际下载的 DEB 解包至忽略目录后，经 `smoke_exe.py` 完成同样 12 类检查。附件大小 EXE 76,148,569 字节、目录 ZIP 76,563,618 字节、DEB 82,037,518 字节。

12 类冻结检查为 GUI、设置、地点、预览、GPS+水印、方向、ICC、拍摄日期、源文件不变、清理、报告、XLSX。商用字体视觉认可沿用 S8 的本地人工记录，公共冻结测试只生成自有合成资源。原片及签名/两款字体指纹再次核对不变；公开资源审计通过。许可证仍为 CC BY-SA 4.0，完整第三方许可随包及 LICENSES.zip 提供。NEF 未纳入本期发布。

本轮故障修复与交付文件：

| 文件 | 内容 |
| --- | --- |
| `src/aim_tool/services/exiftool.py` | 无 DOS 别名时临时复制固定 Perl 支持运行时，保留 API、版本、DLL 隔离与清理 |
| `tests/integration/test_metadata.py` | 构建卷中文路径的实际 GPS/像素、完整运行时哈希和临时清理回归 |
| `.github/workflows/release.yml` | UTF-8 诊断、两种包的中文路径门禁、公开 EXE 下载后原生运行 |
| `README.md` | 完整 JPG 版公开下载入口 |
| `docs/user-guide.md` | 发行包启动方式和实际验证边界 |
| `docs/build-release.md` | 临时运行时兼容规则、固定工具链及标签验证方式 |
| `docs/releases/v0.3.0-rc.1.md` | 功能范围、下载方式、兼容限制 |
| `docs/plan.md` | 本期预发布状态及保留的人工验收项 |
| `docs/acceptance.md` | 根因诊断、各阶段检查、正式发布与下载证据 |

实现调整仅为处理固定 Perl 的 ANSI 路径限制而增加运行时临时副本；无工具升级、公共 API 改动、私人素材公开或格式范围扩大。保留的限制：EXE 未签名；独立 Windows 10 标准用户桌面人工验收尚未进行；没有 DOS 别名且 TEMP/LOCALAPPDATA 都无法由系统代码页表示时，需要设置可写的 ASCII TEMP；Linux 基线为 Ubuntu 24.04 / glibc 2.39，其他发行版尚未逐一验收。

## 本次追加范围：海拔、坐标转换与许可（2026-10-03）

- 海拔的 32 项定向检查与导入/行编辑的 13 项检查通过，源码冻结入口的负海拔/持久化自测通过。旧列表缺省高度 0，列表中的高度为米，负数写入 GPSAltitudeRef=1；高度更新不再当作未授权附属 GPS 清理，旧时间/方向等仍需明确清理。
- 坐标转换使用固定 eviltransform 提交 03ba58d92dfda57f8a1635f3805483c8fc10bd77 的公式；源归档 SHA256 已固定，原始 BSD 许可保留。公开测试向量仅以其上游测试精度比较；另与该提交的 Python 公式直接比较到 1e-12，不将数值残差解释为地面精度。
- 项目许可按用户要求改为 CC BY-NC-SA 4.0，LICENSE 与 CC 官方全文一致（仅规范末尾空白），包元数据 License-Expression 已核对，第三方许可不变。旧发布不回写。
- 完整本地回归（含真实样片及本地视觉资源）170 passed、2 Windows 专属 skipped；关闭转换后台线程的后续 3 项 GUI 检查通过，源码 15 类自测通过；Ruff/格式/mypy/Actionlint 与许可收集均通过。
- 本次正式构建/发布及公开下载验收通过，证据见下节。已按用户要求暂停，不启动后续 NEF 显影或水印工作。


## v0.4.0-rc.1 发布、下载验收与暂停（2026-10-03）

发布于 2026-10-03 23:00:52（UTC+8），为公开预发布，非草稿。源 SHA 和标签均为 `2a0ef1759a42db3d8224d105df1f2dc94b6a0865`；后续文档提交不改变标签或附件。

- [发布源 Windows CI 37130710745](https://github.com/BG2FOU/Auto-Image-Mark-Tool/actions/runs/37130710745)：105 unit、27 GUI、14 metadata/pipeline passed，1 个私人素材视觉用例 deselected；Ruff、格式、mypy 与打包资源检查通过。
- [正式发布流程 37131275318](https://github.com/BG2FOU/Auto-Image-Mark-Tool/actions/runs/37131275318)：prepare、Windows、Linux、assemble、publish、verify-published-windows 全部 success。Linux 为 105 unit、27 GUI、12 integration passed，2 个 Windows 专属 skipped，1 个私人素材视觉用例 deselected。Windows 两种冻结包均通过普通路径和中文含空格路径检查。
- [公开 Windows 下载检查](https://github.com/BG2FOU/Auto-Image-Mark-Tool/actions/runs/37131275318/job/111227980166)：重新下载 EXE，校验哈希、标签和源 SHA，在中文含空格路径离线完成 15 类自测；该 job 未安装项目依赖或外部 ExifTool。
- 本地公开下载：7 个附件下载至忽略目录 `build/published-v0.4.0-rc.1`，在标签源提交上执行 `check_release.py --tag v0.4.0-rc.1 --dist build/published-v0.4.0-rc.1` 通过。实际公开 DEB 解包后经 `smoke_exe.py` 验证，报告为 `version=0.4.0rc1, frozen=true, ok=true, exiftool=13.59`，15 类检查全部通过。
- `LICENSES.zip` 完整性和根项目 LICENSE 已核对；Windows/Linux 的 eviltransform BSD 原文与固定源一致。公开 DEB copyright 与当前项目 LICENSE 一致，公开 Windows ZIP 完整性与私人照片/字体/签名、rawpy/LibRaw 排除检查通过。7 份本地原片/素材 SHA256 再次核对不变。
- 用户报告的 `tests/gui/test_coordinate_converter.py` I001 来源为先前提交；修复 `2a0ef17` 在标准库和应用导入之间增加空行。修复后的 Windows CI 与正式 Release 已通过，当前文件再次 Ruff 检查通过；旧失败记录不覆盖或隐藏。

公开安装包大小：EXE 76,171,026 字节，ZIP 76,584,244 字节，DEB 82,074,272 字节。DEB 内部版本为 `0.4.0~rc1`。下载、构建与自测日志位于本地忽略目录 `build/rc04-*`，不提交私人数据或构建缓存。

15 类自测：GUI、设置、地点、预览、GPS+水印、方向、ICC、拍摄日期、原片不变、清理、报告、XLSX、NEF 范围门禁、海拔、坐标转换。真实 NEF 成功写入只在本地授权 Nikon Z 5 样片上验证，并获用户独立检查确认；冻结 NEF 合成门禁不能替代 Windows 真实 RAW 样片验收。

### 计划调整与剩余边界

变更均来自用户追加要求：NEF 仅坐标不导出 JPG、海拔缺省 0、批量 WGS84/GCJ-02 小工具及 CC BY-NC-SA 4.0。海拔参数保留旧调用默认值和旧列表兼容性，原公共信号保留；列表 schema 不升级。无未授权功能扩展，4 个原有未跟踪 Linux demo 文件保留原状且未提交。

EXE 未签名；特殊 Windows 临时路径仍可能要求可写 ASCII TEMP。坐标转换采用公开近似公式，矩形范围和边界限制已在界面说明，数值残差不表示官方或地面精度。NEF 仅承诺已验证 Nikon Z 5 编码；其他机型/编码、显影和水印均暂缓。当前包基线为 Windows x64 runner 与 Ubuntu 24.04 / glibc 2.39，未扩展到所有桌面/发行版。Actions 提示固定依赖 Action 的 Node 20 已弃用并在平台上强制使用 Node 24，本次流程成功；未在本次范围内升级固定 Actions。

**本次测试、发布和下载验收完成，工作已按用户要求暂停。**

### 本轮修改文件（相对 JPG 收尾前 c14dcad）

以下只列受 Git 跟踪的改动，不包含私人素材或原有未跟踪 demo：

- `.github/workflows/release.yml`
- `LICENSE`
- `README.md`
- `THIRD_PARTY_NOTICES.md`
- `docs/acceptance.md`
- `docs/build-release.md`
- `docs/plan.md`
- `docs/releases/v0.4.0-rc.1.md`
- `docs/user-guide.md`
- `packaging/AutoImageMarkTool.spec`
- `packaging/EVILTRANSFORM_LICENSE.txt`
- `packaging/GPS_GUI_THIRD_PARTY_NOTICES.md`
- `packaging/THIRD_PARTY_NOTICES.md`
- `packaging/license_sources.json`
- `pyproject.toml`
- `scripts/assemble_release.py`
- `scripts/batch_gps.py`
- `scripts/build_deb.py`
- `scripts/build_jpg.py`
- `scripts/check_release.py`
- `scripts/smoke_exe.py`
- `scripts/stage_jpg_artifact.py`
- `src/aim_tool/__init__.py`
- `src/aim_tool/domain/models.py`
- `src/aim_tool/domain/validation.py`
- `src/aim_tool/self_test_jpg.py`
- `src/aim_tool/services/coordinate_conversion.py`
- `src/aim_tool/services/exiftool.py`
- `src/aim_tool/services/nef_gps.py`
- `src/aim_tool/services/storage.py`
- `src/aim_tool/services/table_import.py`
- `src/aim_tool/ui/about_dialog.py`
- `src/aim_tool/ui/coordinate_converter.py`
- `src/aim_tool/ui/gps_window.py`
- `src/aim_tool/ui/location_panel.py`
- `src/aim_tool/ui/main_window.py`
- `src/aim_tool/ui/photo_table.py`
- `src/aim_tool/ui/workers.py`
- `src/aim_tool/ui/workflow_panel.py`
- `src/aim_tool/workflow/steps.py`
- `tests/gui/test_coordinate_converter.py`
- `tests/gui/test_location_panel.py`
- `tests/gui/test_main_window.py`
- `tests/gui/test_photo_table.py`
- `tests/integration/test_exiftool.py`
- `tests/unit/test_coordinate_conversion.py`
- `tests/unit/test_nef_gps.py`
- `tests/unit/test_storage_output.py`
- `tests/unit/test_table_import.py`

## v0.4.0-rc.2 NEF GPS 修补与 Nikon 兼容（2026-10-08）

用户提供正确 GPS NEF 示例并授权修补后提交和 Release，随后明确本次兼容范围为所有 Nikon 相机的 NEF。此前暂停在本范围内恢复，其他品牌 RAW 及 NEF 显影/水印均未扩展。

- NEF 副本补齐卫星数 00、WGS-84 基准、GPSVersionID 2.3.0.0；GPS 日期/时间从 EXIF 拍摄时间及小数秒生成，有照片时区时转为 UTC，无时区则复制相机时钟值。缺失时不补造日期，非法时间拒绝写入。
- 主页面默认仅勾选“写入坐标”。取消固定机型/位深/尺寸/压缩模式白名单，逐文件核对真实 NEF 容器、主图与全部可提取预览 SHA256、非 GPS EXIF/MakerNotes/XMP/IPTC/ICC 和新增验证异常，再独立读回 GPS；失败不提交成品。
- 完整本地回归：186 passed、2 Windows 专属 skipped；真实 Nikon Z5 / Z6 III 的 RAW mosaic、解码预览、全部可提取预览、相机信息、GPS 字段、原片哈希和 JPG/NEF 混合 GUI 批次通过。破坏 RAW 会阻止成品提交，改后缀 JPEG 会被拒绝。
- Ruff、格式、mypy、版本来源检查通过。版本已更新为 0.4.0rc2；本机 editable 元数据同步更新。冻结自测及 smoke_exe 预期清单同步增加到 17 类，包含默认坐标和合成 Nikon TIFF/NEF 容器写入。
- 本地 Linux 程序、DEB 构建及解包后的 17 类冻结自测通过；固定工具仍为 Python 3.12.3 / PyInstaller 6.22.3 / ExifTool 13.59。本地发行资源审计通过，私人照片/字体/签名未打包；7 份清单资产 SHA256 不变，新 NEF 示例已加入 local_only 清单与忽略规则。
- 示例的旧警告由 6 条降为 4 条，消除的是空 SubIFD 数据指针警告；RAW 和预览内容不变。校验允许旧警告被消除，拒绝新增警告或错误。
- 本地 NEF 验证副本及日志位于忽略的 demo-output/nef-gps-rc2 和 build/rc04-nef-fix-*；4 个原有未跟踪 Linux demo 文件保持原状，不纳入提交。

本轮修改：GPS/NEF 服务与 location 步骤、默认流程及冻结自测、对应单元/GUI/集成测试、私有素材忽略/清单、版本与 release 组装/校验/smoke/CI 审计，以及 README、计划、使用/构建说明、新 NEF 兼容说明和 rc.2 发布说明。

尚未覆盖全部 Nikon 型号和编码的真实样片，Windows 资源管理器 System.GPS.Date 显示未逐相机人工核验；EXE 仍未签名。提交后的 Windows CI、正式 Release 和公开下载验收尚待完成，完成后在本节追加证据。

### JPG Adobe 蒙版警告修补（2026-10-08）

用户要求单独提交 JPG 修补，并与 NEF 坐标修补一起发布 rc.2。协调消息送达前 NEF 已提交并推送为 e5d3fb7，保留该历史；JPG 修补另作独立提交，统一标签与发布等待最终提交验证通过。

- 只在元数据白名单不请求 Camera Raw/XMP 全量数据时，允许精确匹配的 GestureDabs 1000 条提取上限警告。保留提取上限，不全局启用 -m；非零退出、其他警告、混合警告及请求蒙版数据时的截断仍拒绝输出。
- 新增合成 JPG 的 1001 条蒙版笔刷用例，真实 ExifTool 重现旧失败并验证修补成功；核对原片 SHA256、GPS/海拔、拍摄时间、机型、版权、像素与 ICC。测试无需私人原片或 Adobe 数据。
- 本地 unit、GUI、ExifTool、metadata、pipeline 及新蒙版回归共 183 passed、2 Windows 专属 skipped、1 visual deselected；日志位于忽略的 build/rc04-jpg-warning-regression.log。Ruff、格式（91 文件）、mypy（41 源文件）和源版本检查通过。
- Windows CI 与 Windows/Linux Release 回归均加入该合成蒙版用例。NEF 提交的 Windows CI 37648837122 已成功；最终联合提交的 CI、Release 和公开下载检查待补充。
- 未读取用户报错中的共享照片，不能把合成回归写成该原图实测；私人素材和原有未跟踪 demo 文件均不纳入本次提交。

## v0.4.0-rc.3 流程文字与小窗口布局（2026-10-08）

用户要求移除现有 rc.2 Release，修复缩小窗口、压缩画幅或展开日志时流程文字被挤压的问题后再发布；允许改用新版本号。已撤下 rc.2 Release，原标签保留，新版本为 0.4.0rc3。

- 修复前在 1100×720 并展开日志时，流程编号及说明的控件高度降为 0。流程面板增加可滚动内容区，字号按可用宽高调整，正文保留至少 12px、说明至少 11px（Qt 逻辑像素）；按真实宽度计算换行后的最低内容高度，空间不足时滚动，不继续压缩流程块。放大后字号恢复。
- 新增 GUI 回归覆盖最小窗口、展开/收起日志、拖动分隔条、反复缩小/放大、全部说明与步骤控件可滚动访问、勾选状态不变。100% 和 150% 缩放均通过；本地空白主窗口截图检查无压缩文字。未宣称逐系统缩放比例完成人工验证。
- 全量 unit/gui/integration（要求真实与视觉素材）：201 passed、2 Windows 专属 skipped；最终布局与启动专项 4 passed。Ruff、格式（92 文件）和 mypy（41 源文件）通过。日志位于忽略的 build/rc3-layout-*。
- 冻结自测增加 workflow_layout，共 18 类，验证缩小并展开日志时文字不截断、放大后恢复；Windows/Linux 构建与公开 Windows 下载后自测沿用同一清单。原 JPG、NEF 写入及原片保护范围保持。
- 本地 Linux 程序编译、目录程序自检、DEB 构建及解包后的 18 类自检通过，DEB 版本为 0.4.0~rc3。
- 私人素材及原有四个未跟踪 Linux demo 文件不纳入提交。Windows CI、正式 Release 和公开下载验收完成后在本节追加证据。

### rc.3 正式发布与公开下载验收

- 修补源提交为 652af38a075154958da8564efd291d8001dbc742，已推送并核对远端主分支 SHA；v0.4.0-rc.3 标签指向同一提交。源码 Windows CI [37703531202](https://github.com/BG2FOU/Auto-Image-Mark-Tool/actions/runs/37703531202) 全部通过。
- 正式发布流程 [37703978957](https://github.com/BG2FOU/Auto-Image-Mark-Tool/actions/runs/37703978957) 首次在既有导入对话框 GUI 测试中出现 Qt 原生进程 Aborted（未给出断言失败信息），结束该尝试后以相同代码完整重跑。第二次 prepare、Windows、Linux、assemble、publish、verify-published-windows 全部成功；未跳过失败用例或放宽检查，不能据此断言首次进程异常的具体原因。
- [v0.4.0-rc.3](https://github.com/BG2FOU/Auto-Image-Mark-Tool/releases/tag/v0.4.0-rc.3) 已公开发布；7 份附件（EXE、ZIP、DEB、BUILD_INFO、SHA256SUMS、第三方声明、许可归档）已从公开 Release 下载。check_release.py 校验全部附件哈希、标签与源 SHA 通过，Windows ZIP 私人素材/RAW 库排除审计及 LICENSES.zip 完整性检查通过。
- 公开 Windows EXE 校验身份与 SHA256 后，在中文含空格下载目录以系统路径实际执行 18 类离线自检通过；公开 Linux DEB 解包后实际运行同一 18 类自检通过，包含 workflow_layout。日志及下载包位于忽略的 build/rc3-published-*。
- rc.2 Release 已撤下，rc.2 原标签与历史提交保留；本次未移动既有标签。此前 JPG Adobe 蒙版及 Nikon NEF GPS 修补保留在 rc.3。EXE 未签名；未宣称所有 Windows 桌面环境/缩放比例均完成人工验收。

## v0.4.0-rc.4 无关编辑列表警告兼容（2026-10-08）

用户要求修复带 `[x2]` 的 GestureDabs 报错，并忽略类似不影响处理的警告，完成后推送并发布小版本。版本更新为 0.4.0rc4，沿用已有 JPG/NEF 功能范围。

- 按 ExifTool 13.59 的已知格式识别列表 1000 项提取上限和处理缓慢提示，兼容 `[xN]` 重复次数；覆盖未参与元数据复制的 Camera Raw/crss、Lightroom、Photoshop DocumentAncestors 和 XMP History。检查本次全部复制/覆写标签，所请求的相关命名空间或 XMP/All 全量数据不允许忽略截断。
- 不全局启用 -m / IgnoreMinorErrors；MakerNotes、预览、XMP 损坏、所需标签、非零退出、未知及混合警告仍拒绝输出。原有元数据白名单、GPS/拍摄信息读回、ICC 和原片保护继续执行。
- 专项回归 90 passed，包含真实 ExifTool 的单/双蒙版、PaintBasedCorrections、DocumentAncestors、History 和 Lightroom 超限列表复制；双蒙版实测产生 `[x2]`。验证 GPS/海拔、拍摄时间、机型、版权、像素、ICC、原片 SHA256。
- 本地 unit/gui/integration 非 RAW 回归 270 passed、2 Windows 专属 skipped、8 RAW deselected；日志位于忽略的 build/rc4-regression.log。Ruff、格式（92 文件）、mypy（41 源文件）、依赖与版本来源检查通过。
- 冻结自测新增 editing_list_warnings，共 19 类：用自有合成 XMP 在真实坐标＋水印批次覆盖两个超限蒙版及超限文档来源列表。源码离线自检全部通过，报告位于忽略的 build/rc4-source-self-test.json；实际发行包自检随两平台构建及公开下载继续验证。
- 未读取报错中的共享原图；合成回归不能视为该原图实测。私人照片、字体、签名和四个原有未跟踪 Linux demo 文件均不纳入提交或公开构建。

### rc.4 正式发布与公开下载验收（2026-10-09）

- 修补源提交为 ad4aa4135448c5ff8c37e9bd5baf9550569b7e30，已推送并核对 origin/main；v0.4.0-rc.4 标签指向同一提交，不移动旧标签。源码 Windows CI [37804492251](https://github.com/BG2FOU/Auto-Image-Mark-Tool/actions/runs/37804492251) 全部成功。
- 正式发布流程 [37805125058](https://github.com/BG2FOU/Auto-Image-Mark-Tool/actions/runs/37805125058) 首次完整运行成功，prepare、Windows、Linux、assemble、publish、verify-published-windows 全部通过。两平台实际程序均通过 19 类冻结自检，Windows 目录版及单文件 EXE 的中文路径检查通过。
- [v0.4.0-rc.4](https://github.com/BG2FOU/Auto-Image-Mark-Tool/releases/tag/v0.4.0-rc.4) 已公开发布，含 EXE、ZIP、DEB、BUILD_INFO、SHA256SUMS、第三方声明和许可归档共 7 份附件。公开 Windows EXE 校验 SHA256 和源身份后，在中文含空格下载目录执行全部 19 类离线自检成功，包含 editing_list_warnings；日志保存在忽略的 build/rc4-release.log。
- 全部 7 份附件已从公开 Release 下载到忽略的 build/rc4-published-download；在标签对应源提交执行 check_release.py，全部哈希、版本/标签、源 SHA 和固定工具链校验通过。Windows ZIP 完整性/公共资源审计（1370 项）、LICENSES.zip 完整性和两平台来源清单（560 项）通过；公开 DEB 解包后的资源审计（992 文件）通过，未包含私人照片/字体/签名、RAW 显影库或原有 demo。
- 实际公开 DEB 解包程序通过全部 19 类离线自检，包含 editing_list_warnings；日志位于忽略的 build/rc4-published-deb-smoke.log。EXE 仍未签名；报错中的共享原图未实测，验证依据为真实 ExifTool 合成用例和发行包实际自检，不扩展 Nikon/Windows 人工实测范围。
### 2026-10-09 P0：性能基准与实施门禁

按用户要求先提交/推送 `docs/plan.md` 第 13 节（`b647d25`），再实施；Windows 测试反馈之前不运行正式远端构建、不创建标签或 Release。既有未跟踪 Linux demo 保持原状，不进入本任务提交。

新增 `scripts/benchmark_pipeline.py`：固定种子的噪声平铺 JPEG（5038×3363）、自有合成字体/签名；每流程 3 张照片、3 轮，每轮新 Python 进程，磁盘缓存未主动清空。记录预检/执行、ExifTool 次数/时间、主进程 VmHWM，RSS 不包含 ExifTool 子进程，不解释为阶段瞬时峰值。脚本 Ruff/格式检查通过。原始 JSON 只保留在忽略目录 `build/performance/`。

基线中位数：GPS-only 预检 0.413 秒、处理 1.840 秒、主进程峰值 150.0 MiB；水印-only 4.121 秒、8.753 秒、360.8 MiB；坐标＋水印 4.573 秒、10.553 秒、361.2 MiB。基线使用现有源码 `b647d25`，不等同于真实混合照片或 Windows 性能。

### 2026-10-09 P1：常驻 ExifTool 与线程收尾

`ExifTool(persistent=True)` 使用编号 execute/ready 和随机 stderr 状态标记，同时消费两个管道并等待两端完成；会话锁串行化共享请求，保留逐请求的退出码和严格警告。原一次性调用默认与公共接口保持有效。超时/异常退出会终止子进程和读线程，后续独立请求可新建会话；不自动重试不确定的写操作。Windows 冻结 DLL 适配拆成共享的启动函数，中文支持目录机制沿用。

实际元数据、预检、预览、批处理及 GPS CLI 接入常驻会话。预检在交付计划前关闭会话，批处理可重启并在结果信号前关闭；取消/异常/窗口关闭均经上下文清理。真实中文路径/GPS/共享会话测试、双管道乱序/严格警告/非零状态/超时/崩溃恢复测试以及相关 GUI、CLI 回归合计 103 passed；Ruff/格式与源码 mypy 通过。Windows 冻结运行仍待 P5 验证，不能据此记为原生 Windows 验收。
