import os
from datetime import timedelta


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # hard ceiling for any request body

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    # Model names get deprecated regularly — keep it in .env, not hardcoded.
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
    # Tried in order when the main model is overloaded (503), retired (404) or out of free quota (429).
    GEMINI_FALLBACK_MODELS = [m.strip() for m in os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-3.1-flash-lite").split(",") if m.strip()]
    GEMINI_RETRIES_PER_MODEL = int(os.environ.get("GEMINI_RETRIES_PER_MODEL", "2"))
    GEMINI_TIMEOUT_SECONDS = int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "30"))

    # ---- Voice input ----
    MAX_AUDIO_BYTES = 10 * 1024 * 1024        # voice notes are short, so keep the cap small
    AUDIO_DIR = os.environ.get("AUDIO_DIR")   # default: <project>/instance/audio, resolved at runtime

    # ---- Amenity booking rules (policy choices — change in .env, no code edit) ----
    SOCIETY_TIMEZONE = os.environ.get("SOCIETY_TIMEZONE", "Asia/Kolkata")  # "now" for booking rules
    MAX_BOOKING_HOURS = int(os.environ.get("MAX_BOOKING_HOURS", "4"))       # stops one booking blocking a facility all day
    MAX_BOOKING_DAYS_AHEAD = int(os.environ.get("MAX_BOOKING_DAYS_AHEAD", "30"))

    # ---- Housekeeping jobs (Step 7) ----
    ESCALATION_DAYS = int(os.environ.get("ESCALATION_DAYS", "5"))                 # untouched "new" complaint -> escalated
    DUPLICATE_WINDOW_HOURS = int(os.environ.get("DUPLICATE_WINDOW_HOURS", "48"))  # how far back "the same problem" looks
    CHAT_RETENTION_DAYS = int(os.environ.get("CHAT_RETENTION_DAYS", "7"))         # chat transcripts older than this are deleted
    ENABLE_SCHEDULER = os.environ.get("ENABLE_SCHEDULER", "false").strip().lower() in ("1", "true", "yes")

    # ---- Translate-on-read (Step 8) ----
    TRANSLATE_BATCH_ITEMS = int(os.environ.get("TRANSLATE_BATCH_ITEMS", "25"))     # texts sent to Gemini per call
    TRANSLATE_BATCH_CHARS = int(os.environ.get("TRANSLATE_BATCH_CHARS", "8000"))   # ...and a size cap per call
