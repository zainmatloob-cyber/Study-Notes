import pytest

from app import ocr
from app.chunking import chunk_segments
from app.extractors import ExtractionError, extract
from app.retriever import DocIndex

from .conftest import MITO_TEXT, PHOTO_TEXT

needs_ocr = pytest.mark.skipif(not ocr.ocr_available(), reason="Tesseract not installed")


def _all(segs):
    return " ".join(s.text for s in segs)


def test_pdf(fixtures):
    segs = extract(fixtures["pdf"])
    assert [s.source for s in segs] == ["Page 1", "Page 2"]
    assert "Photosynthesis" in segs[0].text and "mitochondria" in segs[1].text


def test_docx(fixtures):
    segs = extract(fixtures["docx"])
    sources = [s.source for s in segs]
    assert "Cell Biology" in sources and "Plants" in sources and "Table 1" in sources
    assert "Protein synthesis" in _all(segs)


def test_pptx(fixtures):
    segs = extract(fixtures["pptx"])
    assert [s.source for s in segs] == ["Slide 1", "Slide 2"]
    assert "Speaker notes: Remember Photosynthesis" in segs[0].text


def test_xlsx(fixtures):
    segs = extract(fixtures["xlsx"])
    assert segs[0].source == "Sheet Glossary"
    assert "ATP | Energy currency of the cell" in segs[0].text


def test_txt_and_html(fixtures):
    assert MITO_TEXT in _all(extract(fixtures["txt"]))
    html = _all(extract(fixtures["html"]))
    assert MITO_TEXT in html and "bad()" not in html


def test_unsupported(tmp_path):
    p = tmp_path / "x.zip"
    p.write_bytes(b"PK")
    with pytest.raises(ExtractionError):
        extract(p)


@needs_ocr
def test_image_ocr(fixtures):
    segs = extract(fixtures["png"])
    assert segs[0].ocr and "osmosis" in segs[0].text.lower()


@needs_ocr
def test_scanned_pdf_ocr(fixtures):
    segs = extract(fixtures["scanned_pdf"])
    assert segs[0].ocr and "osmosis" in segs[0].text.lower()


def test_chunking_keeps_labels():
    segs = [{"text": f"para {i} " * 300, "source": f"Page {i}"} for i in range(1, 6)]
    chunks = chunk_segments(segs, max_tokens=500)
    assert len(chunks) > 1
    assert all(c.text.startswith("[Page") for c in chunks)
    assert {s for c in chunks for s in c.sources} == {f"Page {i}" for i in range(1, 6)}


def test_retrieval():
    filler = " Plants need sunlight, water and carbon dioxide." * 50  # make each page its own chunk
    idx = DocIndex([{"text": PHOTO_TEXT + filler, "source": "Page 1"},
                    {"text": MITO_TEXT + filler, "source": "Page 2"}])
    assert idx.search("what produces ATP?", k=1)[0].sources == ["Page 2"]
