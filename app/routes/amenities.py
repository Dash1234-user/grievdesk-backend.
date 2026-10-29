import re
from datetime import date, datetime, time, timedelta

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.utils import timeutil
from app.utils.decorators import login_required, committee_or_secretary_required, current_user
from flask import current_app
from app.models.amenity import Amenity, AmenityBooking, BookingStatus
from app.models.notification import NotificationType
from app.services.tickets import notify

amenities_bp = Blueprint("amenities", __name__, url_prefix="/api/amenities")
bookings_bp = Blueprint("bookings", __name__, url_prefix="/api/amenity-bookings")

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _err(error, message, status=400, **extra):
    return jsonify({"error": error, "message": message, **extra}), status


def _parse_date(value):
    try:
        return date.fromisoformat(value) if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        return None


def _parse_time(value):
    m = TIME_RE.match(value) if isinstance(value, str) else None
    return time(int(m.group(1)), int(m.group(2))) if m else None


def _as_dt(d: date, t: time, tz):
    return datetime.combine(d, t, tzinfo=tz)


# ---------------------------------------------------------------------------
# Amenities
# ---------------------------------------------------------------------------

@amenities_bp.get("")
@login_required
def list_amenities():
    return jsonify({"amenities": [a.to_dict() for a in Amenity.query.order_by(Amenity.name.asc()).all()]}), 200


@amenities_bp.post("")
@committee_or_secretary_required
def create_amenity():
    data = request.get_json(silent=True) or {}
    name, description = data.get("name"), data.get("description")
    if not isinstance(name, str) or not (1 <= len(name.strip()) <= 100):
        return _err("invalid_name", "Name must be 1-100 characters.")
    if description is not None and (not isinstance(description, str) or len(description) > 300):
        return _err("invalid_description", "Description must be text of at most 300 characters.")
    name = name.strip()
    if Amenity.query.filter(db.func.lower(Amenity.name) == name.lower()).first():
        return _err("amenity_exists", f"There is already an amenity called '{name}'.", 409)

    amenity = Amenity(name=name, description=(description or "").strip() or None)
    db.session.add(amenity)
    db.session.commit()
    return jsonify({"message": "Amenity created.", "amenity": amenity.to_dict()}), 201


@amenities_bp.get("/<int:amenity_id>/availability")
@login_required
def availability(amenity_id):
    """What is already booked on ?date=YYYY-MM-DD — the data behind the calendar/slot picker."""
    amenity = db.session.get(Amenity, amenity_id)
    if amenity is None:
        return _err("amenity_not_found", "No such amenity.", 404)
    day = _parse_date(request.args.get("date"))
    if day is None:
        return _err("invalid_date", "Use ?date=YYYY-MM-DD.")

    viewer = current_user()
    rows = (
        AmenityBooking.query.filter_by(amenity_id=amenity_id, date=day, status=BookingStatus.BOOKED)
        .order_by(AmenityBooking.start_time.asc()).all()
    )
    slots = []
    for b in rows:
        slot = {"start_time": b.start_time.strftime("%H:%M"), "end_time": b.end_time.strftime("%H:%M"), "mine": b.user_id == viewer.id}
        if viewer.is_staff():
            slot["booked_by"] = b.user.name
        slots.append(slot)
    return jsonify({"amenity": amenity.to_dict(), "date": day.isoformat(), "booked": slots}), 200


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

@bookings_bp.post("")
@login_required
def create_booking():
    """Body: {"amenity_id": 1, "date": "2026-10-20", "start_time": "18:00", "end_time": "19:30"}"""
    data = request.get_json(silent=True) or {}
    viewer = current_user()
    cfg = current_app.config

    amenity_id = data.get("amenity_id")
    amenity = db.session.get(Amenity, amenity_id) if isinstance(amenity_id, int) and not isinstance(amenity_id, bool) else None
    if amenity is None:
        return _err("amenity_not_found", "Choose an amenity from the list.", 404)

    day = _parse_date(data.get("date"))
    start, end = _parse_time(data.get("start_time")), _parse_time(data.get("end_time"))
    if day is None:
        return _err("invalid_date", "Use YYYY-MM-DD.")
    if start is None or end is None:
        return _err("invalid_time", "Use 24-hour HH:MM, e.g. 18:30.")
    if start >= end:
        return _err("invalid_time_range", "The end time must be after the start time (bookings stay within one day).")

    tz = timeutil.society_tz()
    now = timeutil.society_now()
    max_hours = cfg["MAX_BOOKING_HOURS"]
    if (_as_dt(day, end, tz) - _as_dt(day, start, tz)) > timedelta(hours=max_hours):
        return _err("booking_too_long", f"A booking can be at most {max_hours} hours.", max_hours=max_hours)
    if _as_dt(day, start, tz) <= now:
        return _err("in_the_past", "That time has already started or passed.")
    if day > now.date() + timedelta(days=cfg["MAX_BOOKING_DAYS_AHEAD"]):
        return _err("too_far_ahead", f"You can book at most {cfg['MAX_BOOKING_DAYS_AHEAD']} days ahead.")

    # Serialise bookings per amenity: on PostgreSQL this row lock makes a second simultaneous request
    # wait until the first has committed, so two people can't both pass the clash check for one slot.
    db.session.query(Amenity).filter_by(id=amenity.id).with_for_update().one()

    clash = AmenityBooking.query.filter(
        AmenityBooking.amenity_id == amenity.id,
        AmenityBooking.date == day,
        AmenityBooking.status == BookingStatus.BOOKED,
        AmenityBooking.start_time < end,     # overlap test: they start before I end ...
        AmenityBooking.end_time > start,     # ... and end after I start.  Back-to-back slots are fine.
    ).first()
    if clash:
        return _err("slot_taken", f"{amenity.name} is already booked from "
                    f"{clash.start_time.strftime('%H:%M')} to {clash.end_time.strftime('%H:%M')} on that day.",
                    409, conflict={"start_time": clash.start_time.strftime("%H:%M"), "end_time": clash.end_time.strftime("%H:%M")})

    booking = AmenityBooking(amenity_id=amenity.id, user_id=viewer.id, date=day, start_time=start, end_time=end)
    db.session.add(booking)
    db.session.commit()
    return jsonify({"message": f"{amenity.name} booked.", "booking": booking.to_dict(viewer)}), 201


@bookings_bp.get("/me")
@login_required
def my_bookings():
    viewer = current_user()
    rows = (
        AmenityBooking.query.filter_by(user_id=viewer.id)
        .order_by(AmenityBooking.date.desc(), AmenityBooking.start_time.desc()).all()
    )
    return jsonify({"bookings": [b.to_dict(viewer) for b in rows]}), 200


@bookings_bp.get("")
@committee_or_secretary_required
def all_bookings():
    """Staff view, to resolve clashes. Filters: ?date=YYYY-MM-DD  ?amenity_id=  ?status=booked|cancelled"""
    viewer = current_user()
    query = AmenityBooking.query
    if request.args.get("date"):
        day = _parse_date(request.args["date"])
        if day is None:
            return _err("invalid_date", "Use ?date=YYYY-MM-DD.")
        query = query.filter_by(date=day)
    if request.args.get("amenity_id", "").isdigit():
        query = query.filter_by(amenity_id=int(request.args["amenity_id"]))
    if request.args.get("status"):
        if request.args["status"] not in BookingStatus.ALL:
            return _err("invalid_status", "Use booked or cancelled.")
        query = query.filter_by(status=request.args["status"])
    rows = query.order_by(AmenityBooking.date.desc(), AmenityBooking.start_time.asc()).all()
    return jsonify({"bookings": [b.to_dict(viewer) for b in rows]}), 200


@bookings_bp.delete("/<int:booking_id>")
@login_required
def cancel_booking(booking_id):
    """Cancel your own booking; committee/secretary can cancel anyone's (the person is told). Kept as history."""
    viewer = current_user()
    booking = db.session.get(AmenityBooking, booking_id)
    # Someone else's booking looks exactly like a missing one to a resident.
    if booking is None or not (viewer.is_staff() or booking.user_id == viewer.id):
        return _err("booking_not_found", "No such booking.", 404)

    if booking.status == BookingStatus.CANCELLED:
        return jsonify({"message": "Already cancelled.", "booking": booking.to_dict(viewer)}), 200

    tz = timeutil.society_tz()
    if _as_dt(booking.date, booking.end_time, tz) <= timeutil.society_now():
        return _err("booking_in_past", "That booking is already over.", 409)

    booking.status = BookingStatus.CANCELLED
    if booking.user_id != viewer.id:
        notify(booking.user_id, NotificationType.BOOKING_UPDATE,
               f"Your booking of {booking.amenity.name} on {booking.date.isoformat()} "
               f"({booking.start_time.strftime('%H:%M')}-{booking.end_time.strftime('%H:%M')}) was cancelled by {viewer.name}.",
               viewer)
    db.session.commit()
    return jsonify({"message": "Booking cancelled.", "booking": booking.to_dict(viewer)}), 200
