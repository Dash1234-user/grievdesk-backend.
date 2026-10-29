from datetime import datetime, timezone
from app.extensions import db


class NotificationType:
    ANNOUNCEMENT = "announcement"
    DUE_REMINDER = "due_reminder"
    ROLE_CHANGE = "role_change"
    TICKET_UPDATE = "ticket_update"
    DUE_UPDATE = "due_update"
    BOOKING_UPDATE = "booking_update"
    ALL = (ANNOUNCEMENT, DUE_REMINDER, ROLE_CHANGE, TICKET_UPDATE, DUE_UPDATE, BOOKING_UPDATE)


class Notification(db.Model):
    """target_user_id NULL = broadcast to every resident; otherwise only that user sees it."""
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)  # canonical English
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # NULL = sent by the system
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read_status = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self, read: bool = False) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "message": self.message,
            "is_broadcast": self.target_user_id is None,
            "read_status": read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
