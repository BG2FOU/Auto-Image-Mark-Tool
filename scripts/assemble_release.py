"""Assemble only verified application artifacts and license attachments."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

from check_release import RAW_SCOPE, ROOT, digest, release_tag


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--linux", type=Path, required=True)
    args = parser.parse_args()
    tag = release_tag()
    release = ROOT / "dist/release"
    if release.exists():
        raise FileExistsError("Release staging already exists")
    release.mkdir(parents=True)
    shutil.copy2(
        args.windows / "AutoImageMarkTool.exe", release / f"AutoImageMarkTool-{tag}-windows-x64.exe"
    )
    shutil.copy2(
        args.windows / "AutoImageMarkTool-windows-x64.zip",
        release / f"AutoImageMarkTool-{tag}-windows-x64.zip",
    )
    (deb,) = args.linux.glob("*.deb")
    shutil.copy2(deb, release / f"auto-image-mark-tool_{tag.removeprefix('v')}_amd64.deb")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", release / "THIRD_PARTY_NOTICES.md")
    with zipfile.ZipFile(release / "LICENSES.zip", "w", zipfile.ZIP_DEFLATED) as output:
        output.write(ROOT / "LICENSE", "LICENSE")
        for folder, prefix in [
            (args.windows / "licenses", "windows"),
            (args.linux / "licenses", "linux"),
        ]:
            if not (folder / "SOURCE_ARCHIVES.json").is_file():
                raise ValueError(f"Verified license inventory is missing: {folder}")
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    output.write(path, f"{prefix}/{path.relative_to(folder).as_posix()}")
    (release / "BUILD_INFO.json").write_text(
        json.dumps(
            {
                "tag": tag,
                "commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
                "run_id": os.environ.get("GITHUB_RUN_ID"),
                "python": "3.12.3",
                "pyinstaller": "6.22.3",
                "exiftool": "13.59",
                "platforms": ["windows-2022 x64", "ubuntu-24.04 amd64"],
                "frozen_checks": [
                    "onedir",
                    "onefile",
                    "deb_extracted",
                    "gps_watermark",
                    "xlsx",
                    "nef_scope",
                    "nef_gps",
                    "default_location",
                    "altitude",
                    "coordinate_conversion",
                ],
                "private_assets": "excluded",
                "nef": "gps_only_with_integrity_checks",
                "raw": RAW_SCOPE,
                "code_signed": False,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (release / "SHA256SUMS.txt").write_text(
        "".join(
            f"{digest(path)}  {path.name}\n" for path in sorted(release.iterdir()) if path.is_file()
        ),
        encoding="utf-8",
    )
    print(release)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
