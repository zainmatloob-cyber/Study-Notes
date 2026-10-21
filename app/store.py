"""Very small on-disk store: data/<doc_id>/{meta.json, segments.json, notes.md, files/}."""
import json
import shutil
import time
import uuid
from pathlib import Path

from .config import DATA_DIR


def new_doc_id() -> str:
    return uuid.uuid4().hex[:12]


def doc_dir(doc_id: str) -> Path:
    if not doc_id.isalnum():
        raise KeyError(doc_id)
    return DATA_DIR / doc_id


def exists(doc_id: str) -> bool:
    try:
        return (doc_dir(doc_id) / "meta.json").exists()
    except KeyError:
        return False


def save_doc(doc_id: str, meta: dict, segments: list[dict]) -> None:
    d = doc_dir(doc_id)
    d.mkdir(parents=True, exist_ok=True)
    meta = {**meta, "id": doc_id, "created": meta.get("created", time.time())}
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (d / "segments.json").write_text(json.dumps(segments, ensure_ascii=False), encoding="utf-8")


def load_meta(doc_id: str) -> dict:
    meta = json.loads((doc_dir(doc_id) / "meta.json").read_text(encoding="utf-8"))
    meta["has_notes"] = (doc_dir(doc_id) / "notes.md").exists()
    return meta


def load_segments(doc_id: str) -> list[dict]:
    return json.loads((doc_dir(doc_id) / "segments.json").read_text(encoding="utf-8"))


def load_notes(doc_id: str) -> str | None:
    p = doc_dir(doc_id) / "notes.md"
    return p.read_text(encoding="utf-8") if p.exists() else None


def save_notes(doc_id: str, notes: str) -> None:
    (doc_dir(doc_id) / "notes.md").write_text(notes, encoding="utf-8")


def list_docs() -> list[dict]:
    docs = []
    for d in DATA_DIR.iterdir():
        if (d / "meta.json").exists():
            try:
                docs.append(load_meta(d.name))
            except Exception:
                continue
    return sorted(docs, key=lambda m: m.get("created", 0), reverse=True)


def delete_doc(doc_id: str) -> None:
    shutil.rmtree(doc_dir(doc_id), ignore_errors=True)
