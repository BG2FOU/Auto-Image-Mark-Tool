# GPS GUI third-party notices

The GPS GUI preview includes Python 3.12, PySide6 Essentials 6.11.2, Shiboken6
6.11.2, Qt 6.11.2 libraries, the PyInstaller 6.22.3 bootloader, and ExifTool
13.59. The project source remains under the repository's CC BY-NC-SA 4.0
`LICENSE`. Qt for Python components are offered under LGPL-3.0-only,
GPL-2.0-only, GPL-3.0-only, or a commercial license; see the upstream license
materials for the license applicable to each Qt component.

| Component | Upstream license information |
| --- | --- |
| Python | https://docs.python.org/3/license.html |
| PySide6, Shiboken6 and Qt | https://doc.qt.io/qtforpython-6/licenses.html and https://doc.qt.io/qt-6/licensing.html |
| PyInstaller bootloader | https://github.com/pyinstaller/pyinstaller/blob/v6.22.3/COPYING.txt |
| ExifTool | https://exiftool.org/ ; its bundled `LICENSE` is included. |

Qt shared libraries are shipped as separate files in the Linux DEB and Windows
onedir build. The Windows onefile EXE extracts them to a temporary directory at
runtime. No private photos, signature image, or commercial fonts are included.
