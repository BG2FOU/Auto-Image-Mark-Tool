"""Inspect and load explicitly selected local fonts without silent fallback."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from threading import get_ident

from fontTools.ttLib import TTFont, TTLibError  # type: ignore[import-untyped]
from PIL import ImageFont

type ResourceStamp = tuple[int, int, int, int, int, str]


@dataclass(frozen=True)
class FontIdentity:
    path: Path
    face: int
    family: str
    style: str
    sha256: str


def resource_stamp(path: Path) -> ResourceStamp:
    """Invalidate reuse on replacement or edits, including restored modification times."""
    stat = path.stat()
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return (
        stat.st_dev,
        stat.st_ino,
        stat.st_size,
        stat.st_mtime_ns,
        stat.st_ctime_ns,
        digest.hexdigest(),
    )


@lru_cache(maxsize=16)
def _glyphs(path: Path, face: int, stamp: ResourceStamp) -> frozenset[int]:
    font = _open_font(path, face)
    try:
        return frozenset(font.getBestCmap() or {})
    finally:
        font.close()


@lru_cache(maxsize=32)
def _render_font(
    path: Path, face: int, pixels: int, stamp: ResourceStamp, thread_id: int
) -> ImageFont.FreeTypeFont:
    # Do not share mutable FreeType objects between GUI worker threads.
    try:
        return ImageFont.truetype(str(path), pixels, index=face)
    except OSError as error:
        raise ValueError(f"Font cannot be rendered: {path}#{face}") from error


def _open_font(path: Path, face: int) -> TTFont:
    if not path.is_file() or path.suffix.lower() not in {".otf", ".ttf", ".ttc"}:
        raise ValueError(f"Font is unavailable: {path}")
    if face < 0 or (path.suffix.lower() != ".ttc" and face != 0):
        raise ValueError(f"Invalid font face: {path}#{face}")
    try:
        return TTFont(path, fontNumber=face)
    except (OSError, TTLibError) as error:
        raise ValueError(f"Font cannot be opened: {path}#{face}") from error


def identify_font(path: Path, face: int = 0) -> FontIdentity:
    """Return a stable ID and human-readable family/style for a local font."""
    font = _open_font(path, face)
    try:
        names = font["name"]
        family = names.getDebugName(1) or path.stem
        style = names.getDebugName(2) or "Regular"
    finally:
        font.close()
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return FontIdentity(path.resolve(), face, family, style, digest.hexdigest())


def load_checked_font(path: Path, face: int, text: str, pixels: int) -> ImageFont.FreeTypeFont:
    """Require every glyph in the selected face before drawing a run."""
    if pixels <= 0:
        raise ValueError("Font pixel size must be positive")
    if not path.is_file():
        raise ValueError(f"Font is unavailable: {path}")
    path = path.resolve()
    stamp = resource_stamp(path)
    cmap = _glyphs(path, face, stamp)
    missing = sorted(
        {character for character in text if character != " " and ord(character) not in cmap}
    )
    if missing:
        raise ValueError(f"Font {path.name} is missing glyphs: {''.join(missing)}")
    return _render_font(path, face, pixels, stamp, get_ident())
