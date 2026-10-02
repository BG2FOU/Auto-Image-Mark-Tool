"""Load public, versioned watermark defaults without bundling private assets."""

from __future__ import annotations

import json
from datetime import date
from importlib.resources import files
from typing import Any

from aim_tool.services.watermark import Category, WatermarkConfig


def project_default_config(category: Category, content: str, taken_on: date) -> WatermarkConfig:
    """Return a fresh configuration for one of the three built-in templates."""
    source = files("aim_tool.resources").joinpath("default_templates.json")
    data: Any = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Unsupported watermark template schema")
    if data.get("font_size_unit") != "pt":
        raise ValueError("Project watermark template needs pt units")
    categories = data.get("categories")
    if not isinstance(categories, dict) or category not in categories:
        raise ValueError(f"Unsupported watermark category: {category}")
    selected = categories[category]
    if not isinstance(selected, dict) or selected.get("separator") != "|":
        raise ValueError("Project watermark separator must be ASCII |")
    canvas = data.get("base_canvas")
    defaults = data.get("defaults")
    if not isinstance(canvas, dict) or not isinstance(defaults, dict):
        raise TypeError("Project watermark defaults are incomplete")
    color = defaults.get("color")
    if not isinstance(color, list) or len(color) != 3:
        raise ValueError("Project watermark color is invalid")
    return WatermarkConfig(
        category=category,
        content=content,
        taken_on=taken_on,
        font_size_pt=float(defaults["font_size_pt"]),
        signature_width=float(defaults["signature_width"]),
        margin_x=float(defaults["margin_x"]),
        margin_y=float(defaults["margin_y"]),
        anchor=defaults["anchor"],
        offset_x=float(defaults["offset_x"]),
        offset_y=float(defaults["offset_y"]),
        signature_offset_y=float(defaults["signature_offset_y"]),
        color=tuple(color),
        latin_opacity=float(defaults["latin_opacity"]),
        chinese_opacity=float(defaults["chinese_opacity"]),
        signature_opacity=float(defaults["signature_opacity"]),
        base_width=int(canvas["width"]),
        base_height=int(canvas["height"]),
        base_ppi=float(canvas["ppi"]),
    )
