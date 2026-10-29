from datetime import datetime, timedelta, timezone

from flask import current_app

from app.models.complaint import Complaint, ComplaintCategory, ComplaintStatus
from app.models.user import User


def find_duplicate_root(reporter, category, now=None):
    """
    Is this new complaint about something already reported? Rule from the design:
    same category + same block, an open (not resolved) original, reported within the time window.
    Only ORIGINALS match (never a duplicate), so every duplicate points at one root, never a chain.
    "Other" is too generic to compare, so it never matches.
    Returns the original complaint, or None.
    """
    if not category or category == ComplaintCategory.OTHER:
        return None
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=current_app.config["DUPLICATE_WINDOW_HOURS"])
    return (
        Complaint.query.join(User, Complaint.user_id == User.id)
        .filter(
            Complaint.duplicate_of.is_(None),
            Complaint.status != ComplaintStatus.RESOLVED,
            Complaint.category == category,
            User.block_no == reporter.block_no,
            Complaint.created_at >= since,
        )
        .order_by(Complaint.created_at.asc(), Complaint.id.asc())
        .first()
    )
