import json

import pytest
from fastapi.testclient import TestClient

from app import config, llm, main, store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CHUNK_TOKENS", 60)  # force the map-reduce path on small fixtures
    calls = []

    def fake_complete(messages, **kw):
        calls.append(messages[-1]["content"])
        return "## Overview\nCells and plants.\n\n## Key Notes\n- ATP (Page 2)"

    def fake_stream(messages, **kw):
        calls.append(messages[0]["content"])
        yield "Mitochondria make ATP "
        yield "[Page 2]"

    monkeypatch.setattr(llm, "complete", fake_complete)
    monkeypatch.setattr(llm, "stream", fake_stream)
    c = TestClient(main.app)
    c.calls = calls
    return c


def _events(resp):
    return [json.loads(line[5:]) for line in resp.text.splitlines() if line.startswith("data:")]


def test_upload_notes_chat_flow(client, fixtures):
    with open(fixtures["pdf"], "rb") as f1, open(fixtures["pptx"], "rb") as f2:
        r = client.post("/api/upload", files=[("files", ("bio.pdf", f1)), ("files", ("bio.pptx", f2))])
    assert r.status_code == 200, r.text
    meta = r.json()
    assert meta["segments"] == 4 and len(meta["files"]) == 2
    doc_id = meta["id"]

    ev = _events(client.post(f"/api/docs/{doc_id}/notes"))
    assert any(e["type"] == "progress" for e in ev)
    notes = next(e for e in ev if e["type"] == "notes")
    assert "## Overview" in notes["markdown"]
    assert len(client.calls) > 2  # map calls + reduce

    # cached on second request
    n = len(client.calls)
    ev = _events(client.post(f"/api/docs/{doc_id}/notes"))
    assert next(e for e in ev if e["type"] == "notes")["cached"] and len(client.calls) == n

    r = client.post(f"/api/docs/{doc_id}/chat", json={"messages": [{"role": "user", "content": "what makes ATP?"}]})
    ev = _events(r)
    assert "".join(e["text"] for e in ev if e["type"] == "delta") == "Mitochondria make ATP [Page 2]"
    sources = next(e for e in ev if e["type"] == "sources")["sources"]
    assert any("Page 2" in s for s in sources)
    assert "Cells and plants." in client.calls[-1]  # overview from notes in system prompt

    assert client.get(f"/api/docs/{doc_id}/notes.md").status_code == 200
    assert len(client.get("/api/docs").json()) == 1
    assert client.delete(f"/api/docs/{doc_id}").json()["ok"]
    assert client.get("/api/docs").json() == []


def test_beyond_section_added_and_backfilled(client, fixtures):
    with open(fixtures["txt"], "rb") as f:
        doc_id = client.post("/api/upload", files=[("files", ("a.txt", f))]).json()["id"]

    ev = _events(client.post(f"/api/docs/{doc_id}/notes"))
    final = [e for e in ev if e["type"] == "notes"][-1]["markdown"]
    assert final.count("## Beyond the Notes") == 1
    assert "## Overview" in final.split("## Beyond the Notes")[0]

    # notes saved before the feature existed get the section added once, then stay cached
    store.save_notes(doc_id, "## Overview\nOld notes.")
    ev = _events(client.post(f"/api/docs/{doc_id}/notes"))
    assert [e for e in ev if e["type"] == "notes"][-1]["markdown"].startswith("## Overview\nOld notes.")
    assert "## Beyond the Notes" in store.load_notes(doc_id)
    n = len(client.calls)
    client.post(f"/api/docs/{doc_id}/notes")
    assert len(client.calls) == n


def test_upload_rejects_bad_file(client):
    r = client.post("/api/upload", files=[("files", ("x.zip", b"PK"))])
    assert r.status_code == 422 and "Unsupported" in r.json()["detail"]


def test_llm_error_is_streamed(client, fixtures, monkeypatch):
    with open(fixtures["txt"], "rb") as f:
        doc_id = client.post("/api/upload", files=[("files", ("a.txt", f))]).json()["id"]

    def boom(*a, **k):
        raise llm.LLMError("GROQ_API_KEY is not set.")

    monkeypatch.setattr(llm, "complete", boom)
    ev = _events(client.post(f"/api/docs/{doc_id}/notes"))
    assert ev[-2] == {"type": "error", "message": "GROQ_API_KEY is not set."}
