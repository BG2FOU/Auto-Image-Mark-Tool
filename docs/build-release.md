# 照片坐标与 JPG 水印版构建与发布

本期版本源为 `src/aim_tool/__init__.py`（0.4.0rc1），标签为 `v0.4.0-rc.1`。支持 JPG/JPEG 三流程及已验证 Nikon Z 5 NEF 的坐标副本写入；NEF 显影与水印延后。旧 GPS-only 构建脚本和 Release 保留。

## 固定工具链

Python 3.12.3 x64、pip 24.0、PyInstaller 6.22.3、ExifTool 13.59。依赖按 `requirements-dev.lock` 的哈希安装，再用 `pip install --no-deps --no-build-isolation -e .` 安装项目。Windows 工具通过 `scripts/fetch_tools.py --manifest packaging/toolchain.json` 准备；Linux ExifTool 源归档 URL 和 SHA256 在同一清单中。

Qt/Python 等许可来源归档由 `packaging/license_sources.json` 固定版本、URL 与 SHA256。`collect_licenses.py` 只读取其中的许可文本和归属元数据，不捆绑整个源代码；上游对应版本源码下载方式保留在清单中。Linux 另按实际收集的系统库加入系统版权文件。项目保持 CC BY-NC-SA 4.0；各依赖适用自身许可，完整声明见根目录 `THIRD_PARTY_NOTICES.md`。

## 本地构建

Windows：

```powershell
.\scripts\build.ps1 -Mode onedir
.\scripts\build.ps1 -Mode onefile
```

Linux（Ubuntu 24.04 / amd64 基线）：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/build_deb.py
```

两平台复用 `packaging/AutoImageMarkTool.spec`。Windows 适配器直接使用固定包内的 Perl 和相对 exiftool.pl/lib。路径优先使用系统代码页可无损表示的名称或现有 DOS 短路径；无短路径的中文安装目录会将未经修改的支持运行时复制到用户临时目录（必要时使用 LOCALAPPDATA），在对象释放时清理。只复制公开 ExifTool 运行时，不复制照片、字体、签名或用户设置；不依赖外部 Perl，不修改磁盘短路径设置。临时根目录也须能由系统代码页或短路径表示，否则明确提示设置可写的 ASCII TEMP，不静默继续。公共接口及 13.59 版本校验保持有效。构建脚本会运行 `--self-test-jpg --report`，从源码目录外启动实际冻结程序，清除外部 ExifTool/PYTHONPATH/Qt 插件路径，并把 PATH 限制为系统目录，使用临时自有合成字体/签名/JPG/XLSX，验证 GUI、地点保存、预览、GPS+水印、方向、ICC、拍摄日期、源哈希和清理。旧 `--self-test` GPS 接口保持不变。自测不联网，不读取用户照片。冻结自测共 15 类，包含海拔读回和批量坐标转换/列表追加。新增 `nef_scope` 检查只验证 NEF 编码拒绝、预览/水印边界和未加载 RAW 显影库，不是实际 NEF 成功写入测试。真实 NEF 只在本地授权样片上验证，独立软件试写已获用户确认。DEB 解包后再执行同一自测。

`dist/AutoImageMarkTool/` 为目录版；Windows `dist/AutoImageMarkTool.exe` 为单文件版；Linux DEB 版本使用 Debian 的 `0.4.0~rc1` 排序。字体、签名必须由用户在本地设置中选择，首次启动不会自带私人素材。冻结自测不代表商用字体的人工视觉验收，也不代替独立 Windows 10 桌面交互检查。

## CI 和发布

`.github/workflows/release.yml` 固定 Actions SHA、Python 和 Windows 2022/Ubuntu 24.04 runner。默认只有读取权限，发布 job 才获得 `contents:write`。主分支 `workflow_dispatch` 留空 tag、publish=false 可以构建、测试并生成附件而不创建 Release。

正式发布前必须在同一提交上检查 CI。推送现存且与版本一致的 `v*` 标签后自动执行：版本与提交校验 → 锁定安装/测试 → Windows onedir 与 onefile/中文含空格路径冒烟、Linux DEB 冒烟 → 资源审计 → 生成附件与 SHA256 → 草稿上传 → 下载回读校验 → 发布。

产物包含 EXE、可替换依赖库的目录 ZIP、DEB、完整 `LICENSES.zip`、第三方声明、`BUILD_INFO.json` 和 `SHA256SUMS.txt`。BUILD_INFO 记录源 SHA、工具版本及无签名状态。EXE 未做代码签名；可使用哈希核验下载内容。禁止上传 `data/`、私人字体/签名、demo 输出。

恢复入口为 workflow_dispatch 的既有 tag 和 publish=true。同标签串行；仅允许更新未发布草稿，已发布内容不能静默替换。失败修复需提交并验证，新代码必须使用新版本/标签；不要移动已有标签。回滚使用上一份已发布包，不覆盖新版附件。依赖升级需重新生成锁文件、核对许可源哈希并走全部测试。

## 已发布版本与下载验证

[v0.4.0-rc.1](https://github.com/BG2FOU/Auto-Image-Mark-Tool/releases/tag/v0.4.0-rc.1) 对应源 SHA `2a0ef1759a42db3d8224d105df1f2dc94b6a0865`，正式运行 `37131275318` 全链成功。公开 EXE 中文路径自测、全部附件哈希/许可和实际公开 DEB 解包后的 15 类自测已验证。项目许可为 CC BY-NC-SA 4.0，历史版本保留原状。测试和发布完成后按用户要求暂停，详见 [验收记录](acceptance.md)。

[v0.3.0-rc.1](https://github.com/BG2FOU/Auto-Image-Mark-Tool/releases/tag/v0.3.0-rc.1) 对应源 SHA `946ea9ad9c5c0b9218ff0d4b430bf5bcf2054cf2`，正式运行 `37113456901` 成功，包含公开 Windows EXE 下载后的原生离线自测。全部公开附件哈希及实际下载的 Linux DEB 解包自测已验证，见 [验收记录](acceptance.md)。

验证既有 Release 的 `check_release.py --tag ... --dist ...` 时，必须在该标签对应的 checkout 运行；它严格比较当前 HEAD、标签和 BUILD_INFO 的源 SHA。主分支随后更新文档不改变已有标签或发布附件。发布后只读 Windows job 不安装项目依赖，重新下载并校验 EXE，在中文下载目录实际运行；其失败会独立显示在正式流程中，不静默覆盖公开发行包。
