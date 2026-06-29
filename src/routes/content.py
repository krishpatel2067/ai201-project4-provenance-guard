from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import uuid
import json

from detection import (
    detect_llm,
    detect_stylo_heuristics,
    detect_pos_dist,
    combine_scores,
    score_to_label,
)
from cert import check_provenance_certificate, boost_score
from auth import require_auth
from db import get_db, DB_CONTENT
from rate_limit import rate_limit
from log import write_log

content_bp = Blueprint("content", __name__)


@content_bp.route("/content", methods=["POST"])
@require_auth
@rate_limit("POST /content")
def create_content(creator_id: str):
    body = request.get_json(silent=True) or {}

    # --- Validate ---
    content_text = body.get("content", "")
    metadata_raw = body.get("metadata")

    if not content_text:
        write_log(
            "Rejected content submission: missing content", {"creator_id": creator_id}
        )
        return jsonify({"message": "Missing required field: content"}), 400
    if len(content_text) > 100_000:
        write_log(
            "Rejected content submission: content too long", {"creator_id": creator_id}
        )
        return jsonify({"message": "Content exceeds 100,000 character limit"}), 400

    # --- Run detection signals ---
    llm_score = detect_llm(content_text)
    stylo_score = detect_stylo_heuristics(content_text)
    pos_score = detect_pos_dist(content_text)
    confidence = combine_scores(llm_score, stylo_score, pos_score)

    # --- Provenance certificate ---
    verified_human = False
    metadata_dict = metadata_raw if isinstance(metadata_raw, dict) else {}
    if check_provenance_certificate(metadata_dict):
        confidence = boost_score(confidence)
        verified_human = True

    label, transparency_label = score_to_label(confidence)
    if verified_human and label == "likely_human":
        transparency_label = "Verified human - this content is most likely human-made."

    # --- Store ---
    content_id = str(uuid.uuid4())
    submitted_at = datetime.now(timezone.utc).isoformat()
    metadata_str = json.dumps(metadata_raw) if metadata_raw is not None else None

    with get_db(DB_CONTENT) as conn:
        conn.execute(
            """INSERT INTO content
               (content_id, creator_id, submitted_at, content, metadata, status,
                llm_score, stylo_heuristics_score, pos_dist_score,
                confidence_score, label, transparency_label, verified_human)
               VALUES (?, ?, ?, ?, ?, 'submitted', ?, ?, ?, ?, ?, ?, ?)""",
            (
                content_id,
                creator_id,
                submitted_at,
                content_text,
                metadata_str,
                llm_score,
                stylo_score,
                pos_score,
                confidence,
                label,
                transparency_label,
                int(verified_human),
            ),
        )

    record = {
        "content_id": content_id,
        "creator_id": creator_id,
        "submitted_at": submitted_at,
        "status": "submitted",
        "confidence_score": confidence,
        "label": label,
        "transparency_label": transparency_label,
        "verified_human": verified_human,
    }
    write_log("Stored new content submission", record)

    return (
        jsonify(
            {
                "content_id": content_id,
                "submitted_at": submitted_at,
                "content": content_text[:1000],
                "status": "submitted",
                "confidence_score": confidence,
                "label": label,
                "transparency_label": transparency_label,
                "verified_human": verified_human,
                "message": "Content submitted successfully.",
            }
        ),
        201,
    )
