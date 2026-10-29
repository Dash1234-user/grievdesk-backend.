from datetime import datetime, timezone
from app.extensions import db


class SelectedType:
    COMPLAINT = "complaint"
    SERVICE = "service"
    RULES = "rules"
    COMMITTEE_ACTION = "committee_action"
    ALL = (COMPLAINT, SERVICE, RULES, COMMITTEE_ACTION)


class ChatMessage(db.Model):
    """
    Raw AI conversation transcript — disposable by design (see the data-separation
    rule in the brief). This table gets purged weekly once the scheduled-jobs step
    is built. The *result* of a conversation (a Complaint, ServiceRequest, etc.)
    lives permanently in its own table and is never affected by that cleanup.
    """
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    session_id = db.Column(db.String(64), nullable=False, index=True)

    selected_type = db.Column(db.String(20), nullable=False)  # user-picked, never AI-guessed
    role = db.Column(db.String(10), nullable=False)  # 'user' or 'assistant'
    content_text = db.Column(db.Text, nullable=False)
    audio_url = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
