from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(slots=True)
class Word:
    start: float
    end: float
    text: str
    probability: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ViewingWindow:
    index: int
    start: float
    end: float
    transcript: list[Word]
    frame_paths: list[str]

    @property
    def transcript_text(self) -> str:
        return " ".join(
            f"[{w.start:.2f}-{w.end:.2f}] {w.text.strip()}"
            for w in self.transcript
            if w.text.strip()
        )


@dataclass(slots=True)
class Observation:
    source_id: str
    window_index: int
    start: float
    end: float
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
