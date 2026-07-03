"""
config.py — UPSC Mentor AI (Testing Bot)
==========================================
Separate bot. Separate token. Separate DB file. Zero shared state with the
main UPSC Master Bot until you deliberately wire the integration layer
(see storage/database.py: `import_user_from_main_bot`).

Python 3.11.9 | python-telegram-bot 20.7
"""
import os
import pathlib
import logging

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR: pathlib.Path = pathlib.Path(__file__).parent
LOGS_DIR: pathlib.Path = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

_DATA_DIR = pathlib.Path("/data") if pathlib.Path("/data").exists() else BASE_DIR / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Local/testing storage. Swap ENGINE to "postgres" once you point DATABASE_URL
# at a real Postgres instance (schema: storage/migrations/001_init.sql).
DB_ENGINE: str = os.environ.get("DB_ENGINE", "sqlite")   # "sqlite" | "postgres"
SQLITE_PATH: str = str(_DATA_DIR / "mentor_ai.db")
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")   # postgres://... for prod

# ── Telegram ───────────────────────────────────────────────────────────────────
# MUST be a different bot token from the main bot — get one from @BotFather.
BOT_TOKEN: str = os.environ.get("MENTOR_BOT_TOKEN", "")

ADMIN_IDS: list[int] = [
    int(x.strip())
    for x in os.environ.get("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

# ── Gemini AI ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_TIMEOUT: int = 25   # seconds per call — raised from 15s, see README §1

# ── THE FIX ────────────────────────────────────────────────────────────────────
# gemini-2.5-flash has "thinking" ON by default on the OpenAI-compat endpoint.
# Thinking tokens are billed against max_tokens. At max_tokens=450-600 the
# model was spending nearly the whole budget "thinking" and had ~4-6 words of
# budget left for the actual answer -> the mid-sentence cutoffs you saw.
# reasoning_effort="none" turns thinking off entirely for 2.5-series models.
# See services/ai_provider.py::_call for where this is applied.
GEMINI_REASONING_EFFORT: str = os.environ.get("GEMINI_REASONING_EFFORT", "none")

# Per-task token budgets. Now safe to trust because no thinking tokens eat
# into them. Raised somewhat vs. the old bot to give structured mentor-style
# answers (with numbered sections) room to breathe.
TOKENS_DOUBT: int = 700
TOKENS_EVALUATE: int = 900
TOKENS_ESSAY: int = 800
TOKENS_ETHICS: int = 750
TOKENS_CA_SUMMARY: int = 500
TOKENS_STUDY_ANALYSIS: int = 700
TOKENS_WEEKLY: int = 450
TOKENS_INSIGHTS: int = 550
TOKENS_MEMORY_EXTRACT: int = 300

# ── Flask keep-alive ───────────────────────────────────────────────────────────
PORT: int = int(os.environ.get("PORT", 8081))   # different from main bot's port

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_LEVEL: int = logging.INFO

# ── Memory system ──────────────────────────────────────────────────────────────
MAX_ACTIVE_MEMORIES: int = 25          # per user, injected into every context
MEMORY_EXTRACTION_EVERY_N_MSGS: int = 6  # run extractor every N user turns
RECENT_CHAT_WINDOW: int = 8            # last N messages loaded into context
