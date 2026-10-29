from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import func

from app.extensions import db
from app.utils.decorators import login_required, committee_or_secretary_required, current_user
from app.models.user import User, Role, ApprovalStatus
from app.models.complaint import Complaint, ComplaintStatus, ComplaintCategory, Severity
from app.models.ticket_event import TicketType, TicketAction
from app.services import speech
from app.services.tickets import add_event, timeline
from app.services.complaint_status import set_complaint_status
from app.services.translation import localize_groups
from app.utils.paging import parse_paging

complaints_bp = Blueprint("complaints", __name__, url_prefix="/api/complaints")


def _get_or_none(complaint_id):
    return db.session.get(Complaint, complaint_id)


def _report_counts() -> dict:
    """{original_complaint_id: number_of_duplicates_linked_to_it}"""
    rows = (
        db.session.query(Complaint.duplicate_of, func.count(Complaint.id))
        .filter(Complaint.duplicate_of.isnot(None)).group_by(Complaint.duplicate_of).all()
    )
    return dict(rows)


def _with_reports(complaint, viewer, counts):
    row = complaint.to_public_dict(viewer)
    # For an original: how many residents reported it in total (itself + linked duplicates). None for a duplicate.
    row["reports_count"] = (1 + counts.get(complaint.id, 0)) if complaint.duplicate_of is None else None
    return row


@complaints_bp.get("")
@login_required
def list_complaints():
    """
    Public Inbox — visible to every logged-in user (resident, committee, secretary).
    Filters: ?status= ?category= ?severity= ?block=   Paging: ?limit= (default 20, max 100) ?offset=
    Texts are translated into the reader's preferred language (see the *_local fields).
    """
    viewer = current_user()
    limit, offset, bad = parse_paging(default_limit=20, max_limit=100)
    if bad:
        return jsonify(bad[0]), bad[1]

    query = Complaint.query
    status, category, severity = request.args.get("status"), request.args.get("category"), request.args.get("severity")
    if status:
        if status not in ComplaintStatus.ALL:
            return jsonify({"error": "invalid_status", "allowed": list(ComplaintStatus.ALL)}), 400
        query = query.filter(Complaint.status == status)
    if category:
        if category not in ComplaintCategory.ALL:
            return jsonify({"error": "invalid_category", "allowed": list(ComplaintCategory.ALL)}), 400
        query = query.filter(Complaint.category == category)
    if severity:
        if severity not in Severity.ALL:
            return jsonify({"error": "invalid_severity", "allowed": list(Severity.ALL)}), 400
        query = query.filter(Complaint.severity == severity)
    block = request.args.get("block")
    if block:
        # An anonymous complaint's block is hidden from other residents, so filtering by block must not
        # be a way to find out where it came from: for them it only matches the complaints they may identify.
        query = query.join(User, Complaint.user_id == User.id).filter(User.block_no == block)
        if not viewer.is_staff():
            query = query.filter(db.or_(Complaint.is_anonymous.is_(False), Complaint.user_id == viewer.id))

    total = query.count()
    complaints = query.order_by(Complaint.created_at.desc(), Complaint.id.desc()).limit(limit).offset(offset).all()
    counts = _report_counts()
    rows = [_with_reports(c, viewer, counts) for c in complaints]
    meta = localize_groups(viewer, (rows, ["translated_text", "resolution_notes"]))
    return jsonify({"complaints": rows, "total": total, "limit": limit, "offset": offset, **meta}), 200


@complaints_bp.get("/<int:complaint_id>")
@login_required
def get_complaint(complaint_id):
    complaint = _get_or_none(complaint_id)
    if complaint is None:
        return jsonify({"error": "complaint_not_found"}), 404
    viewer = current_user()
    body = _with_reports(complaint, viewer, _report_counts())
    body["timeline"] = timeline(TicketType.COMPLAINT, complaint.id)
    if complaint.duplicate_of is None:
        body["linked_reports"] = [c.id for c in Complaint.query.filter_by(duplicate_of=complaint.id).order_by(Complaint.id).all()]
    meta = localize_groups(viewer, ([body], ["translated_text", "resolution_notes"]), (body["timeline"], ["note"]))
    return jsonify({**body, **meta}), 200


@complaints_bp.patch("/<int:complaint_id>/status")
@committee_or_secretary_required
def update_status(complaint_id):
    """Committee/secretary: move a complaint along (new -> in_progress -> resolved, or escalated)."""
    complaint = _get_or_none(complaint_id)
    if complaint is None:
        return jsonify({"error": "complaint_not_found"}), 404

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in ComplaintStatus.ALL:
        return jsonify({"error": "invalid_status", "allowed": list(ComplaintStatus.ALL)}), 400

    notes = data.get("resolution_notes")
    if notes is not None and not isinstance(notes, str):
        return jsonify({"error": "invalid_resolution_notes"}), 400
    notes = notes.strip() if notes else None

    if new_status == complaint.status and not notes:
        return jsonify({"message": "Status unchanged.", "complaint": complaint.to_public_dict(current_user())}), 200

    actor = current_user()
    changed = set_complaint_status(complaint, new_status, actor, resolution_notes=notes)
    db.session.commit()
    return jsonify({
        "message": "Status updated.",
        "complaint": complaint.to_public_dict(actor),
        "linked_reports_updated": len(changed) - 1,   # duplicates of this complaint moved with it
    }), 200


@complaints_bp.patch("/<int:complaint_id>/assign")
@committee_or_secretary_required
def assign(complaint_id):
    """Committee/secretary: put a committee member or the Secretary in charge. Send null to unassign."""
    complaint = _get_or_none(complaint_id)
    if complaint is None:
        return jsonify({"error": "complaint_not_found"}), 404

    data = request.get_json(silent=True) or {}
    if "assigned_to" not in data:
        return jsonify({"error": "missing_fields", "fields": ["assigned_to"]}), 400

    actor = current_user()
    assignee_id = data["assigned_to"]
    if assignee_id is None:
        complaint.assigned_to = None
        add_event(TicketType.COMPLAINT, complaint.id, TicketAction.UNASSIGNED, actor=actor)
    else:
        assignee = db.session.get(User, assignee_id) if isinstance(assignee_id, int) and not isinstance(assignee_id, bool) else None
        if assignee is None or assignee.approval_status != ApprovalStatus.APPROVED or assignee.role not in (Role.COMMITTEE, Role.SECRETARY):
            return jsonify({
                "error": "invalid_assignee",
                "message": "Tickets can only be assigned to the Secretary or a committee member.",
            }), 400
        complaint.assigned_to = assignee.id
        add_event(TicketType.COMPLAINT, complaint.id, TicketAction.ASSIGNED, detail=assignee.name, actor=actor)

    db.session.commit()
    return jsonify({"message": "Assignment updated.", "complaint": complaint.to_public_dict(actor)}), 200


@complaints_bp.patch("/<int:complaint_id>/duplicate")
@committee_or_secretary_required
def set_duplicate(complaint_id):
    """
    Committee/secretary: correct the automatic duplicate detection.
    {"duplicate_of": 12} links this complaint to original #12; {"duplicate_of": null} un-links it.
    """
    complaint = _get_or_none(complaint_id)
    if complaint is None:
        return jsonify({"error": "complaint_not_found"}), 404
    data = request.get_json(silent=True) or {}
    if "duplicate_of" not in data:
        return jsonify({"error": "missing_fields", "fields": ["duplicate_of"]}), 400

    actor = current_user()
    target_id = data["duplicate_of"]

    if target_id is None:
        if complaint.duplicate_of is None:
            return jsonify({"message": "Not linked to anything.", "complaint": complaint.to_public_dict(actor)}), 200
        old = complaint.duplicate_of
        complaint.duplicate_of = None
        add_event(TicketType.COMPLAINT, complaint.id, TicketAction.UNLINKED, detail=f"#{old}", actor=actor)
        db.session.commit()
        return jsonify({"message": "Unlinked.", "complaint": complaint.to_public_dict(actor)}), 200

    if not isinstance(target_id, int) or isinstance(target_id, bool):
        return jsonify({"error": "invalid_duplicate_of", "message": "Send a complaint id or null."}), 400
    if target_id == complaint.id:
        return jsonify({"error": "invalid_duplicate_of", "message": "A complaint can't be a duplicate of itself."}), 400
    target = _get_or_none(target_id)
    if target is None:
        return jsonify({"error": "complaint_not_found", "message": f"No complaint #{target_id}."}), 404
    if target.duplicate_of is not None:
        return jsonify({
            "error": "target_is_duplicate",
            "message": f"#{target_id} is itself a duplicate. Link to the original, #{target.duplicate_of}.",
            "original": target.duplicate_of,
        }), 400

    # If this complaint already had duplicates of its own, they now belong to the new original.
    Complaint.query.filter_by(duplicate_of=complaint.id).update({"duplicate_of": target.id})
    complaint.duplicate_of = target.id
    add_event(TicketType.COMPLAINT, complaint.id, TicketAction.LINKED, detail=f"#{target.id}", actor=actor)
    db.session.commit()
    return jsonify({"message": f"Linked as a duplicate of #{target.id}.", "complaint": complaint.to_public_dict(actor)}), 200


@complaints_bp.get("/<int:complaint_id>/audio")
@login_required
def get_complaint_audio(complaint_id):
    """The original voice note. Only its owner and committee/secretary may listen."""
    viewer = current_user()
    complaint = _get_or_none(complaint_id)
    if complaint is None or not complaint.audio_url:
        return jsonify({"error": "audio_not_found"}), 404

    if not (viewer.id == complaint.user_id or viewer.is_staff()):
        return jsonify({"error": "forbidden", "message": "You can't listen to this recording."}), 403

    path = speech.audio_path(complaint.audio_url)
    if path is None:
        return jsonify({"error": "audio_not_found"}), 404
    return send_file(path, mimetype=speech.AUDIO_TYPES.get("." + path.rsplit(".", 1)[-1], "application/octet-stream"))
