from datetime import datetime, timezone
from app.extensions import db


class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)  # canonical English
    is_pinned = db.Column(db.Boolean, nullable=False, default=False)
    posted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    author = db.relationship("User", foreign_keys=[posted_by])

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "is_pinned": self.is_pinned,
            "posted_by": self.author.name if self.author else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
