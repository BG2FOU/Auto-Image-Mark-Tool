"""Unused editing-list notices may pass; required metadata stays strict."""

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


@pytest.mark.parametrize(
    "field",
    (
        "crs:MaskGroupBasedCorrectionsCorrectionMasksGestureDabs",
        "crs:MaskGroupBasedCorrectionsCorrectionMasksMasksDabs",
        "crs:PaintBasedCorrectionsCorrectionMasksDabs",
        "crs:GradientBasedCorrectionsCorrectionMasksDabs",
        "crss:Parameters",
        "lr:hierarchicalSubject",
        "photoshop:DocumentAncestors",
        "xmpMM:History",
    ),
)
@pytest.mark.parametrize("counter", ("", " [x2]", " [x12]"))
@pytest.mark.parametrize("kind", ("limit", "slow"))
def test_unused_editing_lists_do_not_fail_whitelist_copy(
    tmp_path: Path, field: str, counter: str, kind: str
) -> None:
    message = (
        f"[Minor] Extracted only 1000 {field} items. Ignore minor errors to extract all"
        if kind == "limit"
        else f"[minor] Excessive number of items for {field}. Processing may be slow"
    )
    warning = f"Warning: {message}{counter} - \\\\server\\中文 & 照片\\source.jpg\n"
    _copy(tmp_path, warning, ("ExifIFD:DateTimeOriginal", "XMP-dc:Rights", "GPS:all"))


def test_multiple_optional_warnings_do_not_fail_copy(tmp_path: Path) -> None:
    _copy(
        tmp_path,
        MASK_WARNING + MASK_WARNING.replace("all -", "all [x2] -"),
        ("GPS:all",),
    )


@pytest.mark.parametrize(
    "stderr",
    (
        "Warning: [minor] Bad MakerNotes offset - source.jpg\n",
        MASK_WARNING + "Warning: [minor] Bad MakerNotes offset - source.jpg\n",
        "Warning: [minor] Bad MakerNotes offset - source.jpg\n" + MASK_WARNING,
        MASK_WARNING.replace("crs:", "dc:"),
        MASK_WARNING.replace("crs:", "unknown:"),
        MASK_WARNING.replace(
            "crs:MaskGroupBasedCorrectionsCorrectionMasksGestureDabs", "dc:creator"
        ),
        MASK_WARNING.replace(
            "crs:MaskGroupBasedCorrectionsCorrectionMasksGestureDabs", "photoshop:AuthorsPosition"
        ),
        MASK_WARNING.replace("1000", "100"),
        MASK_WARNING.replace("all -", "all [x?] -"),
        MASK_WARNING.replace("[Minor]", "[Major]"),
        "Warning: [minor] Truncated XMP - source.jpg\n",
        "Warning: [minor] Error reading PreviewImage - source.jpg\n",
        "Error: Failed to write GPS - source.jpg\n",
    ),
)
def test_other_or_mixed_warnings_still_fail(tmp_path: Path, stderr: str) -> None:
    with pytest.raises(ExifToolError, match="metadata warning"):
        _copy(tmp_path, stderr, ("GPS:all",))


@pytest.mark.parametrize(
    "namespace, field",
    (
        ("crs", "MaskGroupBasedCorrectionsCorrectionMasksGestureDabs"),
        ("crss", "Parameters"),
        ("lr", "hierarchicalSubject"),
        ("photoshop", "DocumentAncestors"),
        ("xmpMM", "History"),
    ),
)
@pytest.mark.parametrize("group", ("namespace", "xmp-namespace", "XMP", "All"))
def test_requested_editing_metadata_cannot_be_truncated(
    tmp_path: Path, namespace: str, field: str, group: str
) -> None:
    warning = MASK_WARNING.replace(
        "crs:MaskGroupBasedCorrectionsCorrectionMasksGestureDabs", f"{namespace}:{field}"
    ).replace("all -", "all [x2] -")
    group = {"namespace": namespace, "xmp-namespace": f"XMP-{namespace}"}.get(group, group)
    with pytest.raises(ExifToolError, match="metadata warning"):
        _copy(tmp_path, warning, (f"{group}:all",))


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
