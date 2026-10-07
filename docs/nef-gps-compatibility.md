# Nikon NEF 坐标写入兼容范围

EXIF GPS 的经纬度、方向、海拔、卫星数与时间字段是标准化的。各相机 RAW 的容器结构、压缩数据、缩略图及 MakerNotes 布局不同。本次按用户要求先支持 Nikon 相机的 NEF，其他品牌 RAW 暂不开放。

## 相机兼容方式

主页面取消固定 Nikon Z5 机型、位深、像素尺寸和压缩模式白名单，交由固定 ExifTool 13.59 写入，再逐张核对副本。ExifTool 识别出的真实容器须为 NEF，不能通过将 JPEG 改后缀绕过校验。

依据：[ExifTool 13.59 的 NEF 读写能力](https://github.com/exiftool/exiftool/blob/13.59/html/index.html)。旧 `--gps-only` 预览及旧脚本保留原门禁，NEF 使用主页面。

## 写入和时间规则

- 经纬度使用 WGS84 十进制度，海拔单位米，缺省 0，负数写入对应方向标记。
- NEF 副本固定写 GPSVersionID=2.3.0.0、GPSMapDatum=WGS-84、GPSSatellites=00。
- GPSDateStamp 和 GPSTimeStamp 从 EXIF DateTimeOriginal、SubSecTimeOriginal 生成；有 OffsetTimeOriginal 时转为 UTC，同时处理跨日/跨年。原始 EXIF 拍摄时间不变。
- EXIF 未提供时区时按相机时钟原值复制，不借用运行电脑时区。缺失拍摄时间时省略 GPS 日期/时间，非法时间则拒绝写入，不使用 CreateDate、文件时间或当前时间补造。
- 已有时间/方向等附属 GPS 仍须选择“允许清除旧时间/方向等附属 GPS”，清理只发生在副本上，NEF 的日期/卫星/基准按上述规则重新生成。

UTC 规则依据 [ExifTool GPS 标签文档](https://exiftool.org/TagNames/GPS.html)；Windows 属性定义见 [System.GPS.Date](https://learn.microsoft.com/en-us/windows/win32/properties/props-system-gps-date)。不同系统的 RAW 属性处理器决定最终显示，本轮未在 Windows 资源管理器逐相机核验。

## 每张照片的提交条件

1. 能识别 NEF 容器并计算非空主图 SHA256（ExifTool ImageDataHash）。
2. 写入前后的主图哈希、所有可提取预览/缩略图哈希、非 GPS EXIF、MakerNotes、XMP、IPTC 和 ICC 信息一致。仅允许容器重排导致的数据指针移动。
3. 写入后没有新增验证警告或错误；已有警告被消除允许通过。
4. 经纬度、海拔、卫星数、基准与 GPS 日期/时间全部独立读回一致，原片整体 SHA256 不变。

失败则清理临时副本，不提交成品，不覆盖原片或既有输出。NEF 不显影、不加水印、不转换 JPEG。

当前真实样片实测为 Nikon Z5 和 Z6 III，另有合成 Nikon TIFF/NEF 容器的写入、完整性和冻结程序自测。没有全部 Nikon 型号/编码的真实样片验收；逐文件检查不能代替每款相机的独立软件兼容性验证。
