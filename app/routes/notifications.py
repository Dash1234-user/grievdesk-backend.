from flask import Blueprint, jsonify
from sqlalchemy import or_

from app.extensions import db
from app.utils.decorators import login_required, current_user
from app.models.notification import Notification
from app.models.notification_read import NotificationRead
from app.services.translation import localize_groups
from app.utils.paging import parse_paging

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


def _visible_to(user_id):
    """Broadcasts (target NULL) plus anything addressed to me. Other residents' reminders never appear."""
    return Notification.query.filter(
        or_(Notification.target_user_id.is_(None), Notification.target_user_id == user_id)
    )


def _read_ids(user_id) -> set:
    return {r.notification_id for r in NotificationRead.query.filter_by(user_id=user_id).all()}


@notifications_bp.get("/me")
@login_required
def my_notifications():
    """Newest first, paged (?limit= default 30, max 100, ?offset=). unread_count covers ALL of them, not just this page."""
    user = current_user()
    limit, offset, bad = parse_paging(default_limit=30, max_limit=100)
    if bad:
        return jsonify(bad[0]), bad[1]

    query = _visible_to(user.id)
    total = query.count()
    rows = query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit).offset(offset).all()
    read = _read_ids(user.id)
    items = [n.to_dict(read=n.id in read) for n in rows]
    unread_count = sum(1 for n in query.with_entities(Notification.id).all() if n.id not in read)
    meta = localize_groups(user, (items, ["message"]))
    return jsonify({"notifications": items, "unread_count": unread_count, "total": total,
                    "limit": limit, "offset": offset, **meta}), 200


@notifications_bp.patch("/<int:notification_id>/read")
@login_required
def mark_read(notification_id):
    user = current_user()
    # Someone else's private notification looks exactly like a missing one.
    note = _visible_to(user.id).filter(Notification.id == notification_id).first()
    if note is None:
        return jsonify({"error": "notification_not_found"}), 404
    if notification_id not in _read_ids(user.id):
        db.session.add(NotificationRead(user_id=user.id, notification_id=notification_id))
        db.session.commit()
    return jsonify({"message": "Marked as read."}), 200


@notifications_bp.post("/read-all")
@login_required
def mark_all_read():
    user = current_user()
    already = _read_ids(user.id)
    fresh = [n.id for n in _visible_to(user.id).all() if n.id not in already]
    for nid in fresh:
        db.session.add(NotificationRead(user_id=user.id, notification_id=nid))
    db.session.commit()
    return jsonify({"message": "All marked as read.", "marked": len(fresh)}), 200
