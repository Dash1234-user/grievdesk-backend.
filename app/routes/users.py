import re

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.utils.decorators import (
    login_required, committee_or_secretary_required, secretary_required, current_user,
)
from app.models.user import User, Role, ApprovalStatus
from app.models.notification import NotificationType
from app.services.tickets import notify

users_bp = Blueprint("users", __name__, url_prefix="/api/users")

PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-]{5,18}[0-9]$")
LANG_RE = re.compile(r"^[a-z]{2,3}$")
EDITABLE = {"name", "phone", "preferred_language", "share_phone", "flat_no", "block_no",
            "current_password", "new_password", "confirm_reapproval"}
LOCKED = {"gmail", "role", "approval_status", "id", "password_hash"}


def _target(user_id):
    return db.session.get(User, user_id)


def _not_found():
    return jsonify({"error": "user_not_found"}), 404


def _bad(field, message, status=400):
    return jsonify({"error": "invalid_field", "field": field, "message": message}), status


@users_bp.get("/me")
@login_required
def get_me():
    return jsonify({"user": current_user().to_profile_dict()}), 200


@users_bp.put("/me")
@login_required
def update_me():
    """
    Edit your own profile (send only the fields you want to change).
    Not editable: gmail (it's your login), role, approval status.
    Moving to another flat/block sends you back to the Secretary for approval — otherwise anyone could
    claim any flat after being approved. The Secretary is exempt (they are the approver).
    """
    user = current_user()
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({"error": "missing_fields", "message": "Send the fields you want to change."}), 400

    locked = sorted(set(data) & LOCKED)
    if locked:
        return jsonify({"error": "field_not_editable", "fields": locked}), 400
    unknown = sorted(set(data) - EDITABLE)
    if unknown:
        return jsonify({"error": "unknown_fields", "fields": unknown, "allowed": sorted(EDITABLE - {"confirm_reapproval"})}), 400

    changes = {}
    if "name" in data:
        v = data["name"]
        if not isinstance(v, str) or not (1 <= len(v.strip()) <= 120):
            return _bad("name", "Name must be 1-120 characters.")
        changes["name"] = v.strip()
    if "phone" in data:
        v = data["phone"]
        if not isinstance(v, str) or not PHONE_RE.match(v.strip()):
            return _bad("phone", "Enter a valid phone number (digits, optional leading +).")
        changes["phone"] = v.strip()
    if "preferred_language" in data:
        v = data["preferred_language"]
        if not isinstance(v, str) or not LANG_RE.match(v.strip().lower()):
            return _bad("preferred_language", "Use a language code such as en, hi or or.")
        changes["preferred_language"] = v.strip().lower()
    if "share_phone" in data:
        if not isinstance(data["share_phone"], bool):
            return _bad("share_phone", "share_phone must be true or false.")
        changes["share_phone"] = data["share_phone"]

    for field in ("flat_no", "block_no"):
        if field in data:
            v = data[field]
            if not isinstance(v, str) or not (1 <= len(v.strip()) <= 20):
                return _bad(field, f"{field} must be 1-20 characters.")
            changes[field] = v.strip()

    moving = any(f in changes and changes[f] != getattr(user, f) for f in ("flat_no", "block_no"))
    reapproval = moving and user.role != Role.SECRETARY
    if reapproval and data.get("confirm_reapproval") is not True:
        return jsonify({
            "error": "reapproval_required",
            "message": "Changing your flat or block needs the Secretary's approval again, and you will be "
                       "logged out until it is given. Send confirm_reapproval: true to continue.",
        }), 400

    if "new_password" in data:
        if not data.get("current_password") or not user.check_password(str(data["current_password"])):
            return jsonify({"error": "wrong_password", "message": "Your current password is incorrect."}), 403
        new = data["new_password"]
        if not isinstance(new, str) or len(new) < 8:
            return _bad("new_password", "The new password must be at least 8 characters.")
        if new == data["current_password"]:
            return _bad("new_password", "The new password must be different from the current one.")
        user.set_password(new)

    for field, value in changes.items():
        setattr(user, field, value)
    if reapproval:
        user.approval_status = ApprovalStatus.PENDING

    db.session.commit()
    message = "Profile updated."
    if reapproval:
        message = "Profile updated. Your new flat needs the Secretary's approval; you can log in again once it is given."
    return jsonify({"message": message, "user": user.to_profile_dict()}), 200


@users_bp.get("")
@login_required
def list_users():
    """
    Resident Directory.  ?status=approved (default) works for everyone.
    ?status=pending is the Secretary's approval queue — nobody else may see who is waiting.
    """
    viewer = current_user()
    status = request.args.get("status", ApprovalStatus.APPROVED)
    if status not in ApprovalStatus.ALL:
        return jsonify({"error": "invalid_status", "allowed": list(ApprovalStatus.ALL)}), 400
    if status == ApprovalStatus.PENDING and viewer.role != Role.SECRETARY:
        return jsonify({"error": "forbidden", "message": "Only the Secretary can see pending registrations."}), 403

    rows = (
        User.query.filter_by(approval_status=status)
        .order_by(User.block_no.asc(), User.flat_no.asc(), User.name.asc()).all()
    )
    return jsonify({"users": [u.to_directory_dict(viewer) for u in rows]}), 200


@users_bp.patch("/<int:user_id>/approve")
@secretary_required
def approve_user(user_id):
    """Secretary only: lets a pending resident log in."""
    user = _target(user_id)
    if user is None:
        return _not_found()
    if user.approval_status == ApprovalStatus.APPROVED:
        return jsonify({"message": "Already approved.", "user": user.to_public_dict()}), 200

    user.approval_status = ApprovalStatus.APPROVED
    db.session.commit()
    return jsonify({"message": "Resident approved.", "user": user.to_public_dict()}), 200


@users_bp.patch("/<int:user_id>/promote-to-committee")
@committee_or_secretary_required
def promote_to_committee(user_id):
    """Committee members are equal to the Secretary day to day, so either may promote a resident."""
    actor = current_user()
    target = _target(user_id)
    if target is None:
        return _not_found()
    if target.approval_status != ApprovalStatus.APPROVED:
        return jsonify({"error": "not_approved", "message": "Approve this registration before promoting."}), 400
    if target.role != Role.RESIDENT:
        return jsonify({"error": "already_staff", "message": f"This user is already {target.role}.", "role": target.role}), 409

    target.role = Role.COMMITTEE
    notify(target.id, NotificationType.ROLE_CHANGE,
           f"You have been made a committee member by {actor.name}. The committee tools are now available to you.", actor)
    db.session.commit()
    return jsonify({"message": f"{target.name} is now a committee member.", "user": target.to_public_dict()}), 200


@users_bp.patch("/<int:user_id>/demote")
@secretary_required
def demote_from_committee(user_id):
    """
    Secretary only. Committee members are equals, so none of them may remove another —
    otherwise a handful of members could lock the rest out. Passing power to a new
    committee after elections = demote the old members, promote the new ones.
    """
    actor = current_user()
    target = _target(user_id)
    if target is None:
        return _not_found()
    if target.role != Role.COMMITTEE:
        return jsonify({
            "error": "not_committee",
            "message": "Only committee members can be demoted. To change the Secretary, use transfer-secretary.",
            "role": target.role,
        }), 409

    target.role = Role.RESIDENT
    notify(target.id, NotificationType.ROLE_CHANGE,
           f"You are no longer a committee member (changed by {actor.name}). You are now a resident.", actor)
    db.session.commit()
    return jsonify({"message": f"{target.name} is now a resident.", "user": target.to_public_dict()}), 200


@users_bp.patch("/<int:user_id>/transfer-secretary")
@secretary_required
def transfer_secretary(user_id):
    """
    Secretary only: hand the Secretary title to another approved member. The outgoing Secretary
    becomes a committee member (the Secretary can demote them afterwards if wanted — the new Secretary can).
    Needs {"confirm": true} so a stray request can't give the title away.
    """
    actor = current_user()
    data = request.get_json(silent=True) or {}
    if data.get("confirm") is not True:
        return jsonify({"error": "confirmation_required", "message": 'Send {"confirm": true} to confirm this transfer.'}), 400

    target = _target(user_id)
    if target is None:
        return _not_found()
    if target.id == actor.id:
        return jsonify({"error": "already_secretary", "message": "You already hold the Secretary role."}), 400
    if target.approval_status != ApprovalStatus.APPROVED:
        return jsonify({"error": "not_approved", "message": "The new Secretary must be an approved member."}), 400

    try:
        # Order matters: the database allows only ONE secretary row at any moment (partial unique
        # index), so the old one must step down before the new one is promoted.
        actor.role = Role.COMMITTEE
        db.session.flush()
        target.role = Role.SECRETARY
        notify(target.id, NotificationType.ROLE_CHANGE,
               f"{actor.name} has transferred the Secretary role to you. You are now the Secretary.", actor)
        notify(actor.id, NotificationType.ROLE_CHANGE,
               f"You transferred the Secretary role to {target.name}. You are now a committee member.", actor)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "conflict", "message": "The Secretary role changed while you were doing this. Please retry."}), 409

    return jsonify({
        "message": f"{target.name} is now the Secretary. You are now a committee member.",
        "new_secretary": target.to_public_dict(),
        "you": actor.to_public_dict(),
    }), 200
