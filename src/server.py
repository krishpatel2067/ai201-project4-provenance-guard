import sqlite3
import uuid
import json
import re
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Database paths
# ---------------------------------------------------------------------------
DB_CONTENT = "data/content.db"
DB_CREATORS = "data/creators.db"
DB_APPEALS = "data/appeals.db"
LOGS_FILE = "data/logs.jsonl"

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def get_db(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db(DB_CREATORS) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS creators (
                creator_id TEXT PRIMARY KEY,
                joined_at  TEXT NOT NULL,
                email      TEXT NOT NULL UNIQUE
            )
        """)
        # Per-endpoint rate limit counters.
        # `identity` is either the creator_id (authenticated requests) or the
        # client IP address (unauthenticated, e.g. POST /creators).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                identity   TEXT NOT NULL,
                endpoint   TEXT NOT NULL,
                window_min TEXT NOT NULL,
                window_day TEXT NOT NULL,
                count_min  INTEGER NOT NULL DEFAULT 0,
                count_day  INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (identity, endpoint)
            )
        """)

    with get_db(DB_CONTENT) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS content (
                content_id             TEXT PRIMARY KEY,
                creator_id             TEXT NOT NULL,
                submitted_at           TEXT NOT NULL,
                content                TEXT NOT NULL,
                metadata               TEXT,
                status                 TEXT NOT NULL DEFAULT 'submitted',
                llm_score              REAL,
                stylo_heuristics_score REAL,
                pos_dist_score         REAL,
                confidence_score       REAL,
                label                  TEXT,
                transparency_label     TEXT,
                verified_human         INTEGER NOT NULL DEFAULT 0
            )
        """)

    with get_db(DB_APPEALS) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appeals (
                appeal_id    TEXT PRIMARY KEY,
                content_id   TEXT NOT NULL,
                appealed_at  TEXT NOT NULL,
                desired_label TEXT NOT NULL,
                reason       TEXT NOT NULL
            )
        """)


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------


def write_log(message: str, body: dict):
    entry = {
        "log_id": str(uuid.uuid4()),
        "message": message,
        "body": body,
    }
    with open(LOGS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Auth helper  (Bearer = creator_id, simulates auth)
# ---------------------------------------------------------------------------


def get_creator_id_from_header():
    """Returns creator_id string or None if missing/blank."""
    auth = request.headers.get("Bearer", "").strip()
    return auth if auth else None


def require_auth(f):
    """Decorator: validates Bearer header and that the creator exists."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        creator_id = get_creator_id_from_header()
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


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

RATE_LIMITS = {
    # endpoint: (per_min, per_day)
    "POST /content": (3, 15),
    "POST /appeals": (3, 18),
    "POST /creators": (1, 5),
}


def check_rate_limit(identity: str, endpoint: str):
    """
    Returns (allowed: bool, message: str).
    Updates counters regardless of outcome (counts even rejected requests).
    `identity` is the creator_id for authenticated routes, or the client IP otherwise.
    """
    per_min, per_day = RATE_LIMITS[endpoint]
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
                allowed, msg = check_rate_limit(creator_id, endpoint_key)
            else:
                ip = request.remote_addr or "unknown"
                allowed, msg = check_rate_limit(ip, endpoint_key)
            if not allowed:
                return jsonify({"message": msg}), 429
            return f(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Detection stubs  (to be implemented in later milestones)
# ---------------------------------------------------------------------------


def detect_llm(content: str) -> float:
    """Signal 1: LLM-based detection. Returns 0-1 score."""
    # TODO: implement in M3
    return 0.5


def detect_stylo_heuristics(content: str) -> float:
    """Signal 2: Stylometric heuristics. Returns 0-1 score."""
    # TODO: implement in M4
    return 0.5


def detect_pos_dist(content: str) -> float:
    """Signal 3: Part-of-speech distribution. Returns 0-1 score."""
    # TODO: implement in M4
    return 0.5


def combine_scores(llm: float, stylo: float, pos: float) -> float:
    return 0.40 * llm + 0.30 * stylo + 0.30 * pos


def boost_score(score: float) -> float:
    """Provenance certificate score boost: 1 - (1 - score)^3.25"""
    return 1 - (1 - score) ** 3.25


def score_to_label(score: float) -> tuple[str, str]:
    """Returns (label, transparency_label) for a given confidence score."""
    if score < 0.4:
        return (
            "likely_ai",
            "This content appears to be partially or fully AI-generated.",
        )
    if score < 0.6:
        return "uncertain", "We're not sure whether this content was AI-generated."
    return "likely_human", "This content appears human-made."


def check_provenance_certificate(metadata: dict) -> bool:
    """
    Returns True if the metadata meets provenance certificate requirements:
    - Platform must be desktop_app
    - Zero pastes from elsewhere
    - At least 3 sessions of >= 1 hour each
    """
    if not metadata:
        return False
    if metadata.get("platform") != "desktop_app":
        return False
    if metadata.get("pastes_from_elsewhere", 1) != 0:
        return False
    sessions = metadata.get("sessions", [])
    qualifying = 0
    for s in sessions:
        try:
            start = datetime.fromisoformat(s["start"])
            end = datetime.fromisoformat(s["end"])
            if (end - start).total_seconds() >= 3600:
                qualifying += 1
        except (KeyError, ValueError):
            continue
    return qualifying >= 3


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/creators", methods=["POST"])
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
    except sqlite3.IntegrityError:
        write_log("Rejected creator creation: email already exists", {"email": email})
        return jsonify({"message": "Email address already exists"}), 400

    creator = {"creator_id": creator_id, "joined_at": joined_at, "email": email}
    write_log("Created new creator account", creator)
    return jsonify(creator), 201


@app.route("/content", methods=["POST"])
@require_auth
@rate_limit("POST /content")
def submit_content(creator_id: str):
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


@app.route("/appeals", methods=["POST"])
@require_auth
@rate_limit("POST /appeals")
def submit_appeal(creator_id: str):
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
            {"creator_id": creator_id, "missing": missing},
        )
        return (
            jsonify({"message": f"Missing required field(s): {', '.join(missing)}"}),
            400,
        )

    if desired_label not in VALID_LABELS:
        write_log(
            "Rejected appeal: invalid desired label",
            {"creator_id": creator_id, "desired_label": desired_label},
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
        write_log("Rejected appeal: reason too long", {"creator_id": creator_id})
        return jsonify({"message": "Reason exceeds 2,500 character limit"}), 400

    # Look up the content
    with get_db(DB_CONTENT) as conn:
        content_row = conn.execute(
            "SELECT content_id, label, status FROM content WHERE content_id = ?",
            (content_id,),
        ).fetchone()

    if not content_row:
        write_log(
            "Rejected appeal: content not found",
            {"creator_id": creator_id, "content_id": content_id},
        )
        return jsonify({"message": "Content not found"}), 400

    if content_row["label"] == desired_label:
        write_log(
            "Rejected appeal: desired label matches current label",
            {"creator_id": creator_id, "content_id": content_id},
        )
        return jsonify({"message": "Desired label matches the current label"}), 400

    if content_row["status"] == "under_review":
        write_log(
            "Rejected appeal: content already under review",
            {"creator_id": creator_id, "content_id": content_id},
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    os.makedirs("data", exist_ok=True)
    open(LOGS_FILE, "a").close()
    init_db()
    app.run(debug=True)
