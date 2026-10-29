from datetime import datetime, timezone
from app.extensions import db


class TranslationCache(db.Model):
    """
    A remembered translation, so the same sentence is never translated twice for the same language.
    The permanent record (complaint, announcement, ...) always stays in English; this table is only a
    disposable shortcut and can be emptied at any time without losing anything.
    Keyed by a hash of the English text, so it holds no link to who wrote or who is allowed to see it.
    """
    __tablename__ = "translation_cache"

    id = db.Column(db.Integer, primary_key=True)
    source_hash = db.Column(db.String(64), nullable=False)       # sha256 of the English text
    target_lang = db.Column(db.String(10), nullable=False)       # e.g. "hi", "or"
    translated_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("source_hash", "target_lang", name="uq_translation_source_lang"),
    )
