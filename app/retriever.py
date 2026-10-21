"""BM25 keyword retrieval over document chunks for the chat feature."""
import re
from functools import lru_cache

from rank_bm25 import BM25Plus

from . import store
from .chunking import Chunk, chunk_segments

RETRIEVAL_CHUNK_TOKENS = 500

_STOP = set("""a an the and or of to in on for with is are was were be been being by as at from that this these
those it its into than then so such what which who whom how why when where do does did can could should would
will about explain tell me describe give list define""".split())


def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 1]


class DocIndex:
    def __init__(self, segments: list[dict]):
        self.chunks: list[Chunk] = chunk_segments(segments, RETRIEVAL_CHUNK_TOKENS)
        self.bm25 = BM25Plus([tokenize(c.text) or ["_"] for c in self.chunks])

    def search(self, query: str, k: int = 6) -> list[Chunk]:
        q = tokenize(query)
        if not q:
            return self.chunks[:k]
        scores = self.bm25.get_scores(q)
        ranked = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)
        hits = [i for i in ranked[:k] if scores[i] > 0] or ranked[: min(3, k)]
        return [self.chunks[i] for i in sorted(hits)]  # keep document order


@lru_cache(maxsize=16)
def get_index(doc_id: str) -> DocIndex:
    return DocIndex(store.load_segments(doc_id))
