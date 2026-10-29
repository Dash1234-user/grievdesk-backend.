from flask import Blueprint, jsonify, request

from app.extensions import db
from app.utils.decorators import login_required, committee_or_secretary_required, current_user
from app.services.translation import localize_groups
from app.utils.paging import parse_paging
from app.models.announcement import Announcement

announcements_bp = Blueprint("announcements", __name__, url_prefix="/api/announcements")


def _get(announcement_id):
    return db.session.get(Announcement, announcement_id)


@announcements_bp.get("")
@login_required
def list_announcements():
    """
    Split exactly like the UI: a Pinned circulars section (always all of them) and a General circulars
    section (paged: ?limit= default 20, max 100, ?offset=). Translated into the reader's language (*_local).
    """
    limit, offset, bad = parse_paging(default_limit=20, max_limit=100)
    if bad:
        return jsonify(bad[0]), bad[1]

    order = (Announcement.created_at.desc(), Announcement.id.desc())
    pinned = [a.to_public_dict() for a in Announcement.query.filter_by(is_pinned=True).order_by(*order).all()]
    general_query = Announcement.query.filter_by(is_pinned=False)
    general_total = general_query.count()
    general = [a.to_public_dict() for a in general_query.order_by(*order).limit(limit).offset(offset).all()]

    meta = localize_groups(current_user(), (pinned, ["title", "message"]), (general, ["title", "message"]))
    return jsonify({"pinned": pinned, "general": general, "general_total": general_total,
                    "limit": limit, "offset": offset, **meta}), 200


# Announcements are CREATED through the AI chat (committee_action -> announcement), which drafts the
# wording. The endpoints below manage what already exists.

@announcements_bp.patch("/<int:announcement_id>/pin")
@committee_or_secretary_required
def pin(announcement_id):
    """Body: {"pinned": true|false}."""
    row = _get(announcement_id)
    if row is None:
        return jsonify({"error": "announcement_not_found"}), 404
    pinned = (request.get_json(silent=True) or {}).get("pinned")
    if not isinstance(pinned, bool):
        return jsonify({"error": "invalid_pinned", "message": "Send {\"pinned\": true} or {\"pinned\": false}."}), 400
    row.is_pinned = pinned
    db.session.commit()
    return jsonify({"message": "Pinned." if pinned else "Unpinned.", "announcement": row.to_public_dict()}), 200


@announcements_bp.patch("/<int:announcement_id>")
@committee_or_secretary_required
def edit(announcement_id):
    """Fix a typo or detail in the wording. Body: title and/or message."""
    row = _get(announcement_id)
    if row is None:
        return jsonify({"error": "announcement_not_found"}), 404

    data = request.get_json(silent=True) or {}
    if not ({"title", "message"} & set(data)):
        return jsonify({"error": "missing_fields", "message": "Send title and/or message."}), 400
    if "title" in data:
        title = data["title"]
        if not isinstance(title, str) or not (1 <= len(title.strip()) <= 200):
            return jsonify({"error": "invalid_title", "message": "Title must be 1-200 characters."}), 400
        row.title = title.strip()
    if "message" in data:
        message = data["message"]
        if not isinstance(message, str) or not message.strip():
            return jsonify({"error": "invalid_message", "message": "Message can't be empty."}), 400
        row.message = message.strip()
    db.session.commit()
    return jsonify({"message": "Announcement updated.", "announcement": row.to_public_dict()}), 200


@announcements_bp.delete("/<int:announcement_id>")
@committee_or_secretary_required
def delete(announcement_id):
    row = _get(announcement_id)
    if row is None:
        return jsonify({"error": "announcement_not_found"}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({"message": "Announcement deleted."}), 200
