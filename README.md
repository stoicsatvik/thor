# THOR

**Temporal Hypothesis & Ontology Reasoner** — a multimodal continuity engine for studying long-form cinematic universes.

THOR is designed to **actually inspect the source material** instead of hallucinating from remembered plot summaries.

## What "watch" means

For a local movie file THOR:

1. reads the real audio track and creates **word-level timestamps** with Whisper,
2. divides the film into 60-second viewing windows,
3. extracts multiple frames from every window,
4. gives the frames + timestamped dialogue to a vision-language model,
5. stores a structured observation for that exact minute,
6. later compares observations across films, stories and characters.

The unit of evidence is always tied back to a source + timestamp.

## Core rule

`OBSERVATION -> CONNECTION -> HYPOTHESIS -> COUNTER-EVIDENCE -> CONFIDENCE`

A cool coincidence is not automatically foreshadowing. Humanity has YouTube thumbnails for that.

## Quick start

Requirements: Python 3.11+, ffmpeg, and a local movie file you are allowed to process.

```bash
git clone https://github.com/stoicsatvik/thor
cd thor

python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .

export OPENAI_API_KEY=...
# optional:
export THOR_VISION_MODEL=gpt-5.5
export THOR_WHISPER_MODEL=small

thor doctor
thor watch "/path/to/movie.mp4" --title "Movie title"
```

THOR writes private working data to `.thor/`, which is gitignored.

## Read story material

THOR can also read text/Markdown/PDF material you provide:

```bash
thor read-story "/path/to/story.pdf" --title "Story title"
```

It chunks the material, builds structured story memory, and makes it available to the connection agents.

## Storage

```
.thor/
  library.sqlite
  movies/<slug>/
    audio.wav
    frames/
    observations/
  stories/<slug>/
    observations/
```

Do **not** commit movie files, extracted audio, subtitles, screenplays, transcripts, or large copyrighted text. Commit the engine, schemas, prompts, and your own derived research.

## Agent roles

See [AGENTS.md](AGENTS.md).

## Current state

V0.2 focuses on the ingest/watch/read layer. The next layer is cross-title retrieval, adversarial theory generation, and a graph UI.
