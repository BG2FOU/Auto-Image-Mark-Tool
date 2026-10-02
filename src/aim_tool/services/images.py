"""Prepare JPEG pixels for watermarking with explicit orientation and color handling."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageCms, ImageOps

from aim_tool.services.output import commit_no_overwrite
from aim_tool.services.watermark import WatermarkConfig, WatermarkResources, render_watermark_layer

MAX_JPEG_PIXELS = 60_000_000


@dataclass(frozen=True)
class PreparedJpeg:
    pixels: Image.Image
    srgb_icc: bytes
    dpi: tuple[float, float] | None
    warnings: tuple[str, ...]


def prepare_jpeg(path: Path) -> PreparedJpeg:
    """Apply EXIF orientation once, then convert an embedded source profile to sRGB."""
    try:
        with Image.open(path) as original:
            if original.format != "JPEG":
                raise ValueError("Watermark preview needs a JPEG input")
            if original.width * original.height > MAX_JPEG_PIXELS:
                raise ValueError("JPEG exceeds the 60 megapixel watermark limit")
            oriented = ImageOps.exif_transpose(original)
            embedded_icc = original.info.get("icc_profile")
            dpi = original.info.get("dpi")
    except Image.DecompressionBombError as error:
        raise ValueError("JPEG exceeds the 60 megapixel watermark limit") from error
    srgb_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
    if embedded_icc:
        try:
            source_profile = ImageCms.ImageCmsProfile(BytesIO(embedded_icc))
            pixels = ImageCms.profileToProfile(
                oriented, source_profile, srgb_profile, outputMode="RGB"
            )
        except (OSError, ValueError, ImageCms.PyCMSError) as error:
            raise ValueError("JPEG has an unreadable ICC profile") from error
        if pixels is None:
            raise ValueError("ICC conversion produced no pixels")
        warnings: tuple[str, ...] = ()
    else:
        if oriented.mode not in {"RGB", "L"}:
            raise ValueError("JPEG without ICC has an ambiguous color mode")
        pixels = oriented.convert("RGB")
        warnings = ("No ICC profile; assumed sRGB for preview",)
    return PreparedJpeg(pixels, srgb_profile.tobytes(), dpi, warnings)


def watermark_jpeg_pixels(
    path: Path, config: WatermarkConfig, resources: WatermarkResources
) -> PreparedJpeg:
    """Return watermarked RGB pixels and their matching sRGB ICC, without saving."""
    prepared = prepare_jpeg(path)
    overlay = render_watermark_layer(prepared.pixels.size, config, resources)
    composited = Image.alpha_composite(prepared.pixels.convert("RGBA"), overlay)
    return PreparedJpeg(
        composited.convert("RGB"), prepared.srgb_icc, prepared.dpi, prepared.warnings
    )


def _digest(path: Path) -> bytes:
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.digest()


def export_watermark_preview(
    source: Path,
    target: Path,
    config: WatermarkConfig,
    resources: WatermarkResources,
    *,
    quality: int = 95,
    subsampling: int = 0,
) -> tuple[str, ...]:
    """Export a single local JPEG preview without replacing an input or target.

    This S5 preview carries orientation, color and DPI, but full camera metadata
    preservation belongs to the later S6 metadata pipeline.
    """
    if type(quality) is not int or not 1 <= quality <= 100:
        raise ValueError("JPEG quality must be an integer from 1 to 100")
    if type(subsampling) is not int or subsampling not in {0, 1, 2}:
        raise ValueError("JPEG subsampling must be 0, 1 or 2")
    if target.suffix.lower() not in {".jpg", ".jpeg"}:
        raise ValueError("Watermark preview output must be JPEG")
    source = source.resolve()
    target = target.resolve()
    if target == source or target.parent == source.parent:
        raise ValueError("Watermark output directory must differ from source")
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    original_digest = _digest(source)
    prepared = watermark_jpeg_pixels(source, config, resources)
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".aim-mark-", dir=target.parent) as name:
        staged = Path(name) / target.name
        options: dict[str, object] = {
            "quality": quality,
            "subsampling": subsampling,
            "icc_profile": prepared.srgb_icc,
        }
        orientation = Image.Exif()
        orientation[274] = 1
        options["exif"] = orientation.tobytes()
        if prepared.dpi is not None:
            options["dpi"] = prepared.dpi
        prepared.pixels.save(staged, format="JPEG", **options)
        if _digest(source) != original_digest:
            raise OSError("Source changed during watermark preview")
        commit_no_overwrite(staged, target)
    return prepared.warnings
