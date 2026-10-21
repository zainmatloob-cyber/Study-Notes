"""Group labelled segments into ~N-token chunks, keeping source labels for citation."""
from dataclasses import dataclass

CHARS_PER_TOKEN = 4  # rough heuristic; good enough for budgeting requests


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN + 1


@dataclass
class Chunk:
    text: str          # text with inline [source] markers
    sources: list[str]


def chunk_segments(segments: list[dict], max_tokens: int) -> list[Chunk]:
    max_chars = max_tokens * CHARS_PER_TOKEN
    chunks: list[Chunk] = []
    buf: list[str] = []
    sources: list[str] = []
    size = 0

    def flush():
        nonlocal buf, sources, size
        if buf:
            chunks.append(Chunk("\n\n".join(buf), sources))
        buf, sources, size = [], [], 0

    for seg in segments:
        text, src = seg["text"].strip(), seg["source"]
        # A single oversized segment is split into pieces that each carry the label
        while len(text) > max_chars:
            cut = text.rfind("\n", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            flush()
            chunks.append(Chunk(f"[{src}]\n{text[:cut]}", [src]))
            text = text[cut:].strip()
        if not text:
            continue
        block = f"[{src}]\n{text}"
        if size + len(block) > max_chars:
            flush()
        buf.append(block)
        sources.append(src)
        size += len(block)
    flush()
    return chunks
