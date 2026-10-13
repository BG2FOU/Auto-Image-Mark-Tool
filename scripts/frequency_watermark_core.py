"""Experimental frequency watermark primitives; deliberately outside the application.

The key determines slot allocation and bit whitening. This is a demonstration of
signature recovery, not an authenticated detector or a cryptographic watermark.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from hashlib import sha256

import numpy as np
from PIL import Image

VERSION = "frequency-signature-v1"


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

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Spec:
        return cls(
            data["algorithm"],
            tuple(data["image_size"]),
            tuple(data["signature_size"]),
            data["strength"],
            data["repeats"],
            data["version"],
        )


def signature_bits(image: Image.Image, width: int = 128) -> np.ndarray:
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
    resized = mask.resize((width, height), Image.Resampling.LANCZOS)
    result = np.asarray(resized) >= 48
    if not result.any() or result.all():
        raise ValueError("Signature bitmap must contain strokes and background")
    return result


def bitmap_image(bits: np.ndarray, scale: int = 1) -> Image.Image:
    image = Image.fromarray(np.where(bits, 0, 255).astype(np.uint8))
    return image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)


def luminance(rgb: np.ndarray) -> np.ndarray:
    return (
        rgb[..., 0].astype(np.float32) * 0.299
        + rgb[..., 1].astype(np.float32) * 0.587
        + rgb[..., 2].astype(np.float32) * 0.114
    )


def _allocation(spec: Spec, key: str) -> tuple[np.ndarray, np.ndarray]:
    spec.validate()
    if not isinstance(key, str) or len(key) < 16:
        raise ValueError("Use a local key of at least 16 characters")
    seed = int.from_bytes(sha256((VERSION + spec.algorithm + key).encode()).digest(), "big")
    rng = np.random.Generator(np.random.PCG64(seed))
    count = spec.bit_count * spec.repeats
    slots = rng.permutation(spec.capacity)[:count]
    whitening = rng.integers(0, 2, count, dtype=np.uint8).astype(bool)
    return slots, whitening


def _check_pixels(rgb: np.ndarray, spec: Spec) -> None:
    spec.validate()
    w, h = spec.image_size
    if rgb.shape != (h, w, 3) or rgb.dtype != np.uint8:
        raise ValueError("Pixels must be uint8 RGB at the original size; no automatic alignment")


def _dct_pattern(u: int, v: int) -> np.ndarray:
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


def _dct_embed(y: np.ndarray, slots: np.ndarray, signed: np.ndarray, spec: Spec) -> None:
    nx = spec.image_size[0] // 8
    offsets = np.arange(8)
    for start in range(0, len(slots), 8192):
        subset = slots[start : start + 8192]
        row = (subset // nx)[:, None, None] * 8 + offsets[None, :, None]
        col = (subset % nx)[:, None, None] * 8 + offsets[None, None, :]
        blocks = y[row, col]
        diff = np.sum(blocks * _DCT_DIFFERENCE, axis=(1, 2))
        sign = signed[start : start + len(subset)]
        adjustment = (sign * np.maximum(spec.strength, sign * diff) - diff) / 2
        y[row, col] = blocks + adjustment[:, None, None] * _DCT_DIFFERENCE


def _dct_read(y: np.ndarray, slots: np.ndarray, spec: Spec) -> np.ndarray:
    nx = spec.image_size[0] // 8
    offsets = np.arange(8)
    result = np.empty(len(slots), dtype=bool)
    for start in range(0, len(slots), 8192):
        subset = slots[start : start + 8192]
        row = (subset // nx)[:, None, None] * 8 + offsets[None, :, None]
        col = (subset % nx)[:, None, None] * 8 + offsets[None, None, :]
        result[start : start + len(subset)] = (
            np.sum(y[row, col] * _DCT_DIFFERENCE, axis=(1, 2)) >= 0
        )
    return result


def _fft_transform(
    y: np.ndarray, slots: np.ndarray, spec: Spec, signed: np.ndarray | None
) -> np.ndarray:
    nx = spec.image_size[0] // 64
    ny = spec.image_size[1] // 64
    lookup = np.full(nx * ny * 32, -1, dtype=np.int32)
    lookup[slots] = np.arange(len(slots))
    lookup = lookup.reshape(ny, nx, 32)
    result = np.empty(len(slots), dtype=bool)
    for row in range(ny):
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


def embed(rgb: np.ndarray, bits: np.ndarray, spec: Spec, key: str) -> tuple[np.ndarray, dict]:
    _check_pixels(rgb, spec)
    if bits.dtype != bool or bits.shape != spec.signature_size[::-1]:
        raise ValueError("Signature bitmap does not match sidecar size")
    slots, whitening = _allocation(spec, key)
    encoded = np.tile(bits.ravel(), spec.repeats) ^ whitening
    signed = np.where(encoded, 1, -1).astype(np.float32)
    original_y = luminance(rgb)
    marked_y = original_y.copy()
    if spec.algorithm == "dct":
        _dct_embed(marked_y, slots, signed, spec)
    else:
        _fft_transform(marked_y, slots, spec, signed)
    delta = marked_y - original_y
    del original_y, marked_y
    output = np.empty_like(rgb)
    clipped = 0
    for channel in range(3):
        values = rgb[..., channel].astype(np.float32) + delta
        clipped += int(np.count_nonzero((values < 0) | (values > 255)))
        output[..., channel] = np.clip(np.rint(values), 0, 255).astype(np.uint8)
    return output, {"clipped_channel_values": clipped, "slot_count": len(slots)}


def extract(rgb: np.ndarray, spec: Spec, key: str) -> np.ndarray:
    _check_pixels(rgb, spec)
    slots, whitening = _allocation(spec, key)
    y = luminance(rgb)
    observed = (
        _dct_read(y, slots, spec)
        if spec.algorithm == "dct"
        else _fft_transform(y, slots, spec, None)
    )
    votes = (observed ^ whitening).reshape(spec.repeats, spec.bit_count).sum(axis=0)
    return (votes > spec.repeats // 2).reshape(spec.signature_size[::-1])


def recovery_metrics(expected: np.ndarray, recovered: np.ndarray) -> dict:
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


def psnr(first: np.ndarray, second: np.ndarray) -> float | None:
    if first.shape != second.shape:
        raise ValueError("Different image sizes")
    squared = 0.0
    for start in range(0, first.shape[0], 256):
        diff = first[start : start + 256].astype(np.float64) - second[start : start + 256]
        squared += float(np.sum(diff * diff))
    mse = squared / first.size
    return 10 * math.log10(255**2 / mse) if mse else None  # None means +infinity.


def _mean7(data: np.ndarray) -> np.ndarray:
    integral = np.pad(data.astype(np.float64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    return (integral[7:, 7:] - integral[:-7, 7:] - integral[7:, :-7] + integral[:-7, :-7]) / 49


def ssim_y(first: np.ndarray, second: np.ndarray) -> float:
    """Full-resolution Y SSIM: uniform 7x7, sample covariance, valid windows."""
    if first.shape != second.shape or min(first.shape[:2]) < 7:
        raise ValueError("SSIM needs matching images at least 7 pixels across")
    total = 0.0
    count = 0
    for start in range(0, first.shape[0] - 6, 128):
        end = min(start + 128 + 6, first.shape[0])
        a = luminance(first[start:end]).astype(np.float64)
        b = luminance(second[start:end]).astype(np.float64)
        ma, mb = _mean7(a), _mean7(b)
        va = np.maximum(0, (_mean7(a * a) - ma * ma) * 49 / 48)
        vb = np.maximum(0, (_mean7(b * b) - mb * mb) * 49 / 48)
        covariance = (_mean7(a * b) - ma * mb) * 49 / 48
        c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
        values = (2 * ma * mb + c1) * (2 * covariance + c2)
        values /= (ma * ma + mb * mb + c1) * (va + vb + c2)
        total += float(values.sum())
        count += values.size
    return total / count


def image_metrics(first: np.ndarray, second: np.ndarray) -> dict:
    return {"psnr_rgb_db": psnr(first, second), "ssim_y": ssim_y(first, second)}
