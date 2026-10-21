# Study Buddy

Turn lecture slides, readings and handouts into exam-ready study notes, then ask the material questions.

- **Upload:** PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx), CSV, TXT/Markdown, HTML, and images (PNG/JPG…). You can upload several files at once; they become one study set.
- **Scanned PDFs and photos:** read with local Tesseract OCR.
- **Notes:** an overview, organised key notes, a key-terms table, likely exam points and a revision checklist, all with page and slide references. You can copy them, download them as Markdown, or print/save them as PDF.
- **Ask the document:** chat that answers from your files and cites `[Page N]` / `[Slide N]`.
- Legacy .doc/.ppt/.xls/.odt/.rtf files are converted automatically if LibreOffice is installed. Otherwise, save them as .docx/.pptx/.xlsx first.

## Setup (Windows)

1. Install **Python 3.11+**.
2. Get a free Groq API key at https://console.groq.com/keys.
3. *(Optional, for scanned PDFs and images)* install Tesseract OCR from
   https://github.com/UB-Mannheim/tesseract/wiki (the default path `C:\Program Files\Tesseract-OCR` is detected automatically).
4. Double-click **`run.bat`**. The first run creates `.env` and opens it; paste your key into `GROQ_API_KEY` and run `run.bat` again.
   (If `GROQ_API_KEY` is already set as a system environment variable, that works too.)
5. The app opens at http://localhost:8000.

Manual alternative:
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # then edit it
uvicorn app.main:app --port 8000
```

## Configuration (`.env`)

| Setting | Default | Notes |
|---|---|---|
| `GROQ_API_KEY` | none | Required |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Any Groq chat model |
| `REASONING_EFFORT` | `low` | gpt-oss only: `low`, `medium` or `high` |
| `TESSERACT_CMD` | `C:\Program Files\Tesseract-OCR\tesseract.exe` | |
| `OCR_LANG` | `eng` | e.g. `eng+fra` (install the language packs) |
| `CHUNK_TOKENS` | `3000` | Lower this if you hit Groq rate limits on the free tier |

## How it works

1. **Extract:** each file becomes labelled segments (`Page 3`, `Slide 5`, `Sheet Glossary`, a heading name…). PDF pages with almost no text are rendered and OCR'd.
2. **Summarise (map-reduce):** long documents are split into ~3k-token chunks. Each chunk gets dense notes, and the notes are merged into the final study guide. Results are cached in `data/<id>/notes.md`.
3. **Chat:** BM25 keyword search finds the most relevant passages for each question. They're sent to the model with the notes' overview, and the answer streams back with citations.

## Project layout

```
app/
  main.py         FastAPI routes (upload, notes SSE, chat SSE, library)
  extractors.py   file -> labelled text segments (+ OCR fallback)
  ocr.py          Tesseract helpers
  chunking.py     token-budgeted chunks that keep source labels
  summarizer.py   map-reduce notes generation with progress events
  retriever.py    BM25 search for chat
  prompts.py      all prompts; add flashcards/quiz prompts here
  llm.py          Groq client with rate-limit retry
  store.py        on-disk storage under data/
static/           index.html, app.js, style.css (no build step)
tests/            pytest; fixtures are generated automatically
```

## Tests

```
.venv\Scripts\python -m pytest -q
```
The API tests mock the LLM, so they don't need a key. The OCR tests are skipped if Tesseract isn't installed.
