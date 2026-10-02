"""Adaptive geometry on actual output canvases using public synthetic assets."""

from datetime import date
from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image

from aim_tool.services.images import watermark_jpeg_pixels
from aim_tool.services.watermark import WatermarkConfig, WatermarkResources, render_watermark_layer


@pytest.mark.parametrize(
    ("size", "signature_width", "margin"),
    [
        ((6016, 4016), 300, 25),
        ((5038, 3363), 251, 21),
        ((3008, 2008), 150, 12),
        ((4016, 6016), 300, 25),
        ((2008, 3008), 150, 12),
        ((2008, 2008), 100, 8),
        ((6016, 1004), 75, 6),
        ((600, 400), 30, 2),
    ],
)
def test_adaptive_signature_and_group_margins(
    synthetic_watermark_resources: WatermarkResources,
    size: tuple[int, int],
    signature_width: int,
    margin: int,
) -> None:
    config = WatermarkConfig("aviation", "B-1356", date(2026, 9, 26))
    overlay = render_watermark_layer(size, config, synthetic_watermark_resources)
    alpha = overlay.getchannel("A")
    bounds = alpha.getbbox()
    assert bounds is not None
    assert size[0] - bounds[2] == margin
    assert size[1] - bounds[3] == margin
    signature = alpha.crop((bounds[2] - signature_width, 0, bounds[2], size[1]))
    signature_bounds = signature.getbbox()
    assert signature_bounds is not None
    assert signature_bounds[2] - signature_bounds[0] == signature_width
    assert abs(signature_bounds[3] - signature_bounds[1] - signature_width * 18 / 30) <= 1
    assert alpha.getextrema()[1] == 128


def test_dpi_labels_do_not_change_watermark_pixel_scale(
    tmp_path: Path, synthetic_watermark_resources: WatermarkResources
) -> None:
    config = WatermarkConfig("aviation", "B-1356", date(2026, 9, 26))
    source = Image.new("RGB", (1007, 672), (80, 90, 100))
    outputs = []
    for dpi in (72, 300):
        path = tmp_path / f"{dpi}.jpg"
        source.save(path, dpi=(dpi, dpi))
        before = sha256(path.read_bytes()).digest()
        result = watermark_jpeg_pixels(path, config, synthetic_watermark_resources)
        outputs.append(result.pixels.tobytes())
        assert result.pixels.size == source.size
        assert result.dpi == (dpi, dpi)
        assert sha256(path.read_bytes()).digest() == before
    assert outputs[0] == outputs[1]
