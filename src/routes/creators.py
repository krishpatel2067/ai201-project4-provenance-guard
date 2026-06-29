from flask import Blueprint, request, jsonify
from sqlite3 import IntegrityError
from datetime import datetime, timezone
import uuid
import re

from rate_limit import rate_limit
from log import write_log
from db import get_db, DB_CREATORS

creators_bp = Blueprint("creators", __name__)


@creators_bp.route("/creators", methods=["POST"])
@rate_limit("POST /creators")
def create_creator():
    body = request.get_json(silent=True) or {}

    # --- Validate ---
    email = body.get("email", "").strip()
    if not email:
        write_log("Rejected creator creation: missing email", body)
        return jsonify({"message": "Missing required field: email"}), 400

    email_pattern = r"^[A-Za-z0-9\.]+@[A-Za-z0-9\.]+\.[A-Za-z0-9\.]+$"
    if not re.match(email_pattern, email):
        write_log("Rejected creator creation: invalid email format", body)
        return jsonify({"message": "Invalid email address format"}), 400

    # --- Store ---
    creator_id = str(uuid.uuid4())
    joined_at = datetime.now(timezone.utc).isoformat()

    try:
        with get_db(DB_CREATORS) as conn:
            conn.execute(
                "INSERT INTO creators (creator_id, joined_at, email) VALUES (?, ?, ?)",
                (creator_id, joined_at, email),
            )
    except IntegrityError:
        write_log("Rejected creator creation: email already exists", {"email": email})
        return jsonify({"message": "Email address already exists"}), 400

    creator = {"creator_id": creator_id, "joined_at": joined_at, "email": email}
    write_log("Created new creator account", creator)
    return jsonify(creator), 201
