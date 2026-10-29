import uuid
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, g, current_app
from flask_jwt_extended import get_jwt_identity

from app.extensions import db
from app.utils.decorators import login_required, current_user
from app.models.user import User, Role, ApprovalStatus
from app.models.chat_message import ChatMessage, SelectedType
from app.models.complaint import Complaint, ComplaintStatus
from app.models.service_request import ServiceRequest, ServiceType
from app.models.announcement import Announcement
from app.models.notification import Notification, NotificationType
from app.services import gemini
from app.services.gemini import GeminiNotConfigured, GeminiCallFailed
from app.services.rules import ask_rulebook
from app.services.reminders import queue_dues_reminder
from app.services.duplicates import find_duplicate_root
from app.services.translation import localize_texts, localize_groups
from app.services import speech
from app.services.speech import (
    InvalidAudio, SpeechNotConfigured, SpeechCallFailed, NoSpeechDetected,
)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

COMMITTEE_ACTIONS = ("announcement", "dues_reminder")


class ChatInputError(Exception):
    """Bad input or missing permission — nothing is saved, not even the transcript line."""
    def __init__(self, payload: dict, status: int):
        super().__init__(payload.get("error"))
        self.payload = payload
        self.status = status


def _as_bool(value) -> bool:
    """JSON sends real booleans, multipart forms send strings — and bool("false") is True, so parse carefully."""
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("true", "1", "yes", "on")


def _result(reply: str, status: int, **extra) -> dict:
    return {"reply": reply, "status": status, "extra": extra}


# ---------------------------------------------------------------------------
# One handler per selected_type. The user picked the type from the menu, so
# nothing here ever tries to guess intent: if the text doesn't fit the type,
# the handler returns a "didn't understand" reply and saves nothing.
# ---------------------------------------------------------------------------

def _handle_complaint(user, text, data):
    result = gemini.classify_complaint(translated_text=text)
    if result.get("error") == "not_understood":
        return _result(
            "I didn't understand that as a complaint. Could you describe the problem more clearly?",
            200, understood=False,
        )

    audio = g.get("audio")
    # Has someone in this block already reported the same kind of problem recently?
    original = find_duplicate_root(user, result["category"])
    complaint = Complaint(
        user_id=user.id,
        raw_text=text,                                   # what the resident said/typed (voice: its English transcript)
        translated_text=result["english_text"],          # canonical English record
        # A voice note arrives already translated by the speech step, so the spoken language is unknown.
        original_language="und" if audio else result["detected_language"],
        category=result["category"],
        severity=result["severity"],
        is_anonymous=_as_bool(data.get("anonymous")),
        duplicate_of=original.id if original else None,
        status=original.status if original else ComplaintStatus.NEW,   # a linked report starts where its original is
    )
    db.session.add(complaint)
    db.session.flush()
    if audio:
        # Keep the original recording with the permanent complaint record (not with the disposable chat).
        complaint.audio_url = g.saved_audio = speech.save_audio(audio)
    reply = (
        f"Logged your complaint under {result['category']}, "
        f"marked {result['severity']} priority. Summary: {result['formal_summary']}"
    )
    if original:
        reply += (f" A similar {result['category']} complaint (#{original.id}) is already open for your block, so yours has been "
                  "linked to it. The committee will see how many residents are affected.")
    if complaint.is_anonymous:
        reply += " Your name and flat are hidden from other residents; only the committee can see who raised it."
    return _result(reply, 201, understood=True, complaint=complaint.to_public_dict(user),
                   duplicate_of=original.id if original else None)


def _handle_service(user, text, data):
    result = gemini.structure_service_request(translated_text=text)
    if result.get("error") == "not_understood":
        return _result(
            "I didn't understand that as a service request. Which service do you need: "
            "plumber, electrician, AC mechanic, laundry, or vehicle servicing?",
            200, understood=False,
        )

    request_row = ServiceRequest(
        user_id=user.id,
        service_type=result["service_type"],
        raw_text=text,
        translated_text=result["description"],
    )
    db.session.add(request_row)
    db.session.flush()
    label = ServiceType.LABELS[result["service_type"]]
    reply = f"Logged your {label} request: {result['description']} You can track it under My Tickets."
    return _result(reply, 201, understood=True, service_request=request_row.to_public_dict())


def _handle_rules(user, text, data):
    outcome = ask_rulebook(text)
    return _result(outcome["reply"], 200, understood=outcome["status"] == "answered", rules_status=outcome["status"])


def _handle_committee_action(user, text, data):
    if user.role not in (Role.COMMITTEE, Role.SECRETARY):
        raise ChatInputError(
            {"error": "forbidden", "message": "Only the Secretary or committee members can use committee actions."},
            403,
        )

    action = data.get("action")
    if action not in COMMITTEE_ACTIONS:
        raise ChatInputError({"error": "invalid_action", "allowed": list(COMMITTEE_ACTIONS)}, 400)

    if action == "announcement":
        return _announcement(user, text, data)
    return _dues_reminder(user, text, data)


def _announcement(user, text, data):
    drafted = gemini.draft_announcement(text)
    if drafted.get("error") == "not_understood":
        return _result(
            "I didn't understand that as an announcement. Tell me what residents should be told "
            "(for example: water tank cleaning on Friday 9:30 to 2, supply will be off).",
            200, understood=False,
        )

    pinned = _as_bool(data.get("pin"))
    announcement = Announcement(
        title=drafted["title"], message=drafted["message"], is_pinned=pinned, posted_by=user.id,
    )
    db.session.add(announcement)
    db.session.flush()
    # Broadcast notification (target_user_id NULL = every resident sees it).
    db.session.add(Notification(
        type=NotificationType.ANNOUNCEMENT, message=drafted["title"],
        target_user_id=None, created_by=user.id,
    ))
    reply = f"Posted{' and pinned' if pinned else ''} the announcement \"{drafted['title']}\" for all residents."
    return _result(reply, 201, understood=True, announcement=announcement.to_public_dict())


def _dues_reminder(user, text, data):
    flat_no = (data.get("flat_no") or "").strip()
    block_no = (data.get("block_no") or "").strip()
    if not flat_no or not block_no:
        raise ChatInputError({"error": "missing_fields", "fields": ["flat_no", "block_no"]}, 400)

    residents = User.query.filter_by(
        flat_no=flat_no, block_no=block_no, approval_status=ApprovalStatus.APPROVED,
    ).all()
    if not residents:
        raise ChatInputError({"error": "flat_not_found", "message": f"No approved resident found for flat {flat_no}, block {block_no}."}, 404)

    sent_to = []
    for resident in residents:
        message = queue_dues_reminder(user, resident, text)
        if message:
            sent_to.append({"name": resident.name, "reminder": message})

    if not sent_to:
        raise ChatInputError({"error": "no_unpaid_dues", "message": f"Flat {flat_no} has no unpaid dues on record."}, 404)

    names = ", ".join(r["name"] for r in sent_to)
    reply = f"Sent a dues reminder to flat {flat_no} ({names}). Only they can see it."
    return _result(reply, 201, understood=True, reminders=sent_to)


HANDLERS = {
    SelectedType.COMPLAINT: _handle_complaint,
    SelectedType.SERVICE: _handle_service,
    SelectedType.RULES: _handle_rules,
    SelectedType.COMMITTEE_ACTION: _handle_committee_action,
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@chat_bp.post("/message")
@login_required
def send_message():
    """
    Typed:  JSON  {"selected_type": "...", "text": "..."}
    Voice:  multipart/form-data with the same fields plus an `audio` file (send `text` OR `audio`, not both).
    Extra fields per type (action, flat_no, block_no, pin, session_id) work the same in both formats.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = request.form.to_dict()
    audio_file = request.files.get("audio")

    selected_type = data.get("selected_type")
    text = data.get("text")
    session_id = data.get("session_id") or str(uuid.uuid4())

    if selected_type not in SelectedType.ALL:
        return jsonify({"error": "invalid_selected_type", "allowed": list(SelectedType.ALL)}), 400

    has_text = isinstance(text, str) and bool(text.strip())
    if audio_file and has_text:
        return jsonify({"error": "text_and_audio", "message": "Send either text or a voice note, not both."}), 400
    if not audio_file and not has_text:
        return jsonify({"error": "missing_input", "message": "Send text, or a voice note in the `audio` field."}), 400

    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)  # role is read from the database, not trusted from the token
    if user is None:
        return jsonify({"error": "user_not_found"}), 401

    # Refuse before spending a transcription on a request that would be rejected anyway.
    if selected_type == SelectedType.COMMITTEE_ACTION and user.role not in (Role.COMMITTEE, Role.SECRETARY):
        return jsonify({"error": "forbidden", "message": "Only the Secretary or committee members can use committee actions."}), 403

    g.audio = None
    g.saved_audio = None
    voice = audio_file is not None

    try:
        if voice:
            g.audio = speech.read_audio_upload(audio_file)
            text = speech.translate_audio_to_english(g.audio)
        else:
            text = text.strip()

        db.session.add(ChatMessage(
            user_id=user_id, session_id=session_id, selected_type=selected_type,
            role="user", content_text=text,
        ))
        outcome = HANDLERS[selected_type](user, text, data)

        reply = outcome["reply"]
        if voice:
            reply = f'I heard: "{text}"\n{reply}'  # lets the resident catch a mis-heard word
        db.session.add(ChatMessage(
            user_id=user_id, session_id=session_id, selected_type=selected_type,
            role="assistant", content_text=reply,
        ))
        db.session.commit()
    except InvalidAudio as exc:
        db.session.rollback()
        return jsonify(exc.payload), exc.status
    except ChatInputError as exc:
        db.session.rollback()
        return jsonify(exc.payload), exc.status
    except NoSpeechDetected:
        db.session.rollback()
        return jsonify({"error": "no_speech_detected", "message": "I couldn't hear any speech in that recording. Please try again."}), 422
    except SpeechNotConfigured as exc:
        db.session.rollback()
        return jsonify({"error": "speech_not_configured", "message": str(exc)}), 503
    except SpeechCallFailed as exc:
        db.session.rollback()
        return jsonify({"error": "speech_failed", "message": "The speech-to-text call failed.", "detail": str(exc)}), 502
    except GeminiNotConfigured:
        db.session.rollback()
        return jsonify({"error": "ai_not_configured", "message": "GEMINI_API_KEY is missing from .env."}), 503
    except GeminiCallFailed as exc:
        db.session.rollback()
        return jsonify({
            "error": "ai_call_failed",
            "message": "The Gemini API call failed. Check your API key, the GEMINI_MODEL name, and your quota.",
            "detail": str(exc),
        }), 502
    except Exception:
        # Anything unexpected: undo the DB work AND remove a voice file we may have already written.
        db.session.rollback()
        if g.get("saved_audio"):
            speech.delete_audio(g.saved_audio)
        current_app.logger.exception("chat message failed")
        return jsonify({"error": "server_error"}), 500

    extra = dict(outcome["extra"])
    extra["input_mode"] = "voice" if voice else "text"
    if voice:
        extra["transcript"] = text

    # The action is already saved; translating the answer is a courtesy that must never undo or fail it.
    try:
        local, meta = localize_texts([reply], user.preferred_language)
    except Exception:
        current_app.logger.exception("reply translation failed")
        local, meta = [None], {"language": user.preferred_language, "translation": "unavailable"}
    extra.update(meta)
    if meta["language"] != "en":
        extra["reply_local"] = local[0]
    return jsonify({"reply": reply, "session_id": session_id, **extra}), outcome["status"]


def _retention_cutoff():
    return datetime.now(timezone.utc) - timedelta(days=current_app.config["CHAT_RETENTION_DAYS"])


@chat_bp.get("/recents")
@login_required
def recents():
    """
    The sidebar's Recents list: YOUR chat threads from the last CHAT_RETENTION_DAYS days, newest first.
    Threads older than that are hidden immediately and deleted by the weekly cleanup job.
    """
    user_id = int(get_jwt_identity())
    rows = (
        ChatMessage.query.filter(ChatMessage.user_id == user_id, ChatMessage.created_at >= _retention_cutoff())
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).all()
    )
    threads = {}
    for m in rows:
        t = threads.setdefault(m.session_id, {
            "session_id": m.session_id, "selected_type": m.selected_type, "title": None, "message_count": 0,
        })
        t["message_count"] += 1
        t["last_message_at"] = m.created_at.isoformat() if m.created_at else None
        if t["title"] is None and m.role == "user":
            t["title"] = m.content_text if len(m.content_text) <= 60 else m.content_text[:57].rstrip() + "..."
    ordered = sorted(threads.values(), key=lambda t: t["last_message_at"] or "", reverse=True)
    return jsonify({"threads": ordered}), 200


@chat_bp.get("/recents/<session_id>")
@login_required
def recent_thread(session_id):
    """One thread's messages. Send the same session_id with POST /message to continue it."""
    user_id = int(get_jwt_identity())
    rows = (
        ChatMessage.query.filter(
            ChatMessage.user_id == user_id, ChatMessage.session_id == session_id,
            ChatMessage.created_at >= _retention_cutoff(),
        ).order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).all()
    )
    if not rows:   # someone else's thread looks exactly like a missing one
        return jsonify({"error": "thread_not_found"}), 404
    messages = [
        {"selected_type": m.selected_type, "role": m.role, "content_text": m.content_text,
         "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in rows
    ]
    # Only the assistant's replies are translated; what the person typed or said is shown as they gave it.
    meta = localize_groups(current_user(), ([m for m in messages if m["role"] == "assistant"], ["content_text"]))
    return jsonify({"session_id": session_id, "messages": messages, **meta}), 200
