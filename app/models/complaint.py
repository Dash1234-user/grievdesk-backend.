from datetime import datetime, timezone
from app.extensions import db


class ComplaintCategory:
    PLUMBING = "Plumbing"
    ELECTRICAL = "Electrical"
    WATER_SUPPLY = "Water Supply"
    SANITATION = "Sanitation"
    PARKING = "Parking"
    NOISE = "Noise"
    SECURITY = "Security"
    OTHER = "Other"
    ALL = (PLUMBING, ELECTRICAL, WATER_SUPPLY, SANITATION, PARKING, NOISE, SECURITY, OTHER)


class Severity:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ALL = (LOW, MEDIUM, HIGH)


class ComplaintStatus:
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    ALL = (NEW, IN_PROGRESS, RESOLVED, ESCALATED)


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    raw_text = db.Column(db.Text, nullable=False)
    original_language = db.Column(db.String(10), nullable=False, default="en")
    translated_text = db.Column(db.Text, nullable=False)  # canonical English version
    audio_url = db.Column(db.String(500), nullable=True)  # wired up in the voice-input step

    category = db.Column(db.String(30), nullable=True)   # AI-assigned
    severity = db.Column(db.String(10), nullable=True)    # AI-assigned

    status = db.Column(db.String(20), nullable=False, default=ComplaintStatus.NEW)
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)

    duplicate_of = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", foreign_keys=[user_id])
    assignee = db.relationship("User", foreign_keys=[assigned_to])

    def to_public_dict(self, viewer=None) -> dict:
        """
        `viewer` is the logged-in User. Rules enforced here, at the display layer:
          * anonymous complaints hide flat/block from everyone except the owner and committee/secretary
          * the author's name is only ever sent to committee/secretary (so they can resolve it)
          * a voice recording is only advertised to the owner and committee/secretary
        """
        is_staff = viewer is not None and viewer.role in ("committee", "secretary")
        is_owner = viewer is not None and viewer.id == self.user_id
        reveal = (not self.is_anonymous) or is_staff or is_owner
        return {
            "id": self.id,
            "flat_no": self.user.flat_no if (reveal and self.user) else None,
            "block_no": self.user.block_no if (reveal and self.user) else None,
            "submitted_by": self.user.name if (is_staff and self.user) else None,
            "is_anonymous": self.is_anonymous,
            "category": self.category,
            "severity": self.severity,
            "status": self.status,
            "translated_text": self.translated_text,
            "duplicate_of": self.duplicate_of,
            "assigned_to": self.assignee.name if self.assignee else None,
            "resolution_notes": self.resolution_notes,
            "audio_available": bool(self.audio_url) and (is_staff or is_owner),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
