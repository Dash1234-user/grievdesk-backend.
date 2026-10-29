import re

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_

from app.extensions import db
from app.utils.decorators import login_required, current_user
from app.models.announcement import Announcement
from app.models.complaint import Complaint
from app.models.service_request import ServiceRequest
from app.services.rules import latest_rulebook
from app.services.translation import localize_groups, to_english

search_bp = Blueprint("search", __name__, url_prefix="/api/search")


def _contains(column, terms):
    """Case-insensitive 'contains' for any of the terms. autoescape makes a typed % or _ mean itself, not a wildcard."""
    return or_(*[func.lower(column).contains(t.lower(), autoescape=True) for t in terms])


def _snippet(paragraph: str, terms, width: int = 300) -> str:
    text = " ".join(paragraph.split())
    if len(text) <= width:
        return text
    lowered = text.lower()
    hits = [lowered.find(t.lower()) for t in terms if t.lower() in lowered]
    start = max(0, (min(hits) if hits else 0) - width // 3)
    piece = text[start:start + width].strip()
    return ("..." if start else "") + piece + ("..." if start + width < len(text) else "")


@search_bp.get("")
@login_required
def search():
    """
    One search box over: the Public Inbox complaints, service requests (yours; staff see everyone's),
    announcements, and the society rulebook. ?q=  ?limit= per group (default 10, max 50).
    A query typed in another language is also translated to English, because everything is stored in English.
    """
    viewer = current_user()
    q = " ".join((request.args.get("q") or "").split())
    if not (2 <= len(q) <= 100):
        return jsonify({"error": "invalid_query", "message": "Type between 2 and 100 characters."}), 400
    try:
        limit = int(request.args.get("limit", 10))
        if not 1 <= limit <= 50:
            raise ValueError
    except ValueError:
        return jsonify({"error": "invalid_paging", "message": "limit must be a whole number from 1 to 50."}), 400

    terms = [q]
    english = None
    # Only spend a translation when the query might not already be English.
    if viewer.preferred_language != "en" or any(ord(ch) > 127 for ch in q):
        english = to_english(q)
        if english and english.lower() != q.lower():
            terms.append(english)
        else:
            english = None

    # Complaints: only the English text everyone can already read in the Public Inbox is searched —
    # never the original wording, which other residents are not shown.
    c_query = Complaint.query.filter(_contains(Complaint.translated_text, terms))
    complaints = c_query.order_by(Complaint.created_at.desc(), Complaint.id.desc()).limit(limit).all()
    complaint_rows = [c.to_public_dict(viewer) for c in complaints]

    s_query = ServiceRequest.query.filter(_contains(ServiceRequest.translated_text, terms))
    if not viewer.is_staff():
        s_query = s_query.filter(ServiceRequest.user_id == viewer.id)
    requests_ = s_query.order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc()).limit(limit).all()
    request_rows = [r.to_public_dict() for r in requests_]

    a_query = Announcement.query.filter(or_(_contains(Announcement.title, terms), _contains(Announcement.message, terms)))
    announcements = a_query.order_by(Announcement.created_at.desc(), Announcement.id.desc()).limit(limit).all()
    announcement_rows = [a.to_public_dict() for a in announcements]

    rule_rows = []
    rulebook = latest_rulebook()
    if rulebook:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n", rulebook.content_text) if p.strip()]
        if len(paragraphs) <= 1:                      # a rulebook written as one line per rule, no blank lines
            paragraphs = [p.strip() for p in rulebook.content_text.splitlines() if p.strip()]
        for index, paragraph in enumerate(paragraphs, start=1):
            if any(t.lower() in paragraph.lower() for t in terms):
                rule_rows.append({"section": index, "snippet": _snippet(paragraph, terms)})
                if len(rule_rows) >= limit:
                    break

    meta = localize_groups(
        viewer,
        (complaint_rows, ["translated_text"]), (request_rows, ["description"]),
        (announcement_rows, ["title", "message"]), (rule_rows, ["snippet"]),
    )
    return jsonify({
        "query": q,
        "query_english": english,
        "results": {
            "complaints": complaint_rows, "service_requests": request_rows,
            "announcements": announcement_rows, "rules": rule_rows,
        },
        "totals": {
            "complaints": c_query.count(), "service_requests": s_query.count(), "announcements": a_query.count(),
        },
        **meta,
    }), 200
