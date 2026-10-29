import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from flask import Blueprint, request, jsonify

from app.extensions import db
from app.utils.decorators import login_required, committee_or_secretary_required, current_user
from app.models.user import User, ApprovalStatus
from app.models.due import Due, PaidStatus
from app.models.notification import NotificationType
from app.services.gemini import GeminiNotConfigured, GeminiCallFailed
from app.services.reminders import queue_dues_reminder, DEFAULT_NOTE
from app.services.tickets import notify

dues_bp = Blueprint("dues", __name__, url_prefix="/api/dues")

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _total_unpaid(rows) -> str:
    return str(sum((d.amount for d in rows if d.paid_status == PaidStatus.UNPAID), Decimal("0")))


@dues_bp.get("/me")
@login_required
def my_dues():
    """A resident's OWN dues only — nobody else's, whatever they ask for."""
    rows = Due.query.filter_by(user_id=current_user().id).order_by(Due.month.desc()).all()
    return jsonify({
        "dues": [d.to_dict() for d in rows],
        "total_unpaid": _total_unpaid(rows),
        "unpaid_count": sum(1 for d in rows if d.paid_status == PaidStatus.UNPAID),
    }), 200


@dues_bp.get("")
@committee_or_secretary_required
def list_dues():
    """Everyone's dues. Filters: ?status=paid|unpaid  ?month=YYYY-MM  ?flat_no=  ?block_no="""
    query = Due.query.join(User, Due.user_id == User.id)

    status = request.args.get("status")
    if status:
        if status not in PaidStatus.ALL:
            return jsonify({"error": "invalid_status", "allowed": list(PaidStatus.ALL)}), 400
        query = query.filter(Due.paid_status == status)
    month = request.args.get("month")
    if month:
        if not MONTH_RE.match(month):
            return jsonify({"error": "invalid_month", "message": "Use YYYY-MM."}), 400
        query = query.filter(Due.month == month)
    if request.args.get("flat_no"):
        query = query.filter(User.flat_no == request.args["flat_no"])
    if request.args.get("block_no"):
        query = query.filter(User.block_no == request.args["block_no"])

    rows = query.order_by(Due.month.desc(), User.block_no.asc(), User.flat_no.asc()).all()
    return jsonify({"dues": [d.to_dict() for d in rows], "total_unpaid": _total_unpaid(rows), "count": len(rows)}), 200


@dues_bp.post("")
@committee_or_secretary_required
def create_due():
    """
    Creates one due row. Identify the resident by user_id, or by flat_no + block_no.
    """
    data = request.get_json(silent=True) or {}

    month = data.get("month")
    if not isinstance(month, str) or not MONTH_RE.match(month):
        return jsonify({"error": "invalid_month", "message": "Use YYYY-MM, e.g. 2026-09."}), 400

    try:
        amount = Decimal(str(data.get("amount")))
        if amount <= 0 or not amount.is_finite():
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        return jsonify({"error": "invalid_amount", "message": "amount must be a positive number."}), 400

    try:
        due_date = date.fromisoformat(str(data.get("due_date")))
    except ValueError:
        return jsonify({"error": "invalid_due_date", "message": "Use YYYY-MM-DD."}), 400

    if data.get("user_id") is not None:
        resident = db.session.get(User, data["user_id"]) if isinstance(data["user_id"], int) and not isinstance(data["user_id"], bool) else None
        residents = [resident] if resident else []
    else:
        flat_no, block_no = data.get("flat_no"), data.get("block_no")
        if not flat_no or not block_no:
            return jsonify({"error": "missing_fields", "message": "Send user_id, or flat_no and block_no."}), 400
        residents = User.query.filter_by(
            flat_no=flat_no, block_no=block_no, approval_status=ApprovalStatus.APPROVED,
        ).all()

    if not residents:
        return jsonify({"error": "resident_not_found"}), 404
    if len(residents) > 1:
        return jsonify({
            "error": "ambiguous_flat",
            "message": "More than one resident lives in that flat — resend with user_id.",
            "candidates": [{"user_id": r.id, "name": r.name} for r in residents],
        }), 400
    resident = residents[0]

    if Due.query.filter_by(user_id=resident.id, month=month).first():
        return jsonify({"error": "due_already_exists", "message": f"A due for {month} already exists for this resident."}), 409

    due = Due(user_id=resident.id, month=month, amount=amount, due_date=due_date)
    db.session.add(due)
    db.session.commit()
    return jsonify({"message": "Due created.", "due": due.to_dict()}), 201


@dues_bp.patch("/<int:due_id>/mark-paid")
@committee_or_secretary_required
def mark_paid(due_id):
    """Record a payment (default) or undo it with {"paid": false}. The resident gets a private receipt."""
    due = db.session.get(Due, due_id)
    if due is None:
        return jsonify({"error": "due_not_found"}), 404

    data = request.get_json(silent=True) or {}
    paid = data.get("paid", True)
    if not isinstance(paid, bool):
        return jsonify({"error": "invalid_paid", "message": "paid must be true or false."}), 400

    target = PaidStatus.PAID if paid else PaidStatus.UNPAID
    if due.paid_status == target:
        return jsonify({"message": "Status unchanged.", "due": due.to_dict()}), 200

    actor = current_user()
    due.paid_status = target
    due.paid_at = datetime.now(timezone.utc) if paid else None
    if due.user_id != actor.id:
        text = (
            f"Your maintenance due for {due.month} ({due.amount}) has been recorded as paid. Thank you."
            if paid else
            f"Your maintenance due for {due.month} ({due.amount}) was marked unpaid again by {actor.name}."
        )
        notify(due.user_id, NotificationType.DUE_UPDATE, text, actor)
    db.session.commit()
    return jsonify({"message": "Marked paid." if paid else "Marked unpaid.", "due": due.to_dict()}), 200


@dues_bp.post("/<int:due_id>/remind")
@committee_or_secretary_required
def remind(due_id):
    """AI-drafted reminder to the person who owes this due (covers all their unpaid months). Private to them."""
    due = db.session.get(Due, due_id)
    if due is None:
        return jsonify({"error": "due_not_found"}), 404
    if due.paid_status == PaidStatus.PAID:
        return jsonify({"error": "already_paid", "message": "This due is already paid — nothing to remind about."}), 409

    note = (request.get_json(silent=True) or {}).get("note")
    if note is not None and not isinstance(note, str):
        return jsonify({"error": "invalid_note"}), 400
    note = (note or "").strip() or DEFAULT_NOTE

    try:
        message = queue_dues_reminder(current_user(), due.user, note)
    except GeminiNotConfigured:
        db.session.rollback()
        return jsonify({"error": "ai_not_configured", "message": "GEMINI_API_KEY is missing from .env."}), 503
    except GeminiCallFailed as exc:
        db.session.rollback()
        return jsonify({"error": "ai_call_failed", "message": "The Gemini API call failed.", "detail": str(exc)}), 502
    if not message:
        db.session.rollback()
        return jsonify({"error": "nothing_to_remind"}), 409

    db.session.commit()
    return jsonify({"message": f"Reminder sent to {due.user.name}.", "reminder": message}), 201
