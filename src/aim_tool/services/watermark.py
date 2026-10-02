"""Render a configurable, full-resolution watermark layer from local assets."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from aim_tool.domain.validation import validate_watermark_fields
from aim_tool.services.fonts import load_checked_font

Anchor = Literal["top_left", "top_right", "bottom_left", "bottom_right"]
Category = Literal["aviation", "railway", "landscape"]


@dataclass(frozen=True)
class WatermarkResources:
    latin_font: Path
    chinese_font: Path
    signature: Path
    latin_face: int = 0
    chinese_face: int = 0


@dataclass(frozen=True)
class WatermarkConfig:
    category: Category
    content: str
    taken_on: date
    font_size_pt: float = 36.0
    signature_width: float = 300.0
    margin_x: float = 25.0
    margin_y: float = 25.0
    anchor: Anchor = "bottom_right"
    offset_x: float = 0.0
    offset_y: float = 0.0
    signature_offset_y: float = 0.0
    color: tuple[int, int, int] = (255, 255, 255)
    latin_opacity: float = 0.5
    chinese_opacity: float = 0.5
    signature_opacity: float = 0.5
    base_width: int = 6016
    base_height: int = 4016
    base_ppi: float = 300.0


def _validate(config: WatermarkConfig) -> None:
    try:
        validate_watermark_fields(config.category, config.content)
    except ValueError as error:
        raise ValueError(f"Invalid watermark content: {error}") from error
    if config.anchor not in {"top_left", "top_right", "bottom_left", "bottom_right"}:
        raise ValueError("Unsupported watermark anchor")
    positive = (
        config.font_size_pt,
        config.signature_width,
        config.base_ppi,
        config.base_width,
        config.base_height,
    )
    nonnegative = (config.margin_x, config.margin_y)
    alpha = (config.latin_opacity, config.chinese_opacity, config.signature_opacity)
    if (
        any(not math.isfinite(value) or value <= 0 for value in positive)
        or any(not math.isfinite(value) or value < 0 for value in nonnegative)
        or any(not math.isfinite(value) or not 0 <= value <= 1 for value in alpha)
        or any(
            not math.isfinite(value)
            for value in (config.offset_x, config.offset_y, config.signature_offset_y)
        )
        or len(config.color) != 3
        or any(type(channel) is not int or not 0 <= channel <= 255 for channel in config.color)
    ):
        raise ValueError("Invalid watermark dimensions, color or opacity")


def _spans(config: WatermarkConfig) -> list[tuple[str, bool]]:
    if config.category != "landscape":
        return [(f"{config.content}|{config.taken_on:%Y/%m/%d} © ", False)]
    result: list[tuple[str, bool]] = []
    for character in config.content:
        chinese = not character.isascii()
        if result and result[-1][1] == chinese:
            previous, _ = result[-1]
            result[-1] = (previous + character, chinese)
        else:
            result.append((character, chinese))
    suffix = f"|{config.taken_on:%Y/%m/%d} © "
    if result and not result[-1][1]:
        result[-1] = (result[-1][0] + suffix, False)
    else:
        result.append((suffix, False))
    return result


def _scaled_signature(path: Path, width: int, opacity: float) -> Image.Image:
    with Image.open(path) as original:
        rgba = original.convert("RGBA")
    bounds = rgba.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("Signature has no visible pixels")
    rgba = rgba.crop(bounds)
    height = max(1, round(rgba.height * width / rgba.width))
    signature = rgba.convert("RGBa").resize((width, height), Image.Resampling.LANCZOS)
    signature = signature.convert("RGBA")
    alpha = signature.getchannel("A").point(lambda value: round(value * opacity))
    signature.putalpha(alpha)
    return signature


def render_watermark_layer(
    size: tuple[int, int], config: WatermarkConfig, resources: WatermarkResources
) -> Image.Image:
    """Render an RGBA layer in final image coordinates; never modify assets."""
    _validate(config)
    width, height = size
    if width <= 0 or height <= 0:
        raise ValueError("Image size must be positive")
    scale = (
        min(width / config.base_width, height / config.base_height)
        if width >= height
        else min(width / config.base_height, height / config.base_width)
    )
    pixels = max(1, round(config.font_size_pt * config.base_ppi / 72 * scale))
    spans = _spans(config)
    latin_text = "".join(text for text, chinese in spans if not chinese)
    chinese_text = "".join(text for text, chinese in spans if chinese)
    latin = load_checked_font(resources.latin_font, resources.latin_face, latin_text, pixels)
    chinese = (
        load_checked_font(resources.chinese_font, resources.chinese_face, chinese_text, pixels)
        if chinese_text
        else None
    )
    runs: list[tuple[str, ImageFont.FreeTypeFont, float, float]] = []
    position = 0.0
    boxes: list[tuple[int, int, int, int]] = []
    for text, is_chinese in spans:
        font = chinese if is_chinese else latin
        assert font is not None
        opacity = config.chinese_opacity if is_chinese else config.latin_opacity
        box = font.getbbox(text, anchor="ls")
        boxes.append(
            (round(position + box[0]), round(box[1]), round(position + box[2]), round(box[3]))
        )
        runs.append((text, font, position, opacity))
        position += font.getlength(text)
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(round(position), *(box[2] for box in boxes))
    bottom = max(box[3] for box in boxes)
    text_layer = Image.new("RGBA", (right - left + 2, bottom - top + 2))
    for text, font, advance, opacity in runs:
        mask = Image.new("L", text_layer.size)
        ImageDraw.Draw(mask).text((advance - left, -top), text, font=font, anchor="ls", fill=255)
        mask = mask.point(lambda value, factor=opacity: round(value * factor))
        color_layer = Image.new("RGBA", text_layer.size, (*config.color, 0))
        color_layer.putalpha(mask)
        text_layer.alpha_composite(color_layer)
    signature = _scaled_signature(
        resources.signature, max(1, round(config.signature_width * scale)), config.signature_opacity
    )
    # The default is visible-bottom alignment. An explicit offset lets the user
    # calibrate Q4 without changing the confirmed outer 25 px margin.
    signature_top = text_layer.height - signature.height + round(config.signature_offset_y * scale)
    group_top = min(0, signature_top)
    group_bottom = max(text_layer.height, signature_top + signature.height)
    group = Image.new("RGBA", (text_layer.width + signature.width, group_bottom - group_top))
    group.alpha_composite(text_layer, (0, -group_top))
    group.alpha_composite(signature, (text_layer.width, signature_top - group_top))
    visible = group.getchannel("A").getbbox()
    if visible is None:
        raise ValueError("Watermark is invisible")
    group = group.crop(visible)
    margin_x = round(config.margin_x * scale)
    margin_y = round(config.margin_y * scale)
    offset_x = round(config.offset_x * scale)
    offset_y = round(config.offset_y * scale)
    x = (margin_x if config.anchor.endswith("left") else width - margin_x - group.width) + offset_x
    y = (
        margin_y if config.anchor.startswith("top") else height - margin_y - group.height
    ) + offset_y
    if x < 0 or y < 0 or x + group.width > width or y + group.height > height:
        raise ValueError("Watermark does not fit this image")
    overlay = Image.new("RGBA", size)
    overlay.alpha_composite(group, (x, y))
    return overlay
