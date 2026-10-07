"""Only an unused Adobe brush-list limit may pass strict metadata transfer."""

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from aim_tool.services.exiftool import ExifTool, ExifToolError

MASK_WARNING = (
    "Warning: [Minor] Extracted only 1000 "
    "crs:MaskGroupBasedCorrectionsCorrectionMasksGestureDabs items. "
    "Ignore minor errors to extract all - \\\\server\\中文 & 照片\\source.jpg\n"
)


def _copy(tmp_path: Path, stderr: str, tags: tuple[str, ...], returncode: int = 0) -> None:
    executable = tmp_path / "exiftool"
    source, target = tmp_path / "source.jpg", tmp_path / "target.jpg"
    for path in (executable, source, target):
        path.touch()
    with patch("aim_tool.services.exiftool.subprocess.run") as run:
        run.return_value = CompletedProcess([], 0, "13.59\n", "")
        tool = ExifTool(executable)
        run.return_value = CompletedProcess([], returncode, "1 image files updated\n", stderr)
        tool.copy_tags(source, target, tags, {"IFD0:Orientation": 1})
        args = run.call_args.kwargs["input"].splitlines()
        assert "-m" not in args
        assert "-ignoreMinorErrors" not in args


def test_unused_mask_list_limit_does_not_fail_whitelist_copy(tmp_path: Path) -> None:
    _copy(tmp_path, MASK_WARNING, ("ExifIFD:DateTimeOriginal", "XMP-dc:Rights", "GPS:all"))


@pytest.mark.parametrize(
    "stderr",
    (
        "Warning: [minor] Bad MakerNotes offset - source.jpg\n",
        MASK_WARNING + "Warning: [minor] Bad MakerNotes offset - source.jpg\n",
        "Warning: [minor] Bad MakerNotes offset - source.jpg\n" + MASK_WARNING,
        MASK_WARNING.replace("GestureDabs", "MaskName"),
        MASK_WARNING.replace("crs:", "dc:"),
    ),
)
def test_other_or_mixed_warnings_still_fail(tmp_path: Path, stderr: str) -> None:
    with pytest.raises(ExifToolError, match="metadata warning"):
        _copy(tmp_path, stderr, ("GPS:all",))


@pytest.mark.parametrize("tag", ("XMP-crs:all", "crs:all", "XMP:all", "All:all"))
def test_requested_brush_metadata_cannot_be_truncated(tmp_path: Path, tag: str) -> None:
    with pytest.raises(ExifToolError, match="metadata warning"):
        _copy(tmp_path, MASK_WARNING, (tag,))


def test_nonzero_exit_is_never_ignored(tmp_path: Path) -> None:
    with pytest.raises(ExifToolError, match="exited 1"):
        _copy(tmp_path, MASK_WARNING, ("GPS:all",), returncode=1)


def test_strict_run_without_whitelist_still_rejects_warning(tmp_path: Path) -> None:
    executable = tmp_path / "exiftool"
    executable.touch()
    with patch("aim_tool.services.exiftool.subprocess.run") as run:
        run.return_value = CompletedProcess([], 0, "13.59\n", "")
        tool = ExifTool(executable)
        run.return_value = CompletedProcess([], 0, "", MASK_WARNING)
        with pytest.raises(ExifToolError, match="metadata warning"):
            tool._run("-ver", reject_warnings=True)
