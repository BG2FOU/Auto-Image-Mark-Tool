"""Production defaults, resources, fixed demo compatibility and cancellation."""

from dataclasses import replace
from pathlib import Path
from threading import Event

import numpy as np
import pytest
from PIL import Image, ImageDraw

from aim_tool.services import frequency_watermark as frequency

KEY = "a" * 64


def signature(path: Path, *, width: int = 100) -> None:
    image = Image.new("RGBA", (width, 60))
    draw = ImageDraw.Draw(image)
    draw.line([(5, 50), (30, 5), (55, 50), (80, 8), (95, 35)], fill="white", width=5)
    image.save(path)


def test_defaults_preserve_existing_fields_and_stable_key() -> None:
    params = frequency.digital_defaults({"font_size_pt": 24}, existing_key=KEY)
    assert params["font_size_pt"] == 24
    assert params["digital_enabled"] is True
    assert frequency.digital_config(params) == frequency.DigitalWatermarkConfig(KEY)
    assert frequency.digital_defaults(params) == params
    assert KEY not in repr(frequency.DigitalWatermarkConfig(KEY))
    assert frequency.digital_config({}) is None
    assert frequency.digital_config({"digital_enabled": False}) is None


@pytest.mark.parametrize("algorithm,values", [("dct", (8, 16, 32)), ("fft", (10, 20, 40))])
def test_exact_reviewed_strengths(algorithm: str, values: tuple[int, ...]) -> None:
    for level, strength in zip(("low", "medium", "high"), values, strict=True):
        config = frequency.digital_config(
            {
                "digital_enabled": True,
                "digital_algorithm": algorithm,
                "digital_level": level,
                "digital_key": KEY,
            }
        )
        assert config is not None and config.strength == strength


@pytest.mark.parametrize(
    "params",
    [
        {"digital_enabled": 1},
        {"digital_algorithm": "bad"},
        {"digital_level": "auto"},
        {"digital_key": "invalid"},
        {"digital_enabled": True},
    ],
)
def test_invalid_parameters_never_fall_back(params: dict) -> None:
    with pytest.raises(ValueError, match="数字水印"):
        frequency.digital_config(params)


def test_signature_cache_invalidates_after_replacement_with_same_timestamp(tmp_path: Path) -> None:
    import os

    path = tmp_path / "signature.png"
    signature(path)
    first = frequency.signature_payload(path)
    stamp = path.stat()
    with Image.open(path) as image:
        image.transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(path)
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    second = frequency.signature_payload(path)
    assert not np.array_equal(first, second)
    second[:] = False
    assert frequency.signature_payload(path).any()  # Cache is never exposed for mutation.


def test_capacity_and_extreme_aspect_ratio_fail_before_large_allocation(tmp_path: Path) -> None:
    path = tmp_path / "signature.png"
    signature(path)
    with pytest.raises(ValueError, match="容量不足"):
        frequency.signature_spec((512, 384), frequency.DigitalWatermarkConfig(KEY), path)
    with pytest.raises(ValueError, match="16384"):
        frequency.signature_bits(Image.new("RGBA", (1, 1000), (255, 255, 255, 128)))


@pytest.mark.parametrize("algorithm", ["dct", "fft"])
def test_cancellation_interrupts_inside_transform_batches(
    algorithm: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop = Event()
    calls = 0
    original = frequency.check_cancelled

    def cancel_in_batch(signal: Event | None) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            stop.set()
        original(signal)

    monkeypatch.setattr(frequency, "check_cancelled", cancel_in_batch)
    rgb = np.full((384, 512, 3), 100, dtype=np.uint8)
    bits = np.zeros((12, 20), dtype=bool)
    spec = frequency.Spec(algorithm, (512, 384), (20, 12), 24, 3)
    with pytest.raises(InterruptedError, match="已取消"):
        frequency.embed(rgb, bits, spec, KEY, cancelled=stop)
    assert np.all(rgb == 100)
    assert calls == 3


def test_invalid_bitmap_and_wrong_size_fail_before_transform() -> None:
    rgb = np.full((384, 512, 3), 100, dtype=np.uint8)
    spec = frequency.Spec("dct", (512, 384), (20, 12), 16, 3)
    with pytest.raises(ValueError, match="bitmap"):
        frequency.embed(rgb, np.ones((12, 21), dtype=bool), spec, KEY)
    with pytest.raises(ValueError, match="original size"):
        frequency.extract(rgb, replace(spec, image_size=(511, 384)), KEY)
