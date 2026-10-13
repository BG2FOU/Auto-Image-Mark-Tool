"""Experiment measurements using the application's reviewed watermark core."""

from __future__ import annotations

import math

import numpy as np

from aim_tool.services.frequency_watermark import (
    VERSION,
    Spec,
    bitmap_image,
    embed,
    extract,
    luminance,
    recovery_metrics,
    signature_bits,
)

__all__ = [
    "VERSION",
    "Spec",
    "bitmap_image",
    "embed",
    "extract",
    "luminance",
    "recovery_metrics",
    "signature_bits",
]


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
