from flask import request, jsonify
from functools import wraps

from db import get_db, DB_CREATORS

try:
    with open("data/admin-ids.txt") as f:
        admin_ids = {line.strip() for line in f if line.strip()}
except FileNotFoundError:
    admin_ids = {}


def _get_bearer_from_header():
    """Returns the Bearer token string or None if missing/blank."""
    auth = request.headers.get("Bearer", "").strip()
    return auth if auth else None


def _is_admin(bearer: str) -> bool:
    """Returns True if the bearer token matches a known admin ID."""
    return bearer in admin_ids


def _is_creator(bearer: str) -> bool:
    """Returns True if the bearer token matches a known creator ID."""
    with get_db(DB_CREATORS) as conn:
        row = conn.execute(
            "SELECT creator_id FROM creators WHERE creator_id = ?", (bearer,)
        ).fetchone()
    return row is not None


def require_auth(admin: bool = False):
    """
    Decorator factory: validates the Bearer header.

    When admin=True, only admin IDs (from data/admin-ids.txt) are accepted.
    When admin=False (default), only creator IDs (from the creators DB) are accepted.
    Injects `bearer` into the wrapped function's kwargs.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            bearer = _get_bearer_from_header()
            if not bearer:
                return jsonify({"message": "Missing Bearer token"}), 401

            if admin:
                if not _is_admin(bearer):
                    return jsonify({"message": "Invalid admin ID"}), 401
            else:
                if not _is_creator(bearer):
                    return jsonify({"message": "Invalid creator ID"}), 401

            return f(*args, bearer=bearer, **kwargs)

        return wrapper

    return decorator
