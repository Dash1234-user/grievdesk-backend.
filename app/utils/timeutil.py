from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app


def society_tz():
    name = current_app.config.get("SOCIETY_TIMEZONE", "Asia/Kolkata")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        current_app.logger.warning("Unknown SOCIETY_TIMEZONE %r - falling back to UTC", name)
        return timezone.utc


def society_now() -> datetime:
    """Current time where the society is, NOT where the server happens to be."""
    return datetime.now(society_tz())
