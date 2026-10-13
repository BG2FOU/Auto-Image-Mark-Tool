"""Recoverable DCT/FFT signature watermarks with bounded, cancellable processing.

Coefficient rules are the reviewed frequency-signature-v1 demo rules. Recovery
uses a local key and dimensions, without the original photograph or signature.
"""

from __future__ import annotations

import math
import secrets
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from threading import Event, Lock
from typing import Any, Literal, TypedDict, cast

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from aim_tool.domain.models import Parameter
from aim_tool.services.fonts import ResourceStamp, resource_stamp

type Rgb = NDArray[np.uint8]
type Bits = NDArray[np.bool_]
type Floats = NDArray[np.float32]
type Indexes = NDArray[np.int64]
type Algorithm = Literal["dct", "fft"]
type Level = Literal["low", "medium", "high"]


class EmbeddingStats(TypedDict):
    clipped_channel_values: int
    slot_count: int


class RecoveryMetrics(TypedDict):
    ber: float
    stroke_recall: float
    stroke_precision: float
    stroke_iou: float
    exact: bool


def check_cancelled(cancelled: Event | None) -> None:
    if cancelled is not None and cancelled.is_set():
        raise InterruptedError("数字水印处理已取消")


VERSION = "frequency-signature-v1"

STRENGTHS: Mapping[str, Mapping[str, float]] = {
    "dct": {"low": 8, "medium": 16, "high": 32},
    "fft": {"low": 10, "medium": 20, "high": 40},
}
_PAYLOAD_CACHE: OrderedDict[tuple[Path, ResourceStamp], Bits] = OrderedDict()
_PAYLOAD_LOCK = Lock()


@dataclass(frozen=True)
class DigitalWatermarkConfig:
    key: str = field(repr=False)
    algorithm: Algorithm = "dct"
    level: Level = "medium"

    def validate(self) -> None:
        if self.algorithm not in STRENGTHS or self.level not in STRENGTHS[self.algorithm]:
            raise ValueError("数字水印仅支持 DCT/FFT 与低、中、高三个档位")
        if not valid_key(self.key):
            raise ValueError("数字水印本地密钥无效，请在水印设置中保存默认配置")

    @property
    def strength(self) -> float:
        self.validate()
        return STRENGTHS[self.algorithm][self.level]


def valid_key(key: object) -> bool:
    return isinstance(key, str) and len(key) == 64 and all(c in "0123456789abcdef" for c in key)


def digital_config(params: Mapping[str, Parameter]) -> DigitalWatermarkConfig | None:
    """Explicit legacy API workflows without digital parameters remain compatible."""
    enabled = params.get("digital_enabled", False)
    algorithm = params.get("digital_algorithm", "dct")
    level = params.get("digital_level", "medium")
    key = params.get("digital_key", "")
    if type(enabled) is not bool:
        raise ValueError("数字水印开关必须为布尔值")
    if algorithm not in {"dct", "fft"} or level not in {"low", "medium", "high"}:
        raise ValueError("数字水印仅支持 DCT/FFT 与低、中、高三个档位")
    if "digital_key" in params and not valid_key(key):
        raise ValueError("数字水印本地密钥无效")
    if not enabled:
        return None
    config = DigitalWatermarkConfig(cast(str, key), cast(Algorithm, algorithm), cast(Level, level))
    config.validate()
    return config


def digital_defaults(
    params: Mapping[str, Parameter], *, existing_key: str | None = None
) -> dict[str, Parameter]:
    """Fill UI defaults once, retaining every existing parameter and private key."""
    result = dict(params)
    result.setdefault("digital_enabled", True)
    result.setdefault("digital_algorithm", "dct")
    result.setdefault("digital_level", "medium")
    result.setdefault(
        "digital_key", existing_key if existing_key is not None else secrets.token_hex(32)
    )
    digital_config(result)
    return result


@dataclass(frozen=True)
class Spec:
    algorithm: str
    image_size: tuple[int, int]
    signature_size: tuple[int, int]
    strength: float
    repeats: int = 9
    version: str = VERSION

    def validate(self) -> None:
        if self.version != VERSION or self.algorithm not in {"dct", "fft"}:
            raise ValueError("Unsupported watermark algorithm/version")
        if any(type(v) is not int or v <= 0 for v in (*self.image_size, *self.signature_size)):
            raise ValueError("Invalid image/signature size")
        if not math.isfinite(self.strength) or self.strength <= 0:
            raise ValueError("Strength must be finite and positive")
        if type(self.repeats) is not int or self.repeats < 3 or self.repeats % 2 != 1:
            raise ValueError("Repeats must be an odd integer >= 3")
        if self.bit_count * self.repeats > self.capacity:
            raise ValueError("Image has insufficient capacity for this signature and repetition")

    @property
    def block_size(self) -> int:
        return 8 if self.algorithm == "dct" else 64

    @property
    def bit_count(self) -> int:
        return math.prod(self.signature_size)

    @property
    def capacity(self) -> int:
        w, h = self.image_size
        b = self.block_size
        return (w // b) * (h // b) * (1 if self.algorithm == "dct" else 32)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> Spec:
        def pair(name: str) -> tuple[int, int]:
            value = data[name]
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise ValueError("Invalid watermark dimensions")
            if any(type(v) is not int for v in value):
                raise ValueError("Invalid watermark dimensions")
            return cast(int, value[0]), cast(int, value[1])

        algorithm, version = data["algorithm"], data["version"]
        strength, repeats = data["strength"], data["repeats"]
        if not isinstance(algorithm, str) or not isinstance(version, str):
            raise TypeError("Invalid watermark algorithm/version")
        if type(strength) not in {int, float} or type(repeats) is not int:
            raise ValueError("Invalid watermark strength/repeats")
        result = cls(
            algorithm,
            pair("image_size"),
            pair("signature_size"),
            float(cast(float, strength)),
            repeats,
            version,
        )
        result.validate()
        return result


def signature_bits(image: Image.Image, width: int = 128) -> Bits:
    """Use transparent-asset alpha strokes; opaque assets use dark luminance."""
    if type(width) is not int or width < 8:
        raise ValueError("Signature width must be >= 8")
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema() == (255, 255):
        mask = Image.fromarray(255 - np.asarray(rgba.convert("L")))
    else:
        mask = alpha
    bounds = mask.point(lambda v: 255 if v >= 48 else 0).getbbox()
    if bounds is None:
        raise ValueError("Signature has no visible strokes")
    mask = mask.crop(bounds)
    height = max(1, round(mask.height * width / mask.width))
    if width * height > 16_384:
        raise ValueError("数字签名位图超过 16384 位限制，请使用宽高比例适当的签名")
    resized = mask.resize((width, height), Image.Resampling.LANCZOS)
    result = np.asarray(resized) >= 48
    if not result.any() or result.all():
        raise ValueError("Signature bitmap must contain strokes and background")
    return result


def bitmap_image(bits: Bits, scale: int = 1) -> Image.Image:
    image = Image.fromarray(np.where(bits, 0, 255).astype(np.uint8))
    return image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)


def luminance(rgb: Rgb) -> Floats:
    result = (
        rgb[..., 0].astype(np.float32) * 0.299
        + rgb[..., 1].astype(np.float32) * 0.587
        + rgb[..., 2].astype(np.float32) * 0.114
    )
    return cast(Floats, result)


def _allocation(spec: Spec, key: str) -> tuple[Indexes, Bits]:
    spec.validate()
    if not isinstance(key, str) or len(key) < 16:
        raise ValueError("Use a local key of at least 16 characters")
    seed = int.from_bytes(sha256((VERSION + spec.algorithm + key).encode()).digest(), "big")
    rng = np.random.Generator(np.random.PCG64(seed))
    count = spec.bit_count * spec.repeats
    slots = rng.permutation(spec.capacity)[:count]
    whitening = rng.integers(0, 2, count, dtype=np.uint8).astype(bool)
    return slots, whitening


def _check_pixels(rgb: Rgb, spec: Spec) -> None:
    spec.validate()
    w, h = spec.image_size
    if rgb.shape != (h, w, 3) or rgb.dtype != np.uint8:
        raise ValueError("Pixels must be uint8 RGB at the original size; no automatic alignment")


def _dct_pattern(u: int, v: int) -> Floats:
    t = np.arange(8, dtype=np.float32) + 0.5
    basis_u = np.cos(math.pi * u * t / 8) * (math.sqrt(1 / 8) if u == 0 else 0.5)
    basis_v = np.cos(math.pi * v * t / 8) * (math.sqrt(1 / 8) if v == 0 else 0.5)
    return np.outer(basis_u, basis_v).astype(np.float32)


_DCT_A = _dct_pattern(2, 3)
_DCT_B = _dct_pattern(3, 2)
_DCT_DIFFERENCE = _DCT_A - _DCT_B
# Columns strictly between 0 and Nyquist leave independent rFFT bins; all
# partners are represented by irfft2, so modifying these real parts stays real.
_FFT_COORDS = [(y, x) for y in range(4, 12) for x in range(4, 12)]
_FFT_A = np.array(_FFT_COORDS[::2])
_FFT_B = np.array(_FFT_COORDS[1::2])


def _dct_embed(
    y: NDArray[Any], slots: NDArray[Any], signed: NDArray[Any], spec: Spec, cancelled: Event | None
) -> None:
    nx = spec.image_size[0] // 8
    offsets = np.arange(8)
    for start in range(0, len(slots), 8192):
        check_cancelled(cancelled)
        subset = slots[start : start + 8192]
        row = (subset // nx)[:, None, None] * 8 + offsets[None, :, None]
        col = (subset % nx)[:, None, None] * 8 + offsets[None, None, :]
        blocks = y[row, col]
        diff = np.sum(blocks * _DCT_DIFFERENCE, axis=(1, 2))
        sign = signed[start : start + len(subset)]
        adjustment = (sign * np.maximum(spec.strength, sign * diff) - diff) / 2
        y[row, col] = blocks + adjustment[:, None, None] * _DCT_DIFFERENCE


def _dct_read(y: NDArray[Any], slots: NDArray[Any], spec: Spec, cancelled: Event | None) -> Bits:
    nx = spec.image_size[0] // 8
    offsets = np.arange(8)
    result = np.empty(len(slots), dtype=bool)
    for start in range(0, len(slots), 8192):
        check_cancelled(cancelled)
        subset = slots[start : start + 8192]
        row = (subset // nx)[:, None, None] * 8 + offsets[None, :, None]
        col = (subset % nx)[:, None, None] * 8 + offsets[None, None, :]
        result[start : start + len(subset)] = (
            np.sum(y[row, col] * _DCT_DIFFERENCE, axis=(1, 2)) >= 0
        )
    return result


def _fft_transform(
    y: NDArray[Any],
    slots: NDArray[Any],
    spec: Spec,
    signed: NDArray[Any] | None,
    cancelled: Event | None,
) -> NDArray[Any]:
    nx = spec.image_size[0] // 64
    ny = spec.image_size[1] // 64
    flat_lookup = np.full(nx * ny * 32, -1, dtype=np.int32)
    flat_lookup[slots] = np.arange(len(slots))
    lookup = flat_lookup.reshape(ny, nx, 32)
    result = np.empty(len(slots), dtype=bool)
    for row in range(ny):
        check_cancelled(cancelled)
        stripe = y[row * 64 : (row + 1) * 64, : nx * 64]
        blocks = stripe.reshape(64, nx, 64).transpose(1, 0, 2)
        freq = np.fft.rfft2(blocks, norm="ortho")
        a = freq[:, _FFT_A[:, 0], _FFT_A[:, 1]]
        b = freq[:, _FFT_B[:, 0], _FFT_B[:, 1]]
        diff = a.real - b.real
        chosen = lookup[row] >= 0
        indexes = lookup[row][chosen]
        if signed is None:
            result[indexes] = diff[chosen] >= 0
        else:
            sign = signed[indexes]
            adjustment = (sign * np.maximum(spec.strength, sign * diff[chosen]) - diff[chosen]) / 2
            delta = np.zeros(diff.shape, dtype=np.float32)
            delta[chosen] = adjustment
            freq[:, _FFT_A[:, 0], _FFT_A[:, 1]] += delta
            freq[:, _FFT_B[:, 0], _FFT_B[:, 1]] -= delta
            restored = np.fft.irfft2(freq, s=(64, 64), norm="ortho")
            stripe[:] = restored.transpose(1, 0, 2).reshape(64, nx * 64)
    return result


def embed(
    rgb: Rgb, bits: Bits, spec: Spec, key: str, *, cancelled: Event | None = None
) -> tuple[Rgb, EmbeddingStats]:
    check_cancelled(cancelled)
    _check_pixels(rgb, spec)
    if bits.dtype != bool or bits.shape != spec.signature_size[::-1]:
        raise ValueError("Signature bitmap does not match sidecar size")
    slots, whitening = _allocation(spec, key)
    encoded = np.tile(bits.ravel(), spec.repeats) ^ whitening
    signed = np.where(encoded, 1, -1).astype(np.float32)
    original_y = luminance(rgb)
    marked_y = original_y.copy()
    if spec.algorithm == "dct":
        _dct_embed(marked_y, slots, signed, spec, cancelled)
    else:
        _fft_transform(marked_y, slots, spec, signed, cancelled)
    marked_y -= original_y
    delta = marked_y
    del original_y
    output = np.empty_like(rgb)
    clipped = 0
    for channel in range(3):
        check_cancelled(cancelled)
        values = rgb[..., channel].astype(np.float32) + delta
        clipped += int(np.count_nonzero((values < 0) | (values > 255)))
        output[..., channel] = np.clip(np.rint(values), 0, 255).astype(np.uint8)
    return output, {"clipped_channel_values": clipped, "slot_count": len(slots)}


def extract(rgb: Rgb, spec: Spec, key: str, *, cancelled: Event | None = None) -> Bits:
    check_cancelled(cancelled)
    _check_pixels(rgb, spec)
    slots, whitening = _allocation(spec, key)
    y = luminance(rgb)
    observed = (
        _dct_read(y, slots, spec, cancelled)
        if spec.algorithm == "dct"
        else _fft_transform(y, slots, spec, None, cancelled)
    )
    votes = (observed ^ whitening).reshape(spec.repeats, spec.bit_count).sum(axis=0)
    return (votes > spec.repeats // 2).reshape(spec.signature_size[::-1])


def recovery_metrics(expected: Bits, recovered: Bits) -> RecoveryMetrics:
    if expected.shape != recovered.shape:
        raise ValueError("Different bitmap sizes")
    tp = int(np.count_nonzero(expected & recovered))
    fp = int(np.count_nonzero(~expected & recovered))
    fn = int(np.count_nonzero(expected & ~recovered))
    return {
        "ber": float(np.mean(expected != recovered)),
        "stroke_recall": tp / (tp + fn) if tp + fn else 0.0,
        "stroke_precision": tp / (tp + fp) if tp + fp else 0.0,
        "stroke_iou": tp / (tp + fp + fn) if tp + fp + fn else 0.0,
        "exact": bool(np.array_equal(expected, recovered)),
    }


def signature_payload(path: Path) -> Bits:
    """Cache only the small bitmap, keyed by content-aware resource identity."""
    stamp = resource_stamp(path)
    key = path.resolve(), stamp
    with _PAYLOAD_LOCK:
        if key in _PAYLOAD_CACHE:
            _PAYLOAD_CACHE.move_to_end(key)
            return _PAYLOAD_CACHE[key].copy()
    try:
        with Image.open(path) as image:
            if image.width * image.height > 16_000_000:
                raise ValueError("数字签名素材超过 1600 万像素限制")
            if image.format != "PNG":
                raise ValueError("数字签名素材必须为 PNG")
            bits = signature_bits(image)
    except Image.DecompressionBombError as error:
        raise ValueError("数字签名素材超过 1600 万像素限制") from error
    if resource_stamp(path) != stamp:
        raise ValueError("数字签名素材在读取时发生变化")
    with _PAYLOAD_LOCK:
        _PAYLOAD_CACHE[key] = bits.copy()
        _PAYLOAD_CACHE.move_to_end(key)
        while len(_PAYLOAD_CACHE) > 8:
            _PAYLOAD_CACHE.popitem(last=False)
    return bits


def signature_spec(
    size: tuple[int, int], config: DigitalWatermarkConfig, signature: Path
) -> tuple[Spec, Bits]:
    config.validate()
    bits = signature_payload(signature)
    spec = Spec(config.algorithm, size, (bits.shape[1], bits.shape[0]), config.strength)
    if spec.bit_count * spec.repeats > spec.capacity:
        raise ValueError(
            "图片容量不足，无法嵌入数字签名（128 px、9 次重复）；请使用较大图片或关闭附加数字水印"
        )
    spec.validate()
    return spec, bits


def apply_signature(
    pixels: Image.Image,
    config: DigitalWatermarkConfig,
    signature: Path,
    *,
    cancelled: Event | None = None,
) -> Image.Image:
    check_cancelled(cancelled)
    spec, bits = signature_spec(pixels.size, config, signature)
    rgb = np.asarray(pixels)
    marked, _ = embed(rgb, bits, spec, config.key, cancelled=cancelled)
    return Image.fromarray(marked)


def verify_signature(
    target: Path,
    config: DigitalWatermarkConfig,
    signature: Path,
    *,
    cancelled: Event | None = None,
) -> None:
    check_cancelled(cancelled)
    with Image.open(target) as image:
        spec, expected = signature_spec(image.size, config, signature)
        pixels = np.asarray(image.convert("RGB"))
    recovered = extract(pixels, spec, config.key, cancelled=cancelled)
    if not np.array_equal(expected, recovered):
        raise ValueError(
            "导出后数字签名未能完整恢复；请提高 JPEG 质量或数字水印档位，或关闭附加数字水印"
        )
