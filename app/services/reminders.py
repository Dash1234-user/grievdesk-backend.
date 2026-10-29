from decimal import Decimal

from app.models.due import Due, PaidStatus
from app.models.notification import NotificationType
from app.services import gemini
from app.services.tickets import notify

DEFAULT_NOTE = "Please clear your pending maintenance dues."


def queue_dues_reminder(actor, resident, note: str):
    """
    Drafts a polite reminder covering ALL of this resident's unpaid dues and queues it as a private
    notification (only `resident` will see it). Returns the message text, or None if there is nothing
    to remind about. Raises GeminiNotConfigured / GeminiCallFailed — callers decide how to report that.
    Shared by the chat flow (reminder by flat) and POST /api/dues/<id>/remind (reminder for one due).
    """
    unpaid = (
        Due.query.filter_by(user_id=resident.id, paid_status=PaidStatus.UNPAID)
        .order_by(Due.month.asc()).all()
    )
    if not unpaid:
        return None

    total = sum((d.amount for d in unpaid), Decimal("0"))
    message = gemini.draft_dues_reminder(
        flat_no=resident.flat_no, months=[d.month for d in unpaid], total=str(total), note=note,
    )
    if not message:
        return None

    notify(resident.id, NotificationType.DUE_REMINDER, message, actor)
    return message
