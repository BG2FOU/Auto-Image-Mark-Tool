"""Collect pinned upstream license texts without copying source code or private assets."""

from __future__ import annotations

import hashlib
import json
import posixpath
import shutil
import sys
import tarfile
import urllib.request
from importlib.metadata import distribution
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "build/jpg-licenses"
PACKAGES = ("Pillow", "fonttools", "platformdirs", "PyInstaller", "numpy", "packaging", "altgraph")


def _is_license(name: str) -> bool:
    path = PurePosixPath(name)
    text_suffixes = {"", ".txt", ".rst", ".md", ".html", ".lib", ".lgpl", ".gpl", ".bsd", ".mit"}
    return (
        "LICENSES" in path.parts
        or path.suffix.lower() in text_suffixes
        and path.name.lower().startswith(("license", "licence", "copying", "copyright", "notice"))
        or path.name == "qt_attribution.json"
        and "/src/" in name
    )


def collect() -> Path:
    manifest_path = ROOT / "packaging/license_sources.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["schema_version"] != 1:
        raise ValueError("Unsupported license source schema")
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    DESTINATION.mkdir(parents=True)
    cache = ROOT / "tools/license-sources"
    cache.mkdir(parents=True, exist_ok=True)
    for entry in manifest["archives"]:
        archive = cache / f"{entry['name']}-{entry['version']}.tar.gz"
        if not archive.is_file():
            with urllib.request.urlopen(entry["url"], timeout=180) as response:
                archive.write_bytes(response.read())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"License source checksum mismatch: {archive.name}")
        with tarfile.open(archive) as source:
            members = {member.name: member for member in source.getmembers() if member.isfile()}
            selected = {name for name in members if _is_license(name)}
            for name in tuple(selected):
                if not name.endswith("qt_attribution.json"):
                    continue
                handle = source.extractfile(members[name])
                if handle is None:
                    raise ValueError(f"Unreadable attribution: {name}")
                metadata = json.load(handle, strict=False)
                records = metadata if isinstance(metadata, list) else [metadata]
                for record in records:
                    filenames = record.get("LicenseFile", [])
                    for filename in [filenames] if isinstance(filenames, str) else filenames:
                        target = posixpath.normpath(
                            posixpath.join(posixpath.dirname(name), filename)
                        )
                        if target not in members:
                            raise ValueError(f"Missing referenced license: {target}")
                        selected.add(target)
            if not selected:
                raise ValueError(f"No license texts found: {archive.name}")
            for name in sorted(selected):
                relative = PurePosixPath(name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("Unsafe license archive path")
                target = DESTINATION / entry["name"] / Path(*relative.parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                handle = source.extractfile(members[name])
                if handle is None:
                    raise ValueError(f"Unreadable license: {name}")
                content = handle.read()
                if len(content) > 2_000_000 or b"\0" in content:
                    raise ValueError(f"Unexpected non-text license: {name}")
                target.write_bytes(content)
    inventory = []
    for package in PACKAGES:
        installed = distribution(package)
        found = False
        for item in installed.files or ():
            if any(word in item.name.lower() for word in ("license", "copying", "copyright")):
                path = Path(installed.locate_file(item))
                if path.is_file() and ".dist-info/" in str(item):
                    target = DESTINATION / package / item.name
                    target.parent.mkdir(exist_ok=True)
                    shutil.copy2(path, target)
                    found = True
        if not found:
            raise ValueError(f"Installed dependency has no license text: {package}")
        inventory.append({"name": package, "version": installed.version})
    runtime = ROOT / (
        "tools/exiftool/exiftool_files" if sys.platform == "win32" else "tools/exiftool-13.59"
    )
    tool_notices = DESTINATION / "ExifTool"
    tool_notices.mkdir()
    shutil.copy2(runtime / "LICENSE", tool_notices / "LICENSE")
    if sys.platform == "win32":
        shutil.copy2(
            runtime / "Licenses_Strawberry_Perl.zip", tool_notices / "Licenses_Strawberry_Perl.zip"
        )
        shutil.copy2(runtime / "readme_windows.txt", tool_notices / "readme_windows.txt")
    shutil.copy2(manifest_path, DESTINATION / "SOURCE_ARCHIVES.json")
    (DESTINATION / "PYTHON_PACKAGES.json").write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Collected {len(list(DESTINATION.rglob('*')))} license paths")
    return DESTINATION


if __name__ == "__main__":
    collect()
