from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from email_validator import validate_email, EmailNotValidError

from app.extensions import db
from app.models.user import User, Role, ApprovalStatus

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

REQUIRED_FIELDS = [
    "role", "name", "phone", "flat_no", "block_no",
    "gmail", "preferred_language", "password",
]


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}

    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if missing:
        return jsonify({"error": "missing_fields", "fields": missing}), 400

    if not isinstance(data["password"], str) or len(data["password"]) < 8:
        return jsonify({"error": "weak_password", "message": "Password must be at least 8 characters."}), 400

    requested_role = data["role"].strip().lower()
    if requested_role not in ("resident", "admin"):
        return jsonify({"error": "invalid_role", "message": "role must be 'resident' or 'admin'."}), 400

    try:
        validate_email(data["gmail"], check_deliverability=False)
    except EmailNotValidError:
        return jsonify({"error": "invalid_email"}), 400

    if User.query.filter_by(gmail=data["gmail"]).first():
        return jsonify({"error": "email_already_registered"}), 409

    if requested_role == "admin":
        # Only one Secretary may exist for this single society. Enforced here
        # AND at the DB level via the partial unique index on User.role.
        existing_secretary = User.query.filter_by(role=Role.SECRETARY).first()
        if existing_secretary:
            return jsonify({
                "error": "secretary_already_exists",
                "message": "An admin (Secretary) is already registered for this society.",
            }), 409

        new_user = User(
            name=data["name"],
            phone=data["phone"],
            gmail=data["gmail"],
            flat_no=data["flat_no"],
            block_no=data["block_no"],
            preferred_language=data["preferred_language"],
            role=Role.SECRETARY,
            approval_status=ApprovalStatus.APPROVED,  # first-ever Secretary is auto-approved
        )
    else:
        new_user = User(
            name=data["name"],
            phone=data["phone"],
            gmail=data["gmail"],
            flat_no=data["flat_no"],
            block_no=data["block_no"],
            preferred_language=data["preferred_language"],
            role=Role.RESIDENT,
            approval_status=ApprovalStatus.PENDING,  # needs Secretary approval before login works
        )

    new_user.set_password(data["password"])

    db.session.add(new_user)
    db.session.commit()

    message = (
        "Registered as Secretary."
        if new_user.role == Role.SECRETARY
        else "Registered. Your account is pending Secretary approval before you can log in."
    )
    return jsonify({"message": message, "user": new_user.to_public_dict()}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    gmail = data.get("gmail")
    password = data.get("password")

    if not gmail or not password:
        return jsonify({"error": "missing_fields", "fields": ["gmail", "password"]}), 400

    user = User.query.filter_by(gmail=gmail).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "invalid_credentials"}), 401

    if user.approval_status != ApprovalStatus.APPROVED:
        return jsonify({"error": "pending_approval", "message": "Your account is awaiting Secretary approval."}), 403

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role},
    )
    return jsonify({"access_token": access_token, "user": user.to_public_dict()}), 200
