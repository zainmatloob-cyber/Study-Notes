import json
import re
import tempfile
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, llm, ocr, prompts, retriever, store
from .extractors import SUPPORTED_EXTS, ExtractionError, extract
from .summarizer import add_beyond, generate_notes, has_beyond

MAX_UPLOAD_MB = 100

app = FastAPI(title="Study Buddy")


@app.middleware("http")
async def revalidate_static(request, call_next):
    # make browsers check for updated CSS/JS on every load instead of serving stale cached copies
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


# ---------- helpers ----------

def _sse(events: Iterator[dict]) -> StreamingResponse:
    def gen():
        try:
            for ev in events:
                yield f"data: {json.dumps(ev)}\n\n"
        except llm.LLMError as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        except Exception as e:  # surface unexpected errors to the UI instead of a dead stream
            yield f"data: {json.dumps({'type': 'error', 'message': f'Unexpected error: {e}'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _require(doc_id: str) -> dict:
    if not store.exists(doc_id):
        raise HTTPException(404, "Document not found")
    return store.load_meta(doc_id)


def _overview(doc_id: str) -> str:
    notes = store.load_notes(doc_id)
    if notes:
        m = re.search(r"##\s*Overview\s*\n(.*?)(?=\n##\s|\Z)", notes, re.S)
        if m:
            return m.group(1).strip()
    # only read the full document from disk when there are no notes to use
    return "\n".join(s["text"] for s in store.load_segments(doc_id))[:1500]


# ---------- API ----------

@app.get("/api/status")
def status():
    return {
        "groq_configured": bool(config.GROQ_API_KEY) and not config.GROQ_API_KEY.startswith("your_"),
        "model": config.GROQ_MODEL,
        "ocr_available": ocr.ocr_available(),
        "supported": sorted(SUPPORTED_EXTS),
    }


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "No files uploaded")
    all_segments: list[dict] = []
    names, errors = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for f in files:
            name = Path(f.filename or "file").name
            data = await f.read()
            if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
                errors.append(f"{name}: larger than {MAX_UPLOAD_MB} MB")
                continue
            path = Path(tmp) / name
            path.write_bytes(data)
            try:
                segs = extract(path)
            except ExtractionError as e:
                errors.append(str(e))
                continue
            except Exception as e:
                errors.append(f"{name}: could not read file ({e})")
                continue
            prefix = f"{Path(name).stem} · " if len(files) > 1 else ""
            all_segments += [{**s.to_dict(), "source": prefix + s.source} for s in segs]
            names.append(name)

    if not all_segments:
        raise HTTPException(422, "; ".join(errors) or "No readable text found")

    doc_id = store.new_doc_id()
    title = names[0] if len(names) == 1 else f"{Path(names[0]).stem} + {len(names) - 1} more"
    meta = {
        "title": title,
        "files": names,
        "segments": len(all_segments),
        "ocr_segments": sum(1 for s in all_segments if s.get("ocr")),
        "chars": sum(len(s["text"]) for s in all_segments),
        "warnings": errors,
    }
    store.save_doc(doc_id, meta, all_segments)
    return store.load_meta(doc_id)


@app.get("/api/docs")
def docs():
    return store.list_docs()


@app.get("/api/docs/{doc_id}")
def doc(doc_id: str):
    meta = _require(doc_id)
    return {**meta, "notes": store.load_notes(doc_id)}


@app.delete("/api/docs/{doc_id}")
def delete(doc_id: str):
    _require(doc_id)
    store.delete_doc(doc_id)
    retriever.get_index.cache_clear()
    return {"ok": True}


@app.get("/api/docs/{doc_id}/text", response_class=PlainTextResponse)
def doc_text(doc_id: str):
    _require(doc_id)
    return "\n\n".join(f"[{s['source']}]\n{s['text']}" for s in store.load_segments(doc_id))


@app.post("/api/docs/{doc_id}/notes")
def notes(doc_id: str, regenerate: bool = False):
    meta = _require(doc_id)

    def events():
        cached = None if regenerate else store.load_notes(doc_id)
        if cached:
            yield {"type": "notes", "markdown": cached, "cached": True}
            if has_beyond(cached):
                return
            # notes made before the "Beyond the Notes" section existed: add just that section
            yield {"type": "progress", "message": "Adding related material beyond your notes...", "done": 0, "total": 1}
            try:
                full = add_beyond(meta["title"], cached)
            except llm.LLMError:
                return
            store.save_notes(doc_id, full)
            yield {"type": "notes", "markdown": full, "cached": True}
            return
        for ev in generate_notes(meta["title"], store.load_segments(doc_id)):
            if ev["type"] == "notes":
                store.save_notes(doc_id, ev["markdown"])
            yield ev

    return _sse(events())


@app.get("/api/docs/{doc_id}/notes.md")
def notes_download(doc_id: str):
    meta = _require(doc_id)
    if not store.load_notes(doc_id):
        raise HTTPException(404, "Notes not generated yet")
    fname = f"{Path(meta['title']).stem} - study notes.md"
    return FileResponse(store.doc_dir(doc_id) / "notes.md", media_type="text/markdown", filename=fname)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@app.post("/api/docs/{doc_id}/chat")
def chat(doc_id: str, req: ChatRequest):
    meta = _require(doc_id)
    history = [m for m in req.messages if m.role in ("user", "assistant")][-10:]
    if not history or history[-1].role != "user":
        raise HTTPException(400, "Last message must be from the user")

    # Use the last two user turns as the query so follow-ups ("explain more") still retrieve well
    query = " ".join([m.content for m in history if m.role == "user"][-2:])
    hits = retriever.get_index(doc_id).search(query, k=6)
    context = "\n\n---\n\n".join(c.text for c in hits)
    system = prompts.CHAT_SYSTEM.format(
        title=meta["title"], overview=_overview(doc_id), context=context)
    messages = [{"role": "system", "content": system}] + [m.model_dump() for m in history]

    def events():
        yield {"type": "sources", "sources": sorted({s for c in hits for s in c.sources}, key=_natural)}
        for delta in llm.stream(messages):
            yield {"type": "delta", "text": delta}

    return _sse(events())


def _natural(s: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


# ---------- static UI ----------

app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html")
