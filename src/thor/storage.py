from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import Observation, Word


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT,
    duration REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS words (
    source_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    start REAL NOT NULL,
    end REAL NOT NULL,
    text TEXT NOT NULL,
    probability REAL,
    PRIMARY KEY (source_id, idx)
);

CREATE TABLE IF NOT EXISTS observations (
    source_id TEXT NOT NULL,
    window_index INTEGER NOT NULL,
    start REAL NOT NULL,
    end REAL NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_id, window_index)
);

CREATE TABLE IF NOT EXISTS story_chunks (
    source_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    start_word INTEGER NOT NULL,
    end_word INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_id, chunk_index)
);
"""


class Library:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)

    def upsert_source(
        self,
        source_id: str,
        title: str,
        kind: str,
        path: str | None = None,
        duration: float | None = None,
    ) -> None:
        self.db.execute(
            """
            INSERT INTO sources(id,title,kind,path,duration)
            VALUES(?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              title=excluded.title,
              kind=excluded.kind,
              path=excluded.path,
              duration=excluded.duration
            """,
            (source_id, title, kind, path, duration),
        )
        self.db.commit()

    def replace_words(self, source_id: str, words: list[Word]) -> None:
        with self.db:
            self.db.execute("DELETE FROM words WHERE source_id=?", (source_id,))
            self.db.executemany(
                "INSERT INTO words(source_id,idx,start,end,text,probability) VALUES(?,?,?,?,?,?)",
                [
                    (source_id, i, w.start, w.end, w.text, w.probability)
                    for i, w in enumerate(words)
                ],
            )

    def save_observation(self, obs: Observation) -> None:
        self.db.execute(
            """
            INSERT INTO observations(source_id,window_index,start,end,payload_json)
            VALUES(?,?,?,?,?)
            ON CONFLICT(source_id,window_index) DO UPDATE SET
              start=excluded.start,
              end=excluded.end,
              payload_json=excluded.payload_json
            """,
            (
                obs.source_id,
                obs.window_index,
                obs.start,
                obs.end,
                json.dumps(obs.payload, ensure_ascii=False),
            ),
        )
        self.db.commit()

    def has_observation(self, source_id: str, window_index: int) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM observations WHERE source_id=? AND window_index=?",
            (source_id, window_index),
        ).fetchone()
        return bool(row)

    def save_story_chunk(
        self,
        source_id: str,
        chunk_index: int,
        start_word: int,
        end_word: int,
        payload: dict[str, Any],
    ) -> None:
        self.db.execute(
            """
            INSERT INTO story_chunks(source_id,chunk_index,start_word,end_word,payload_json)
            VALUES(?,?,?,?,?)
            ON CONFLICT(source_id,chunk_index) DO UPDATE SET
              start_word=excluded.start_word,
              end_word=excluded.end_word,
              payload_json=excluded.payload_json
            """,
            (
                source_id,
                chunk_index,
                start_word,
                end_word,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        self.db.commit()

    def counts(self) -> dict[str, int]:
        names = ["sources", "words", "observations", "story_chunks"]
        return {
            name: int(self.db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
            for name in names
        }

    def iter_observations(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            """
            SELECT s.title, o.source_id, o.window_index, o.start, o.end, o.payload_json
            FROM observations o
            JOIN sources s ON s.id=o.source_id
            ORDER BY s.title, o.window_index
            """
        ).fetchall()
        return [
            {
                "title": row[0],
                "source_id": row[1],
                "window_index": row[2],
                "start": row[3],
                "end": row[4],
                "payload": json.loads(row[5]),
            }
            for row in rows
        ]
