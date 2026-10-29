import io
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import func

from app.extensions import db
from app.utils.decorators import login_required, committee_or_secretary_required
from app.models.bylaws_document import BylawsDocument
from app.services.gemini import GeminiNotConfigured, GeminiCallFailed
from app.services.rules import ask_rulebook

rules_bp = Blueprint("rules", __name__, url_prefix="/api/rules")

MAX_RULEBOOK_BYTES = 5 * 1024 * 1024
MAX_RULEBOOK_CHARS = 150_000  # the whole rulebook is pasted into the prompt, so keep a sane ceiling


def _extract_text_from_upload(upload):
    """Returns (text, error_response). Supports .txt and text-based .pdf files."""
    name = (upload.filename or "").lower()
    raw = upload.read()
    if len(raw) > MAX_RULEBOOK_BYTES:
        return None, (jsonify({"error": "file_too_large", "max_bytes": MAX_RULEBOOK_BYTES}), 413)

    if name.endswith(".txt"):
        return raw.decode("utf-8", errors="replace"), None

    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            if reader.is_encrypted:
                return None, (jsonify({"error": "encrypted_pdf", "message": "This PDF is password-protected."}), 400)
            return "\n".join((page.extract_text() or "") for page in reader.pages), None
        except Exception:
            return None, (jsonify({"error": "unreadable_pdf", "message": "Couldn't read this PDF."}), 400)

    return None, (jsonify({"error": "unsupported_file_type", "message": "Upload a .txt or .pdf file, or send JSON with content_text."}), 400)


@rules_bp.post("/upload")
@committee_or_secretary_required
def upload_rulebook():
    """New upload = new version. Q&A always answers from the highest version."""
    if request.files.get("file"):
        text, error = _extract_text_from_upload(request.files["file"])
        if error:
            return error
    else:
        text = (request.get_json(silent=True) or {}).get("content_text")

    text = (text or "").strip()
    if not text:
        return jsonify({
            "error": "missing_content",
            "message": "No text found. If this is a scanned PDF (an image), paste the text as content_text instead.",
        }), 400
    if len(text) > MAX_RULEBOOK_CHARS:
        return jsonify({"error": "rulebook_too_large", "max_characters": MAX_RULEBOOK_CHARS}), 413

    version = (db.session.query(func.max(BylawsDocument.version)).scalar() or 0) + 1
    db.session.add(BylawsDocument(
        content_text=text, version=version, uploaded_by=int(get_jwt_identity()),
    ))
    db.session.commit()
    return jsonify({"message": "Rulebook uploaded.", "version": version, "characters": len(text)}), 201


@rules_bp.post("/ask")
@login_required
def ask():
    """Direct rules Q&A without a chat transcript — same logic the chat flow uses."""
    text = (request.get_json(silent=True) or {}).get("text")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "missing_text"}), 400

    try:
        outcome = ask_rulebook(text.strip())
    except GeminiNotConfigured:
        return jsonify({"error": "ai_not_configured", "message": "GEMINI_API_KEY is missing from .env."}), 503
    except GeminiCallFailed as exc:
        return jsonify({"error": "ai_call_failed", "detail": str(exc)}), 502
    return jsonify({"status": outcome["status"], "reply": outcome["reply"]}), 200
