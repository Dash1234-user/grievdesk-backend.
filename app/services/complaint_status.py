from app.models.complaint import Complaint
from app.models.ticket_event import TicketType, TicketAction
from app.services.tickets import add_event, notify_owner_of_status


def set_complaint_status(complaint, new_status, actor, resolution_notes=None, event_note=None):
    """
    The ONE way a complaint's status changes (committee action or automatic escalation).

    Reports linked to this complaint as duplicates follow it, so the 5 residents who reported the same leak all
    see it move to "resolved" without anyone updating 5 tickets. Each owner gets their own private notification.
    actor=None means the system made the change. Returns every complaint that changed (this one first).
    """
    changed = []

    def apply(target, note):
        target.status = new_status
        if resolution_notes:
            target.resolution_notes = resolution_notes
        add_event(TicketType.COMPLAINT, target.id, TicketAction.STATUS_CHANGED, detail=new_status, note=note, actor=actor)
        notify_owner_of_status(TicketType.COMPLAINT, target, target.user_id, actor, new_status, resolution_notes or event_note)
        changed.append(target)

    apply(complaint, event_note or resolution_notes)
    for follower in Complaint.query.filter_by(duplicate_of=complaint.id).all():
        if follower.status != new_status:
            apply(follower, f"Follows complaint #{complaint.id}")
    return changed
