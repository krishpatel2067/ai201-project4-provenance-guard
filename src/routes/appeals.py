from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import uuid

from auth import require_auth
from rate_limit import rate_limit
from log import write_log
from db import get_db, DB_CONTENT, DB_APPEALS

appeals_bp = Blueprint("appeals", __name__)


@appeals_bp.route("/appeals", methods=["POST"])
@require_auth()
@rate_limit("POST /appeals")
def create_appeal(bearer: str):
    body = request.get_json(silent=True) or {}

    # --- Validate ---
    content_id = body.get("content_id", "").strip()
    desired_label = body.get("desired_label", "").strip()
    reason = body.get("reason", "").strip()

    VALID_LABELS = {"likely_ai", "uncertain", "likely_human"}

    if not content_id or not desired_label or not reason:
        missing = [
            f
            for f, v in [
                ("content_id", content_id),
                ("desired_label", desired_label),
                ("reason", reason),
            ]
            if not v
        ]
        write_log(
            "Rejected appeal: missing fields",
            {"creator_id": bearer, "missing": missing},
        )
        return (
            jsonify({"message": f"Missing required field(s): {', '.join(missing)}"}),
            400,
        )

    if desired_label not in VALID_LABELS:
        write_log(
            "Rejected appeal: invalid desired label",
            {"creator_id": bearer, "desired_label": desired_label},
        )
        return (
            jsonify(
                {
                    "message": f"Invalid desired_label. Must be one of: {', '.join(VALID_LABELS)}"
                }
            ),
            400,
        )

    if len(reason) > 2500:
        write_log("Rejected appeal: reason too long", {"creator_id": bearer})
        return jsonify({"message": "Reason exceeds 2,500 character limit"}), 400

    # Look up the content
    with get_db(DB_CONTENT) as conn:
        content_row = conn.execute(
            "SELECT content_id, creator_id, label, status FROM content WHERE content_id = ?",
            (content_id,),
        ).fetchone()

    if not content_row:
        write_log(
            "Rejected appeal: content not found",
            {"creator_id": bearer, "content_id": content_id},
        )
        return jsonify({"message": "Content not found"}), 400

    if content_row["creator_id"] != bearer:
        write_log(
            "Rejected appeal: content belongs to a different creator",
            {
                "request_creator_id": bearer,
                "content_creator_id": content_row["creator_id"],
                "content_id": content_id,
            },
        )
        return jsonify({"message": "Content belongs to a different creator"}), 400

    if content_row["label"] == desired_label:
        write_log(
            "Rejected appeal: desired label matches current label",
            {"creator_id": bearer, "content_id": content_id},
        )
        return jsonify({"message": "Desired label matches the current label"}), 400

    if content_row["status"] == "under_review":
        write_log(
            "Rejected appeal: content already under review",
            {"creator_id": bearer, "content_id": content_id},
        )
        return jsonify({"message": "This content is already under review"}), 400

    # --- Store ---
    appeal_id = str(uuid.uuid4())
    appealed_at = datetime.now(timezone.utc).isoformat()

    with get_db(DB_APPEALS) as conn:
        conn.execute(
            """INSERT INTO appeals (appeal_id, content_id, appealed_at, desired_label, reason)
               VALUES (?, ?, ?, ?, ?)""",
            (appeal_id, content_id, appealed_at, desired_label, reason),
        )

    with get_db(DB_CONTENT) as conn:
        conn.execute(
            "UPDATE content SET status = 'under_review' WHERE content_id = ?",
            (content_id,),
        )

    appeal = {
        "appeal_id": appeal_id,
        "content_id": content_id,
        "appealed_at": appealed_at,
        "desired_label": desired_label,
        "reason": reason,
    }
    write_log("Stored new appeal", appeal)
    write_log("Updated content status to under_review", {"content_id": content_id})

    return (
        jsonify(
            {
                "appeal_id": appeal_id,
                "content_id": content_id,
                "appealed_at": appealed_at,
                "desired_label": desired_label,
                "reason": reason[:250],
            }
        ),
        201,
    )
