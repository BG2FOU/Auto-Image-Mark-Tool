# GPS prototype third-party notices

This GPS-only build includes Python 3.12, the PyInstaller bootloader, and
ExifTool 13.59. The project's own source and documentation remain under
the repository's CC BY-NC-SA 4.0 `LICENSE`.

| Component | Upstream and license information |
| --- | --- |
| Python 3.12 | https://www.python.org/ and https://docs.python.org/3/license.html |
| PyInstaller bootloader 6.22.3 | https://pyinstaller.org/ and https://github.com/pyinstaller/pyinstaller/blob/v6.22.3/COPYING.txt |
| ExifTool 13.59 | https://exiftool.org/ ; its bundled `LICENSE` and support files are included in the executable. |

The Windows ExifTool executable comes from the pinned official ZIP listed in
`packaging/toolchain.json`. The Linux package embeds the pinned ExifTool Perl
source and requires the system `perl-base` package. User photographs, signature,
and fonts are not part of either public artifact.
