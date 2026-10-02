"""Export one local JPEG through the configurable S5 watermark preview renderer."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import cast

from aim_tool.services.images import export_watermark_preview
from aim_tool.services.resources import identify_watermark_assets, local_project_resources
from aim_tool.services.watermark import Anchor, Category, WatermarkConfig


def _rgb(value: str) -> tuple[int, int, int]:
    if len(value) != 7 or not value.startswith("#"):
        raise argparse.ArgumentTypeError("Color must be #RRGGBB")
    try:
        channels = bytes.fromhex(value[1:])
        return channels[0], channels[1], channels[2]
    except ValueError as error:
        raise argparse.ArgumentTypeError("Color must be #RRGGBB") from error


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Local original JPEG")
    parser.add_argument("--output", type=Path, required=True, help="New preview JPEG path")
    parser.add_argument("--category", choices=("aviation", "railway", "landscape"), required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--date", type=date.fromisoformat, required=True, metavar="YYYY-MM-DD")
    parser.add_argument("--latin-font", type=Path)
    parser.add_argument("--chinese-font", type=Path)
    parser.add_argument("--signature", type=Path)
    parser.add_argument("--latin-face", type=int, default=0)
    parser.add_argument("--chinese-face", type=int, default=0)
    parser.add_argument("--font-size-pt", type=float, default=36)
    parser.add_argument("--signature-width", type=float, default=300)
    parser.add_argument("--margin-x", type=float, default=25)
    parser.add_argument("--margin-y", type=float, default=25)
    parser.add_argument(
        "--anchor",
        choices=("top_left", "top_right", "bottom_left", "bottom_right"),
        default="bottom_right",
    )
    parser.add_argument("--offset-x", type=float, default=0)
    parser.add_argument("--offset-y", type=float, default=0)
    parser.add_argument("--signature-offset-y", type=float, default=0)
    parser.add_argument("--color", type=_rgb, default=(255, 255, 255))
    parser.add_argument("--latin-opacity", type=float, default=0.5)
    parser.add_argument("--chinese-opacity", type=float, default=0.5)
    parser.add_argument("--signature-opacity", type=float, default=0.5)
    args = parser.parse_args()
    defaults = local_project_resources(root)
    resources = replace(
        defaults,
        latin_font=args.latin_font or defaults.latin_font,
        chinese_font=args.chinese_font or defaults.chinese_font,
        signature=args.signature or defaults.signature,
        latin_face=args.latin_face,
        chinese_face=args.chinese_face,
    )
    config = WatermarkConfig(
        category=cast(Category, args.category),
        content=args.content,
        taken_on=args.date,
        font_size_pt=args.font_size_pt,
        signature_width=args.signature_width,
        margin_x=args.margin_x,
        margin_y=args.margin_y,
        anchor=cast(Anchor, args.anchor),
        offset_x=args.offset_x,
        offset_y=args.offset_y,
        signature_offset_y=args.signature_offset_y,
        color=args.color,
        latin_opacity=args.latin_opacity,
        chinese_opacity=args.chinese_opacity,
        signature_opacity=args.signature_opacity,
    )
    try:
        identify_watermark_assets(resources)
        warnings = export_watermark_preview(args.source, args.output, config, resources)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Watermark preview failed: {error}\n")
    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
