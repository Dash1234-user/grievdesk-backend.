"""Shared helpers for anything that changes a ticket (complaint / service request)."""
from app.extensions import db
from app.models.notification import Notification, NotificationType
from app.models.ticket_event import TicketEvent, TicketType

STATUS_LABELS = {
    "new": "New",
    "in_progress": "In progress",
    "resolved": "Resolved",
    "escalated": "Escalated",
}


def add_event(ticket_type, ticket_id, action, detail=None, note=None, actor=None):
    db.session.add(TicketEvent(
        ticket_type=ticket_type, ticket_id=ticket_id, action=action,
        detail=detail, note=note, actor_id=actor.id if actor else None,
    ))


def timeline(ticket_type, ticket_id):
    rows = (
        TicketEvent.query.filter_by(ticket_type=ticket_type, ticket_id=ticket_id)
        .order_by(TicketEvent.created_at.asc(), TicketEvent.id.asc()).all()
    )
    return [r.to_dict() for r in rows]


def notify(user_id, notification_type, message, created_by):
    """A private notification — only `user_id` will ever see it."""
    db.session.add(Notification(
        type=notification_type, message=message, target_user_id=user_id,
        created_by=created_by.id if created_by is not None else None,   # None = the system
    ))


def notify_owner_of_status(ticket_type, ticket, owner_id, actor, new_status, note=None):
    """Tell the person who raised the ticket that its status changed (not when they changed it themselves).
    actor=None means the system did it (e.g. automatic escalation)."""
    if actor is not None and owner_id == actor.id:
        return
    kind = "complaint" if ticket_type == TicketType.COMPLAINT else "service request"
    message = f"Update on your {kind} #{ticket.id}: status is now {STATUS_LABELS.get(new_status, new_status)}."
    if note:
        message += f" {'Note from the committee' if actor is not None else 'Note'}: {note}"
    notify(owner_id, NotificationType.TICKET_UPDATE, message, actor)


def timelines_for(ticket_type, ticket_ids):
    """{ticket_id: [events...]} for many tickets in a single query."""
    result = {tid: [] for tid in ticket_ids}
    if not ticket_ids:
        return result
    rows = (
        TicketEvent.query.filter(TicketEvent.ticket_type == ticket_type, TicketEvent.ticket_id.in_(ticket_ids))
        .order_by(TicketEvent.created_at.asc(), TicketEvent.id.asc()).all()
    )
    for row in rows:
        result[row.ticket_id].append(row.to_dict())
    return result
