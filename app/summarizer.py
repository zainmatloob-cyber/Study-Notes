"""Map-reduce study-notes generation. Yields progress events so the UI can show a progress bar."""
from typing import Iterator

from . import config, llm, prompts
from .chunking import Chunk, chunk_segments, estimate_tokens


def _reduce_budget() -> int:
    return max(config.CHUNK_TOKENS * 2, 4000)


def generate_notes(title: str, segments: list[dict]) -> Iterator[dict]:
    """Yields {"type": "progress", "message", "done", "total"} ... then {"type": "notes", "markdown"}."""
    chunks = chunk_segments(segments, config.CHUNK_TOKENS)
    sys = {"role": "system", "content": prompts.SYSTEM_TUTOR}

    if len(chunks) == 1:
        yield _progress("Writing study guide...", 0, 1)
        md = llm.complete([sys, {"role": "user", "content": prompts.SINGLE_NOTES.format(
            title=title, text=chunks[0].text)}], max_tokens=3000)
        yield {"type": "notes", "markdown": md.strip()}
        return

    # Map: notes per chunk
    total = len(chunks) + 1
    part_notes: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        yield _progress(f"Reading part {i} of {len(chunks)} ({_span(chunk)})...", i - 1, total)
        part_notes.append(llm.complete([sys, {"role": "user", "content": prompts.MAP_NOTES.format(
            index=i, total=len(chunks), title=title, text=chunk.text)}], max_tokens=1500))

    # Collapse until the notes fit in a single reduce request
    while sum(estimate_tokens(n) for n in part_notes) > _reduce_budget() and len(part_notes) > 1:
        yield _progress(f"Condensing {len(part_notes)} sets of notes...", len(chunks), total)
        part_notes = list(_merge_round(title, part_notes, sys))

    yield _progress("Writing final study guide...", len(chunks), total)
    md = llm.complete([sys, {"role": "user", "content": prompts.REDUCE_NOTES.format(
        title=title, text="\n\n---\n\n".join(part_notes))}], max_tokens=4000)
    yield {"type": "notes", "markdown": md.strip()}


def _merge_round(title: str, notes: list[str], sys: dict) -> Iterator[str]:
    budget = _reduce_budget()
    group, size = [], 0
    for n in notes:
        t = estimate_tokens(n)
        if group and size + t > budget:
            yield _merge(title, group, sys)
            group, size = [], 0
        group.append(n)
        size += t
    if group:
        yield group[0] if len(group) == 1 else _merge(title, group, sys)


def _merge(title: str, group: list[str], sys: dict) -> str:
    return llm.complete([sys, {"role": "user", "content": prompts.MERGE_NOTES.format(
        title=title, text="\n\n---\n\n".join(group))}], max_tokens=2000)


def _span(chunk: Chunk) -> str:
    s = chunk.sources
    return s[0] if s[0] == s[-1] else f"{s[0]} – {s[-1]}"


def _progress(message: str, done: int, total: int) -> dict:
    return {"type": "progress", "message": message, "done": done, "total": total}
