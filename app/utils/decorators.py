from functools import wraps
from flask import g, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

from app.extensions import db
from app.models.user import User, Role, ApprovalStatus


def current_user():
    """The logged-in user for this request (set by the decorators below), or None."""
    return g.get("current_user")


def _authenticate():
    """
    Validates the token, then loads the user FRESH from the database. The role written into the
    token is never trusted: if the Secretary promotes, demotes or transfers a role, it takes effect
    on the very next request instead of whenever that person happens to log in again.
    Returns the user, or None if the account no longer exists / is not approved.
    """
    verify_jwt_in_request()
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None or user.approval_status != ApprovalStatus.APPROVED:
        return None
    g.current_user = user
    return user


def _unauthorized():
    return jsonify({"error": "unauthorized", "message": "This account is not active."}), 401


def _forbidden():
    return jsonify({"error": "forbidden", "message": "You do not have permission for this action."}), 403


def _role_required(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = _authenticate()
            if user is None:
                return _unauthorized()
            if user.role not in allowed_roles:
                return _forbidden()
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# Any logged-in, approved user (resident, committee, or secretary)
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if _authenticate() is None:
            return _unauthorized()
        return fn(*args, **kwargs)
    return wrapper


# Committee or Secretary — ticket status/assignment, dues, announcements, promotions
def committee_or_secretary_required(fn):
    return _role_required(Role.COMMITTEE, Role.SECRETARY)(fn)


# Secretary only — approving registrations, demoting, transferring the Secretary title
def secretary_required(fn):
    return _role_required(Role.SECRETARY)(fn)
