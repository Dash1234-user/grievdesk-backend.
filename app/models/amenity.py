from datetime import datetime, timezone
from app.extensions import db


class BookingStatus:
    BOOKED = "booked"
    CANCELLED = "cancelled"   # cancelled bookings are kept (history) but never block a slot
    ALL = (BOOKED, CANCELLED)


class Amenity(db.Model):
    __tablename__ = "amenities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(300), nullable=True)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description}


class AmenityBooking(db.Model):
    __tablename__ = "amenity_bookings"

    id = db.Column(db.Integer, primary_key=True)
    amenity_id = db.Column(db.Integer, db.ForeignKey("amenities.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(10), nullable=False, default=BookingStatus.BOOKED)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    amenity = db.relationship("Amenity", foreign_keys=[amenity_id])
    user = db.relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        db.Index("ix_booking_amenity_date", "amenity_id", "date"),
    )

    def to_dict(self, viewer=None) -> dict:
        """Residents see their own bookings; committee/secretary also see who booked (to resolve clashes)."""
        staff = viewer is not None and viewer.role in ("committee", "secretary")
        row = {
            "id": self.id,
            "amenity_id": self.amenity_id,
            "amenity": self.amenity.name if self.amenity else None,
            "date": self.date.isoformat(),
            "start_time": self.start_time.strftime("%H:%M"),
            "end_time": self.end_time.strftime("%H:%M"),
            "status": self.status,
        }
        if staff and self.user:
            row["booked_by"] = self.user.name
            row["flat_no"] = self.user.flat_no
            row["block_no"] = self.user.block_no
        return row
