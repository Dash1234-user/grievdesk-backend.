from datetime import datetime, timezone
from app.extensions import db


class BylawsDocument(db.Model):
    """
    The society rulebook, stored as one versioned block of plain text and pasted
    whole into the Rules Q&A prompt (no chunking/embeddings — rulebooks are short).
    Every upload creates a new version; Q&A always uses the highest version.
    """
    __tablename__ = "bylaws_document"

    id = db.Column(db.Integer, primary_key=True)
    content_text = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, nullable=False, unique=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
