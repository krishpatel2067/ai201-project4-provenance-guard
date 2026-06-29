from flask import request, jsonify
from functools import wraps

from db import get_db, DB_CREATORS


def _get_creator_id_from_header():
    """Returns creator_id string or None if missing/blank."""
    auth = request.headers.get("Bearer", "").strip()
    return auth if auth else None


def require_auth(f):
    """Decorator: validates Bearer header and that the creator exists."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        creator_id = _get_creator_id_from_header()
        if not creator_id:
            return jsonify({"message": "Missing Bearer token"}), 401
        with get_db(DB_CREATORS) as conn:
            row = conn.execute(
                "SELECT creator_id FROM creators WHERE creator_id = ?", (creator_id,)
            ).fetchone()
        if not row:
            return jsonify({"message": "Invalid creator ID"}), 401
        return f(*args, creator_id=creator_id, **kwargs)

    return wrapper
