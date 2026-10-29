"""
Housekeeping jobs. Each one is safe to run twice (idempotent), so it doesn't matter if cron, the
in-process scheduler and a manual `flask jobs ...` all fire around the same time.
"""
import json
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.chat_message import ChatMessage
from app.models.complaint import Complaint, ComplaintStatus
from app.models.job_run import JobRun
from app.models.notification import NotificationType
from app.models.user import User, Role, ApprovalStatus
from app.services.complaint_status import set_complaint_status
from app.services.tickets import notify


def _utcnow():
    return datetime.now(timezone.utc)


def run_chat_cleanup(now=None) -> dict:
    """
    Deletes chat TRANSCRIPTS older than CHAT_RETENTION_DAYS. It touches the chat_messages table and
    nothing else: complaints, service requests, dues, announcements, notifications and stored voice
    notes all live in their own tables/folder and are never affected.
    """
    now = now or _utcnow()
    days = current_app.config["CHAT_RETENTION_DAYS"]
    cutoff = now - timedelta(days=days)
    deleted = ChatMessage.query.filter(ChatMessage.created_at < cutoff).delete(synchronize_session=False)
    db.session.commit()
    return {"deleted_chat_messages": deleted, "older_than_days": days}


def run_escalation(now=None) -> dict:
    """
    A complaint still "new" after ESCALATION_DAYS has had no response: mark it escalated, tell the person
    who raised it, and send every committee member/the Secretary ONE digest (not one message per complaint).
    Duplicates are skipped: they follow their original, which is what gets escalated.
    """
    now = now or _utcnow()
    days = current_app.config["ESCALATION_DAYS"]
    cutoff = now - timedelta(days=days)

    stale = (
        Complaint.query.filter(
            Complaint.status == ComplaintStatus.NEW,
            Complaint.duplicate_of.is_(None),
            Complaint.created_at <= cutoff,
        )
        .order_by(Complaint.created_at.asc())
        .with_for_update(skip_locked=True)   # PostgreSQL: a second simultaneous run skips rows this run holds
        .all()
    )
    if not stale:
        return {"escalated": 0, "linked_reports_escalated": 0}

    linked, parts = 0, []
    for complaint in stale:
        changed = set_complaint_status(
            complaint, ComplaintStatus.ESCALATED, actor=None,
            event_note=f"Automatically escalated: no response for {days} days.",
        )
        extra = len(changed) - 1
        linked += extra
        parts.append(f"#{complaint.id} ({complaint.category or 'complaint'})" + (f" +{extra} linked" if extra else ""))

    digest = (
        f"{len(stale)} complaint{'s' if len(stale) != 1 else ''} had no response for {days}+ days "
        f"and {'were' if len(stale) != 1 else 'was'} escalated: " + ", ".join(parts) + "."
    )
    staff = User.query.filter(
        User.role.in_((Role.COMMITTEE, Role.SECRETARY)), User.approval_status == ApprovalStatus.APPROVED,
    ).all()
    for member in staff:
        notify(member.id, NotificationType.TICKET_UPDATE, digest, None)

    db.session.commit()
    return {"escalated": len(stale), "linked_reports_escalated": linked}


def run_job(name, fn, **kwargs):
    """Runs a job and records the outcome in job_runs. Re-raises on failure so callers can report it."""
    run = JobRun(job=name, started_at=_utcnow())
    db.session.add(run)
    db.session.commit()          # recorded BEFORE running, so a crash mid-job is still visible (ok = NULL)
    run_id = run.id
    try:
        result = fn(**kwargs)
    except Exception as exc:
        db.session.rollback()
        failed = db.session.get(JobRun, run_id)
        failed.ok, failed.finished_at, failed.summary = False, _utcnow(), f"{type(exc).__name__}: {exc}"
        db.session.commit()
        raise
    done = db.session.get(JobRun, run_id)
    done.ok, done.finished_at, done.summary = True, _utcnow(), json.dumps(result)
    db.session.commit()
    return result


JOBS = {
    "chat_cleanup": run_chat_cleanup,
    "escalation": run_escalation,
}
