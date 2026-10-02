from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path


class MediaError(RuntimeError):
    pass


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise MediaError(f"{name} is required but was not found on PATH")
    return path


def probe_duration(video: Path) -> float:
    require_binary("ffprobe")
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    return float(payload["format"]["duration"])


def extract_audio(video: Path, out_wav: Path) -> Path:
    require_binary("ffmpeg")
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if out_wav.exists() and out_wav.stat().st_size > 0:
        return out_wav

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(out_wav),
        ],
        check=True,
    )
    return out_wav


def detect_shot_boundaries(video: Path, threshold: float = 0.30) -> list[float]:
    """Detect visual cuts with ffmpeg's scene-change score.

    The returned list includes 0.0 and the video duration, so consecutive values
    define shot-like intervals.
    """
    require_binary("ffmpeg")
    duration = probe_duration(video)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-i",
            str(video),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise MediaError(proc.stderr[-4000:])

    times = [0.0]
    pattern = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")
    for match in pattern.finditer(proc.stderr):
        t = float(match.group(1))
        if 0.0 < t < duration:
            times.append(t)
    times.append(duration)

    # Scene filters can emit near-duplicate timestamps. Collapse them.
    unique: list[float] = []
    for t in sorted(times):
        if not unique or abs(t - unique[-1]) > 0.04:
            unique.append(t)
    return unique


def sample_times_from_shots(
    boundaries: list[float],
    start: float,
    end: float,
    max_gap: float = 5.0,
) -> list[float]:
    """Sample every detected shot, plus extra frames inside long shots."""
    if end <= start:
        return []
    max_gap = max(0.5, max_gap)
    samples: list[float] = []

    for a, b in zip(boundaries, boundaries[1:]):
        left = max(start, a)
        right = min(end, b)
        if right <= left:
            continue
        span = right - left
        count = max(1, math.ceil(span / max_gap))
        for i in range(count):
            samples.append(left + span * (i + 0.5) / count)

    if not samples:
        samples = [(start + end) / 2.0]

    # Protect against accidental duplicates at boundaries.
    deduped: list[float] = []
    for t in sorted(samples):
        if not deduped or abs(t - deduped[-1]) > 0.04:
            deduped.append(t)
    return deduped


def extract_frames_at(
    video: Path,
    times: list[float],
    out_dir: Path,
    max_width: int = 768,
) -> list[Path]:
    require_binary("ffmpeg")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for i, t in enumerate(times):
        out = out_dir / f"{i:03d}_{t:010.3f}.jpg"
        if not out.exists():
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-ss",
                    f"{t:.3f}",
                    "-i",
                    str(video),
                    "-frames:v",
                    "1",
                    "-vf",
                    f"scale='min({max_width},iw)':-2",
                    "-q:v",
                    "5",
                    str(out),
                ],
                check=True,
            )
        paths.append(out)
    return paths


def extract_storyboard(
    video: Path,
    start: float,
    end: float,
    out_dir: Path,
    frame_count: int = 6,
    max_width: int = 768,
) -> list[Path]:
    """Fallback evenly-spaced sampler kept for experiments."""
    duration = max(end - start, 0.001)
    count = max(1, frame_count)
    times = [start + duration * (i + 0.5) / count for i in range(count)]
    return extract_frames_at(video, times, out_dir, max_width=max_width)
