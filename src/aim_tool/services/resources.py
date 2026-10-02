"""Resolve local-only watermark assets and describe them without copying them."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image

from aim_tool.services.fonts import FontIdentity, identify_font
from aim_tool.services.watermark import WatermarkResources


@dataclass(frozen=True)
class SignatureIdentity:
    path: Path
    sha256: str
    size: tuple[int, int]
    visible_bounds: tuple[int, int, int, int]
    has_partial_alpha: bool


@dataclass(frozen=True)
class WatermarkAssetIdentities:
    latin: FontIdentity
    chinese: FontIdentity
    signature: SignatureIdentity


def local_project_resources(repository_root: Path) -> WatermarkResources:
    """Use known local data files; the caller still preflights their presence."""
    data = repository_root.resolve() / "data"
    return WatermarkResources(
        data / "TrajanPro-Bold.otf",
        data / "FangZhengShengShiKaiShuJianTi-Da.ttf",
        data / "NAME.png",
    )


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identify_signature(path: Path) -> SignatureIdentity:
    if not path.is_file():
        raise ValueError(f"Signature is unavailable: {path}")
    try:
        with Image.open(path) as original:
            rgba = original.convert("RGBA")
    except (OSError, ValueError) as error:
        raise ValueError(f"Signature cannot be opened: {path}") from error
    alpha = rgba.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError("Signature has no visible pixels")
    histogram = alpha.histogram()
    return SignatureIdentity(
        path.resolve(),
        _hash(path),
        rgba.size,
        bounds,
        any(histogram[1:255]),
    )


def identify_watermark_assets(resources: WatermarkResources) -> WatermarkAssetIdentities:
    return WatermarkAssetIdentities(
        identify_font(resources.latin_font, resources.latin_face),
        identify_font(resources.chinese_font, resources.chinese_face),
        identify_signature(resources.signature),
    )


def default_local_resources() -> WatermarkResources:
    """Resolve development defaults or portable user assets without scanning data."""
    root = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[3]
    )
    return local_project_resources(root)
