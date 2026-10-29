from datetime import datetime, timezone
from app.extensions import db


class TicketType:
    COMPLAINT = "complaint"
    SERVICE_REQUEST = "service_request"


class TicketAction:
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    LINKED = "linked"        # marked as a duplicate of another complaint
    UNLINKED = "unlinked"


class TicketEvent(db.Model):
    """
    One row per change on a complaint/service request. This is what the "status timeline"
    in My Tickets is built from (and what the escalation job will write to as the system).
    actor_id is NULL for automatic changes made by the system.
    """
    __tablename__ = "ticket_events"

    id = db.Column(db.Integer, primary_key=True)
    ticket_type = db.Column(db.String(20), nullable=False)
    ticket_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(20), nullable=False)
    detail = db.Column(db.String(100), nullable=True)   # new status, or the assignee's name
    note = db.Column(db.Text, nullable=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    actor = db.relationship("User", foreign_keys=[actor_id])

    __table_args__ = (
        db.Index("ix_ticket_events_ticket", "ticket_type", "ticket_id"),
    )

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "detail": self.detail,
            "note": self.note,
            "by": self.actor.name if self.actor else "system",
            "at": self.created_at.isoformat() if self.created_at else None,
        }
