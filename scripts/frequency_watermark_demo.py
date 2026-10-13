"""Embed/extract an experimental signature watermark in local JPEG copies."""

from __future__ import annotations

import argparse
import json
import secrets
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import numpy as np
from PIL import Image

from aim_tool.services.images import PreparedJpeg, prepare_jpeg

try:  # Executable script and namespace-package imports for synthetic tests.
    from scripts.frequency_watermark_core import Spec, bitmap_image, embed, extract, signature_bits
except ModuleNotFoundError:
    from frequency_watermark_core import Spec, bitmap_image, embed, extract, signature_bits


def digest(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def write_json(path: Path, data: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def save_jpeg(
    path: Path, rgb: np.ndarray, prepared: PreparedJpeg, *, quality: int = 95, subsampling: int = 0
) -> None:
    orientation = Image.Exif()
    orientation[274] = 1
    options = {
        "quality": quality,
        "subsampling": subsampling,
        "icc_profile": prepared.srgb_icc,
        "exif": orientation.tobytes(),
    }
    if prepared.dpi is not None:
        options["dpi"] = prepared.dpi
    with path.open("xb") as stream:
        Image.fromarray(rgb).save(stream, format="JPEG", **options)


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"))


def save_bitmap(path: Path, bits: np.ndarray, scale: int = 4) -> None:
    with path.open("xb") as stream:
        bitmap_image(bits, scale).save(stream, format="PNG")


def embed_file(args: argparse.Namespace) -> None:
    source = args.source.resolve()
    signature = args.signature.resolve()
    before = {source: digest(source), signature: digest(signature)}
    prepared = prepare_jpeg(source)
    rgb = np.asarray(prepared.pixels)
    with Image.open(signature) as asset:
        bits = signature_bits(asset, args.signature_width)
    spec = Spec(
        args.algorithm,
        prepared.pixels.size,
        (bits.shape[1], bits.shape[0]),
        args.strength,
        args.repeats,
    )
    spec.validate()
    target = args.output_dir.resolve()
    if target == source.parent or target == signature.parent:
        raise ValueError("Choose a new output directory separate from the source assets")
    target.mkdir(parents=True, exist_ok=False)
    key = secrets.token_hex(32)
    marked, stats = embed(rgb, bits, spec, key)
    save_jpeg(target / "watermarked.jpg", marked, prepared)
    save_bitmap(target / "signature-embedded.png", bits)
    recovered = extract(load_rgb(target / "watermarked.jpg"), spec, key)
    save_bitmap(target / "signature-recovered.png", recovered)
    write_json(target / "watermarked.json", {"spec": spec.to_dict(), "key": key})
    write_json(
        target / "local-integrity.json",
        {
            "input_hashes": {str(p): value for p, value in before.items()},
            "embedding_stats": stats,
            "warnings": prepared.warnings,
        },
    )
    if any(digest(p) != value for p, value in before.items()):
        raise OSError("Source assets changed during the experiment")
    print(target)


def extract_file(args: argparse.Namespace) -> None:
    sidecar = json.loads(args.sidecar.read_text(encoding="utf-8"))
    spec = Spec.from_dict(sidecar["spec"])
    # Geometry normalization is opt-in and is labelled as assisted extraction.
    prepared = prepare_jpeg(args.source)
    if args.restore_size:
        prepared = replace(
            prepared,
            pixels=prepared.pixels.resize(
                spec.image_size,
                Image.Resampling.LANCZOS,
            ),
        )
    recovered = extract(np.asarray(prepared.pixels), spec, sidecar["key"])
    save_bitmap(args.output, recovered)
    print(args.output.resolve())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    marking = sub.add_parser("embed")
    marking.add_argument("--source", required=True, type=Path)
    marking.add_argument("--signature", required=True, type=Path)
    marking.add_argument("--output-dir", required=True, type=Path)
    marking.add_argument("--algorithm", choices=("dct", "fft"), default="dct")
    marking.add_argument("--strength", type=float, default=16)
    marking.add_argument("--signature-width", type=int, default=128)
    marking.add_argument("--repeats", type=int, default=9)
    reading = sub.add_parser("extract")
    reading.add_argument("--source", required=True, type=Path)
    reading.add_argument("--sidecar", required=True, type=Path)
    reading.add_argument("--output", required=True, type=Path)
    reading.add_argument(
        "--restore-size",
        action="store_true",
        help="Assisted resize to original dimensions; not automatic synchronization",
    )
    args = parser.parse_args()
    try:
        if args.command == "embed":
            embed_file(args)
        else:
            extract_file(args)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Frequency watermark experiment failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
