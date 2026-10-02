from __future__ import annotations

import json
import math
import os
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from openai import OpenAI
from rich.console import Console

from .pipeline import thor_root
from .storage import Library


console = Console()

STOP = {
    "about", "after", "again", "also", "because", "before", "being", "between",
    "could", "does", "from", "have", "into", "just", "more", "most", "only",
    "other", "over", "same", "some", "such", "than", "that", "their", "them",
    "then", "there", "these", "they", "this", "through", "under", "very",
    "what", "when", "where", "which", "while", "with", "would",
}


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_strings(item))
        return out
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_strings(item))
        return out
    return []


def _terms(payload: dict[str, Any]) -> set[str]:
    text = " ".join(_strings(payload)).lower()
    words = re.findall(r"[a-z][a-z0-9'-]{3,}", text)
    return {w for w in words if w not in STOP}


def generate_candidates(
    observations: list[dict[str, Any]],
    limit: int = 100,
) -> list[tuple[float, int, int, list[str]]]:
    """Cheap retrieval before expensive reasoning.

    Uses an inverted term index, avoiding naive all-pairs comparison across
    thousands of minute observations.
    """
    term_sets = [_terms(o["payload"]) for o in observations]
    inverted: dict[str, list[int]] = defaultdict(list)
    for idx, terms in enumerate(term_sets):
        for term in terms:
            inverted[term].append(idx)

    shared_counts: Counter[tuple[int, int]] = Counter()
    shared_terms: dict[tuple[int, int], set[str]] = defaultdict(set)

    for term, ids in inverted.items():
        # Ignore generic terms appearing in too many observations.
        if len(ids) > 80:
            continue
        for a, b in combinations(ids, 2):
            if observations[a]["source_id"] == observations[b]["source_id"]:
                continue
            key = (a, b)
            shared_counts[key] += 1
            if len(shared_terms[key]) < 20:
                shared_terms[key].add(term)

    scored: list[tuple[float, int, int, list[str]]] = []
    for (a, b), overlap in shared_counts.items():
        denom = math.sqrt(max(1, len(term_sets[a])) * max(1, len(term_sets[b])))
        score = overlap / denom
        scored.append((score, a, b, sorted(shared_terms[(a, b)])))

    scored.sort(reverse=True, key=lambda x: x[0])
    return scored[:limit]


CONNECTION_INSTRUCTIONS = """You are THOR's CONTINUITY + HYPOTHESIS agent.

You receive two timestamped observations from different titles that were retrieved
because they share evidence. Determine whether the connection is meaningful.

Return strict JSON:
connection_type
shared_structure
emotion_parallel
visual_or_object_parallel
dialogue_or_concept_parallel
continuity_implication
doomsday_relevance
evidence_for
evidence_against
alternative_explanations
confidence

Rules:
- Do not invent source facts.
- Similarity alone is not intentional foreshadowing.
- Separate canonical continuity from thematic echo and production coincidence.
- Doomsday relevance may be "none".
- confidence must be 0.0 to 1.0.
"""

SKEPTIC_INSTRUCTIONS = """You are THOR's SKEPTIC agent.
Attack the proposed connection using only the supplied evidence.

Return strict JSON:
strongest_objection
generic_trope_risk
chronology_risk
identity_or_observation_risk
production_coincidence_risk
missing_evidence
survives_skeptic
adjusted_confidence

Do not reward a theory for being entertaining.
"""


def _json_response(client: OpenAI, model: str, instructions: str, payload: Any) -> dict[str, Any]:
    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=json.dumps(payload, ensure_ascii=False),
    )
    text = response.output_text.strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        first_newline = text.find("\n")
        if first_newline >= 0:
            text = text[first_newline + 1 :]
        if text.rstrip().endswith(fence):
            text = text.rstrip()[: -len(fence)].rstrip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < 0:
            raise
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def connect_library(
    db: Library,
    focus: str = "Avengers: Doomsday",
    candidates: int = 50,
    analyze: int = 20,
    skeptic: bool = True,
) -> Path:
    observations = db.iter_observations()
    if len(observations) < 2:
        raise RuntimeError("THOR needs observations from at least two films first.")

    retrieved = generate_candidates(observations, limit=candidates)
    client = OpenAI()
    model = os.getenv(
        "THOR_REASONING_MODEL",
        os.getenv("THOR_VISION_MODEL", "gpt-6-luna"),
    )

    results: list[dict[str, Any]] = []
    for rank, (retrieval_score, a_idx, b_idx, shared) in enumerate(retrieved[:analyze], 1):
        a, b = observations[a_idx], observations[b_idx]
        console.print(
            f"connect {rank:03d}/{min(analyze, len(retrieved)):03d}: "
            f"{a['title']} @{a['start'] / 60:.2f}m <-> "
            f"{b['title']} @{b['start'] / 60:.2f}m"
        )

        evidence = {
            "focus": focus,
            "retrieval_score": retrieval_score,
            "shared_retrieval_terms": shared,
            "A": a,
            "B": b,
        }
        connection = _json_response(
            client,
            model,
            CONNECTION_INSTRUCTIONS,
            evidence,
        )

        skeptical_review = None
        if skeptic:
            skeptical_review = _json_response(
                client,
                model,
                SKEPTIC_INSTRUCTIONS,
                {"evidence": evidence, "proposed_connection": connection},
            )

        results.append(
            {
                "rank": rank,
                "retrieval_score": retrieval_score,
                "A": {
                    "title": a["title"],
                    "source_id": a["source_id"],
                    "window_index": a["window_index"],
                    "start": a["start"],
                    "end": a["end"],
                },
                "B": {
                    "title": b["title"],
                    "source_id": b["source_id"],
                    "window_index": b["window_index"],
                    "start": b["start"],
                    "end": b["end"],
                },
                "shared_retrieval_terms": shared,
                "connection": connection,
                "skeptic": skeptical_review,
            }
        )

    reports = thor_root() / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    out = reports / "connections.json"
    out.write_text(
        json.dumps(
            {
                "focus": focus,
                "model": model,
                "observations_considered": len(observations),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    console.print(f"[green]connection report[/green] {out}")
    return out
