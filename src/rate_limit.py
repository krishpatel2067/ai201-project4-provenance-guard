from flask import request, jsonify
from datetime import datetime, timezone
from functools import wraps

from db import get_db, DB_CREATORS

_RATE_LIMITS = {
    # endpoint: (per_min, per_day)
    "POST /content": (3, 15),
    "POST /appeals": (3, 18),
    "POST /creators": (1, 5),
}


def _check_rate_limit(identity: str, endpoint: str):
    """
    Returns (allowed: bool, message: str).
    Updates counters regardless of outcome (counts even rejected requests).
    `identity` is the creator_id for authenticated routes, or the client IP otherwise.
    """
    per_min, per_day = _RATE_LIMITS[endpoint]
    now = datetime.now(timezone.utc)
    window_min = now.strftime("%Y-%m-%dT%H:%M")
    window_day = now.strftime("%Y-%m-%d")

    with get_db(DB_CREATORS) as conn:
        row = conn.execute(
            "SELECT * FROM rate_limits WHERE identity = ? AND endpoint = ?",
            (identity, endpoint),
        ).fetchone()

        if row is None:
            conn.execute(
                """INSERT INTO rate_limits
                   (identity, endpoint, window_min, window_day, count_min, count_day)
                   VALUES (?, ?, ?, ?, 1, 1)""",
                (identity, endpoint, window_min, window_day),
            )
            return True, ""

        # Reset stale windows
        cur_min = row["count_min"] if row["window_min"] == window_min else 0
        cur_day = row["count_day"] if row["window_day"] == window_day else 0
        new_min = cur_min + 1
        new_day = cur_day + 1

        conn.execute(
            """UPDATE rate_limits
               SET window_min = ?, window_day = ?, count_min = ?, count_day = ?
               WHERE identity = ? AND endpoint = ?""",
            (window_min, window_day, new_min, new_day, identity, endpoint),
        )

    if new_min > per_min:
        return (
            False,
            f"Rate limit exceeded: max {per_min} requests per minute for {endpoint}",
        )
    if new_day > per_day:
        return (
            False,
            f"Rate limit exceeded: max {per_day} requests per day for {endpoint}",
        )
    return True, ""


def rate_limit(endpoint_key: str):
    """Decorator: checks rate limit before executing the route handler.

    Uses creator_id (from kwargs injected by @require_auth) when available,
    otherwise falls back to the client IP address.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            creator_id = kwargs.get("creator_id")
            if creator_id:
                allowed, msg = _check_rate_limit(creator_id, endpoint_key)
            else:
                ip = request.remote_addr or "unknown"
                allowed, msg = _check_rate_limit(ip, endpoint_key)
            if not allowed:
                return jsonify({"message": msg}), 429
            return f(*args, **kwargs)

        return wrapper

    return decorator
