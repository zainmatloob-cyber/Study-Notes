import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "low")  # gpt-oss models only: low | medium | high
TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
OCR_LANG = os.getenv("OCR_LANG", "eng")
CHUNK_TOKENS = int(os.getenv("CHUNK_TOKENS", "3000"))
NOTES_MAX_TOKENS = int(os.getenv("NOTES_MAX_TOKENS", "8000"))  # length cap for the final study guide

DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR.mkdir(exist_ok=True)
