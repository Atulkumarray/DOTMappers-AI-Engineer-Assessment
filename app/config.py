from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "support_tickets.csv"
DB_PATH = BASE_DIR / "data" / "support_tickets.db"
STATIC_DIR = BASE_DIR / "static"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
ALLOW_LLM_FALLBACK = os.getenv("ALLOW_LLM_FALLBACK", "true").lower() == "true"
