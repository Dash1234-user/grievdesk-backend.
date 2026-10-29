from flask import Blueprint, jsonify

from app.utils.decorators import login_required, current_user
from app.models.complaint import Complaint
from app.models.service_request import ServiceRequest
from app.models.ticket_event import TicketType
from app.services.tickets import timelines_for
from app.services.translation import localize_groups

my_tickets_bp = Blueprint("my_tickets", __name__, url_prefix="/api/my-tickets")


@my_tickets_bp.get("")
@login_required
def my_tickets():
    """
    The My Tickets screen: everything THIS user raised (their anonymous complaints included),
    each with its status timeline. Other people's tickets live in the Public Inbox.
    """
    user = current_user()
    complaints = Complaint.query.filter_by(user_id=user.id).order_by(Complaint.created_at.desc(), Complaint.id.desc()).all()
    requests_ = ServiceRequest.query.filter_by(user_id=user.id).order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc()).all()

    c_events = timelines_for(TicketType.COMPLAINT, [c.id for c in complaints])
    s_events = timelines_for(TicketType.SERVICE_REQUEST, [r.id for r in requests_])

    complaint_rows = [dict(c.to_public_dict(user), timeline=c_events[c.id]) for c in complaints]
    request_rows = [dict(r.to_public_dict(), timeline=s_events[r.id]) for r in requests_]
    events = [e for row in complaint_rows + request_rows for e in row["timeline"]]
    meta = localize_groups(
        user,
        (complaint_rows, ["translated_text", "resolution_notes"]),
        (request_rows, ["description"]),
        (events, ["note"]),
    )
    return jsonify({"complaints": complaint_rows, "service_requests": request_rows, **meta}), 200
