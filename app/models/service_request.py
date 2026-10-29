from datetime import datetime, timezone
from app.extensions import db


class ServiceType:
    PLUMBER = "plumber"
    ELECTRICIAN = "electrician"
    AC_MECHANIC = "ac_mechanic"
    LAUNDRY = "laundry"
    VEHICLE_SERVICE = "vehicle_service"
    ALL = (PLUMBER, ELECTRICIAN, AC_MECHANIC, LAUNDRY, VEHICLE_SERVICE)
    LABELS = {
        PLUMBER: "plumber",
        ELECTRICIAN: "electrician",
        AC_MECHANIC: "AC mechanic",
        LAUNDRY: "laundry",
        VEHICLE_SERVICE: "vehicle servicing",
    }


class ServiceRequestStatus:
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ALL = (NEW, IN_PROGRESS, RESOLVED)


class ServiceRequest(db.Model):
    __tablename__ = "service_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    service_type = db.Column(db.String(30), nullable=False)
    raw_text = db.Column(db.Text, nullable=False)
    translated_text = db.Column(db.Text, nullable=False)  # canonical English description
    preferred_time = db.Column(db.DateTime(timezone=True), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=ServiceRequestStatus.NEW)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", foreign_keys=[user_id])

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "requested_by": self.user.name if self.user else None,
            "flat_no": self.user.flat_no if self.user else None,
            "block_no": self.user.block_no if self.user else None,
            "service_type": self.service_type,
            "description": self.translated_text,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
