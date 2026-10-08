"""Real stay-open commands retain strict metadata and request-local diagnostics."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PIL import Image

from aim_tool.services.exiftool import ExifTool, ExifToolError
from aim_tool.services.metadata import preserve_watermark_metadata


def test_real_session_reuses_process_and_recovers_after_bad_request(tmp_path: Path) -> None:
    source = tmp_path / "中文 空格.jpg"
    Image.new("RGB", (64, 32)).save(source)
    with ExifTool(persistent=True) as tool:
        assert tool.metadata(source, "-File:ImageWidth")["File:ImageWidth"] == 64
        process = tool._process
        assert process is not None
        with pytest.raises(ExifToolError, match="exited"):
            tool.metadata(tmp_path / "missing.jpg")
        tool.write_gps(source, -24.2, 118.4, -10)
        gps = tool.read_gps(source)
        assert gps is not None and gps.altitude == -10
        assert tool._process is process
        assert tool.metadata(source, "-File:ImageHeight")["File:ImageHeight"] == 32
        readers = tuple(tool._readers)
    assert process.poll() is not None
    assert not any(reader.is_alive() for reader in readers)
    assert tool._process is None
    # Plans can reuse the tool after preflight has closed its first session.
    with tool:
        assert tool.read_gps(source) == gps
        assert tool._process is not process


def test_shared_session_serializes_requests(tmp_path: Path) -> None:
    paths = []
    for index in range(6):
        path = tmp_path / f"image-{index}.jpg"
        Image.new("RGB", (20 + index, 10)).save(path)
        paths.append(path)
    with ExifTool(persistent=True) as tool, ThreadPoolExecutor(max_workers=3) as workers:
        records = tuple(workers.map(lambda path: tool.metadata(path, "-File:ImageWidth"), paths))
    assert [record["File:ImageWidth"] for record in records] == list(range(20, 26))
    assert [Path(record["SourceFile"]) for record in records] == paths


def test_metadata_transfer_shares_reads_but_reads_written_target_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PIL import ImageCms

    source, target = tmp_path / "source.jpg", tmp_path / "target.jpg"
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    for path in (source, target):
        Image.new("RGB", (64, 32)).save(path, icc_profile=profile)
    with ExifTool(persistent=True) as tool:
        tool.write_gps(source, -1.2, 3.4, -10)
        reads = []
        metadata = tool.metadata

        def record(path: Path, *tags: str) -> dict[str, object]:
            reads.append(path)
            return metadata(path, *tags)

        monkeypatch.setattr(tool, "metadata", record)
        preserve_watermark_metadata(tool, source, target)
        assert reads == [source, target]
        assert tool.read_gps(target) == tool.read_gps(source)
