from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI

from .models import ViewingWindow


WATCHER_INSTRUCTIONS = """You are THOR's WATCHER agent.

You are inspecting one exact time window from a film. Use ONLY the supplied frames and timestamped dialogue as primary evidence.

Return strict JSON with these keys:
summary
characters
locations
objects
actions
dialogue_concepts
visual_motifs
emotions
relationships
callbacks_or_echoes_inside_window
unresolved_details
interpretations
uncertainties

For characters use objects with name, confidence, evidence.
For locations use objects with name, confidence.
For objects use name, importance, evidence.
For emotions use subject, emotion, confidence, evidence.
For relationships use a, relation, b, confidence.
For interpretations use claim, confidence, why.

Rules:
- Observation and interpretation are different things.
- Do not use outside plot knowledge to fill missing evidence.
- If identity is uncertain, say so.
- Do not call something foreshadowing in this stage.
- Treat silence, framing, repeated objects, entrances/exits, costume changes, and emotional transitions as evidence when visible.
"""

STORY_INSTRUCTIONS = """You are THOR's STORY READER.
Read the supplied chunk as evidence, not as a trivia prompt.

Return strict JSON with:
summary
entities
events
causal_links
motives
themes
promises_or_prophecies
objects
locations
emotional_states
unresolved_threads
important_phrasing
uncertainties

Do not import facts not present in the supplied chunk.
"""


def _data_url(path: Path) -> str:
    raw = path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        first_newline = text.find("\\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.rstrip().endswith(fence):
            text = text.rstrip()[: -len(fence)].rstrip()

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise
        value = json.loads(text[start : end + 1])

    if not isinstance(value, dict):
        raise ValueError("model returned non-object JSON")
    return value


class OpenAIVisionReader:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("THOR_VISION_MODEL", "gpt-5.5")
        self.client = OpenAI()

    def watch(self, title: str, window: ViewingWindow) -> dict[str, Any]:
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    f"TITLE: {title}\\n"
                    f"WINDOW: {window.start:.3f}s to {window.end:.3f}s\\n\\n"
                    "TIMESTAMPED DIALOGUE:\\n"
                    f"{window.transcript_text or '[no intelligible dialogue]'}"
                ),
            }
        ]
        for frame in window.frame_paths:
            content.append({"type": "input_image", "image_url": _data_url(Path(frame))})

        response = self.client.responses.create(
            model=self.model,
            instructions=WATCHER_INSTRUCTIONS,
            input=[{"role": "user", "content": content}],
        )
        return _parse_json(response.output_text)

    def read_story_chunk(self, title: str, chunk_index: int, text: str) -> dict[str, Any]:
        response = self.client.responses.create(
            model=self.model,
            instructions=STORY_INSTRUCTIONS,
            input=(
                f"TITLE: {title}\\n"
                f"CHUNK: {chunk_index}\\n\\n"
                f"SOURCE TEXT:\\n{text}"
            ),
        )
        return _parse_json(response.output_text)
