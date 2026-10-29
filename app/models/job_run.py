from datetime import datetime, timezone
from app.extensions import db


class JobRun(db.Model):
    """One row per run of a scheduled job, so "did the weekly cleanup actually run?" has an answer."""
    __tablename__ = "job_runs"

    id = db.Column(db.Integer, primary_key=True)
    job = db.Column(db.String(50), nullable=False, index=True)
    started_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    ok = db.Column(db.Boolean, nullable=True)        # NULL = still running (or the process died mid-run)
    summary = db.Column(db.Text, nullable=True)
