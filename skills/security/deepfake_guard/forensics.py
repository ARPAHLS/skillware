"""Classical image forensics and frequency analysis for security/deepfake_guard."""

from __future__ import annotations

import base64
import io
import math
from typing import Any, Dict, List, Tuple, Union

import numpy as np
from PIL import Image, ImageChops

try:
    from .constants import (
        DEFAULT_JPEG_ELA_QUALITY,
        ELA_ANOMALY_ZSCORE,
        ELA_SCALE_FACTOR,
        MOIRE_PEAK_RATIO_THRESHOLD,
        SPECTRAL_SLOPE_ANOMALY_THRESHOLD,
    )
except (ImportError, ValueError):
    import os
    import sys

    _pkg_dir = os.path.dirname(os.path.abspath(__file__))
    if _pkg_dir not in sys.path:
        sys.path.insert(0, _pkg_dir)
    from constants import (
        DEFAULT_JPEG_ELA_QUALITY,
        ELA_ANOMALY_ZSCORE,
        ELA_SCALE_FACTOR,
        MOIRE_PEAK_RATIO_THRESHOLD,
        SPECTRAL_SLOPE_ANOMALY_THRESHOLD,
    )


def load_image(source: Union[str, bytes, Image.Image]) -> Image.Image:
    """
    Safely decodes an image from a file path, base64 data string, raw bytes, or PIL Image.
    Converts palletized or RGBA images into consistent RGB format.
    """
    if isinstance(source, Image.Image):
        return source.convert("RGB")

    if isinstance(source, bytes):
        try:
            img = Image.open(io.BytesIO(source))
            return img.convert("RGB")
        except Exception as exc:
            raise ValueError(f"Failed to decode image from raw bytes: {exc}") from exc

    if isinstance(source, str):
        src_str = source.strip()
        # Check if base64 data URI
        if src_str.startswith("data:image/") and ";base64," in src_str:
            _, b64_part = src_str.split(";base64,", 1)
            raw_bytes = base64.b64decode(b64_part)
            return load_image(raw_bytes)

        # Check if plain base64 string
        if len(src_str) > 100 and not src_str.endswith(
            (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp")
        ):
            try:
                raw_bytes = base64.b64decode(src_str)
                img = Image.open(io.BytesIO(raw_bytes))
                return img.convert("RGB")
            except Exception:
                pass

        # Treat as file path
        try:
            img = Image.open(src_str)
            return img.convert("RGB")
        except Exception as exc:
            raise ValueError(f"Failed to open image file '{src_str}': {exc}") from exc

    raise TypeError(f"Unsupported image source type: {type(source).__name__}")


def compute_ela(
    image: Image.Image,
    quality: int = DEFAULT_JPEG_ELA_QUALITY,
    scale_factor: float = ELA_SCALE_FACTOR,
    grid_size: int = 16,
) -> Dict[str, Any]:
    """
    Error Level Analysis (ELA).
    Recompresses image as JPEG in memory, computes pixel difference matrix,
    and identifies local compression hotspots indicating splices or layered edits.
    """
    # Save copy to JPEG buffer
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    recompressed = Image.open(buffer)

    # Compute difference
    diff = ImageChops.difference(image, recompressed)
    diff_arr = np.asarray(diff, dtype=np.float32)

    # Scale extrema
    ela_lum = np.mean(diff_arr, axis=2)  # 2D luminance difference
    global_mean = float(np.mean(ela_lum))
    global_std = float(np.std(ela_lum))
    global_max = float(np.max(ela_lum))

    # Tiling grid anomaly search
    h, w = ela_lum.shape
    tile_h = max(8, h // grid_size)
    tile_w = max(8, w // grid_size)

    hotspots: List[Dict[str, Any]] = []
    threshold = global_mean + (ELA_ANOMALY_ZSCORE * global_std)

    for i in range(0, h - tile_h + 1, tile_h):
        for j in range(0, w - tile_w + 1, tile_w):
            patch = ela_lum[i : i + tile_h, j : j + tile_w]
            patch_mean = float(np.mean(patch))
            if patch_mean > threshold and global_std > 0.5:
                z_score = float((patch_mean - global_mean) / (global_std + 1e-6))
                hotspots.append(
                    {
                        "x": int(j),
                        "y": int(i),
                        "width": int(tile_w),
                        "height": int(tile_h),
                        "patch_mean": round(patch_mean, 2),
                        "z_score": round(z_score, 2),
                    }
                )

    # Determine ELA anomaly score between 0.0 and 1.0
    if global_std < 0.1:
        anomaly_score = 0.0
    else:
        hotspot_ratio = min(1.0, len(hotspots) / 10.0)
        z_factor = min(
            1.0, max(0.0, (global_max - global_mean) / (5.0 * (global_std + 1e-6)))
        )
        anomaly_score = round(0.6 * hotspot_ratio + 0.4 * z_factor, 3)

    return {
        "global_mean": round(global_mean, 2),
        "global_std": round(global_std, 2),
        "global_max": round(global_max, 2),
        "hotspot_count": len(hotspots),
        "anomaly_score": anomaly_score,
        "is_anomalous": anomaly_score >= 0.45 or len(hotspots) >= 3,
        "sample_hotspots": hotspots[:5],
    }


def compute_noise_residuals(image: Image.Image, grid_size: int = 12) -> Dict[str, Any]:
    """
    Computes high-pass noise residuals using a 3x3 Laplacian kernel.
    Detects spliced faces or edited patches where local noise variance deviates
    substantially from background camera substrate.
    """
    # Convert to grayscale float array
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    h, w = gray.shape

    # Apply 3x3 Laplacian high-pass filter
    # Kernel: [[0, -1, 0], [-1, 4, -1], [0, -1, 0]]
    padded = np.pad(gray, 1, mode="reflect")
    laplacian = (
        4.0 * padded[1:-1, 1:-1]
        - padded[:-2, 1:-1]
        - padded[2:, 1:-1]
        - padded[1:-1, :-2]
        - padded[1:-1, 2:]
    )

    tile_h = max(12, h // grid_size)
    tile_w = max(12, w // grid_size)

    tile_variances: List[float] = []
    tile_mads: List[float] = []
    tile_coords: List[Tuple[int, int]] = []

    for i in range(0, h - tile_h + 1, tile_h):
        for j in range(0, w - tile_w + 1, tile_w):
            patch = laplacian[i : i + tile_h, j : j + tile_w]
            var = float(np.var(patch))
            mad = float(np.median(np.abs(patch - np.median(patch))))
            tile_variances.append(var)
            tile_mads.append(mad)
            tile_coords.append((j, i))

    if not tile_variances:
        return {"noise_score": 0.0, "is_inconsistent": False, "variance_ratio": 1.0}

    var_arr = np.array(tile_variances, dtype=np.float32)
    mad_arr = np.array(tile_mads, dtype=np.float32)

    median_var = float(np.median(var_arr))
    max_var = float(np.max(var_arr))
    var_ratio = max_var / (median_var + 1e-4) if median_var > 0 else 1.0

    median_mad = float(np.median(mad_arr))
    max_mad = float(np.max(mad_arr))
    mad_ratio = max_mad / (median_mad + 1e-4) if median_mad > 0 else 1.0

    # Inconsistency detection:
    # Requires elevated MAD dispersion (filtering edge spikes) and variance divergence,
    # or severe divergence in either.
    is_inconsistent = bool(
        (mad_ratio >= 3.4 and var_ratio >= 5.0)
        or (mad_ratio >= 4.5)
        or (var_ratio >= 8.0)
    )
    noise_score = min(1.0, max(0.0, (mad_ratio - 1.0) / 4.0))

    return {
        "median_variance": round(median_var, 2),
        "max_variance": round(max_var, 2),
        "variance_ratio": round(var_ratio, 2),
        "mad_ratio": round(mad_ratio, 2),
        "noise_score": round(noise_score, 3),
        "is_inconsistent": bool(is_inconsistent),
    }


def detect_screen_moire(image: Image.Image) -> Dict[str, Any]:
    """
    Fourier frequency domain analysis to detect screen-photo recapture moire patterns.
    Screens exhibit sharp periodic delta spikes in 2D FFT spectrum due to subpixel grids.
    """
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    h, w = gray.shape

    # Resize to standard power-of-two square for robust FFT comparison
    target_dim = 256
    thumb = image.convert("L").resize(
        (target_dim, target_dim), Image.Resampling.BILINEAR
    )
    arr = np.asarray(thumb, dtype=np.float32)

    # 2D FFT and centered shift
    fft = np.fft.fft2(arr)
    fft_shift = np.fft.fftshift(fft)
    magnitude = np.abs(fft_shift)
    power_spectrum = np.log1p(magnitude)

    cy, cx = target_dim // 2, target_dim // 2
    # Mask out the center low-frequency DC component (radius 18)
    y_coords, x_coords = np.ogrid[:target_dim, :target_dim]
    dist_from_center = np.sqrt((x_coords - cx) ** 2 + (y_coords - cy) ** 2)

    high_freq_mask = (dist_from_center > 24) & (
        dist_from_center < (target_dim // 2 - 4)
    )
    high_freq_vals = power_spectrum[high_freq_mask]

    if high_freq_vals.size == 0:
        return {"moire_detected": False, "peak_ratio": 1.0, "score": 0.0}

    mean_hf = float(np.mean(high_freq_vals))
    std_hf = float(np.std(high_freq_vals))
    max_hf = float(np.max(high_freq_vals))

    peak_ratio = (max_hf - mean_hf) / (std_hf + 1e-6)
    moire_detected = peak_ratio >= MOIRE_PEAK_RATIO_THRESHOLD

    score = min(1.0, max(0.0, (peak_ratio - 2.5) / 4.0))

    return {
        "moire_detected": bool(moire_detected),
        "peak_ratio": round(peak_ratio, 2),
        "score": round(score, 3),
    }


def detect_copy_move(
    image: Image.Image,
    tile_size: int = 16,
    stride: int = 8,
    similarity_threshold: float = 0.96,
) -> Dict[str, Any]:
    """
    Spatial block-matching to identify clone-stamped or copy-moved regions.
    Extracts normalized luminance and gradient feature vectors across sliding tiles.
    """
    # Downscale for high-speed deterministic execution
    thumb = image.convert("L").resize((160, 160), Image.Resampling.BILINEAR)
    arr = np.asarray(thumb, dtype=np.float32)
    h, w = arr.shape

    blocks: List[Tuple[np.ndarray, int, int]] = []
    for y in range(0, h - tile_size + 1, stride):
        for x in range(0, w - tile_size + 1, stride):
            block = arr[y : y + tile_size, x : x + tile_size]
            b_mean = np.mean(block)
            b_std = np.std(block)
            if b_std > 4.0:  # Skip flat uniform blocks
                norm_block = (block - b_mean) / (b_std + 1e-6)
                blocks.append((norm_block.flatten(), x, y))

    if len(blocks) < 4:
        return {"copy_move_detected": False, "duplicate_clusters": 0, "score": 0.0}

    # Compare features between non-adjacent blocks (min physical separation)
    min_dist = tile_size * 2
    matched_pairs: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []

    # Sample comparison with step to remain O(N) bounded
    step = max(1, len(blocks) // 80)
    for i in range(0, len(blocks), step):
        vec_a, xa, ya = blocks[i]
        for j in range(i + 1, len(blocks), step):
            vec_b, xb, yb = blocks[j]
            spatial_dist = math.hypot(xa - xb, ya - yb)
            if spatial_dist < min_dist:
                continue

            # Normalized correlation
            corr = float(np.dot(vec_a, vec_b) / len(vec_a))
            if corr >= similarity_threshold:
                matched_pairs.append(((xa, ya), (xb, yb)))
                if len(matched_pairs) >= 15:
                    break
        if len(matched_pairs) >= 15:
            break

    detected = len(matched_pairs) >= 3
    score = min(1.0, len(matched_pairs) / 8.0)

    return {
        "copy_move_detected": bool(detected),
        "duplicate_pairs_found": len(matched_pairs),
        "score": round(score, 3),
    }


def analyze_spectral_synthetic(image: Image.Image) -> Dict[str, Any]:
    """
    Radial power spectrum profile analysis for synthetic / diffusion generation cues.
    AI diffusion generators typically display high-frequency drop-off anomalies
    or lattice frequency energy bursts distinct from optical camera captures.
    """
    thumb = image.convert("L").resize((256, 256), Image.Resampling.BILINEAR)
    arr = np.asarray(thumb, dtype=np.float32)

    global_std = float(np.std(arr))
    if global_std < 12.0:
        # Smooth, uniform, or basic graphic surface; no diffusion noise to evaluate
        return {
            "spectral_slope": 0.0,
            "energy_ratio": 1.0,
            "spectral_anomaly_score": 0.0,
            "synthetic_cue_detected": False,
        }

    fft = np.fft.fft2(arr)
    magnitude = np.abs(np.fft.fftshift(fft))
    power = np.log1p(magnitude)

    cy, cx = 128, 128
    y, x = np.ogrid[:256, :256]
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2).astype(np.int32)

    # Calculate radially averaged power profile
    max_radius = 120
    radial_profile = []
    for radius in range(5, max_radius, 5):
        mask = (r >= radius) & (r < radius + 5)
        if np.any(mask):
            radial_profile.append(float(np.mean(power[mask])))

    if len(radial_profile) < 8:
        return {"synthetic_cue_detected": False, "spectral_anomaly_score": 0.0}

    # Fit linear slope to log-power vs radius
    radii = np.arange(len(radial_profile))
    slope, _ = np.polyfit(radii, radial_profile, 1)

    # Check high-frequency peak anomalies (checkerboard / VAE lattice spikes)
    high_freq_profile = radial_profile[-6:]
    hf_mean = float(np.mean(high_freq_profile))
    hf_std = float(np.std(high_freq_profile))
    hf_max = float(np.max(high_freq_profile))

    lattice_spike_ratio = (hf_max - hf_mean) / (hf_std + 1e-6)

    # Extreme slope drop or abnormal high-frequency lattice spike
    is_anomalous = (slope < -0.40 or slope > 0.08) and (
        lattice_spike_ratio > SPECTRAL_SLOPE_ANOMALY_THRESHOLD
    )
    anomaly_score = min(1.0, max(0.0, (lattice_spike_ratio - 2.0) / 3.0))

    return {
        "spectral_slope": round(float(slope), 3),
        "lattice_spike_ratio": round(lattice_spike_ratio, 2),
        "spectral_anomaly_score": round(anomaly_score, 3),
        "synthetic_cue_detected": bool(is_anomalous and anomaly_score >= 0.5),
    }
