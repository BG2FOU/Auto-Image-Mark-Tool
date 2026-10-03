# Auto Image Mark Tool: third-party notices

The project code and documentation retain CC BY-SA 4.0; see `LICENSE`.
The JPG edition includes the following upstream components. Their licenses are
independent of the project's license and are preserved in the `licenses/`
directory of the frozen application and in the release license archive.

| Component | Version | License / corresponding upstream source |
| --- | --- | --- |
| CPython | 3.12.3 | PSF and incorporated licenses: https://github.com/python/cpython/tree/v3.12.3 |
| PySide6 Essentials / Shiboken6 / Qt | 6.11.2 | Qt for Python and the used Qt Core, GUI, Widgets, SVG and platform/image plugins: https://github.com/pyside/pyside-setup/tree/v6.11.2 and https://github.com/qt/qtbase/tree/v6.11.2 ; LGPL-3.0, GPL alternatives and component-specific third-party notices are in the license archive. |
| Pillow | 12.3.0 | HPND and incorporated codec licenses; installed distribution's complete LICENSE is included. https://github.com/python-pillow/Pillow/tree/12.3.0 |
| fontTools | 4.66.1 | MIT and external component notices: https://github.com/fonttools/fonttools/tree/4.66.1 |
| openpyxl | 3.1.5 | MIT: https://pypi.org/project/openpyxl/3.1.5/ |
| et_xmlfile | 2.0.0 | MIT: https://pypi.org/project/et-xmlfile/2.0.0/ |
| platformdirs | 4.12.2 | MIT: https://github.com/tox-dev/platformdirs/tree/4.12.2 |
| PyInstaller bootloader | 6.22.3 | GPL with the bootloader exception; complete COPYING included. https://github.com/pyinstaller/pyinstaller/tree/v6.22.3 |
| ExifTool | 13.59 | Same terms as Perl; original LICENSE and complete required runtime included. https://github.com/exiftool/exiftool/tree/13.59 |

`licenses/SOURCE_ARCHIVES.json` records the exact upstream archive URLs and
SHA-256 values. `licenses/PYTHON_PACKAGES.json` records the installed package
versions used by the build. License material includes upstream attribution
records and the full referenced license texts; the Qt material is a superset
of the plugins collected by PyInstaller. Additional installed Python dependency
notices are included when their modules can be collected by the freezer.

Qt shared libraries are separate files in the Windows directory ZIP and Linux
DEB. A Windows single-file EXE extracts shared libraries to its temporary runtime
directory. The directory ZIP is also provided so those libraries can be inspected
and replaced with compatible rebuilt libraries. Corresponding sources are linked
above and pinned in SOURCE_ARCHIVES.json; no Qt libraries are modified by this
project. The application does not restrict reverse engineering for debugging
modifications of the LGPL components.

Linux system-library copyrights collected by the build are included under
`licenses/linux-system/`. The Linux package also declares required system runtime
packages, including Perl and the Qt platform dependencies.

Photos, signatures and user fonts are local inputs. No private font, photograph,
or signature image is bundled or published. The synthetic block-glyph font and
plain signature used during self-tests are generated in a temporary directory
from project code, not copied from a third-party font or the user's assets.
NEF processing is deferred and rawpy/LibRaw are excluded from this JPG release.
