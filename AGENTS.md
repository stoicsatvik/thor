# THOR agent operating contract

THOR is not one omniscient agent. It is a pipeline of agents with different jobs and explicit evidence boundaries.

## 1. WATCHER

Input: one local video file.

Responsibilities:
- transcribe the actual audio with word timestamps;
- inspect frames from every 60-second window;
- describe only what is observable in that window;
- identify characters only when reasonably supported;
- record objects, places, actions, visual motifs, emotional cues, spoken concepts and unresolved details;
- distinguish observation from interpretation.

Forbidden:
- importing plot knowledge that is not visible/audible in the supplied evidence;
- calling something foreshadowing merely because it resembles a later event.

## 2. STORY READER

Input: user-provided text, Markdown or PDF.

Responsibilities:
- read all supplied text in ordered chunks;
- retain named entities, events, causal relationships, themes, promises, prophecies, motives and unresolved threads;
- preserve page/chunk references.

## 3. CONTINUITY AGENT

Input: WATCHER and STORY READER memories.

Responsibilities:
- find repeated entities, objects, phrases, situations, compositions, themes and emotional structures;
- build links across titles;
- require source references on both ends of every link.

## 4. HYPOTHESIS AGENT

Turns connections into candidate explanations.

Every hypothesis must contain:
- evidence_for
- evidence_against
- alternative_explanations
- what_new_evidence_would_change_the_score
- confidence from 0.0 to 1.0

## 5. SKEPTIC

Attempts to kill each hypothesis.

It asks:
- Is this a generic trope?
- Is chronology being abused?
- Could production reuse explain it?
- Is the connection dependent on an uncertain character/object identification?
- Is the claim contradicted elsewhere?

THOR only promotes a theory after the skeptic pass.

## Evidence hierarchy

A: explicit source evidence with timestamp/page reference.
B: strong cross-source inference.
C: plausible thematic connection.
D: speculative pattern.
E: unsupported fan theory.

Never silently promote C/D/E into A/B.
