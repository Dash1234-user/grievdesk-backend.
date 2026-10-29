from flask import Blueprint, jsonify, request

from app.extensions import db
from app.utils.decorators import login_required, committee_or_secretary_required, current_user
from app.models.service_request import ServiceRequest, ServiceRequestStatus
from app.models.ticket_event import TicketType, TicketAction
from app.services.tickets import add_event, timeline, notify_owner_of_status
from app.services.translation import localize_groups

service_requests_bp = Blueprint("service_requests", __name__, url_prefix="/api/service-requests")


@service_requests_bp.get("")
@login_required
def list_service_requests():
    """Residents see only their own; committee/secretary see everyone's."""
    viewer = current_user()
    query = ServiceRequest.query
    if not viewer.is_staff():
        query = query.filter_by(user_id=viewer.id)
    rows = [r.to_public_dict() for r in query.order_by(ServiceRequest.created_at.desc(), ServiceRequest.id.desc()).all()]
    meta = localize_groups(viewer, (rows, ["description"]))
    return jsonify({"service_requests": rows, **meta}), 200


@service_requests_bp.get("/<int:request_id>")
@login_required
def get_service_request(request_id):
    viewer = current_user()
    row = db.session.get(ServiceRequest, request_id)
    # A resident asking for someone else's request gets the same answer as for a missing one.
    if row is None or not (viewer.is_staff() or row.user_id == viewer.id):
        return jsonify({"error": "service_request_not_found"}), 404
    body = row.to_public_dict()
    body["timeline"] = timeline(TicketType.SERVICE_REQUEST, row.id)
    meta = localize_groups(viewer, ([body], ["description"]), (body["timeline"], ["note"]))
    return jsonify({**body, **meta}), 200


@service_requests_bp.patch("/<int:request_id>/status")
@committee_or_secretary_required
def update_status(request_id):
    row = db.session.get(ServiceRequest, request_id)
    if row is None:
        return jsonify({"error": "service_request_not_found"}), 404

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in ServiceRequestStatus.ALL:
        return jsonify({"error": "invalid_status", "allowed": list(ServiceRequestStatus.ALL)}), 400
    if new_status == row.status:
        return jsonify({"message": "Status unchanged.", "service_request": row.to_public_dict()}), 200

    actor = current_user()
    row.status = new_status
    add_event(TicketType.SERVICE_REQUEST, row.id, TicketAction.STATUS_CHANGED, detail=new_status, actor=actor)
    notify_owner_of_status(TicketType.SERVICE_REQUEST, row, row.user_id, actor, new_status)
    db.session.commit()
    return jsonify({"message": "Status updated.", "service_request": row.to_public_dict()}), 200
