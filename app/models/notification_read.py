from datetime import datetime, timezone
from app.extensions import db


class NotificationRead(db.Model):
    """
    Per-person "I've read this". A broadcast notification (one row, shown to everyone) can't carry a
    single read flag, otherwise one resident opening it would mark it read for the whole society.
    """
    __tablename__ = "notification_reads"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    notification_id = db.Column(db.Integer, db.ForeignKey("notifications.id"), nullable=False)
    read_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("user_id", "notification_id", name="uq_notification_read"),
    )
