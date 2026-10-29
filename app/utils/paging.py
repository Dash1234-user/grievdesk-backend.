from flask import request


def parse_paging(default_limit: int, max_limit: int = 100):
    """
    Reads ?limit=&offset=. Returns (limit, offset, error) — error is a (json_dict, status) pair to send back
    when the values are not whole numbers in range, otherwise None.
    """
    def read(name, default, minimum, maximum):
        raw = request.args.get(name)
        if raw is None or raw == "":
            return default, None
        try:
            value = int(raw)
        except ValueError:
            return None, f"{name} must be a whole number"
        if value < minimum or (maximum is not None and value > maximum):
            return None, f"{name} must be between {minimum} and {maximum}" if maximum else f"{name} must be {minimum} or more"
        return value, None

    limit, err = read("limit", default_limit, 1, max_limit)
    if err:
        return None, None, ({"error": "invalid_paging", "message": err}, 400)
    offset, err = read("offset", 0, 0, None)
    if err:
        return None, None, ({"error": "invalid_paging", "message": err}, 400)
    return limit, offset, None
