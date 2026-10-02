from __future__ import annotations

import json
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


def extract_storyboard(
    video: Path,
    start: float,
    end: float,
    out_dir: Path,
    frame_count: int = 6,
    max_width: int = 768,
) -> list[Path]:
    """Extract evenly spaced visual evidence from one viewing window."""
    require_binary("ffmpeg")
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = max(end - start, 0.001)
    count = max(1, frame_count)
    offsets = [start + duration * (i + 0.5) / count for i in range(count)]

    paths: list[Path] = []
    for i, t in enumerate(offsets):
        out = out_dir / f"{i:02d}_{t:010.3f}.jpg"
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
