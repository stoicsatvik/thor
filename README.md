# THOR

**Temporal Hypothesis & Ontology Reasoner** — a multimodal continuity engine for studying long-form cinematic universes.

THOR is designed to **actually inspect the source material** instead of hallucinating from remembered plot summaries.

## What "watch" means

For a local movie file THOR:

1. reads the real audio track and creates **word-level timestamps** with Whisper,
2. detects scene changes across the full film,
3. divides the film into 60-second viewing windows,
4. samples **every detected shot** and also samples inside long shots so motion-heavy scenes are not represented by one lonely JPEG,
5. labels every visual sample with its exact timestamp,
6. gives those images + every timestamped spoken word to a vision-language model,
7. stores a structured observation for that exact minute,
8. later compares observations across films, stories and characters.

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
export THOR_VISION_MODEL=gpt-6-luna
export THOR_WHISPER_MODEL=small
# optional: use a stronger model only for connection adjudication
export THOR_REASONING_MODEL=gpt-6.1-sol

thor doctor
thor watch "/path/to/movie.mp4" --title "Movie title"

# denser visual coverage inside long shots:
thor watch "/path/to/movie.mp4" --title "Movie title" --max-visual-gap 2.0
```

THOR writes private working data to `.thor/`, which is gitignored.

## Read story material

THOR can also read text/Markdown/PDF material you provide:

```bash
thor read-story "/path/to/story.pdf" --title "Story title"
```

It chunks the material, builds structured story memory, and makes it available to the connection agents.

## Find connections

After THOR has watched at least two titles:

```bash
thor connect --focus "Avengers: Doomsday" --candidates 80 --analyze 30
```

This first performs cheap cross-title retrieval, then asks the CONTINUITY/HYPOTHESIS agent to inspect the strongest pairs. A separate SKEPTIC agent attacks each proposed connection and returns an adjusted confidence. Reports stay under `.thor/reports/`.

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

V0.2 includes full-film shot detection, dense timestamped vision, word-level transcription, story reading, cross-title retrieval, hypothesis generation, and a skeptic pass. The next layer is semantic embeddings, persistent character identity memory, audio/music motifs, camera-motion understanding, and a graph UI.

### Important limitation

Current OpenAI vision models accept image inputs but not raw video input, so THOR converts video into dense, timestamped visual evidence rather than handing an MP4 directly to the model. The default path covers every detected shot and inserts extra samples into long shots. It is materially closer to "watching" than fixed screenshots, but true continuous motion understanding remains a separate layer.
