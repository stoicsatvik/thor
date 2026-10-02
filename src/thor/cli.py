from __future__ import annotations

import os
import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .pipeline import library, read_story, watch_movie
from .connections import connect_library


app = typer.Typer(
    no_args_is_help=True,
    help="THOR: multimodal cinematic continuity and hypothesis engine.",
)
console = Console()


@app.command()
def doctor() -> None:
    """Check the local machine before a long watch run."""
    table = Table(title="THOR doctor")
    table.add_column("dependency")
    table.add_column("status")
    table.add_row("ffmpeg", shutil.which("ffmpeg") or "MISSING")
    table.add_row("ffprobe", shutil.which("ffprobe") or "MISSING")
    table.add_row(
        "OPENAI_API_KEY",
        "set" if os.getenv("OPENAI_API_KEY") else "MISSING",
    )
    table.add_row(
        "THOR_VISION_MODEL",
        os.getenv("THOR_VISION_MODEL", "gpt-6-luna"),
    )
    table.add_row(
        "THOR_WHISPER_MODEL",
        os.getenv("THOR_WHISPER_MODEL", "small"),
    )
    console.print(table)


@app.command("watch")
def watch(
    video: Path = typer.Argument(..., exists=True, readable=True),
    title: str = typer.Option(..., "--title", "-t"),
    window: float = typer.Option(60.0, min=10.0, help="Seconds per viewing window."),
    max_visual_gap: float = typer.Option(
        5.0,
        min=0.5,
        help="Maximum seconds between visual samples inside a long shot.",
    ),
    scene_threshold: float = typer.Option(
        0.30,
        min=0.05,
        max=0.95,
        help="ffmpeg scene-change threshold; lower detects more cuts.",
    ),
    start_minute: int = typer.Option(0, min=0),
    limit_minutes: int | None = typer.Option(None, min=1),
    resume: bool = typer.Option(True, "--resume/--restart"),
) -> None:
    """Actually inspect a local video: audio words + visual frames + minute memory."""
    watch_movie(
        video=video,
        title=title,
        window_seconds=window,
        max_visual_gap=max_visual_gap,
        scene_threshold=scene_threshold,
        start_minute=start_minute,
        limit_minutes=limit_minutes,
        resume=resume,
    )


@app.command("read-story")
def read_story_command(
    path: Path = typer.Argument(..., exists=True, readable=True),
    title: str = typer.Option(..., "--title", "-t"),
    chunk_words: int = typer.Option(1200, min=200),
    overlap_words: int = typer.Option(150, min=0),
) -> None:
    """Read all supplied text/Markdown/PDF material into THOR story memory."""
    if overlap_words >= chunk_words:
        raise typer.BadParameter("overlap_words must be smaller than chunk_words")
    read_story(
        path=path,
        title=title,
        chunk_words=chunk_words,
        overlap_words=overlap_words,
    )


@app.command("connect")
def connect(
    focus: str = typer.Option("Avengers: Doomsday", "--focus"),
    candidates: int = typer.Option(50, min=1),
    analyze: int = typer.Option(20, min=1),
    skeptic: bool = typer.Option(True, "--skeptic/--no-skeptic"),
) -> None:
    """Find cross-film echoes, generate hypotheses, then attack them."""
    connect_library(
        db=library(),
        focus=focus,
        candidates=candidates,
        analyze=analyze,
        skeptic=skeptic,
    )


@app.command()
def status() -> None:
    """Show how much evidence THOR has actually ingested."""
    counts = library().counts()
    table = Table(title="THOR evidence library")
    table.add_column("kind")
    table.add_column("count", justify="right")
    for key, value in counts.items():
        table.add_row(key, f"{value:,}")
    console.print(table)


if __name__ == "__main__":
    app()
