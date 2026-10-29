"""
Voice input: turn an uploaded voice note into English text, and store the audio
when it becomes part of a permanent complaint record.

The audio goes straight to Gemini (the same model and API key used for text) with a
transcribe-and-translate instruction, so no second provider or key is needed.
"""
import os
import uuid
from dataclasses import dataclass

from flask import current_app
from google.genai import types

from app.services.gemini_client import generate, GeminiNotConfigured, GeminiCallFailed

# extension -> mime type. Covers what browsers record (webm, mp4/m4a, ogg) and WhatsApp voice notes (ogg).
AUDIO_TYPES = {
    ".mp3": "audio/mpeg", ".mpeg": "audio/mpeg", ".mpga": "audio/mpeg",
    ".m4a": "audio/mp4", ".mp4": "audio/mp4",
    ".wav": "audio/wav", ".webm": "audio/webm",
    ".ogg": "audio/ogg", ".oga": "audio/ogg", ".opus": "audio/ogg", ".flac": "audio/flac",
}
# Browsers sometimes upload a blob with no useful filename — fall back to the mime type.
MIME_TO_EXT = {
    "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
    "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/webm": ".webm",
    "audio/ogg": ".ogg", "audio/flac": ".flac", "video/webm": ".webm",
}

NO_SPEECH = "NO_SPEECH"

GEMINI_TRANSCRIBE_PROMPT = (
    "Transcribe this audio and translate it into English. "
    "Return only the English text, nothing else. "
    f"If there is no intelligible speech, return exactly: {NO_SPEECH}"
)


class InvalidAudio(Exception):
    """The upload itself is unusable (wrong type, empty, too big). Carries the HTTP response to send."""
    def __init__(self, payload: dict, status: int):
        super().__init__(payload.get("error"))
        self.payload = payload
        self.status = status


class SpeechNotConfigured(Exception):
    """GEMINI_API_KEY is missing."""


class SpeechCallFailed(Exception):
    """The Gemini audio call failed (bad key, quota, unsupported format, network)."""


class NoSpeechDetected(Exception):
    """The provider returned nothing usable."""


@dataclass
class AudioUpload:
    data: bytes
    ext: str
    mime: str


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def read_audio_upload(file_storage) -> AudioUpload:
    max_bytes = current_app.config["MAX_AUDIO_BYTES"]

    name = (file_storage.filename or "").lower()
    ext = os.path.splitext(name)[1]
    if ext not in AUDIO_TYPES:
        mimetype = (file_storage.mimetype or "").split(";")[0].strip().lower()
        ext = MIME_TO_EXT.get(mimetype, "")
    if ext not in AUDIO_TYPES:
        raise InvalidAudio({
            "error": "unsupported_audio_type",
            "message": "Send a voice note as " + ", ".join(sorted(AUDIO_TYPES)) + ".",
        }, 400)

    if ext == ".opus":
        ext = ".ogg"  # Android WhatsApp voice notes are Opus-in-Ogg; providers only recognise the .ogg name

    data = file_storage.read(max_bytes + 1)  # never pull more than the cap into memory
    if not data:
        raise InvalidAudio({"error": "empty_audio", "message": "The audio file is empty."}, 400)
    if len(data) > max_bytes:
        raise InvalidAudio({"error": "audio_too_large", "max_bytes": max_bytes}, 413)

    return AudioUpload(data=data, ext=ext, mime=AUDIO_TYPES[ext])


# ---------------------------------------------------------------------------
# Speech -> English text
# ---------------------------------------------------------------------------

def translate_audio_to_english(audio: AudioUpload) -> str:
    try:
        text = generate([GEMINI_TRANSCRIBE_PROMPT, types.Part.from_bytes(data=audio.data, mime_type=audio.mime)])
    except GeminiNotConfigured as exc:
        raise SpeechNotConfigured(str(exc)) from exc
    except GeminiCallFailed as exc:
        raise SpeechCallFailed(str(exc)) from exc

    if not text or text.upper().startswith(NO_SPEECH):
        raise NoSpeechDetected()
    return text


# ---------------------------------------------------------------------------
# Storage — only complaints keep their audio (so staff can listen to the original)
# ---------------------------------------------------------------------------

def audio_dir() -> str:
    path = current_app.config.get("AUDIO_DIR") or os.path.join(current_app.instance_path, "audio")
    os.makedirs(path, exist_ok=True)
    return path


def save_audio(audio: AudioUpload) -> str:
    """Writes the file under a random name (never the user's filename) and returns that stored name."""
    stored_name = uuid.uuid4().hex + audio.ext
    with open(os.path.join(audio_dir(), stored_name), "wb") as fh:
        fh.write(audio.data)
    return stored_name


def audio_path(stored_name: str):
    """Resolved path for a stored file, or None if it's missing or would escape the audio folder."""
    base = os.path.realpath(audio_dir())
    path = os.path.realpath(os.path.join(base, stored_name))
    if os.path.dirname(path) != base or not os.path.isfile(path):
        return None
    return path


def delete_audio(stored_name: str) -> None:
    path = audio_path(stored_name)
    if path:
        os.remove(path)
