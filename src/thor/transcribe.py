from __future__ import annotations

import json
import os
from pathlib import Path

from .models import Word


def transcribe_words(audio_path: Path, cache_path: Path | None = None) -> list[Word]:
    """Transcribe actual audio with word timestamps using faster-whisper."""
    if cache_path and cache_path.exists():
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return [Word(**item) for item in data]

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed. Run: pip install -e .") from exc

    model_name = os.getenv("THOR_WHISPER_MODEL", "small")
    device = os.getenv("THOR_WHISPER_DEVICE", "auto")
    compute_type = os.getenv("THOR_WHISPER_COMPUTE", "default")

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
    )

    words: list[Word] = []
    for segment in segments:
        for word in segment.words or []:
            words.append(
                Word(
                    start=float(word.start),
                    end=float(word.end),
                    text=str(word.word),
                    probability=float(word.probability) if word.probability is not None else None,
                )
            )

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps([w.to_dict() for w in words], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return words


def words_for_window(words: list[Word], start: float, end: float) -> list[Word]:
    return [w for w in words if w.end >= start and w.start < end]
