from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from pypdf import PdfReader
from rich.console import Console

from .media import detect_shot_boundaries, extract_audio, extract_frames_at, probe_duration, sample_times_from_shots
from .models import Observation, ViewingWindow
from .storage import Library
from .transcribe import transcribe_words, words_for_window
from .vision import OpenAIVisionReader


console = Console()


def thor_root() -> Path:
    return Path(".thor")


def library() -> Library:
    return Library(thor_root() / "library.sqlite")


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return value or "source"


def source_id_for(title: str, path: Path) -> str:
    raw = f"{title}|{path.resolve()}".encode("utf-8")
    return f"{slugify(title)}-{hashlib.sha256(raw).hexdigest()[:10]}"


def watch_movie(
    video: Path,
    title: str,
    window_seconds: float = 60.0,
    max_visual_gap: float = 5.0,
    scene_threshold: float = 0.30,
    start_minute: int = 0,
    limit_minutes: int | None = None,
    resume: bool = True,
) -> str:
    video = video.expanduser().resolve()
    if not video.exists():
        raise FileNotFoundError(video)

    root = thor_root()
    db = library()
    source_id = source_id_for(title, video)
    source_dir = root / "movies" / source_id
    duration = probe_duration(video)
    db.upsert_source(source_id, title, "video", str(video), duration)

    console.print(f"[bold]THOR WATCHER[/bold] {title}")
    console.print(f"duration={duration / 60:.2f} min source_id={source_id}")

    audio = extract_audio(video, source_dir / "audio.wav")
    word_cache = source_dir / "words.json"
    console.print("Transcribing actual audio with word timestamps...")
    words = transcribe_words(audio, word_cache)
    db.replace_words(source_id, words)
    console.print(f"words={len(words):,}")

    shot_cache = source_dir / "shot_boundaries.json"
    if shot_cache.exists():
        shot_boundaries = json.loads(shot_cache.read_text(encoding="utf-8"))
    else:
        console.print("Detecting shot boundaries across the full video...")
        shot_boundaries = detect_shot_boundaries(video, threshold=scene_threshold)
        source_dir.mkdir(parents=True, exist_ok=True)
        shot_cache.write_text(
            json.dumps(shot_boundaries, indent=2),
            encoding="utf-8",
        )
    console.print(f"shot_intervals={max(0, len(shot_boundaries) - 1):,}")

    reader = OpenAIVisionReader()
    total_windows = math.ceil(duration / window_seconds)
    first = max(0, int((start_minute * 60) // window_seconds))
    last = total_windows
    if limit_minutes is not None:
        max_seconds = max(0, limit_minutes * 60)
        last = min(total_windows, first + math.ceil(max_seconds / window_seconds))

    for index in range(first, last):
        if resume and db.has_observation(source_id, index):
            console.print(f"[dim]skip window {index:04d}: already observed[/dim]")
            continue

        start = index * window_seconds
        end = min(duration, start + window_seconds)
        frame_dir = source_dir / "frames" / f"{index:04d}"
        frame_times = sample_times_from_shots(
            boundaries=shot_boundaries,
            start=start,
            end=end,
            max_gap=max_visual_gap,
        )
        frames = extract_frames_at(
            video=video,
            times=frame_times,
            out_dir=frame_dir,
        )
        window = ViewingWindow(
            index=index,
            start=start,
            end=end,
            transcript=words_for_window(words, start, end),
            frame_paths=[str(p) for p in frames],
        )

        console.print(
            f"watch {index + 1:04d}/{total_windows:04d} "
            f"[{start / 60:.2f}-{end / 60:.2f} min] "
            f"visual_samples={len(frames)}"
        )
        payload = reader.watch(title, window)
        obs = Observation(
            source_id=source_id,
            window_index=index,
            start=start,
            end=end,
            payload=payload,
        )
        db.save_observation(obs)

        obs_dir = source_dir / "observations"
        obs_dir.mkdir(parents=True, exist_ok=True)
        (obs_dir / f"{index:04d}.json").write_text(
            json.dumps(obs.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    console.print(f"[green]finished[/green] {title}")
    return source_id


def _read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if suffix in {".txt", ".md", ".markdown"}:
        return path.read_text(encoding="utf-8")
    raise ValueError("Story input must be .txt, .md, .markdown or .pdf")


def _word_chunks(
    text: str,
    chunk_words: int = 1200,
    overlap_words: int = 150,
) -> list[tuple[int, int, str]]:
    words = text.split()
    if not words:
        return []
    step = max(1, chunk_words - overlap_words)
    chunks: list[tuple[int, int, str]] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + chunk_words)
        chunks.append((start, end, " ".join(words[start:end])))
        if end == len(words):
            break
        start += step
    return chunks


def read_story(
    path: Path,
    title: str,
    chunk_words: int = 1200,
    overlap_words: int = 150,
) -> str:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    db = library()
    source_id = source_id_for(title, path)
    db.upsert_source(source_id, title, "story", str(path), None)

    text = _read_text(path)
    chunks = _word_chunks(text, chunk_words, overlap_words)
    reader = OpenAIVisionReader()
    out_dir = thor_root() / "stories" / source_id / "observations"
    out_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]THOR STORY READER[/bold] {title}")
    console.print(f"chunks={len(chunks)}")

    for index, (start_word, end_word, chunk) in enumerate(chunks):
        console.print(f"read {index + 1:04d}/{len(chunks):04d}")
        payload = reader.read_story_chunk(title, index, chunk)
        db.save_story_chunk(
            source_id=source_id,
            chunk_index=index,
            start_word=start_word,
            end_word=end_word,
            payload=payload,
        )
        (out_dir / f"{index:04d}.json").write_text(
            json.dumps(
                {
                    "source_id": source_id,
                    "chunk_index": index,
                    "start_word": start_word,
                    "end_word": end_word,
                    "payload": payload,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    console.print(f"[green]finished[/green] {title}")
    return source_id
